import asyncio
import hmac
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.config import settings
from services.api.auth import require_actor
from services.api.domain import authorize_case, serialize_case, command, closure_check
from .engine import propose, FUNCTIONS
from .gateway import GroqGateway, GatewayError
from .graph import persist_pause, resume_review
from .retrieval import PolicyReviewRequired

router = APIRouter()


def model_case(db, case, actor):
    snapshot = serialize_case(db, case, actor)
    secret = settings()["session_secret"].encode("utf-8")
    organization = snapshot["source_organization"]

    def patient_token(patient_id):
        message = json.dumps(["suhail-model-patient-v1", organization, patient_id], ensure_ascii=False)
        return hmac.digest(secret, message.encode("utf-8"), "sha256").hex()[:32]

    token = patient_token(snapshot["patient_id"])
    return {**snapshot, "patient_id": "patient-" + token, "patient_name": "Patient " + token,
            **{field: [{**record, "patient_id": "patient-" + patient_token(record["patient_id"])}
                for record in snapshot[field]] for field in ("evidence", "experience")}}


@router.post("/agents/{function}/propose")
async def create_proposal(function: str, payload: dict, actor=Depends(require_actor), db: Session = Depends(get_db)):
    if actor["role"] not in ("navigator", "clinician", "specialist", "admin"):
        raise HTTPException(403, "This workspace is restricted to authorized staff.")
    if function not in FUNCTIONS:
        raise HTTPException(422, "Unknown bounded function.")
    case = authorize_case(db, actor, payload.get("case_id"))
    if payload.get("expected_version") != case.version:
        raise HTTPException(409, "The case changed; reload before requesting a draft.")
    data = model_case(db, case, actor)
    data["source_references"] = ["synthetic://case/" + case.id]
    thread_id = "proposal-" + uuid.uuid4().hex
    gateway = GroqGateway(run_dir=Path("runtime") / "interactive" / thread_id, max_calls=6, max_tokens=30000)
    try:
        def adapter(name, arguments):
            current = authorize_case(db, actor, case.id)
            db.refresh(current)
            if current.version != arguments["case_version"]:
                raise GatewayError("version_conflict", "The case changed during proposal preparation.")
            if name == "check_closure":
                return closure_check(db, current)
            if name == "read_case":
                return model_case(db, current, actor)
            from .engine import execute_tool
            return execute_tool(function, name, arguments, data, actor)
        result = await propose(function, data, gateway, {"case_id": case.id, "run_id": thread_id}, actor=actor,
                               read_adapter=adapter, tool_mode=function in ("coordination", "closure_evidence"))
        pause = await asyncio.to_thread(persist_pause, settings()["database_url"], thread_id, case.id, case.version, result["proposal"])
        return {**result, "review": pause, "clinical_authority": "Human application command required"}
    except PolicyReviewRequired as exc:
        # Review task itself uses the application command and current version.
        command(db, actor, case.id, "task", {**payload, "type": "policy_review", "assignee": "clinical-policy-review", "next_action": str(exc), "required": True})
        return {"mode": "fixed_template_fallback", "status": "review_required", "reason": str(exc), "live_success": False}
    except GatewayError as exc:
        return {"mode": "fixed_template_fallback", "status": exc.code, "live_success": False,
                "message": "AI draft unavailable. Your assigned care team and approved workflow remain available.", "call_id": exc.call_id}


@router.post("/agent-reviews/{thread_id}/resume")
def review_proposal(thread_id: str, payload: dict, actor=Depends(require_actor), db: Session = Depends(get_db)):
    if actor["role"] not in ("clinician", "specialist"):
        raise HTTPException(403, "A qualified clinical reviewer is required.")
    case = authorize_case(db, actor, payload.get("case_id"))
    if payload.get("expected_version") != case.version:
        raise HTTPException(409, "Case version changed; prepare a fresh proposal.")
    from .graph import approval_graph
    with approval_graph(settings()["database_url"]) as graph:
        snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
        if snapshot.values.get("case_id") != case.id or snapshot.values.get("case_version") != case.version:
            raise HTTPException(409, "Review thread scope/version does not match this case.")
    result = resume_review(settings()["database_url"], thread_id, {"actor_id": actor["id"], "decision": payload.get("decision"), "reason": payload.get("reason")})
    return {"thread_id": thread_id, "status": result["status"], "clinical_state_changed": False}
