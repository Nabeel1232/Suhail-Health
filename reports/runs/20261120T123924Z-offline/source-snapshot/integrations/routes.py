"""FHIR test intake into the same source-versioned domain command."""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from services.api.auth import require_actor
from services.api.config import settings
from services.api.db import get_db
from services.api.domain import intake, require_role

router = APIRouter()


class FHIRImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation_id: str = Field(pattern=r"^synthetic-[A-Za-z0-9_-]+$", max_length=150)


@router.post("/integrations/fhir/import")
async def import_result(payload: FHIRImport, actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {"navigator", "clinician", "connector"})
    headers = {"X-Connector-Token": settings()["connector_tokens"]["source-clinic"]}
    base = settings()["fhir_url"].rstrip("/") + "/fhir"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(base + "/Observation/" + payload.observation_id, headers=headers)
            response.raise_for_status()
            observation = response.json()
            patient_ref = observation.get("subject", {}).get("reference", "")
            order_ref = next(iter(observation.get("basedOn", [])), {}).get("reference", "")
            if not patient_ref.startswith("Patient/synthetic-") or not order_ref.startswith("ServiceRequest/synthetic-"):
                raise HTTPException(422, "Exact synthetic patient and source order references are required.")
            patient_response = await client.get(base + "/" + patient_ref, headers=headers)
            patient_response.raise_for_status()
            patient = patient_response.json()
            if patient.get("id") != patient_ref.split("/")[-1]:
                raise HTTPException(422, "FHIR source identity reference mismatch.")
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "The authenticated FHIR test source is unavailable or invalid; intake was not applied.") from None
    name = next(iter(patient.get("name", [])), {})
    codes = [c.get("code") for c in observation.get("code", {}).get("coding", [])]
    positive = any(c.get("code") in ("positive", "POS", "FIT_POS") for c in observation.get("valueCodeableConcept", {}).get("coding", []))
    code = "FIT_POS" if positive and any(c in ("58453-2", "FIT_POS", "FIT_POSITIVE") for c in codes) else "UNSUPPORTED"
    version = int(observation.get("meta", {}).get("versionId", "1"))
    data = {"event_id": "fhir:" + payload.observation_id + ":" + str(version), "source_organization": "source-clinic",
            "patient_id": patient["id"], "patient_name": name.get("text") or " ".join([*name.get("given", []), name.get("family", "")]).strip() or "Synthetic participant",
            "order_id": order_ref.split("/")[-1], "result_version": version, "test_code": code,
            "issued_at": observation.get("issued") or observation.get("effectiveDateTime"),
            "identity_verified": True, "trusted_urgent": any(c.get("code") == "HH" for i in observation.get("interpretation", []) for c in i.get("coding", [])),
            "source_reference": base + "/Observation/" + payload.observation_id + "/_history/" + str(version),
            "dataset": "demo-fhir-v1"}
    if not data["issued_at"]:
        raise HTTPException(422, "The source result has no issuance/effective timestamp.")
    return intake(db, actor, data)
