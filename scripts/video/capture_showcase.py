"""Record the approved v2 showcase from actual Suhail pages.

Preparation only: --list validates the storyboard/shotlist without opening a browser.
Recording requires an explicit --go after the coordinating agent approves capture.
The original v1 recorder and artifacts are preserved.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from capture_ui import Tour, atomic_json, media_duration


ROOT = Path(__file__).resolve().parents[2]
STORYBOARD = ROOT / "runtime/video-v2/storyboard.json"
SHOTLIST = ROOT / "runtime/video-v2/shotlist.json"
OUTPUT = ROOT / "runtime/video-v2/captures"
TARGET_SECONDS = {"01": 26, "02": 28, "03": 34, "04": 34, "05": 34,
                  "06": 34, "07": 34, "08": 30, "09": 30, "10": 30, "11": 28}


class ShowcaseTour(Tour):
    """Small readable movements, real navigation and explicit read-only commands."""

    def __init__(self, page, context, record, base, api, folder):
        super().__init__(page, context, record, base, api)
        self.folder = folder

    def log(self, action, **detail):
        super().log(action, **detail)
        if hasattr(self, "folder"):
            atomic_json(self.folder / "progress.json", self.record["actions"])

    def goto(self, path):
        self.log("navigate", path=path)
        self.page.goto(self.base + path, wait_until="networkidle", timeout=30000)
        self.page.locator("h1").first.wait_for(state="visible", timeout=15000)
        self.page.wait_for_function(
            "!document.body.innerText.includes('Opening your secure workspace…')", timeout=15000)
        self.page.evaluate("document.fonts.ready")
        self.pause(.55)

    def scroll_y(self, target, seconds=.9):
        target = max(0, float(target))
        self.log("smooth_scroll", target=target, duration=seconds)
        start = self.page.evaluate("window.scrollY")
        steps = max(6, int(seconds * 16))
        for index in range(1, steps + 1):
            fraction = index / steps
            ease = fraction * fraction * (3 - 2 * fraction)
            self.page.evaluate("y=>window.scrollTo({top:y,behavior:'instant'})", start + (target - start) * ease)
            self.pause(seconds / steps)

    def scroll_to(self, locator, seconds=.9):
        locator.first.wait_for(state="visible", timeout=10000)
        offset = 105 if self.record["viewport"]["width"] > 600 else 25
        target = locator.first.evaluate("(e,offset)=>e.getBoundingClientRect().top+window.scrollY-offset", offset)
        self.scroll_y(target, seconds)
        self.pause(.25)

    def focus(self, locator, hold=1.5, seconds=.9):
        self.scroll_to(locator, seconds)
        self.pause(hold)

    def top(self):
        self.scroll_y(0, .7)

    def open(self, title, container=None, required=True):
        scope = container if container is not None else self.page
        summary = scope.locator("summary").filter(has_text=title).first
        if not summary.count():
            if required:
                raise RuntimeError("Required visible disclosure is absent: " + title)
            self.log("conditional_control_absent", label=title)
            return False
        self.scroll_to(summary, .65)
        if summary.locator("..").get_attribute("open") is None:
            self.log("open_disclosure", label=title)
            summary.click()
        self.pause(.6)
        return True

    def tab(self, label):
        target = self.page.get_by_role("tab", name=re.compile("^" + re.escape(label))).first
        self.scroll_to(target, .5)
        self.log("select_tab", label=label)
        target.click()
        self.pause(.75)

    def read(self, path):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Expected a local API read path")
        self.log("read_actual_api", path=path)
        response = self.context.request.get(self.api + path)
        if not response.ok:
            raise RuntimeError(f"Actual read failed {path}: HTTP {response.status}")
        return response.json()

    def authenticate(self, role):
        self.log("synthetic_demo_authentication", role=role)
        response = self.context.request.post(self.api + "/auth/demo", data={"role": role})
        if not response.ok:
            raise RuntimeError(f"Demo authentication failed {role}: HTTP {response.status}")
        seen = self.record.setdefault("roles_seen", [])
        if role not in seen:
            seen.append(role)

    def snap(self, name):
        path = self.folder / f"{self.record['id']}-{name}.png"
        self.page.screenshot(path=str(path), full_page=False)
        self.record.setdefault("screenshots", []).append({
            "name": name, "path": str(path.relative_to(ROOT)),
            "seconds": round(time.monotonic() - self.started, 3), "url": self.page.url})
        self.log("qc_screenshot", name=name, path=str(path.relative_to(ROOT)))
        return path


def perform(t: ShowcaseTour, scene: str):
    p = t.page
    if scene == "evaluation_opening":
        t.focus(p.locator(".ws-conformance-hero"), 2.8)
        t.snap("conformance-and-limits")
        t.focus(p.locator(".ws-evidence-card").first, 2.5)
        t.snap("software-and-partial-live-record")
        t.focus(p.locator(".ws-agent-grid"), 2.5)
        t.snap("six-bounded-functions")
    elif scene == "public_signin":
        t.pause(2.5)
        t.snap("public-hero")
        p.get_by_role("button", name="Show the people preview", exact=True).click()
        t.log("illustrative_preview_control", stage="The people")
        t.pause(1.6)
        t.focus(p.locator(".lp-feature-grid"), 1.5)
        t.focus(p.locator("#people"), .8)
        p.get_by_role("button", name="Patients", exact=True).click()
        t.log("role_perspective", role="Patients")
        t.pause(1.2)
        t.focus(p.locator("#signin"), 2)
        p.get_by_label("Email address", exact=True).hover()
        t.pause(.7)
        p.get_by_label("Demonstration role", exact=True).select_option("navigator")
        t.log("local_demo_role_selection", role="navigator", submitted=False)
        t.focus(p.get_by_label("Demonstration role", exact=True), 1.1)
        t.snap("signin-and-synthetic-demo")
    elif scene == "worklist_journey":
        t.pause(1.7)
        t.snap("worklist-summary")
        t.focus(p.locator("[aria-label='Filter cases']"), .8)
        t.button("Urgent review").click(); t.pause(.8)
        t.button("All cases").click()
        search = p.get_by_role("searchbox")
        search.fill("Mariam"); t.log("local_search", value="Mariam"); t.pause(.8)
        search.fill("")
        t.open("Import a synthetic source file"); t.pause(.9)
        t.snap("source-file-intake-unsubmitted")
        t.goto("/cases/SC-001"); t.pause(1.1)
        t.snap("accountable-case-and-milestones")
        t.tab("Coordination"); t.pause(.9)
        t.tab("Activity & provenance"); t.pause(.9)
    elif scene == "patient_active_mobile":
        view = p.locator(".patient-view")
        if view.get_attribute("lang") != "en":
            t.log("safe_isolated_language_preference", language="en")
            t.button("English").click()
            p.wait_for_function("document.querySelector('.patient-view')?.lang==='en'")
        t.top(); t.pause(1.7); t.snap("active-patient-english")
        t.focus(p.locator(".pt-understanding"), 1.3)
        t.snap("understanding-separate-from-receipt")
        t.focus(p.locator(".pt-questions"), 1)
        t.open("Preferred appointment times", p.locator(".pt-appointments"))
        t.focus(p.locator(".pt-survey"), 1.2)
        t.snap("optional-experience-feedback")
        t.top()
        t.log("safe_isolated_language_preference", language="ar")
        p.locator(".pt-language").click()
        p.wait_for_function("document.querySelector('.patient-view')?.dir==='rtl'")
        t.pause(1.7); t.snap("active-patient-arabic-rtl")
        t.focus(p.locator(".pt-next"), 1.4)
    elif scene == "clinical_specialist":
        selected = p.locator(".clinical-case-list button").filter(has_text="SC-001").first
        selected.wait_for(); selected.click(); t.pause(.6)
        t.focus(p.locator(".ws-consultations"), 2)
        t.snap("clinician-human-reply")
        t.focus(p.locator(".ws-consult-request"), 1)
        t.authenticate("specialist"); t.goto("/clinical")
        cases = t.read("/cases")
        chosen = None
        for item in sorted(cases, key=lambda c: not str(c["id"]).startswith("BRW-specialist")):
            detail = t.read("/cases/" + item["id"])
            if any(q.get("type") == "clinician_to_specialist" and q.get("reply")
                   for q in detail.get("consultations", [])):
                chosen = detail; break
        if chosen is None:
            raise RuntimeError("No actual answered specialist consultation is available")
        t.log("actual_assigned_specialist_case", case_id=chosen["id"])
        p.locator(".clinical-case-list button").filter(has_text=chosen["id"]).first.click()
        t.focus(p.locator(".ws-consultations"), 1.8)
        t.snap("specialist-human-consultation")
        # The specialist consultation workspace is the correct scoped surface.
        # Closure-check access is clinician-only, so show optional draft controls
        # after returning to a genuinely authenticated clinician context.
        t.authenticate("clinician")
        t.goto("/cases/SC-001")
        t.open("Prepare an AI-assisted draft")
        field = p.get_by_label("What would help?", exact=True)
        t.focus(field, .7)
        for value in ["intake", "patient_navigator", "closure_evidence"]:
            field.select_option(value); t.pause(.45)
        t.log("bounded_assistance_controls", submitted=False)
        t.snap("bounded-draft-controls-unsubmitted")
    elif scene == "receiving_appointments":
        pending = p.locator(".ws-referral-card").filter(has_text="SC-001").first
        pending.wait_for()
        pending.get_by_role("button", name="Accept referral", exact=True).wait_for()
        t.focus(pending, 1.5); t.snap("minimum-pending-referral-packet")
        t.open("Reject or request more information", pending); t.pause(.7)
        t.authenticate("receiver_b"); t.goto("/receiving")
        packets = t.read("/referrals")
        accepted = [x for x in packets if x.get("status", x.get("handoff", {}).get("status")) == "accepted"]
        accepted.sort(key=lambda x: (not bool(x.get("appointments")), x.get("case_id") != "SC-002"))
        if not accepted:
            raise RuntimeError("No seeded accepted Provider B packet is available")
        packet = accepted[0]
        card = p.locator(".ws-referral-card").filter(has_text=packet["case_id"]).first
        t.focus(card, 1.2)
        t.open("Report no available slots", card); t.pause(1)
        t.open("Confirm an appointment", card); t.pause(1)
        events = card.get_by_label("Attendance / booking event", exact=True)
        if not events.count():
            raise RuntimeError("Accepted seeded packet has no actual appointment event controls")
        t.focus(events.first, 1.2)
        t.snap("accepted-booking-and-attendance-controls")
        t.open("Return source evidence", card); t.pause(.8)
    elif scene == "source_onward_closure":
        case = t.read("/cases/SC-001")
        evidence = [e for e in case.get("evidence", [])
                    if e.get("status", "current") == "current"
                    and e.get("verification") in {"pending", "pending_verification", "unverified"}
                    and e.get("patient_id") == case["patient_id"]
                    and e.get("order_id") == case["order_id"]]
        evidence.sort(key=lambda e: e.get("type") != "investigation")
        if not evidence:
            raise RuntimeError("Isolated SC-001 has no genuine current pending retained evidence")
        item = evidence[0]
        card = p.locator(".evidence-card").filter(has_text=item["reference"]).first
        t.log("pending_source_selection", evidence_id=item["id"], reference=item["reference"])
        source_summary = card.locator("summary").filter(has_text="Read retained source").first
        t.focus(source_summary, .6)
        trigger = source_summary.locator(".care-source-trigger")

        def check_trigger(state):
            computed = trigger.evaluate("""el=>{const style=getComputedStyle(el);return {
                width:style.width,width_px:el.getBoundingClientRect().width,
                height:style.height,transform:style.transform,text:el.innerText
            }}""")
            t.record.setdefault("source_trigger_checks", []).append({"state": state, **computed})
            t.log("source_trigger_computed_style", state=state, **computed)
            assert computed["width_px"] > 100, computed
            assert computed["transform"] == "none", computed
            t.snap("source-trigger-" + state)

        check_trigger("closed")
        t.open("Read retained source", card)
        document = card.locator(".source-document")
        document.wait_for(state="visible", timeout=15000)
        check_trigger("open")
        t.focus(document, 2); t.snap("actual-pending-retained-source")
        t.focus(card.locator(".care-source-checks"), 1.1)
        t.focus(card.locator(".care-source-provenance-section"), 1.1)
        t.snap("source-provenance-and-matching")
        t.open("Verify or reject evidence", card); t.pause(1)
        t.snap("clinician-verification-form-unsubmitted")
        t.goto("/cases/SC-007")
        closure = p.locator(".care-closure-panel")
        t.focus(closure, 3)
        t.snap("complete-onward-blocking-checklist")
        t.open("Record authorized disposition", closure); t.pause(.7)
        summary = closure.locator("summary").filter(has_text="Record authorized disposition").first
        summary.click()
        t.log("close_disposition_form_unsubmitted")
        t.pause(.35)
        t.focus(closure, 2.5)
        t.snap("onward-endpoint-still-required")
    elif scene == "safety_exceptions":
        t.pause(1.5); t.snap("trusted-urgent-source-signal")
        t.focus(p.locator(".care-urgent-panel"), 1.5)
        t.goto("/cases/SC-004"); t.pause(1.5)
        t.snap("identity-quarantine")
        t.goto("/cases/SC-008"); t.pause(1.2)
        t.focus(p.locator(".care-evidence-panel"), 2)
        t.snap("amended-result-and-superseded-evidence")
    elif scene == "patient_completed_mobile":
        if p.locator(".patient-view").get_attribute("lang") != "en":
            raise RuntimeError("Native completed patient is not English; recorder will not change native preferences")
        t.pause(1.7); t.snap("completed-patient-next-step")
        t.open("View earlier result message"); t.pause(.7)
        t.focus(p.locator(".pt-understanding"), 1)
        t.focus(p.locator(".pt-appointments"), 1.4)
        t.focus(p.locator(".pt-approved-plan"), 2.2)
        t.snap("actual-approved-patient-care-plan")
    elif scene == "operations":
        t.focus(p.locator(".ws-stage-panel"), 2)
        t.snap("full-denominator-milestones-and-dispositions")
        t.focus(p.locator(".ws-outbox-panel"), 1.2)
        p.get_by_role("button", name="Needs attention", exact=True).click(); t.pause(.9)
        p.get_by_role("button", name="All delivery", exact=True).click(); t.pause(.9)
        t.log("read_only_outbox_filters", retried=False)
        t.snap("owned-delivery-and-urgent-review")
        t.focus(p.locator(".ws-connectors"), 1.5)
        t.focus(p.locator(".ws-experience-note"), 1.4)
    elif scene == "reports_closing":
        t.focus(p.locator(".ws-agent-grid"), 1.8)
        t.snap("actual-function-records-and-scoring-audit")
        t.focus(p.locator(".ws-budget-card"), 2)
        t.snap("request-and-token-accounting")
        t.focus(p.locator(".ws-current-run"), 1.3)
        t.focus(p.locator(".ws-run-archive"), 1.2)
        t.snap("actual-report-downloads-and-archive")
        t.top(); t.pause(1.5)
        t.snap("closing-evidence-and-limits")
    else:
        raise ValueError("Unknown v2 scene: " + scene)


def checkpoint(manifest, record):
    manifest["scenes"] = sorted(
        [r for r in manifest["scenes"] if r["id"] != record["id"]] + [record], key=lambda r: r["id"])
    atomic_json(OUTPUT / "manifest.json", manifest)


def capture(browser, chapter, plan, stacks, manifest, seconds=None, reduced_motion=False):
    scene_id = chapter["id"]
    stack = plan["stack"]
    base, api = stacks[stack]["web"], stacks[stack]["api"]
    viewport = plan["viewport"]
    role = plan["roles"][0]
    folder = OUTPUT / scene_id
    folder.mkdir(parents=True, exist_ok=True)
    record = {"id": scene_id, "title": chapter["title"], "scene": chapter["scene"],
              "stack": stack, "role": role, "base_url": base, "api_url": api,
              "browser_engine": browser.browser_type.name,
              "viewport": viewport, "status": "recording", "actions": [], "errors": [],
              "screenshots": [], "non_get_requests": [], "trim_start_seconds": 0,
              "motion_preference": "reduce" if reduced_motion else "no-preference",
              "started_at": datetime.now(timezone.utc).isoformat()}
    context_options = {"viewport": viewport, "record_video_dir": str(folder),
                       "record_video_size": viewport,
                       "reduced_motion": "reduce" if reduced_motion else "no-preference"}
    # Firefox records the same actual responsive viewport, but does not implement
    # Playwright's Chromium/WebKit isMobile emulation option.
    if browser.browser_type.name != "firefox":
        context_options.update(is_mobile=viewport["width"] < 600, has_touch=viewport["width"] < 600)
    context = browser.new_context(**context_options)

    def guard(route):
        request = route.request
        url = urlsplit(request.url)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            allowed = False
            approved_origin = (url.scheme + "://" + url.netloc) in {base, api}
            if approved_origin and request.method == "POST":
                if url.path in {"/api/auth/demo", "/auth/demo"}:
                    allowed = True
                elif stack == "isolated" and chapter["scene"] == "patient_active_mobile" and url.path == "/api/cases/SC-001/preferences":
                    try:
                        data = request.post_data_json
                        allowed = (isinstance(data, dict) and data.get("language") in {"en", "ar"}
                                   and set(data) <= {"expected_version", "idempotency_key", "correlation_id", "language", "channel"})
                    except Exception:
                        allowed = False
            record["non_get_requests"].append({"method": request.method, "path": url.path, "allowed": allowed})
            if not allowed:
                record["errors"].append({"type": "blocked_non_readonly_request", "method": request.method, "path": url.path})
                route.abort(); return
        route.continue_()

    context.route("**/*", guard)
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda e: record["errors"].append({"type": "pageerror", "message": str(e)}))
    page.on("crash", lambda: record["errors"].append({"type": "browser_page_crash"}))

    def response_check(response):
        if "/api/" in response.url and response.status >= 400:
            record["errors"].append({"type": "api_http_error", "path": urlsplit(response.url).path, "status": response.status})

    page.on("response", response_check)
    began = time.monotonic()
    tour = ShowcaseTour(page, context, record, base, api, folder)
    checkpoint(manifest, record)
    try:
        if role != "public":
            tour.authenticate(role)
        tour.goto(plan.get("route", plan.get("routes", ["/"])[0]))
        record["trim_start_seconds"] = round(time.monotonic() - began, 3)
        perform(tour, chapter["scene"])
        remaining = (seconds if seconds is not None else TARGET_SECONDS[scene_id]) - (time.monotonic() - began)
        if remaining > 0:
            tour.pause(remaining)
        screenshot = tour.snap("final")
        record.update(status="completed" if not record["errors"] else "completed_with_errors",
                      screenshot_path=str(screenshot.relative_to(ROOT)), final_url=page.url)
    except Exception as exc:
        record["status"] = "failed"
        record["errors"].append({"type": type(exc).__name__, "message": str(exc)[:2000]})
        try:
            screenshot = tour.snap("error")
            record["screenshot_path"] = str(screenshot.relative_to(ROOT))
        except Exception:
            pass
    finally:
        video = page.video
        context.close()
        path = Path(video.path())
        actual = media_duration(path)
        record.update(video_path=str(path.relative_to(ROOT)),
                      duration_seconds=actual if actual is not None else round(time.monotonic() - began, 3),
                      duration_method="ffprobe" if actual is not None else "wall_clock",
                      finished_at=datetime.now(timezone.utc).isoformat())
        checkpoint(manifest, record)
        print(json.dumps({k: record.get(k) for k in ["id", "status", "video_path", "duration_seconds", "screenshot_path", "errors"]}), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="Validate and list scenes; no browser or network")
    parser.add_argument("--go", action="store_true", help="Record only after the coordinating agent's explicit GO")
    parser.add_argument("--scenes", nargs="*")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seconds", type=float, help="Override the minimum raw duration per scene")
    parser.add_argument("--reduced-motion", action="store_true", help="Approved resource fallback using the application's real reduced-motion preference")
    parser.add_argument("--browser", choices=["chromium", "firefox"], default="chromium")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()
    chapters = json.loads(STORYBOARD.read_text())
    shotlist = json.loads(SHOTLIST.read_text())
    plans = {p["id"]: p for p in shotlist["scenes"]}
    if {c["id"] for c in chapters} != set(plans):
        parser.error("Storyboard and shotlist scene IDs differ")
    for chapter in chapters:
        plan = plans[chapter["id"]]
        if chapter["scene"] != plan["scene"]:
            parser.error("Storyboard and shotlist scene names differ")
        expected = {"width": 390, "height": 844} if chapter["id"] in {"04", "09"} else {"width": 1600, "height": 760}
        if plan["viewport"] != expected:
            parser.error("Unexpected viewport for chapter " + chapter["id"])
    if plans["07"]["stack"] != "isolated":
        parser.error("Chapter 07 must show actual isolated pending source evidence")
    selected = set(args.scenes or plans)
    if selected - set(plans):
        parser.error("Unknown scenes: " + ", ".join(sorted(selected - set(plans))))
    if args.list:
        print(json.dumps([{"id": c["id"], "scene": c["scene"], "stack": plans[c["id"]]["stack"],
                           "roles": plans[c["id"]]["roles"], "viewport": plans[c["id"]]["viewport"],
                           "minimum_raw_seconds": args.seconds or TARGET_SECONDS[c["id"]]}
                          for c in chapters if c["id"] in selected], indent=2))
        return 0
    if not args.go:
        parser.error("Recording is paused. Use --list for preparation; pass --go only after root approves capture.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUTPUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        "generated_at": datetime.now(timezone.utc).isoformat(), "version": "2",
        "storyboard_path": str(STORYBOARD.relative_to(ROOT)), "shotlist_path": str(SHOTLIST.relative_to(ROOT)),
        "capture_policy": "Actual UI; one context/page/stack/viewport per scene; no clinical or model submissions; isolated scene04 language preference only.",
        "scenes": []}
    failed = False
    with sync_playwright() as playwright:
        browser = (playwright.firefox.launch(headless=True) if args.browser == "firefox" else
                   playwright.chromium.launch(headless=True,
                       args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--renderer-process-limit=2"]))
        try:
            for chapter in chapters:
                if chapter["id"] not in selected:
                    continue
                existing = next((r for r in manifest["scenes"] if r["id"] == chapter["id"]), None)
                if args.resume and existing and existing["status"] == "completed" and (ROOT / existing["video_path"]).exists():
                    continue
                record = capture(browser, chapter, plans[chapter["id"]], shotlist["stacks"], manifest, args.seconds, args.reduced_motion)
                if record["status"] != "completed":
                    failed = True
                    if not args.continue_on_error:
                        break
        finally:
            browser.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
