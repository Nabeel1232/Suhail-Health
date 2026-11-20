"""Small authenticated FHIR R4 test server. Synthetic resources only; not a certified EHR."""
import json
import os
import secrets
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, Header, HTTPException, Response

from services.api.config import settings

KINDS = ("Patient", "Observation", "DiagnosticReport", "ServiceRequest", "Task", "Appointment", "Encounter", "Procedure")
PATH = Path(os.environ.get("FHIR_DATA_PATH", "runtime/fhir.sqlite3"))
PATH.parent.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Suhail synthetic FHIR R4 test server", version="4.0.1")


def patient_references(kind, resource):
    # FHIR R4 Task uses `for`; Appointment uses participant.actor, not subject.
    if kind == "Task":
        return [resource.get("for", {}).get("reference", "")]
    if kind == "Appointment":
        return [p.get("actor", {}).get("reference", "") for p in resource.get("participant", [])
                if p.get("actor", {}).get("reference", "").startswith("Patient/")]
    return [resource.get("subject", {}).get("reference", "")]


def authenticated(x_connector_token: str = Header(default="")):
    if not secrets.compare_digest(x_connector_token, settings()["connector_tokens"]["source-clinic"]):
        raise HTTPException(401, "FHIR test connector authentication required.")


def db():
    c = sqlite3.connect(PATH)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS resources(kind TEXT,id TEXT,version INTEGER,resource TEXT,PRIMARY KEY(kind,id))")
    return c


@app.get("/health")
def health():
    return {"status": "ok", "mode": "synthetic_fhir_r4_test", "fhir_version": "4.0.1"}


@app.get("/fhir/metadata")
def capability():
    return {"resourceType": "CapabilityStatement", "status": "active", "date": "2026-11-15", "kind": "instance", "fhirVersion": "4.0.1", "format": ["json"],
            "description": "Limited synthetic test server; supports read, search by patient and version-aware update. No live clinical integration or full FHIR validation.",
            "rest": [{"mode": "server", "resource": [{"type": kind, "interaction": [{"code": "read"}, {"code": "update"}, {"code": "search-type"}]} for kind in KINDS]}]}


@app.put("/fhir/{kind}/{rid}", dependencies=[Depends(authenticated)])
def put(kind: str, rid: str, payload: dict, response: Response, if_match: str | None = Header(default=None)):
    if kind not in KINDS or payload.get("resourceType") != kind or payload.get("id") != rid:
        raise HTTPException(422, "Supported resourceType and matching identifier are required.")
    if not rid.startswith("synthetic-"):
        raise HTTPException(422, "Only explicit synthetic resource identifiers are permitted.")
    if kind != "Patient":
        refs = patient_references(kind, payload)
        if not refs or any(not ref.startswith("Patient/synthetic-") for ref in refs):
            raise HTTPException(422, "A synthetic patient reference in the correct FHIR R4 field is required.")
        if not payload.get("status"):
            raise HTTPException(422, "FHIR resource status is required.")
        if kind in {"Task", "ServiceRequest"} and not payload.get("intent"):
            raise HTTPException(422, "FHIR Task/ServiceRequest intent is required.")
        if kind == "Appointment" and any(p.get("status") not in {"accepted", "declined", "tentative", "needs-action"} for p in payload.get("participant", [])):
            raise HTTPException(422, "FHIR appointment participants require a valid participation status.")
    with db() as c:
        old = c.execute("SELECT * FROM resources WHERE kind=? AND id=?", (kind, rid)).fetchone()
        if if_match and (not old or if_match != 'W/"' + str(old["version"]) + '"'):
            raise HTTPException(412, "FHIR resource version changed.")
        version = old["version"] + 1 if old else 1
        payload["meta"] = {**payload.get("meta", {}), "versionId": str(version), "lastUpdated": datetime.now(timezone.utc).isoformat()}
        c.execute("INSERT INTO resources VALUES (?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET version=excluded.version,resource=excluded.resource", (kind, rid, version, json.dumps(payload)))
    response.headers["ETag"] = 'W/"' + str(version) + '"'
    return payload


@app.get("/fhir/{kind}/{rid}", dependencies=[Depends(authenticated)])
def get(kind: str, rid: str, response: Response):
    with db() as c:
        row = c.execute("SELECT * FROM resources WHERE kind=? AND id=?", (kind, rid)).fetchone()
    if not row:
        raise HTTPException(404, "Synthetic resource not found.")
    response.headers["ETag"] = 'W/"' + str(row["version"]) + '"'
    return json.loads(row["resource"])


@app.get("/fhir/{kind}", dependencies=[Depends(authenticated)])
def search(kind: str, patient: str | None = None):
    if kind not in KINDS:
        raise HTTPException(404, "Unsupported test resource type.")
    with db() as c:
        rows = c.execute("SELECT resource FROM resources WHERE kind=? ORDER BY id LIMIT 200", (kind,)).fetchall()
    resources = [json.loads(r["resource"]) for r in rows]
    if patient:
        resources = [r for r in resources if "Patient/" + patient in patient_references(kind, r)]
    return {"resourceType": "Bundle", "type": "searchset", "total": len(resources), "entry": [{"resource": r} for r in resources]}
