"""Independent durable provider simulators; run with PROVIDER_ID=provider-a/b."""
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, ConfigDict, Field

from services.api.config import settings

PROVIDER = os.environ.get("PROVIDER_ID", "provider-a")
if PROVIDER not in {"provider-a", "provider-b"}:
    raise RuntimeError("A supported synthetic provider organization is required.")
DATA_PATH = Path(os.environ.get("PROVIDER_DATA_PATH", f"runtime/{PROVIDER}.sqlite3"))
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
API = os.environ.get("API_INTERNAL_URL", "http://127.0.0.1:18000")
app = FastAPI(title=f"Suhail {PROVIDER} synthetic provider simulator", version="1.0")


def db():
    c = sqlite3.connect(DATA_PATH)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS referrals(id TEXT PRIMARY KEY,outbox_id TEXT UNIQUE,case_id TEXT,packet TEXT,status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS callbacks(id TEXT PRIMARY KEY,handoff_id TEXT,kind TEXT,payload TEXT,status TEXT,response_code INTEGER)")
    return c


def authenticated(x_connector_token: str = Header(default="")):
    if not secrets.compare_digest(x_connector_token, settings()["connector_tokens"][PROVIDER]):
        raise HTTPException(401, "Provider connector credential required.")


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    reason: str = Field(min_length=1, max_length=1000)
    event_id: str | None = None


class Callback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    data: dict
    event_id: str | None = None


@app.get("/health")
def health():
    with db() as c:
        count = c.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
    return {"status": "ok", "organization": PROVIDER, "mode": "synthetic_simulator", "persisted_referrals": count}


@app.post("/referrals", dependencies=[Depends(authenticated)])
def receive(payload: dict):
    # Explicit allowlist prevents a sending adapter from leaking a full source chart.
    fields = {"id", "handoff_id", "case_id", "version", "patient_id", "patient_name", "order_id", "result_version", "pathway", "reason_for_referral", "owner", "urgent", "appointments", "scope_notice", "scope", "status", "receiver", "reason", "outbox_id", "sender", "requested_at", "due_at", "decided_at", "decision_actor"}
    packet = {k: v for k, v in payload.items() if k in fields}
    hid = packet.get("handoff_id") or packet.get("id")
    if not hid or not packet.get("case_id") or not payload.get("outbox_id"):
        raise HTTPException(422, "A correlated handoff and outbox receipt are required.")
    if packet.get("receiver", PROVIDER) != PROVIDER:
        raise HTTPException(403, "Referral destination does not match this provider.")
    with db() as c:
        old = c.execute("SELECT * FROM referrals WHERE outbox_id=?", (payload["outbox_id"],)).fetchone()
        if old:
            previous_packet = json.loads(old["packet"])
            if any(previous_packet.get(k) != packet.get(k) for k in ["id", "case_id", "patient_id", "order_id", "receiver", "scope"]):
                raise HTTPException(409, "Outbox identity was already used for a different referral packet.")
            return {"status": "recorded", "id": old["id"], "duplicate": True}
        existing = c.execute("SELECT * FROM referrals WHERE id=?", (hid,)).fetchone()
        if existing and existing["case_id"] != packet["case_id"]:
            raise HTTPException(409, "Handoff identity already belongs to another case.")
        c.execute("INSERT INTO referrals VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET packet=excluded.packet", (hid, payload["outbox_id"], packet["case_id"], json.dumps(packet), "requested"))
    return {"status": "recorded", "id": hid, "organization": PROVIDER}


@app.get("/referrals", dependencies=[Depends(authenticated)])
def list_referrals():
    with db() as c:
        return [{**json.loads(r["packet"]), "local_status": r["status"]} for r in c.execute("SELECT * FROM referrals").fetchall()]


async def callback(hid, kind, data, event_id=None):
    with db() as c:
        row = c.execute("SELECT * FROM referrals WHERE id=?", (hid,)).fetchone()
    if not row:
        raise HTTPException(404, "Referral is not held by this simulated provider.")
    event_id = event_id or PROVIDER + "-" + uuid.uuid4().hex
    headers = {"X-Connector-Token": settings()["connector_tokens"][PROVIDER], "X-Organization": PROVIDER}
    async with httpx.AsyncClient(timeout=12) as client:
        try:
            fresh = await client.get(f"{API}/integrations/providers/{PROVIDER}/referrals/{hid}", headers=headers)
            if fresh.status_code != 200:
                raise HTTPException(fresh.status_code, "Authorized packet refresh failed.")
            packet = fresh.json()
            payload = {"event_id": event_id, "kind": kind, "case_id": row["case_id"], "expected_version": packet["version"], "data": {**data, **({"handoff_id": hid} if kind in ("handoff_accept", "handoff_reject") else {})}}
            with db() as c:
                previous = c.execute("SELECT * FROM callbacks WHERE id=?", (event_id,)).fetchone()
                if previous:
                    original = json.loads(previous["payload"])
                    if previous["handoff_id"] != hid or previous["kind"] != kind or original["data"] != payload["data"]:
                        raise HTTPException(409, "Provider event identity was already used for a different command.")
                if previous and previous["status"] == "delivered":
                    return {"status": "delivered", "duplicate": True, "event_id": event_id}
                c.execute("INSERT OR IGNORE INTO callbacks VALUES (?,?,?,?,?,NULL)", (event_id, hid, kind, json.dumps(payload), "pending"))
            response = await client.post(f"{API}/integrations/providers/{PROVIDER}/events", headers=headers, json=payload)
            with db() as c:
                c.execute("UPDATE callbacks SET status=?,response_code=? WHERE id=?", ("delivered" if response.is_success else "failed", response.status_code, event_id))
            if not response.is_success:
                raise HTTPException(response.status_code, "Backend rejected this provider event; retained for explicit retry.")
            with db() as c:
                c.execute("UPDATE referrals SET status=? WHERE id=?", (kind, hid))
            return {"status": "delivered", "event_id": event_id, "application": response.json()}
        except httpx.HTTPError:
            raise HTTPException(503, "Application callback unavailable; source event remains persisted for retry.") from None


@app.post("/referrals/{hid}/decision", dependencies=[Depends(authenticated)])
async def decide(hid: str, payload: Decision):
    if payload.decision not in ("accept", "reject"):
        raise HTTPException(422, "Choose accept or reject.")
    return await callback(hid, "handoff_" + payload.decision, {"reason": payload.reason}, payload.event_id)


@app.post("/referrals/{hid}/events", dependencies=[Depends(authenticated)])
async def event(hid: str, payload: Callback):
    if payload.kind not in ("appointment_create", "appointment_event", "evidence_add"):
        raise HTTPException(422, "This simulator supports appointment and evidence callbacks only.")
    return await callback(hid, payload.kind, payload.data, payload.event_id)


@app.get("/callbacks", dependencies=[Depends(authenticated)])
def callback_status():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT id,handoff_id,kind,status,response_code FROM callbacks").fetchall()]
