"""Check saved narration hashes, alignments, decoding and audio levels locally.

No provider requests, credential reads or application changes are performed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[2]


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).split())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path):
    return json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format",
        "-show_streams", "-of", "json", str(path)], text=True))


def alignment_checks(alignment, text, seconds):
    characters = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])
    same_length = len(characters) == len(starts) == len(ends) > 0
    finite = same_length and all(type(a) in (int, float) and type(b) in (int, float) and
        math.isfinite(a) and math.isfinite(b) and 0 <= a <= b <= seconds + .1 for a, b in zip(starts, ends))
    monotonic = finite and all(starts[i] >= starts[i-1] and ends[i] >= ends[i-1] for i in range(1, len(starts)))
    reconstructed = "".join(characters)
    source_match = normalized(reconstructed) == normalized(text)
    return {"passed": bool(same_length and finite and monotonic and source_match),
        "characters": len(characters), "starts": len(starts), "ends": len(ends),
        "array_lengths_equal": same_length, "starts_and_ends_monotonic": bool(monotonic),
        "finite_nonnegative_ranges_within_audio": bool(finite),
        "last_end_seconds": ends[-1] if ends else None,
        "normalized_whitespace_source_text_match": source_match}


def audio_levels(path, seconds):
    result = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path),
        "-af", "astats=metadata=0:reset=0,silencedetect=noise=-40dB:d=0.35,volumedetect",
        "-f", "null", "-"], capture_output=True, text=True)
    log = result.stderr
    peaks = [float(value) for value in re.findall(r"Peak level dB:\s*(-?[\d.]+)", log)]
    max_volume = re.findall(r"max_volume:\s*(-?[\d.]+) dB", log)
    mean_volume = re.findall(r"mean_volume:\s*(-?[\d.]+) dB", log)
    rms = [float(value) for value in re.findall(r"RMS level dB:\s*(-?[\d.]+)", log)]
    peak = max(peaks) if peaks else float(max_volume[-1]) if max_volume else None
    intervals, current = [], None
    for match in re.finditer(r"silence_(start|end):\s*([\d.]+)", log):
        kind, value = match[1], min(seconds, float(match[2]))
        if kind == "start":
            current = value
        elif current is not None:
            intervals.append({"start_seconds": current, "end_seconds": value, "duration_seconds": max(0, value-current)})
            current = None
    if current is not None:
        intervals.append({"start_seconds": current, "end_seconds": seconds, "duration_seconds": max(0, seconds-current)})
    decode_clean = result.returncode == 0 and not re.search(r"error while|invalid data found|corrupt decoded|header missing", log, re.I)
    return {"ffmpeg_decode_exit_code": result.returncode, "decode_clean": bool(decode_clean),
        "audio_levels": {"peak_dbfs": peak, "rms_dbfs": max(rms) if rms else None,
            "mean_volume_db": float(mean_volume[-1]) if mean_volume else None,
            "max_volume_db": float(max_volume[-1]) if max_volume else None,
            "possible_full_scale_clipping": peak is None or peak >= -.05},
        "silence": {"threshold_db": -40, "minimum_interval_seconds": .35,
            "longest_seconds": max((i["duration_seconds"] for i in intervals), default=0),
            "total_seconds": sum(i["duration_seconds"] for i in intervals), "interval_count": len(intervals),
            "intervals": intervals}}


def narration_ready(work):
    try:
        scenes = json.loads((work/"storyboard.json").read_text())
        narration = json.loads((work/"narration-manifest.json").read_text())
        ids = [scene["id"] for scene in scenes]
        return bool(ids and ids == [chapter["chapter"] for chapter in narration["chapters"]] and
            all((work/(ident+suffix)).is_file() for ident in ids for suffix in [".mp3", "-text.txt", "-alignment.json"]))
    except (OSError, ValueError, KeyError):
        return False


def check(work, lead, tail, speed, target):
    started = datetime.now(timezone.utc).isoformat()
    scenes = json.loads((work/"storyboard.json").read_text())
    manifest = json.loads((work/"narration-manifest.json").read_text())
    records = {chapter["chapter"]: chapter for chapter in manifest["chapters"]}
    clips, total_seconds = [], 0.
    for scene in scenes:
        ident = scene["id"]
        audio, text_path, alignment_path = (work/(ident+suffix) for suffix in [".mp3", "-text.txt", "-alignment.json"])
        source_text = text_path.read_text()
        info, record = probe(audio), records[ident]
        seconds = float(info["format"]["duration"])
        stream = next(item for item in info["streams"] if item["codec_type"] == "audio")
        alignment = json.loads(alignment_path.read_text())
        alignments = {name: alignment_checks(alignment[name], source_text, seconds)
            for name in ("alignment", "normalized_alignment") if alignment.get(name)}
        levels = audio_levels(audio, seconds)
        checks = {"audio_sha256_matches_manifest": sha(audio) == record["audio_sha256"],
            "text_sha256_matches_manifest": sha(text_path) == record["text_sha256"],
            "manifest_characters_match": len(source_text) == record["characters"],
            "storyboard_text_exact": source_text == scene["text"],
            "manifest_duration_matches": abs(seconds-record["duration_seconds"]) <= .002,
            "positive_audio_duration": math.isfinite(seconds) and seconds > 0,
            "decode_succeeded": levels["decode_clean"],
            "all_alignments_pass": bool(alignments) and all(item["passed"] for item in alignments.values()),
            "no_full_scale_clipping": not levels["audio_levels"]["possible_full_scale_clipping"]}
        warnings = []
        if levels["silence"]["longest_seconds"] > 2:
            warnings.append("Silence interval exceeds two seconds; listen during editorial review.")
        item = {"chapter": ident, "passed": all(checks.values()), "audio_file": str(audio.relative_to(ROOT)),
            "duration_seconds": seconds, "codec": stream["codec_name"], "sample_rate": int(stream["sample_rate"]),
            "channels": stream["channels"], "checks": checks, "text_characters": len(source_text),
            "alignments": alignments, **levels, "warnings": warnings}
        clips.append(item)
        total_seconds += seconds
        print(json.dumps({"chapter": ident, "audio_qc": "passed" if item["passed"] else "review_required"}), flush=True)
    projected = total_seconds/speed+len(scenes)*(lead+tail)
    rounded = sum(math.ceil((clip["duration_seconds"]/speed+lead+tail)*25)/25 for clip in clips)
    characters = sum(clip["text_characters"] for clip in clips)
    result = {"mode": "local_ffprobe_ffmpeg_audio_alignment_and_level_qc_no_provider_requests",
        "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(clip["passed"] for clip in clips) else "review_required",
        "expected_chapters": len(scenes), "chapter_count": len(clips), "all_expected_audio_files_present": True,
        "selected_characters": characters, "selected_characters_match_manifest": characters == manifest["selected_text_characters"],
        "within_character_cap": characters <= manifest["maximum_text_characters"],
        "total_audio_seconds": total_seconds,
        "projected_duration": {"target_seconds": target, "chapter_count": len(scenes),
            "lead_seconds_per_chapter": lead, "tail_seconds_per_chapter": tail, "audio_speed": speed,
            "planned_padding_seconds": len(scenes)*(lead+tail), "projected_seconds": projected,
            "expected_fps_rounded_seconds": rounded, "within_target": target[0] <= rounded <= target[1],
            "status": "projection_only_final_movie_not_yet_verified"},
        "clips": clips, "provider_calls": 0, "credential_reads": 0, "application_state_changes": 0,
        "limits": ["Audio technical checks do not replace listening or clinical review.", "Silence warnings require editorial judgment; no perceptual quality score is invented."]}
    if not result["selected_characters_match_manifest"] or not result["within_character_cap"]:
        result["status"] = "review_required"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT/"runtime/video")
    parser.add_argument("--lead", type=float, default=.85)
    parser.add_argument("--tail", type=float, default=1.15)
    parser.add_argument("--audio-speed", type=float, default=1.)
    parser.add_argument("--min-duration", type=float, default=360.)
    parser.add_argument("--max-duration", type=float, default=420.)
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if not (.85 <= args.audio_speed <= 1.2 and 0 <= args.lead <= 2 and 0 <= args.tail <= 3 and 0 < args.min_duration <= args.max_duration):
        parser.error("Audio speed, padding or target-duration bounds are invalid")
    work, deadline, announced = args.work_dir.resolve(), time.monotonic()+args.timeout, 0.
    while not narration_ready(work):
        if not args.wait or time.monotonic() > deadline:
            raise SystemExit("Complete narration files and reconciled manifest are not ready; no audio-QC result written.")
        if time.monotonic()-announced > 45:
            print("Waiting for all saved narration files and the reconciled manifest; audio QC has not run.", flush=True)
            announced = time.monotonic()
        time.sleep(3)
    result = check(work, args.lead, args.tail, args.audio_speed, [args.min_duration, args.max_duration])
    (work/"audio-qc.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"status": result["status"], "chapters": result["chapter_count"],
        "expected_fps_rounded_seconds": result["projected_duration"]["expected_fps_rounded_seconds"]}), flush=True)
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
