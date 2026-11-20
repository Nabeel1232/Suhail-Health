"""Render deterministic, authored Suhail vector motion scenes without network calls.

The resulting silent H.264 clips are illustrations, not application recordings.
Example: TMPDIR="$PWD/.runtime/tmp" .venv/bin/python scripts/video/motion_scenes.py \
    --scene agents --duration 35 --output runtime/video-v3/motion/02-agents.mp4 \
    --evidence reports/ui-redesign/benchmark-evidence.json
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).with_name("motion_assets")
FUNCTIONS = [
    ("intake", "Intake", "Reconcile source facts", "file"),
    ("pathway_router", "Router", "Propose the pathway", "route"),
    ("safety_escalation", "Safety", "Flag for human review", "shield"),
    ("patient_navigator", "Navigator", "Explain the next step", "message"),
    ("coordination", "Coordination", "Prepare owned actions", "network"),
    ("closure_evidence", "Closure", "Check evidence gaps", "check"),
]
ALIASES = {"router": "pathway_router", "safety": "safety_escalation",
           "navigator": "patient_navigator", "closure": "closure_evidence"}


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_url(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def evidence_metrics(path: Path | None) -> dict:
    """Accept explicit counts or derive counts from actual, disjoint saved cases."""
    metrics = {key: {"primary": {"passed": 0, "evaluated": 0},
                     "audit": {"passed": 0, "evaluated": 0}} for key, *_ in FUNCTIONS}
    if path is None:
        return {"available": False, "functions": metrics, "source": None,
                "label": "Awaiting evaluation records"}
    raw = json.loads(path.read_text())
    original_errors = raw.get("original_primary_scoring_errors")
    error_source = None
    if original_errors is not None and (type(original_errors) is not int or original_errors < 0):
        raise ValueError("Original primary scoring-error count must be a nonnegative integer")
    explicit = raw.get("functions")
    if explicit is not None:
        items = explicit if isinstance(explicit, list) else [{"id": key, **value} for key, value in explicit.items()]
        seen = set()
        for item in items:
            key = ALIASES.get(item["id"], item["id"])
            if key not in metrics or key in seen:
                raise ValueError("Evidence must contain unique supported function IDs")
            seen.add(key)
            for layer in ("primary", "audit"):
                metric = item.get(layer, {"passed": 0, "evaluated": 0})
                passed, evaluated = metric["passed"], metric["evaluated"]
                if type(passed) is not int or type(evaluated) is not int or not 0 <= passed <= evaluated:
                    raise ValueError("Evidence counts must be nonnegative integers with passed <= evaluated")
                metrics[key][layer] = {"passed": passed, "evaluated": evaluated}
        if len(seen) != len(FUNCTIONS):
            raise ValueError("Explicit evidence must identify all six functions")
    else:
        cases = raw["standalone_function_conformance"]["cases"]
        seen = set()
        for case in cases:
            ident = case["case_id"]
            if ident in seen or type(case.get("passed")) is not bool:
                raise ValueError("Saved evidence cases must be unique and have a scored boolean result")
            seen.add(ident)
            key = case.get("component") or next((key for key in metrics if ident.startswith(key + "-")), None)
            if key not in metrics:
                raise ValueError("Cannot attribute a saved case to a bounded function")
            layer = {"primary": "primary", "secondary_saved_response_audit": "audit"}.get(case["layer"])
            if layer is None:
                raise ValueError("Unrecognized scoring layer; primary and audit must remain separate")
            metrics[key][layer]["evaluated"] += 1
            metrics[key][layer]["passed"] += int(case["passed"])
        selected = raw["standalone_function_conformance"]
        derived_passed = sum(m[layer]["passed"] for m in metrics.values() for layer in ("primary", "audit"))
        derived_evaluated = sum(m[layer]["evaluated"] for m in metrics.values() for layer in ("primary", "audit"))
        if derived_passed != selected["passed"] or derived_evaluated != selected["evaluated"]:
            raise ValueError("Case-derived counts disagree with the supplied evidence summary")
        # Preserve the original failed scoring layer while showing a later audit.
        # Link audit IDs back to hashed original execution records; never infer
        # an error count solely from a hand-entered display label.
        sources = [source for source in raw.get("sources", []) if source["path"].endswith("/cases.jsonl")]
        if sources:
            source = sources[0]
            source_path = (ROOT / source["path"]).resolve()
            if not source_path.is_relative_to(ROOT / "reports") or sha(source_path) != source["sha256"]:
                raise ValueError("Original execution-record source hash or scope mismatch")
            original = [json.loads(line) for line in source_path.read_text().splitlines() if line.strip()]
            audit_ids = {case["case_id"] for case in cases if case["layer"] == "secondary_saved_response_audit"}
            original_failed_ids = {case["case_id"] for case in original if case["case_id"] in audit_ids
                                   and case.get("error") and not case.get("evaluated")}
            if original_failed_ids != audit_ids:
                raise ValueError("Post-hoc audit IDs do not match retained original failed scoring records")
            original_errors = len(original_failed_ids)
            error_source = {"path": relative(source_path), "sha256": sha(source_path)}
    totals = {layer: {name: sum(m[layer][name] for m in metrics.values()) for name in ("passed", "evaluated")}
              for layer in ("primary", "audit")}
    return {"available": True, "functions": metrics, "totals": totals,
            "source": relative(path.resolve()), "sha256": sha(path),
            "original_primary_scoring_errors": original_errors, "original_error_source": error_source,
            "label": "Known synthetic conformance",
            "limits": "Small known-family synthetic function set. Primary scoring and a separate post-hoc saved-response audit. Not clinical accuracy or patient-outcome evidence."}


def software_metrics(path: Path | None) -> dict:
    """Validate the closing's software counts against their saved source report."""
    if path is None:
        return {"available": False}
    raw = json.loads(path.read_text())
    measurement = raw.get("deterministic_software_checks")
    if not measurement:
        return {"available": False}
    passed, selected, calls = (measurement[name] for name in ("passed", "selected", "model_calls"))
    if any(type(value) is not int for value in (passed, selected, calls)) or not 0 <= passed <= selected or selected <= 0 or calls < 0:
        raise ValueError("Software measurements must be actual nonnegative integer counts")
    functions = raw["bounded_agent_functions"]
    if len(functions) != len(set(functions)) or set(functions) != {item[0] for item in FUNCTIONS}:
        raise ValueError("The closing function count must match the named application functions")
    source = next((item for item in raw.get("sources", [])
                   if item["path"] == "reports/runs/software-delivery-final/summary.json"), None)
    if source is None:
        raise ValueError("A linked executed software report is required for the closing")
    source_path = (ROOT / source["path"]).resolve()
    if not source_path.is_relative_to(ROOT / "reports") or sha(source_path) != source["sha256"]:
        raise ValueError("The linked software report hash does not match")
    report = json.loads(source_path.read_text())
    if (report["counts"]["selected"], report["counts"]["task_passed"], report["usage"]["api_calls"]) != (selected, passed, calls):
        raise ValueError("Displayed software counts disagree with the actual execution report")
    return {"available": True, "passed": passed, "selected": selected, "model_calls": calls,
            "function_count": len(functions), "functions": functions,
            "source": source["path"], "source_sha256": source["sha256"],
            "evidence": relative(path), "evidence_sha256": sha(path),
            "label": "Deterministic software checks; not a model-accuracy measurement"}


def render(scene: str, duration: float, output: Path, evidence: Path | None,
           metrics_mode: str = "evidence", asset: Path | None = None,
           timing_config: Path | None = None) -> dict:
    os.environ.setdefault("TMPDIR", str(ROOT / ".runtime/tmp"))
    Path(os.environ["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    fonts = {"Manrope": ROOT / "apps/web/public/fonts/Manrope.ttf",
             "DM Sans": ROOT / "apps/web/public/fonts/DM-Sans.ttf"}
    logo = ROOT / "apps/web/public/brand/logo-light.png"
    metrics = evidence_metrics(evidence)
    software = software_metrics(evidence) if scene == "closing" else {"available": False}
    if scene == "closing" and not software["available"]:
        raise ValueError("The closing requires validated software-check evidence")
    config = {"scene": scene, "duration": duration, "width": 1920, "height": 1080,
              "metricsMode": metrics_mode,
              "software": software,
              "functions": [{"id": key, "name": name, "purpose": purpose, "icon": icon,
                             **metrics["functions"][key]} for key, name, purpose, icon in FUNCTIONS],
              "evidence": metrics, "logo": data_url(logo, "image/png"),
              "fonts": {name: data_url(path, "font/ttf") for name, path in fonts.items()}}
    active_asset = asset.resolve() if asset else ASSETS/'scene.js'
    if timing_config:
        additions = json.loads(timing_config.read_text())
        if set(additions)-{'phase_anchors','focus_cues','show_workspace_assistant','deployment_labels'}:
            raise ValueError('Unsupported narration-driven animation configuration')
        config.update(additions)
    # Durations such as33.84 are exact frame boundaries, even when their binary
    # representation multiplies to846.0000000000001.
    frames = math.ceil(duration * 25 - 1e-9)
    log_path = output.with_suffix(".render.log")
    command = [shutil.which("ffmpeg") or "ffmpeg", "-hide_banner", "-y", "-f", "image2pipe",
               "-vcodec", "mjpeg", "-framerate", "25", "-i", "pipe:0", "-an", "-c:v", "libx264",
               "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-threads", "4",
               "-movflags", "+faststart", str(output)]
    html = "<!doctype html><html><meta charset='utf-8'><style>html,body{margin:0;overflow:hidden;background:#f5f6f3}canvas{display:block}</style><canvas width='1920' height='1080'></canvas></html>"
    with log_path.open("w") as log, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.set_content(html)
        if scene == "closing":
            page.add_script_tag(content=(ASSETS / "closing.js").read_text())
        page.add_script_tag(content=active_asset.read_text())
        page.evaluate("config => window.initialize(config)", config)
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
        try:
            for frame in range(frames):
                image = page.evaluate("t => window.motionFrame(t, 'image/jpeg')", frame / 25)
                encoder.stdin.write(base64.b64decode(image.split(",", 1)[1]))
                if frame % 250 == 0:
                    print(json.dumps({"scene": scene, "frame": frame, "total_frames": frames}), flush=True)
            encoder.stdin.close()
            if encoder.wait() != 0:
                raise RuntimeError("FFmpeg motion encoding failed; inspect the local render log")
            # A mid-scene poster provides a fast visual review without video tools.
            poster = output.with_suffix(".png")
            image = page.evaluate("t => window.motionFrame(t, 'image/png')", duration * (.75 if scene == "solution" else .65 if scene == "models" else .76 if scene == "closing" else .55))
            poster.write_bytes(base64.b64decode(image.split(",", 1)[1]))
        except BaseException:
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait()
            raise
        finally:
            browser.close()
    info = json.loads(subprocess.check_output([shutil.which("ffprobe") or "ffprobe", "-v", "error",
        "-show_format", "-show_streams", "-of", "json", str(output)], text=True))
    video = next(stream for stream in info["streams"] if stream["codec_type"] == "video")
    if video["codec_name"] != "h264" or video["width"] != 1920 or video["height"] != 1080:
        raise ValueError("Motion output has an unexpected video format")
    result = {"status": "completed", "errors": [], "media_type": "authored_motion_graphics",
              "application_recording": False, "scene": scene, "role": "illustration",
              "presentation_mode": metrics_mode,
              "benchmark_metrics_displayed": scene == "agents" and metrics_mode == "evidence",
              "software_metrics_displayed": scene == "closing",
              "current_model_label": "GPT-OSS 120B via Groq" if metrics_mode == "capabilities" or scene == "models" else None,
              "future_model_claim": "Future model integration and evaluation; no other frontier provider or accuracy improvement is claimed." if scene == "models" else None,
              "base_url": "authored://suhail/" + scene, "video_path": relative(output),
              "poster_path": relative(poster), "generated_at": datetime.now(timezone.utc).isoformat(),
              "duration_seconds": float(info["format"]["duration"]), "requested_duration_seconds": duration,
              "width": 1920, "height": 1080, "fps": 25, "frames": frames, "silent": True,
              "bytes": output.stat().st_size, "video_sha256": sha(output),
              "evidence": metrics, "software_check_measurement": software, "network_requests": 0, "model_calls": 0,
              "assets": {relative(path): sha(path) for path in [logo, *fonts.values(), active_asset, Path(__file__), *([ASSETS / "closing.js"] if scene == "closing" else []), *([timing_config] if timing_config else [])]},
              "safe_area": {"content_top": 90, "content_bottom": 930,
                            "reserved_top_pixels": 60, "reserved_bottom_pixels": 108}}
    output.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
    notes = {"format": "Deterministic Canvas vector shapes and local font/logo assets, sampled at 25fps.",
             "provenance": "Authored solution illustration, explicitly distinct from actual UI footage.",
             "canvas": [1920, 1080], "palette": {"teal": "#086c68", "ink": "#112e35", "cream": "#f5f6f3", "gold": "#c2a36d"},
             "logo": "Original supplied logo pixels preserved; no recoloring or redrawing.",
             "fonts": [relative(path) for path in fonts.values()],
             "safe_content_y": [90, 930], "narration_and_captions": "Added by the parent renderer; motion MP4s are silent.",
             "solution_beats": ["Brand and screening-to-care purpose", "Broken handoffs without invented prevalence", "Shared ownership and independent evidence", "Patient, care team, receiving service", "Human-authorized next step"],
             "agent_beats": ["Six cards pop in", "All six remain visible", "Focus cycles through each capability", "Capabilities mode describes the current configured model and modular intelligence layer; evidence mode preserves separate primary/audit denominators."],
             "model_beats": ["Six bounded functions feed a distinct model adapter", "Current GPT-OSS120B inference via Groq is identified", "Future model integration and evaluation is visibly separate from the current configuration", "Care ownership and clinical gates remain governed"],
             "closing_beats": ["Actual deterministic software-check counts and their zero-model-call measurement", "Reviewable provenance and execution records", "Original logo, six focused functions and human clinical oversight"],
             "metrics": "Read and validated from --evidence; never displayed in capabilities mode. Evidence mode has no hardcoded scores and missing records display Not evaluated.",
             "last_render": result}
    notes_path = output.parent / "motion-design.json"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(json.dumps(notes, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", choices=["solution", "agents", "models", "closing"], required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", "--evidence-json", "--evidenceJSON", dest="evidence", type=Path)
    parser.add_argument("--metrics-mode", choices=["capabilities", "evidence"], default="evidence",
                        help="Use capabilities for the product pitch; evidence preserves the separately qualified benchmark view.")
    parser.add_argument("--asset", type=Path, help="Versioned authored JavaScript asset")
    parser.add_argument("--timing-config", type=Path, help="Narration-driven phase/focus configuration")
    args = parser.parse_args()
    if not math.isfinite(args.duration) or not 1 <= args.duration <= 120:
        parser.error("--duration must be between 1 and 120 seconds")
    result = render(args.scene, args.duration, args.output.resolve(), args.evidence.resolve() if args.evidence else None,
                    args.metrics_mode, args.asset, args.timing_config)
    print(json.dumps({key: result[key] for key in ["status", "scene", "video_path", "duration_seconds", "bytes"]}), flush=True)


if __name__ == "__main__":
    main()
