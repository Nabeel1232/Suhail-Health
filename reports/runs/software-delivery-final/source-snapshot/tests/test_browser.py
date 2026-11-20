"""Actual Chromium desktop/mobile journeys over the persisted running application."""
import json
import re
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import sync_playwright, expect

API = os.environ.get("TEST_API_URL", "http://127.0.0.1:18000")
WEB = os.environ.get("TEST_WEB_URL", "http://127.0.0.1:3000")


def checked(response):
    assert response.is_success, (response.status_code, response.text[:500])
    return response.json()


def api_client(role):
    c = httpx.Client(base_url=API, timeout=20)
    checked(c.post("/auth/demo", json={"role": role}))
    return c


def case_command(client, case_id, path, data):
    for attempt in range(4):
        case = checked(client.get("/cases/" + case_id))
        response = client.post(path, json={"expected_version": case["version"], "idempotency_key": "browser:" + uuid.uuid4().hex, **data})
        if response.status_code == 409 and "version" in response.text.lower():
            continue
        return checked(response)
    return checked(response)


def new_case(nav, label, **changes):
    cid = "BRW-" + label + "-" + uuid.uuid4().hex[:7]
    event = {"event_id": cid, "case_id": cid, "dataset": "browser-v1", "source_organization": "source-clinic", "patient_id": cid + "-P", "patient_name": "Synthetic " + label, "order_id": cid + "-O", "result_version": 1, "test_code": "FIT_POS", "issued_at": (datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(), "identity_verified": True, **changes}
    return checked(nav.post("/events/results", json=event))


def browser_login(context, role, path=None):
    response = context.request.post(API + "/auth/demo", data={"role": role})
    assert response.ok
    page = context.new_page()
    page.goto(WEB + (path or {"patient":"/patient","clinician":"/clinical","specialist":"/clinical","receiver_a":"/receiving","receiver_b":"/receiving","admin":"/operations"}.get(role,"/worklist")))
    expect(page.get_by_text("Opening your secure workspace…")).to_have_count(0)
    return page


def form_for(page, button):
    return page.locator("form").filter(has=page.get_by_role("button", name=button, exact=True)).first


def submit(page, button, values=None):
    form = form_for(page, button)
    for name, value in (values or {}).items():
        field = form.locator(f'[name="{name}"]')
        if field.evaluate("e => e.tagName") == "SELECT":
            field.select_option(str(value))
        else:
            field.fill(str(value))
    with page.expect_response(lambda r: r.request.method == "POST" and "/api/" in r.url) as response:
        form.get_by_role("button", name=button, exact=True).click()
    assert response.value.ok, (response.value.status, response.value.text()[:500])
    expect(page.get_by_role("button", name="Saving…", exact=True)).to_have_count(0, timeout=15000)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--no-sandbox"])
        yield b
        b.close()


@pytest.fixture(scope="module")
def nav():
    client = api_client("navigator")
    yield client
    client.close()


def test_public_entry_keyboard_and_demo_signin(browser):
    context = browser.new_context(viewport={"width":1440,"height":1000})
    page=context.new_page(); page.goto(WEB)
    expect(page.get_by_role("heading",name="Guiding every result to care.")).to_be_visible()
    expect(page.get_by_text("Fictional patients and simulated providers.",exact=False)).to_be_visible()
    page.get_by_label("Demonstration role").select_option("navigator")
    page.get_by_role("button",name="Enter synthetic demo",exact=True).click()
    page.wait_for_url("**/worklist")
    expect(page.get_by_role("heading",name="Every case, a clear next step.")).to_be_visible()
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.tagName") != "BODY"
    Path("runtime/screenshots").mkdir(parents=True,exist_ok=True)
    page.screenshot(path="runtime/screenshots/worklist-desktop.png",full_page=True)
    context.close()


def test_patient_question_human_reply_two_sessions_and_rtl_mobile(browser,nav):
    patient=api_client("patient")
    case_command(patient,"SC-001","/cases/SC-001/preferences",{"language":"en","channel":"portal"})
    mobile=browser.new_context(viewport={"width":390,"height":844},is_mobile=True,has_touch=True)
    page=browser_login(mobile,"patient")
    expect(page.get_by_role("heading",name="Your next step, in one place.")).to_be_visible()
    ack=page.get_by_role("button",name="I have received this update",exact=True)
    if ack.count():
        ack.click();expect(page.get_by_text("Thank you. Your acknowledgement is recorded.")).to_be_visible()
    submit(page,"Send my understanding",{"outcome":"needs_help"})
    case=checked(nav.get("/cases/SC-001"))
    assert any(t["type"]=="understanding_help" and t["assignee"] for t in case["tasks"])
    question="Browser proof: can my clinician explain the next assessment? " + uuid.uuid4().hex[:8]
    submit(page,"Send to my clinician",{"question":question})
    clinical=browser.new_context(viewport={"width":1440,"height":1000})
    clinician=browser_login(clinical,"clinician","/cases/SC-001")
    clinician.get_by_role("tab",name="Consultations",exact=False).click()
    thread=clinician.locator("article.consultation").filter(has_text=question)
    reply="Your care team will explain and coordinate the diagnostic follow-up. This screening result is not a diagnosis."
    thread.get_by_label("Your clinical reply").fill(reply)
    thread.get_by_label("Agreed next action").fill("Call the patient to explain the assessment")
    thread.get_by_label("Accountable action owner").fill("navigation-team")
    thread.get_by_role("button",name="Send human reply & next action",exact=True).click()
    expect(thread.get_by_text(reply,exact=True)).to_be_visible()
    page.reload();expect(page.get_by_text(reply,exact=True)).to_be_visible()
    page.get_by_role("button",name="العربية",exact=True).click()
    expect(page.locator('.patient-view')).to_have_attribute("dir","rtl")
    expect(page.get_by_role("heading",name="خطوتك التالية في مكان واحد.")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth+1")
    page.reload();expect(page.locator('.patient-view')).to_have_attribute("dir","rtl")
    page.screenshot(path="runtime/screenshots/patient-arabic-mobile.png",full_page=True)
    assert "gpt-oss" not in page.locator("body").inner_text()
    mobile.close();clinical.close();patient.close()


def test_clinician_specialist_consultation_real_human_reply(browser,nav):
    case=new_case(nav,"specialist")
    context=browser.new_context();page=browser_login(context,"clinician","/cases/"+case["id"])
    page.get_by_role("tab",name="Consultations",exact=False).click()
    question="Browser e-consult: confirm the appropriate coordination next action. " + uuid.uuid4().hex[:8]
    submit(page,"Assign consultation",{"question":question,"recipient":"specialist"})
    other=browser.new_context();specialist=browser_login(other,"specialist","/cases/"+case["id"])
    specialist.get_by_role("tab",name="Consultations",exact=False).click()
    reply="Specialist human response: arrange the source-reviewed assessment with the receiving service."
    submit(specialist,"Send human reply & next action",{"reply":reply,"agreed_action":"Coordinate diagnostic assessment","action_owner":"navigation-team"})
    page.reload();page.get_by_role("tab",name="Consultations",exact=False).click()
    expect(page.get_by_text(reply,exact=True)).to_be_visible()
    stored=checked(nav.get("/cases/"+case["id"]))
    assert stored["consultations"][0]["human_author"]=="demo-specialist"
    context.close();other.close()


def test_quarantine_authorized_recovery_browser(browser,nav):
    case=new_case(nav,"identity",identity_verified=False)
    context=browser.new_context();page=browser_login(context,"navigator","/cases/"+case["id"])
    expect(page.get_by_text("Progression blocked: identity conflict")).to_be_visible()
    submit(page,"Reconcile with evidence",{"source_reference":"synthetic://source-clinic/identity-check","reason":"Authorized operator checked exact synthetic patient and order identifiers against source document"})
    expect(page.get_by_text("Progression blocked:",exact=False)).to_have_count(0)
    assert checked(nav.get("/cases/"+case["id"]))["quarantine_reason"] is None
    context.close()


def test_urgent_with_unavailable_inference_ack_separate_disposition(browser,nav):
    case=new_case(nav,"urgent",trusted_urgent=True)
    context=browser.new_context();page=browser_login(context,"clinician","/cases/"+case["id"])
    expect(page.get_by_text("Trusted urgent signal · clinician review required")).to_be_visible()
    page.get_by_role("button",name="Acknowledge staff alert",exact=True).click()
    expect(page.get_by_role("button",name="Acknowledge staff alert",exact=True)).to_have_count(0)
    stored=checked(nav.get("/cases/"+case["id"]))
    assert stored["escalations"][0]["acknowledged_at"] and not stored["escalations"][0]["disposition"]
    # No AI request is made; trusted escalation and disposition are application commands.
    submit(page,"Record clinical disposition",{"decision":"continue_pathway","reason":"Qualified human assessed the synthetic trusted source and documented safe screening follow-up disposition"})
    assert checked(nav.get("/cases/"+case["id"]))["escalations"][0]["disposition"]
    context.close()


def test_invalid_evidence_and_onward_endpoint_blocked_in_browser(browser,nav):
    for label,changes in [("wrong-evidence",{}),("onward",{"requires_onward":True})]:
        case=new_case(nav,label,**changes)
        clinical=api_client("clinician")
        if label=="wrong-evidence":
            item=case_command(clinical,case["id"],f'/cases/{case["id"]}/evidence',{"type":"investigation","reference":"synthetic://fabricated/missing","patient_id":"WRONG-PATIENT","order_id":case["order_id"],"result_version":1})
            detail=checked(clinical.get("/cases/"+case["id"]))
            response=clinical.post(f'/evidence/{item["record_id"]}/verification',json={"expected_version":detail["version"],"idempotency_key":uuid.uuid4().hex,"verified":True,"reason":"Attempt invalid source proof"})
            assert response.status_code==409
        context=browser.new_context();page=browser_login(context,"clinician","/cases/"+case["id"])
        page.locator("summary").filter(has_text="Record authorized disposition").click()
        form=form_for(page,"Record disposition")
        form.get_by_label("Clinical rationale").fill("Attempt closure before source evidence and required care endpoint")
        form.get_by_role("button",name="Record disposition",exact=True).click()
        expect(form.get_by_role("alert")).to_be_visible()
        assert checked(nav.get("/cases/"+case["id"]))["disposition"]=="open"
        context.close();clinical.close()


def test_amended_result_reopens_approved_work_in_browser(browser,nav):
    case=checked(nav.get("/cases/SC-008"))
    context=browser.new_context();page=browser_login(context,"clinician","/cases/SC-008")
    version=case["result_version"]+1
    checked(nav.post("/events/results",json={"event_id":"browser-correction-"+uuid.uuid4().hex,"source_organization":"source-clinic","patient_id":case["patient_id"],"patient_name":case["patient_name"],"order_id":case["order_id"],"result_version":version,"test_code":"FIT_POS","issued_at":datetime.now(timezone.utc).isoformat(),"identity_verified":True}))
    page.reload();expect(page.get_by_text(f"Source result v{version}",exact=False)).to_be_visible()
    stored=checked(nav.get("/cases/SC-008"))
    assert stored["disposition"]=="open" and all(e["status"]=="superseded" for e in stored["evidence"])
    expect(page.get_by_text("More evidence is needed",exact=True)).to_be_visible()
    context.close()


def test_informed_decline_retains_residual_need_and_permissions(browser,nav):
    context=browser.new_context();page=browser_login(context,"clinician","/cases/SC-006")
    expect(page.get_by_text("informed decline",exact=True).first).to_be_visible()
    case=checked(nav.get("/cases/SC-006"));assert case["residual_need"] and case["disposition"]=="informed_decline"
    other=browser.new_context();patient=browser_login(other,"patient","/evaluation")
    expect(patient.get_by_role("heading",name="This workspace is restricted")).to_be_visible()
    assert other.request.get(API+"/cases/SC-006").status==403
    assert other.request.get(API+"/reports").status==403
    context.close();other.close()


def test_operations_evaluation_reports_and_no_js_failures(browser):
    context=browser.new_context(viewport={"width":1440,"height":1000});page=browser_login(context,"admin")
    errors=[];page.on("pageerror",lambda e:errors.append(str(e)))
    expect(page.get_by_role("heading",name="Keep the loop moving.")).to_be_visible()
    operation_response = context.request.get(API+"/operations")
    assert operation_response.ok
    outbox = operation_response.json()["outbox"]
    if outbox:
        first = outbox[0]
        title = first["kind"].replace("_", " ").replace("-", " ")
        row = page.locator(".outbox-row").filter(has=page.get_by_role("link", name=f"Open case {first['case_id']}", exact=False)).filter(has=page.get_by_text(title, exact=True)).first
        expect(row).to_be_visible()
        expect(row.locator(".record-row strong")).to_have_text(title)
        expect(row.get_by_role("link", name=f"Open case {first['case_id']}", exact=False)).to_have_attribute("href", f"/cases/{first['case_id']}")
        if first.get("error_code") and first["status"] == "dead_letter":
            expect(row.get_by_text("Error: "+first["error_code"].replace("_", " ").replace("-", " "), exact=True)).to_be_visible()
    page.goto(WEB+"/evaluation")
    expect(page.get_by_role("heading",name="Measured evidence. Clear limits.")).to_be_visible()
    expect(page.get_by_text("software-holdout-v1",exact=False).first).to_be_visible()
    assert not errors
    page.screenshot(path="runtime/screenshots/evaluation-desktop.png",full_page=True)
    context.close()
