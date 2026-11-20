"""Prepare and optionally render two authored scenes for the under-three-minute cut.

No TTS, inference, application requests or v4 artifact mutations are performed.
The JSON spec supplies chapters01 and09 and exact saved-audio phrase cues.
Final-clock clips require preserve_source_timing in the parent video renderer.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

from motion_scenes import render
from sync_plan import aligned_phrase, build_chapter

ROOT = Path(__file__).resolve().parents[2]
FPS = 25
ANTICIPATION = .24


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_floor(value):
    return math.floor(value * FPS + 1e-8) / FPS


def frame_ceil(value):
    return math.ceil(value * FPS - 1e-8) / FPS


def relative(path):
    return str(path.relative_to(ROOT))


def phase_points(intervals, duration):
    """Merge overlapping holds only when they show the same visual stage."""
    merged = []
    for start, end, phase in intervals:
        if merged and start <= merged[-1][1]:
            previous = merged[-1]
            if phase != previous[2]:
                raise ValueError("Different authored stages overlap a spoken hold. Shorten the prior until_phrase or revise the cue spec.")
            merged[-1] = (previous[0], max(previous[1], end), phase)
        else:
            merged.append((start, end, phase))
    points = []
    for start, end, phase in merged:
        for at in (start, end):
            if points and at <= points[-1]["time_seconds"]:
                raise ValueError("Authored phase times must be strictly increasing")
            if points and phase < points[-1]["phase"]:
                raise ValueError("Authored visual stages must progress forwards")
            points.append({"time_seconds": at, "phase": phase})
    if points[-1]["time_seconds"] < duration:
        points.append({"time_seconds": duration, "phase": points[-1]["phase"]})
    return points


def prepare(ident, chapter, audio, spec, work, speed, lead, tail):
    assert audio["status"] == "generated", f"Narration not complete:{ident}"
    assert audio["model"] == "eleven_v4" and audio["voice"] == "Sarah"
    assert hashlib.sha256(chapter["text"].encode()).hexdigest() == audio["text_sha256"]
    assert sha(work / (ident + ".mp3")) == audio["audio_sha256"]
    alignment_path = work / (ident + "-alignment.json")
    alignment = json.loads(alignment_path.read_text())["alignment"]
    duration = frame_ceil(audio["duration_seconds"] / speed + lead + tail)
    cues, intervals, focus = [], [], []
    for raw in spec["cues"]:
        row = dict(raw)
        start = aligned_phrase(alignment, row["phrase"])
        end = aligned_phrase(alignment, row["until_phrase"])
        ready = 0. if row.get("initial_state") else frame_floor(start["start_seconds"] / speed + lead - ANTICIPATION)
        hold_end = frame_ceil(end["end_seconds"] / speed + lead + 1 / FPS)
        if ready < 0 or hold_end <= ready or hold_end > duration:
            raise ValueError(f"Invalid authored ready/hold interval:{ident}/{row['id']}")
        intervals.append((ready, hold_end, row["phase"]))
        row.update(source_seconds=ready, source_visible_until_seconds=hold_end,
                   source_description="Authored vector stage on the final narrated clock; decoded ready reference retained.",
                   highlight=False)
        if row.get("focus_agent"):
            focus.append({"id": row["focus_agent"], "start_seconds": ready, "end_seconds": hold_end})
        cues.append(row)
    if not cues or not cues[0].get("initial_state"):
        raise ValueError("Each authored chapter must declare an initially visible first cue")
    config = {"phase_anchors": phase_points(intervals, duration), "focus_cues": focus,
              "show_workspace_assistant": True}
    folder = work / "motion"
    folder.mkdir(parents=True, exist_ok=True)
    timing = folder / (ident + "-timing.json")
    timing.write_text(json.dumps(config, indent=2) + "\n")
    return {"id": ident, "scene": spec["scene"], "duration_seconds": duration,
            "audio_duration_seconds": audio["duration_seconds"], "alignment": alignment,
            "cues": cues, "timing_path": timing, "output": folder / (ident + "-" + spec["scene"] + ".mp4"),
            "audio_sha256": audio["audio_sha256"], "text_sha256": audio["text_sha256"],
            "alignment_sha256": sha(alignment_path), "speed": speed, "lead": lead, "tail": tail,
            "work": work}


def render_one(plan, asset, reuse):
    metadata_path = plan["output"].with_suffix(".json")
    metadata = None
    if reuse and metadata_path.is_file():
        candidate = json.loads(metadata_path.read_text())
        assert candidate.get("status") == "completed" and candidate.get("scene") == plan["scene"]
        assert abs(candidate["duration_seconds"] - plan["duration_seconds"]) < .002 and candidate["fps"] == FPS
        assert sha(plan["output"]) == candidate["video_sha256"]
        for name, digest in candidate["assets"].items():
            assert sha(ROOT / name) == digest, "Rendered asset changed:" + name
        assert candidate["assets"].get(relative(plan["timing_path"])) == sha(plan["timing_path"])
        metadata = candidate
    if metadata is None:
        metadata = render(plan["scene"], plan["duration_seconds"], plan["output"],
                          ROOT / "reports/ui-redesign/benchmark-evidence.json",
                          metrics_mode="capabilities", asset=asset, timing_config=plan["timing_path"])
    assert sha(plan["work"] / (plan["id"] + ".mp3")) == plan["audio_sha256"]
    metadata["narration_binding"] = {
        "audio_sha256": plan["audio_sha256"], "alignment_sha256": plan["alignment_sha256"],
        "text_sha256": plan["text_sha256"], "audio_speed": plan["speed"],
        "lead_seconds": plan["lead"], "tail_seconds": plan["tail"],
        "method": "Phrase timing regenerated from verified saved narration; rendered on the final chapter clock.",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    folder = plan["work"] / "motion" / ("ready-" + plan["id"])
    folder.mkdir(exist_ok=True)
    actions, cue_rows = [], []
    for row in plan["cues"]:
        ready = folder / (row["id"] + "-ready.png")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{row['source_seconds']:.6f}",
                        "-i", str(plan["output"]), "-frames:v", "1", "-threads", "1", str(ready)], check=True)
        actions.extend([
            {"action": "visual_ready", "cue_id": row["id"], "source_seconds": row["source_seconds"],
             "bbox": row["box"], "screenshot_path": relative(ready), "screenshot_sha256": sha(ready),
             "source_visible_until_seconds": row["source_visible_until_seconds"],
             "method": "decoded_frame_from_authored_clip"},
            {"action": "visual_end", "cue_id": row["id"], "source_seconds": row["source_visible_until_seconds"]},
        ])
        cue_rows.append({**row, "visual_event": {"action": "visual_ready", "cue_id": row["id"]},
                         "visual_end_event": {"action": "visual_end", "cue_id": row["id"]}})
    capture = {**metadata, "id": plan["id"], "title": plan["scene"],
               "viewport": {"width": 1920, "height": 1080}, "trim_start_seconds": 0, "actions": actions}
    sync = build_chapter(plan["id"], capture, plan["alignment"], cue_rows, plan["audio_duration_seconds"],
                         speed=plan["speed"], lead=plan["lead"], tail=plan["tail"],
                         anticipation=ANTICIPATION, fps=FPS, require_visible_holds=True)
    sync["preserve_source_timing"] = True
    for cue in sync["cues"]:
        cue["highlight"] = False
    assert all(abs(point["source_seconds"] - point["output_seconds"]) < 1e-6 for point in sync["control_points"])
    return capture, sync


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "runtime/video-3min")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--asset", type=Path, default=ROOT / "scripts/video/motion_assets/scene_submission.js")
    parser.add_argument("--audio-speed", type=float, required=True)
    parser.add_argument("--lead", type=float, default=.4)
    parser.add_argument("--tail", type=float, default=.4)
    parser.add_argument("--go", action="store_true")
    parser.add_argument("--jobs", type=int, choices=[1, 2], default=2)
    parser.add_argument("--reuse-rendered", action="store_true")
    args = parser.parse_args()
    if not .8 <= args.audio_speed <= 1.4 or not 0 <= args.lead <= 2 or not 0 <= args.tail <= 2:
        parser.error("Require bounded positive narration speed and padding")
    work = args.work_dir.resolve()
    if not work.is_relative_to(ROOT / "runtime/video-3min"):
        parser.error("Authored submission output must stay within runtime/video-3min")
    os.environ.setdefault("TMPDIR", str(ROOT / ".runtime/showcase-tmp"))
    story_path = work / "storyboard.json"
    story = json.loads(story_path.read_text())
    narration_path = work / "narration-manifest.json"
    narration = json.loads(narration_path.read_text())
    audio = {row["chapter"]: row for row in narration["chapters"]}
    assert len(story) == 9 and len(audio) == 9 and all(row["status"] == "generated" for row in audio.values())
    spec = json.loads(args.spec.read_text())
    specs = spec["chapters"]
    assert set(specs) == {"01", "09"}
    total = sum(frame_ceil(audio[c["id"]]["duration_seconds"] / args.audio_speed + args.lead + args.tail) for c in story)
    assert 1 <= total <= 179.8, (total, "Allow room below the user180-second file cap")
    plans = [prepare(c["id"], c, audio[c["id"]], specs[c["id"]], work,
                     args.audio_speed, args.lead, args.tail) for c in story if c["id"] in specs]
    summary = {
        "storyboard_sha256": sha(story_path), "narration_manifest_sha256": sha(narration_path),
        "authored_spec_sha256": sha(args.spec), "audio_speed": args.audio_speed,
        "lead_seconds": args.lead, "tail_seconds": args.tail, "fps": FPS,
        "planned_video_duration_seconds": total, "maximum_video_duration_seconds": 180,
        "chapters": [{"id": p["id"], "scene": p["scene"], "duration_seconds": p["duration_seconds"],
                      "timing_config": relative(p["timing_path"])} for p in plans],
    }
    (work / "authored-motion-plan.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)
    if not args.go:
        return
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        jobs = {pool.submit(render_one, p, args.asset.resolve(), args.reuse_rendered): p["id"] for p in plans}
        for job in as_completed(jobs):
            results.append(job.result())
            print(json.dumps({"completed": jobs[job]}), flush=True)
    result = {
        **summary, "status": "completed", "created_at": datetime.now(timezone.utc).isoformat(),
        "captures": sorted((r[0] for r in results), key=lambda r: r["id"]),
        "chapters": sorted((r[1] for r in results), key=lambda r: r["id"]),
        "preserve_source_timing": True,
        "all_semantic_anchors_pass": all(r[1]["all_semantic_anchors_pass"] for r in results),
        "provider_requests": 0, "application_state_changes": 0,
        "scope": "Two authored illustrations only; actual decoded ready PNGs retained. Final encoded frame and independent semantic checks remain required.",
    }
    path = work / "authored-sync-chapters.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": "completed", "path": relative(path)}), flush=True)


if __name__ == "__main__":
    main()
