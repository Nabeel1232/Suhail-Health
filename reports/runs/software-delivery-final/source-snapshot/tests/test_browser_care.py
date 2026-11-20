"""Complete visible care workflow after test_browser.py's patient/clinician journey.

The release runner resets only the identified synthetic demo dataset, then runs
test_browser.py before this module. This test deliberately completes SC-001 so
the authenticated demonstration patient can see the evidenced final care plan.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import uuid

from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).parent))
from test_browser import API, WEB, api_client, checked, case_command, browser_login


def save(page, container, button, values=None):
    form = container.locator("form").filter(has=page.get_by_role("button", name=button, exact=True)).first
    for name, value in (values or {}).items():
        field = form.locator(f'[name="{name}"]')
        if field.evaluate("e=>e.tagName") == "SELECT":
            field.select_option(str(value))
        else:
            field.fill(str(value))
    with page.expect_response(lambda r: r.request.method == "POST" and "/api/" in r.url) as response:
        form.get_by_role("button", name=button, exact=True).click()
    assert response.value.ok, (response.value.status, response.value.text()[:500])
    expect(page.get_by_role("button", name="Saving…", exact=True)).to_have_count(0, timeout=15000)
    return response.value.json()


def open_section(container, title):
    summary = container.locator("summary").filter(has_text=title).first
    if summary.locator("..").get_attribute("open") is None:
        summary.click()


def patient_packet(page, patient_name):
    return page.locator("section.panel").filter(has=page.get_by_role("heading", name=patient_name, exact=True)).first


def test_full_visible_result_to_care_with_two_providers():
    nav, clinician, patient = api_client("navigator"), api_client("clinician"), api_client("patient")
    case_id, token = "SC-001", uuid.uuid4().hex[:10]
    approved_plan = "Your clinician has reviewed the assessment and recorded that no further action is required for this synthetic screening episode. Contact your responsible care team if you have questions."
    record = {"case_id": case_id, "started_at": datetime.now(timezone.utc).isoformat(),
              "evidence_mode": "actual_browser_over_persisted_synthetic_application", "steps": [], "status": "running"}
    output = Path("runtime/browser-fullcare-journey.json")
    Path("runtime/screenshots").mkdir(parents=True, exist_ok=True)

    def snapshot(step):
        current = checked(nav.get(f"/cases/{case_id}"))
        record["steps"].append({"step": step, "case_version": current["version"], "owner": current["owner"],
            "disposition": current["disposition"], "handoffs": [{k: h.get(k) for k in ("id", "receiver", "scope", "status")} for h in current["handoffs"]],
            "appointments": [{"id": a["id"], "status": a["status"]} for a in current["appointments"]],
            "evidence": [{"id": e["id"], "type": e["type"], "verification": e["verification"], "source": e["source"]} for e in current["evidence"]]})
        return current

    try:
        initial = snapshot("initial_post_consultation_state")
        assert initial["disposition"] == "open", "Run make test-e2e to reset/replay the identified synthetic baseline first."
        case_command(patient, case_id, f"/cases/{case_id}/preferences", {"language": "en", "channel": "portal"})
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            mobile = browser.new_context(viewport={"width":390, "height":844}, is_mobile=True, has_touch=True)
            patient_page = browser_login(mobile, "patient")
            ack = patient_page.get_by_role("button", name="I have received this update", exact=True)
            if ack.count():
                with patient_page.expect_response(lambda r: r.request.method == "POST" and "/acknowledgement" in r.url) as response:
                    ack.click()
                assert response.value.ok
            save(patient_page, patient_page, "Send my understanding", {"outcome": "passed"})
            save(patient_page, patient_page, "Share optional feedback", {"confidence": "4", "reassurance": "4"})
            current = snapshot("patient_acknowledgement_understanding_and_optional_feedback")
            assert current["communications"][-1]["understanding"] == "passed"
            assert current["experience"][-1]["confidence"] == 4

            nav_context = browser.new_context(viewport={"width":1440,"height":1000})
            nav_page = browser_login(nav_context, "navigator", f"/cases/{case_id}")
            nav_page.get_by_role("tab", name="Coordination", exact=True).click()
            open_section(nav_page, "Propose a referral")
            save(nav_page, nav_page, "Propose referral", {"receiver":"provider-a", "scope":"episode", "reason":f"Synthetic browser assessment referral {token}; require explicit destination decision"})
            before = snapshot("provider_a_proposed_sender_retains_owner")
            assert before["owner"] == initial["owner"]

            provider_a_context = browser.new_context(viewport={"width":1280,"height":900})
            provider_a = browser_login(provider_a_context, "receiver_a")
            packet_a = patient_packet(provider_a, current["patient_name"])
            expect(packet_a).to_be_visible()
            open_section(packet_a, "Reject or request more information")
            save(provider_a, packet_a, "Reject with recorded reason", {"reason":"Synthetic service has no available assessment capacity in the requested window"})
            rejected = snapshot("provider_a_rejected_sender_still_accountable")
            assert rejected["owner"] == initial["owner"]
            assert any(h["receiver"] == "provider-a" and h["status"] == "rejected" for h in rejected["handoffs"])

            nav_page.reload(); nav_page.get_by_role("tab", name="Coordination", exact=True).click()
            open_section(nav_page, "Propose a referral")
            save(nav_page, nav_page, "Propose referral", {"receiver":"provider-b", "scope":"episode", "reason":f"Alternative synthetic service capacity after recorded rejection {token}"})
            provider_b_context = browser.new_context(viewport={"width":1440,"height":1000})
            provider_b = browser_login(provider_b_context, "receiver_b")
            packet_b = patient_packet(provider_b, current["patient_name"])
            with provider_b.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/accept")) as response:
                packet_b.get_by_role("button", name="Accept referral", exact=True).click()
            assert response.value.ok
            expect(packet_b.get_by_role("button", name="Accept referral", exact=True)).to_have_count(0)
            accepted = snapshot("provider_b_authorized_acceptance_changes_episode_owner")
            assert accepted["owner"] == "provider-b"

            open_section(packet_b, "Report no available slots")
            save(provider_b, packet_b, "Record unavailable capacity", {"reason":"Synthetic service has no immediately available slot; named receiving team will arrange the next confirmed appointment"})
            unavailable = snapshot("capacity_problem_before_booking_creates_owned_recovery")
            assert not unavailable["appointments"], "No-slot capacity reporting must not fabricate an appointment."
            assert "no_slots" in unavailable["delay_reasons"]
            assert any(t["assignee"] for t in unavailable["tasks"] if "recovery" in t["type"])

            booked_at = (datetime.now(timezone.utc)+timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
            save(provider_b, packet_b, "Record confirmed appointment", {"scheduled_at":booked_at})
            appointment = packet_b.locator(".appointment-card").last
            save(provider_b, appointment, "Record appointment event", {"status":"no_show"})
            no_show = snapshot("no_show_creates_owned_recovery")
            assert any(t["type"] == "appointment_recovery" and t["assignee"] for t in no_show["tasks"])
            patient_page.reload()
            expect(patient_page.get_by_text("Recovery work remains with the care team. A new appointment needs confirmation.", exact=True)).to_be_visible()
            save(provider_b, appointment, "Record appointment event", {"status":"booked"})
            save(provider_b, appointment, "Record appointment event", {"status":"attended"})
            attended = snapshot("rebooked_then_attended_investigation_still_required")
            assert attended["appointments"][-1]["status"] == "attended"
            assert not checked(clinician.get(f"/cases/{case_id}/closure-check"))["allowed"]

            # The receiving service returns an actual retained synthetic source document.
            investigation_ref = f"synthetic://browser-care/{token}/investigation"
            open_section(packet_b, "Return source evidence")
            save(provider_b, packet_b, "Link evidence for verification", {"type":"investigation", "reference":investigation_ref,
                "document_text":f"Synthetic completed investigation source. Patient {current['patient_id']}; order {current['order_id']}; result version {current['result_version']}. The fictional assessment was completed and requires clinician review.", "requires_onward":"false"})
            provider_b.evaluate("document.activeElement?.blur(); window.scrollTo({top:0,behavior:'instant'})")
            provider_b.screenshot(path="runtime/screenshots/fullcare-receiving-b.png", full_page=True)

            clinical_context = browser.new_context(viewport={"width":1440,"height":1000})
            clinical_page = browser_login(clinical_context, "clinician", f"/cases/{case_id}")
            investigation = clinical_page.locator(".evidence-card").filter(has_text=investigation_ref)
            with clinical_page.expect_response(lambda r: r.request.method == "GET" and "/api/evidence/" in r.url and r.url.endswith("/source")) as source_response:
                open_section(investigation, "Read retained source")
            assert source_response.value.ok
            source_record = source_response.value.json()
            assert source_record["verification"] == "pending" and source_record["source"] == "provider-b"
            record.setdefault("source_reviews", []).append({k:source_record[k] for k in ("evidence_id","case_id","case_version","reference","source","content_hash","verification","status","matching")})
            expect(investigation.locator(".source-document")).to_contain_text("Synthetic completed investigation source.")
            expect(investigation.locator(".source-document")).to_contain_text(current["patient_id"])
            expect(investigation.locator(".source-provenance")).to_contain_text("provider b")
            clinical_page.evaluate("document.activeElement?.blur(); window.scrollTo({top:0,behavior:'instant'})")
            clinical_page.screenshot(path="runtime/screenshots/fullcare-source-review-before-verification.png", full_page=True)
            open_section(investigation, "Verify or reject evidence")
            save(clinical_page, investigation, "Record verification", {"verified":"true", "reason":"Qualified synthetic reviewer checked retained provider document, source identity, patient/order match and current result version"})

            for evidence_type in ("reviewed_outcome", "patient_updated"):
                reference = f"synthetic://browser-care/{token}/{evidence_type}"
                open_section(clinical_page, "Link supporting evidence")
                save(clinical_page, clinical_page, "Link evidence for verification", {"type":evidence_type, "reference":reference,
                    "document_text":approved_plan, "requires_onward":"false"})
                item = clinical_page.locator(".evidence-card").filter(has_text=reference)
                with clinical_page.expect_response(lambda r: r.request.method == "GET" and "/api/evidence/" in r.url and r.url.endswith("/source")) as source_response:
                    open_section(item, "Read retained source")
                assert source_response.value.ok
                source_record = source_response.value.json()
                assert source_record["verification"] == "pending"
                record.setdefault("source_reviews", []).append({k:source_record[k] for k in ("evidence_id","case_id","case_version","reference","source","content_hash","verification","status","matching")})
                expect(item.locator(".source-document")).to_contain_text(approved_plan)
                open_section(item, "Verify or reject evidence")
                save(clinical_page, item, "Record verification", {"verified":"true", "reason":"Qualified synthetic reviewer matched the retained source document to patient, order, current result version and applicable care endpoint."})
            snapshot("investigation_reviewed_outcome_and_patient_plan_verified")

            # Clinical evidence gates are satisfied only by their dedicated commands.
            # Here the navigator records the distinct human coordination/recovery work.
            current = checked(nav.get(f"/cases/{case_id}"))
            protected = {"result_ingested","identity","notification","acknowledgement","understanding","referral","appointment","attendance","investigation","reviewed_outcome","patient_updated","treatment_initiated","surveillance_plan","urgent_review","consultation","quarantine"}
            for task in current["tasks"]:
                if task["status"] in ("completed","cancelled") or task["type"] in protected or task["type"].startswith(("consultation:","evidence_review:")):
                    continue
                nav_page.reload();nav_page.get_by_role("tab",name="Coordination",exact=True).click()
                label = task["type"].replace("_"," ").replace("-"," ")
                row = nav_page.locator(".task-row").filter(has=nav_page.get_by_text(label,exact=True)).first
                open_section(row, "Record coordination work")
                save(nav_page, row, "Update task", {"status":"completed", "reason":"Navigator completed the agreed human follow-up, confirmed understanding after explanation, resolved referral capacity/no-show recovery, and confirmed the evidenced care plan with the receiving team"})
            preclose = snapshot("owned_consultation_and_recovery_tasks_completed")
            check = checked(clinician.get(f"/cases/{case_id}/closure-check"))
            assert check["allowed"], check["missing"]
            assert all(t["status"] == "completed" for t in preclose["tasks"] if t["required"])

            clinical_page.reload()
            expect(clinical_page.get_by_text("Evidence requirements satisfied",exact=True)).to_be_visible()
            open_section(clinical_page, "Record authorized disposition")
            save(clinical_page, clinical_page, "Record disposition", {"category":"completed_required_care",
                "reason":"Authorized synthetic clinician reviewed sourced investigation, outcome and patient communication, confirmed completed required endpoint and all owned work, and documented the follow-up plan", "residual_need":""})
            closed = snapshot("authorized_completed_required_care_disposition")
            assert closed["disposition"] == "completed_required_care" and not closed["residual_need"]
            clinical_page.evaluate("document.activeElement?.blur(); window.scrollTo({top:0,behavior:'instant'})")
            clinical_page.screenshot(path="runtime/screenshots/fullcare-closed-clinical.png", full_page=True)
            patient_page.reload()
            expect(patient_page.get_by_role("heading",name="Your follow-up plan is documented.",exact=True).first).to_be_visible()
            expect(patient_page.get_by_text(approved_plan,exact=False)).to_be_visible()
            expect(patient_page.get_by_role("button",name="Send my understanding",exact=True)).to_have_count(0)
            expect(patient_page.get_by_text("Your care-team communication record",exact=True)).to_be_visible()
            assert patient_page.evaluate("document.documentElement.scrollWidth<=window.innerWidth+1")
            patient_page.evaluate("document.activeElement?.blur(); window.scrollTo({top:0,behavior:'instant'})")
            patient_page.screenshot(path="runtime/screenshots/fullcare-closed-patient-mobile.png", full_page=True)
            browser.close()
        record["status"] = "completed"
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = {"type":type(exc).__name__,"message":str(exc)[:1500]}
        raise
    finally:
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(record,indent=2))
        nav.close();clinician.close();patient.close()
