"""Real independently running services and PostgreSQL, not mocked HTTP adapters."""
import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
import pytest

API = os.environ.get("TEST_API_URL", "http://127.0.0.1:18000")


def checked(response):
    assert response.is_success, (response.status_code, response.text[:400])
    return response.json()


def login(role):
    client = httpx.Client(base_url=API, timeout=15)
    checked(client.post("/auth/demo", json={"role": role}))
    return client


def post(client, path, case_ref, **data):
    for attempt in range(3):
        case = checked(client.get("/cases/" + case_ref))
        body = {"expected_version": case["version"], "idempotency_key": "integration:" + uuid.uuid4().hex, **data}
        response = client.post(path, json=body)
        if response.status_code != 409 or "version" not in response.text.lower():
            return checked(response)
    return checked(response)


@pytest.fixture(scope="module")
def source():
    nav = login("navigator")
    cid = "INT-" + uuid.uuid4().hex[:10]
    result = checked(nav.post("/events/results", json={"event_id": cid + "-result", "case_id": cid, "dataset": "integration-v1", "source_organization": "source-clinic", "patient_id": cid + "-patient", "patient_name": "Synthetic integration participant", "order_id": cid + "-order", "result_version": 1, "test_code": "FIT_POS", "issued_at": (datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(), "identity_verified": True}))
    yield nav, cid
    nav.close()


def provider_headers(provider="source-clinic"):
    from services.api.config import settings
    return {"X-Connector-Token": settings()["connector_tokens"][provider]}


def wait_packet(port, hid):
    for _ in range(40):
        packets = checked(httpx.get(f"http://127.0.0.1:{port}/referrals", headers=provider_headers("provider-a" if port==8101 else "provider-b")))
        if any(p.get("id") == hid for p in packets):
            return next(p for p in packets if p.get("id") == hid)
        time.sleep(.3)
    raise AssertionError("Durable worker did not deliver the referral to the independent provider service")


def test_AT18_two_real_provider_services_callbacks_and_source_evidence(source):
    nav, cid = source
    h1 = post(nav, "/handoffs", cid, case_id=cid, receiver="provider-a", scope="episode", reason="Synthetic assessment request")
    hid1 = h1["record_id"]
    packet = wait_packet(8101, hid1)
    assert "evidence" not in packet and "audit" not in packet and "consultations" not in packet
    assert httpx.get("http://127.0.0.1:8101/referrals").status_code == 401
    reject = checked(httpx.post(f"http://127.0.0.1:8101/referrals/{hid1}/decision", headers=provider_headers("provider-a"), json={"decision": "reject", "reason": "No slots in demonstration service window", "event_id": cid + "-reject"}))
    assert reject["status"] == "delivered"
    assert checked(nav.get("/cases/"+cid))["owner"] == "navigation-team"
    h2 = post(nav, "/handoffs", cid, case_id=cid, receiver="provider-b", scope="task", reason="Alternative service with capacity")
    hid2 = h2["record_id"]
    wait_packet(8102, hid2)
    accept = checked(httpx.post(f"http://127.0.0.1:8102/referrals/{hid2}/decision", headers=provider_headers("provider-b"), json={"decision": "accept", "reason": "Assessment task accepted", "event_id": cid + "-accept"}))
    assert accept["status"] == "delivered"
    duplicate = checked(httpx.post(f"http://127.0.0.1:8102/referrals/{hid2}/decision", headers=provider_headers("provider-b"), json={"decision": "accept", "reason": "Assessment task accepted", "event_id": cid + "-accept"}))
    assert duplicate["duplicate"] is True
    base = f"http://127.0.0.1:8102/referrals/{hid2}/events"
    create = checked(httpx.post(base, headers=provider_headers("provider-b"), json={"kind":"appointment_create","event_id":cid+"-book","data":{"provider":"provider-b","scheduled_at":(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}}))
    appt = create["application"]["record_id"]
    demo_now = datetime.fromisoformat(checked(nav.get("/operations"))["clock"])
    for index,status in enumerate(["no_show", "booked", "attended"]):
        checked(httpx.post(base, headers=provider_headers("provider-b"), json={"kind":"appointment_event","event_id":cid+"-appt-"+str(index),"data":{"appointment_id":appt,"status":status,"occurred_at":(demo_now+timedelta(minutes=index+1)).isoformat()}}))
    case = checked(nav.get("/cases/"+cid))
    assert case["appointments"][-1]["status"] == "attended"
    assert "no_show" in case["delay_reasons"]
    assert not any(m["type"] == "investigation" and m["status"] == "completed" for m in case["milestones"])
    evidence = checked(httpx.post(base, headers=provider_headers("provider-b"), json={"kind":"evidence_add","event_id":cid+"-evidence","data":{"type":"investigation","reference":"synthetic://provider-b/"+cid+"/procedure","patient_id":case["patient_id"],"order_id":case["order_id"],"result_version":case["result_version"]}}))
    eid = evidence["application"]["record_id"]
    case = checked(nav.get("/cases/"+cid))
    assert next(e for e in case["evidence"] if e["id"] == eid)["verification"] == "pending"
    clinical = login("clinician")
    post(clinical, f"/evidence/{eid}/verification", cid, verified=True, reason="Reviewed authenticated provider-b procedure source and exact patient/order/result match")
    assert "patient_updated" in " ".join(checked(clinical.get(f"/cases/{cid}/closure-check"))["missing"])
    Path("runtime").mkdir(exist_ok=True)
    Path("runtime/provider-journey-proof.json").write_text(json.dumps({"case_id":cid,"provider_a_rejected":hid1,"provider_b_accepted":hid2,"appointment_id":appt,"returned_verified_evidence":eid,"owner":case["owner"],"mode":"real_http_synthetic_provider_services","captured_at":datetime.now(timezone.utc).isoformat()},indent=2))
    clinical.close()


def test_AT01_real_fhir_r4_test_intake_versioning():
    nav=login("navigator")
    rid="synthetic-"+uuid.uuid4().hex[:10]
    headers=provider_headers()
    base="http://127.0.0.1:8103/fhir"
    checked(httpx.put(base+"/Patient/"+rid,headers=headers,json={"resourceType":"Patient","id":rid,"name":[{"text":"Synthetic FHIR participant"}]}))
    checked(httpx.put(base+"/ServiceRequest/"+rid+"-order",headers=headers,json={"resourceType":"ServiceRequest","id":rid+"-order","status":"active","intent":"order","subject":{"reference":"Patient/"+rid}}))
    resource={"resourceType":"Observation","id":rid,"status":"final","subject":{"reference":"Patient/"+rid},"basedOn":[{"reference":"ServiceRequest/"+rid+"-order"}],"code":{"coding":[{"system":"http://loinc.org","code":"58453-2"}]},"valueCodeableConcept":{"coding":[{"code":"positive"}]},"issued":datetime.now(timezone.utc).isoformat()}
    checked(httpx.put(base+"/Observation/"+rid,headers=headers,json=resource))
    first=checked(nav.post("/integrations/fhir/import",json={"observation_id":rid}))
    repeated=checked(nav.post("/integrations/fhir/import",json={"observation_id":rid}))
    assert repeated["id"]==first["id"] and first["result_version"]==1
    resource["status"]="amended"
    changed=checked(httpx.put(base+"/Observation/"+rid,headers={**headers,"If-Match":'W/"1"'},json=resource))
    second=checked(nav.post("/integrations/fhir/import",json={"observation_id":rid}))
    assert second["id"]==first["id"] and second["result_version"]==2
    assert "corrected_result" in second["delay_reasons"]
    assert httpx.put(base+"/Observation/"+rid,headers={**headers,"If-Match":'W/"1"'},json=resource).status_code==412
    nav.close()


def test_fhir_r4_task_and_appointment_use_correct_patient_fields():
    rid="synthetic-"+uuid.uuid4().hex[:10]
    headers=provider_headers();base="http://127.0.0.1:8103/fhir"
    task={"resourceType":"Task","id":rid+"-task","status":"requested","intent":"order","for":{"reference":"Patient/"+rid}}
    checked(httpx.put(base+"/Task/"+task['id'],headers=headers,json=task))
    appointment={"resourceType":"Appointment","id":rid+"-appointment","status":"proposed","participant":[{"actor":{"reference":"Patient/"+rid},"status":"needs-action"}]}
    checked(httpx.put(base+"/Appointment/"+appointment['id'],headers=headers,json=appointment))
    for kind in ['Task','Appointment']:
        bundle=checked(httpx.get(base+'/'+kind,headers=headers,params={'patient':rid}))
        assert bundle['total']==1 and bundle['entry'][0]['resource']['id']==(task if kind=='Task' else appointment)['id']
    invalid={"resourceType":"Task","id":rid+"-invalid","status":"requested","intent":"order","subject":{"reference":"Patient/"+rid}}
    assert httpx.put(base+'/Task/'+invalid['id'],headers=headers,json=invalid).status_code==422
