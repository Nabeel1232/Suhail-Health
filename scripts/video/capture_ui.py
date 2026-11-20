"""Record actual Suhail pages, without clinical commands or model requests.

Examples:
  .venv/bin/python scripts/video/capture_ui.py --scenes 01 02
  .venv/bin/python scripts/video/capture_ui.py --resume
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
STORYBOARD = ROOT / "runtime/video/storyboard.json"
OUTPUT = ROOT / "runtime/video/captures"
STACKS = {"isolated": ("http://127.0.0.1:13000", "http://127.0.0.1:18001"),
          "native": ("http://127.0.0.1:3000", "http://127.0.0.1:18000")}
CONFIG = {
    "public": ("isolated", None, "/"), "signin": ("isolated", None, "/"),
    "worklist": ("isolated", "navigator", "/worklist"),
    "intake": ("isolated", "navigator", "/worklist"),
    "journey": ("isolated", "navigator", "/cases/SC-001"),
    "evidence": ("isolated", "clinician", "/cases/SC-001"),
    "coordination": ("isolated", "navigator", "/cases/SC-002"),
    "receiving": ("isolated", "receiver_a", "/receiving"),
    "appointments": ("isolated", "receiver_b", "/receiving"),
    "consultations": ("native", "clinician", "/clinical"),
    "safety": ("native", "clinician", "/cases/SC-003"),
    "closure": ("native", "clinician", "/cases/SC-007"),
    "patient_active": ("isolated", "patient", "/patient"),
    "patient_mobile": ("isolated", "patient", "/patient"),
    "patient_complete": ("native", "patient", "/patient"),
    "assistant": ("native", "clinician", "/cases/SC-007"),
    "operations": ("native", "admin", "/operations"),
    "evaluation": ("native", "admin", "/evaluation"),
    "closing": ("isolated", None, "/"),
}


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


def media_duration(path):
    if not shutil.which("ffprobe"):
        return None
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path)], capture_output=True, text=True)
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (ValueError, KeyError, TypeError):
        return None


class Tour:
    def __init__(self, page, context, record, base, api):
        self.page, self.context, self.record = page, context, record
        self.base, self.api = base, api
        self.started = time.monotonic()

    def log(self, action, **detail):
        self.record["actions"].append({"seconds": round(time.monotonic()-self.started, 3),
            "action": action, **detail})

    def pause(self, seconds=1.5):
        self.page.wait_for_timeout(int(seconds*1000))

    def goto(self, path):
        self.log("navigate", path=path)
        self.page.goto(self.base+path, wait_until="networkidle", timeout=20000)
        self.page.locator("h1").first.wait_for(state="visible", timeout=15000)
        self.page.wait_for_function("!document.body.innerText.includes('Opening your secure workspace…')", timeout=15000)
        self.pause(.7)

    def top(self):
        self.scroll_y(0, 1.5)

    def scroll_y(self, target, seconds=2.2):
        start = self.page.evaluate("window.scrollY")
        target = max(0, float(target))
        steps = max(6, int(seconds*10))
        self.log("slow_scroll", start=start, target=target, duration=seconds)
        for i in range(1, steps+1):
            f=i/steps; ease=f*f*(3-2*f)
            self.page.evaluate("y=>window.scrollTo({top:y,behavior:'instant'})", start+(target-start)*ease)
            self.pause(seconds/steps)

    def scroll_to(self, locator, seconds=2.1):
        locator.first.wait_for(state="attached", timeout=8000)
        target=locator.first.evaluate("e=>e.getBoundingClientRect().top+window.scrollY-130")
        self.scroll_y(target, seconds)
        self.pause(.7)

    def text(self, label):
        return self.page.get_by_text(label, exact=True).first

    def heading(self, label):
        return self.page.get_by_role("heading", name=label, exact=True).first

    def button(self, label):
        return self.page.get_by_role("button", name=label, exact=True).first

    def open(self, title, container=None):
        scope=container if container is not None else self.page
        summary=scope.locator("summary").filter(has_text=title).first
        if not summary.count():
            self.log("conditional_control_absent", label=title)
            return False
        self.scroll_to(summary, 1.1)
        if summary.locator("..").get_attribute("open") is None:
            self.log("open_disclosure", label=title)
            summary.click()
        self.pause(1.2)
        return True

    def tab(self, label):
        self.log("select_tab", label=label)
        self.page.get_by_role("tab", name=re.compile("^"+re.escape(label))).click()
        self.pause(1.1)

    def source_case(self):
        response=self.context.request.get(self.api+"/cases/SC-001")
        assert response.ok, f"Case read failed: {response.status}"
        return response.json()

    def english(self):
        view=self.page.locator(".patient-view")
        if view.get_attribute("lang")=="ar":
            self.log("safe_language_preference", language="en")
            self.button("English").click()
            self.page.wait_for_function("document.querySelector('.patient-view')?.lang==='en'")
            self.pause(1)


def perform(t: Tour, scene):
    p=t.page
    if scene in {"public", "closing"}:
        t.pause(4)
        p.get_by_role("link", name="Open your workspace", exact=False).hover()
        t.pause(2)
        t.scroll_to(p.locator(".benefit-strip"), 3)
        t.pause(4)
        t.top();t.pause(4)
    elif scene == "signin":
        t.pause(2);t.scroll_to(p.locator("#signin"), 3);t.pause(3)
        p.get_by_label("Email address", exact=True).hover();t.pause(1)
        p.get_by_label("Demonstration role", exact=True).select_option("navigator")
        t.log("demo_authentication", role="navigator")
        t.button("Enter synthetic demo").click()
        p.wait_for_url("**/worklist");p.get_by_role("heading", name="Every case, a clear next step.").wait_for()
        t.pause(3);p.get_by_role("navigation", name="Main navigation").hover();t.pause(2)
        p.get_by_label("Synthetic demo role", exact=True).hover();t.pause(2)
    elif scene == "worklist":
        t.pause(3);t.scroll_to(p.locator(".case-table"), 2);t.pause(3)
        p.locator('.patient-link[href="/cases/SC-003"]').hover();t.pause(2)
        t.button("Urgent review").click();t.log("filter", label="Urgent review");t.pause(3)
        t.button("All cases").click();t.top();t.pause(3)
    elif scene == "intake":
        t.scroll_to(p.locator(".filter-tabs"), 1)
        for label in ["Quarantined", "Rejected transfer", "All cases"]:
            t.button(label).click();t.log("filter", label=label);t.pause(1.5)
        p.get_by_role("searchbox").fill("Omar");t.log("search", value="Omar");t.pause(2)
        p.get_by_role("searchbox").fill("")
        t.open("Import a synthetic source file");t.scroll_to(p.get_by_label("File format", exact=True), 2)
        p.get_by_label("File format", exact=True).select_option("csv");t.pause(2)
        p.get_by_label("File format", exact=True).select_option("json");t.pause(2)
    elif scene == "journey":
        t.pause(4);t.scroll_to(t.heading("A connected care journey"), 2);t.pause(3)
        t.scroll_y(p.evaluate("window.scrollY")+330, 3);t.pause(3);t.top();t.pause(2)
        for label in ["Journey & evidence","Consultations","Coordination","Activity & provenance"]:
            p.get_by_role("tab",name=re.compile("^"+re.escape(label))).hover();t.pause(.8)
    elif scene == "evidence":
        case=t.source_case()
        matching=[e for e in case.get("evidence",[]) if e.get("patient_id")==case["patient_id"] and e.get("order_id")==case["order_id"] and e.get("status")=="current"]
        matching.sort(key=lambda e:e.get("verification")!="pending")
        if not matching:raise RuntimeError("No current retained evidence is available for actual source-review footage")
        item=matching[0];card=p.locator(".evidence-card").filter(has_text=item["reference"]).first
        t.log("source_review_selection", evidence_id=item["id"], reference=item["reference"], verification=item.get("verification"))
        t.scroll_to(card,2);t.pause(2);t.open("Read retained source",card)
        card.locator(".source-document").wait_for(state="visible",timeout=10000)
        t.scroll_to(card.locator(".source-document"),2);t.pause(4)
        t.scroll_to(card.get_by_role("heading",name="Source provenance",exact=True),2);t.pause(3)
        t.scroll_to(card.get_by_role("heading",name="Matching checks",exact=True),2);t.pause(2)
        t.open("Verify or reject evidence",card);t.pause(3)
    elif scene == "coordination":
        t.tab("Coordination");t.pause(2);t.open("Propose a referral");t.pause(2)
        p.get_by_label("Handoff scope",exact=True).select_option("episode");t.log("local_form_selection", field="Handoff scope",value="episode");t.pause(2)
        t.scroll_to(t.heading("Appointments & attendance"),2);t.pause(2)
        t.scroll_to(t.heading("Assigned follow-up"),2);t.pause(2)
        t.open("Record coordination work");t.pause(3)
    elif scene == "receiving":
        t.pause(3);cards=p.locator(".referral-grid>section.panel");cards.first.wait_for()
        t.scroll_to(cards.first,2);t.pause(4)
        pending=p.get_by_role("button",name="Accept referral",exact=True)
        if pending.count():
            pending.first.hover();t.pause(2);t.open("Reject or request more information")
        else:t.log("conditional_control_absent", label="Accept/reject", reason="Current authorized packets already have decisions")
        t.scroll_y(p.evaluate("window.scrollY")+430,3);t.pause(4)
    elif scene == "appointments":
        cards=p.locator(".referral-grid>section.panel")
        target=cards.filter(has_text="SC-002").first
        if not target.count():target=cards.first
        t.scroll_to(target,2);t.pause(2);t.open("Report no available slots",target);t.pause(2)
        t.open("Confirm an appointment",target);t.pause(2)
        events=target.get_by_label("Attendance / booking event",exact=True)
        if events.count():
            t.scroll_to(events.first,2)
            for value in ["cancelled","no_show","booked","attended"]:
                events.first.select_option(value);t.log("local_form_selection",field="Attendance / booking event",value=value);t.pause(1)
        t.open("Return source evidence",target);t.pause(3)
    elif scene == "consultations":
        t.pause(2);buttons=p.locator(".clinical-case-list>button")
        patient_case=buttons.filter(has_text="SC-001").first
        if patient_case.count():patient_case.click();t.pause(2)
        t.scroll_to(t.heading("Questions & specialist replies"),2);t.pause(4)
        t.scroll_to(t.heading("Request a specialist opinion"),2);t.pause(2)
        t.top()
        role_switch=p.get_by_label("Synthetic demo role",exact=True)
        role_switch.select_option("specialist")
        p.wait_for_function("document.querySelector('.role-switch select')?.value==='specialist'")
        t.log("demo_role_switch",role="specialist",note="One page/context only; fresh reload obtains specialist-scoped cases")
        t.record["roles_seen"]=["clinician","specialist"]
        p.reload(wait_until="networkidle");t.pause(1.5)
        specialist_cases=p.locator(".clinical-case-list>button")
        other=specialist_cases.filter(has_text="BRW-specialist-8a60d46").first
        if not other.count():other=specialist_cases.filter(has_text="BRW-specialist").first
        if not other.count():other=specialist_cases.first
        other.wait_for(state="visible");other.click();t.pause(1.5)
        t.scroll_to(t.heading("Questions & specialist replies"),2);t.pause(5)
    elif scene == "safety":
        t.pause(3);t.scroll_to(t.heading("Urgent review"),2);t.pause(3)
        t.goto("/cases/SC-004");t.pause(2);t.scroll_to(t.heading("Authorized reconciliation"),2);t.pause(3)
        t.goto("/cases/SC-008");t.scroll_to(t.heading("Source evidence"),2);t.pause(4)
    elif scene == "closure":
        t.pause(2);t.scroll_to(t.heading("Closure evidence check"),2);t.pause(4)
        t.open("Record authorized disposition");t.pause(2)
        t.tab("Coordination");t.scroll_to(t.heading("Assigned follow-up"),2);t.pause(3)
        t.tab("Activity & provenance");t.scroll_to(t.heading("Audit & ownership history"),2);t.pause(3)
    elif scene == "patient_active":
        t.english();t.pause(3)
        t.scroll_to(t.heading("Have you received your care-team update?"),2);t.pause(2)
        t.button("I have received this update").hover();t.pause(1)
        p.get_by_label("My understanding",exact=True).select_option("needs_help");t.log("local_form_selection",field="My understanding",value="needs_help");t.pause(2)
        t.scroll_to(t.heading("Questions for your clinician"),2);t.pause(2)
        t.scroll_to(t.heading("What would make the next step easier?"),3);t.pause(3)
    elif scene == "patient_mobile":
        view=p.locator(".patient-view");t.pause(3)
        if view.get_attribute("lang")=="en":
            t.log("safe_language_preference",language="ar");t.button("العربية").click()
            p.wait_for_function("document.querySelector('.patient-view')?.dir==='rtl'");t.pause(3)
        t.scroll_y(900,4);t.pause(2);t.scroll_y(2000,4);t.pause(2)
        preferences=p.get_by_role("heading",name="تفضيلات التواصل",exact=True)
        if preferences.count():t.scroll_to(preferences,3);t.pause(2)
        feedback=p.get_by_role("heading",name="كيف تبدو لك الخطوة التالية؟",exact=True)
        if feedback.count():t.scroll_to(feedback,3);t.pause(2)
    elif scene == "patient_complete":
        t.pause(3);t.scroll_to(t.heading("Your care-team communication record"),2)
        t.open("View earlier result message");t.pause(2)
        p.locator("summary").filter(has_text="View earlier result message").click();t.pause(1)
        t.scroll_to(t.heading("Recorded understanding"),2);t.pause(2)
        t.scroll_to(t.heading("Your documented care plan"),3);t.pause(5)
    elif scene == "assistant":
        t.open("Prepare an AI-assisted draft");field=p.get_by_label("What would help?",exact=True)
        t.scroll_to(field,2);t.pause(2)
        for value in ["intake","pathway_router","safety_escalation","patient_navigator","coordination","closure_evidence"]:
            field.select_option(value);t.log("local_form_selection",field="What would help?",value=value);t.pause(1.6)
        t.button("Prepare source-linked draft").hover();t.log("no_model_request",note="Draft submission deliberately not activated");t.pause(4)
    elif scene == "operations":
        t.pause(3);t.scroll_to(t.heading("Delivery & integration outbox"),2);t.pause(3)
        t.scroll_to(t.heading("Connector capabilities"),3);t.pause(3)
        t.scroll_to(t.heading("Measured coordination outcomes"),2);t.pause(2)
        t.scroll_to(t.heading("Synthetic demonstration controls"),3);t.open("Reset identified synthetic dataset");t.pause(3)
    elif scene == "evaluation":
        t.pause(3)
        run=p.locator("section.panel").filter(has=p.get_by_role("heading",name="groq-smoke-holdout-v1",exact=True)).first
        if run.count():t.scroll_to(run,3);t.pause(5);run.get_by_role("link",name="summary.html",exact=False).hover();t.pause(2)
        software=p.locator("section.panel").filter(has=p.get_by_role("heading",name="software-delivery-final",exact=True)).first
        if software.count():t.scroll_to(software,3);t.pause(4)
        t.top();t.pause(2)
    else:raise ValueError("Unknown storyboard scene "+scene)


def capture(browser, chapter, manifest, target_seconds):
    scene_id,scene=chapter["id"],chapter["scene"]
    stack,role,path=CONFIG[scene];base,api=STACKS[stack]
    viewport={"width":390,"height":844} if scene=="patient_mobile" else {"width":1600,"height":760}
    folder=OUTPUT/scene_id;folder.mkdir(parents=True,exist_ok=True)
    record={"id":scene_id,"title":chapter["title"],"scene":scene,"stack":stack,"role":role or "public",
        "base_url":base,"api_url":api,"viewport":viewport,"status":"recording","actions":[],"errors":[],
        "started_at":datetime.now(timezone.utc).isoformat(),"trim_start_seconds":0}
    context=browser.new_context(viewport=viewport,record_video_dir=str(folder),record_video_size=viewport,
        reduced_motion="reduce",is_mobile=scene=="patient_mobile",has_touch=scene=="patient_mobile")
    def route_guard(route):
        req=route.request;url=urlsplit(req.url)
        if req.method not in {"GET","HEAD","OPTIONS"}:
            allowed=url.path=="/api/auth/demo" or (stack=="isolated" and scene in {"patient_active","patient_mobile"} and url.path=="/api/cases/SC-001/preferences")
            if not allowed:
                record["errors"].append({"type":"blocked_non_readonly_request","method":req.method,"path":url.path})
                route.abort();return
        route.continue_()
    context.route("**/api/**",route_guard)
    if role:
        response=context.request.post(api+"/auth/demo",data={"role":role})
        if not response.ok:
            context.close();raise RuntimeError(f"Demo authentication failed {role}/{stack}: {response.status}")
    page=context.new_page();page.set_default_timeout(8000)
    page.on("pageerror",lambda e:record["errors"].append({"type":"pageerror","message":str(e)}))
    began=time.monotonic();tour=Tour(page,context,record,base,api)
    try:
        tour.goto(path)
        record["trim_start_seconds"]=round(time.monotonic()-began,3)
        perform(tour,scene)
        remaining=target_seconds-(time.monotonic()-began)
        if remaining>0:tour.pause(remaining)
        screenshot=folder/(scene_id+"-"+scene+".png")
        page.screenshot(path=str(screenshot),full_page=False)
        record.update(status="completed" if not record["errors"] else "completed_with_errors",screenshot_path=str(screenshot.relative_to(ROOT)),final_url=page.url)
    except Exception as exc:
        record["status"]="failed";record["errors"].append({"type":type(exc).__name__,"message":str(exc)[:2000]})
        screenshot=folder/(scene_id+"-error.png")
        try:page.screenshot(path=str(screenshot));record["screenshot_path"]=str(screenshot.relative_to(ROOT))
        except Exception:pass
    finally:
        video=page.video;context.close()
        video_path=Path(video.path());actual=media_duration(video_path)
        record.update(video_path=str(video_path.relative_to(ROOT)),duration_seconds=actual if actual is not None else round(time.monotonic()-began,3),
            duration_method="ffprobe" if actual is not None else "wall_clock",finished_at=datetime.now(timezone.utc).isoformat())
        prior=[s for s in manifest["scenes"] if s["id"]!=scene_id]
        manifest["scenes"]=sorted(prior+[record],key=lambda s:s["id"])
        atomic_json(OUTPUT/"manifest.json",manifest)
        print(json.dumps({"id":scene_id,"status":record["status"],"video_path":record["video_path"],"screenshot_path":record.get("screenshot_path"),"duration_seconds":record["duration_seconds"],"errors":record["errors"]}),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--scenes",nargs="*");parser.add_argument("--resume",action="store_true");parser.add_argument("--seconds",type=float,default=28)
    args=parser.parse_args();OUTPUT.mkdir(parents=True,exist_ok=True)
    chapters=json.loads(STORYBOARD.read_text())
    selected=set(args.scenes) if args.scenes else None
    manifest=json.loads((OUTPUT/"manifest.json").read_text()) if (OUTPUT/"manifest.json").exists() else {"generated_at":datetime.now(timezone.utc).isoformat(),"storyboard_path":str(STORYBOARD.relative_to(ROOT)),"scenes":[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        for chapter in chapters:
            if selected and chapter["id"] not in selected:continue
            existing=next((s for s in manifest["scenes"] if s["id"]==chapter["id"]),None)
            if args.resume and existing and existing["status"]=="completed" and (ROOT/existing["video_path"]).exists():continue
            capture(browser,chapter,manifest,args.seconds)
        browser.close()


if __name__=="__main__":main()
