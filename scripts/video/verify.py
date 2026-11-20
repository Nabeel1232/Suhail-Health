"""Local final-media verification. No application writes or provider requests."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import time
import unicodedata
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
WORK, OUT = ROOT/'runtime/video', ROOT/'reports/video'
STEM = 'Suhail_Health_UI_Walkthrough'
LEAD, TAIL, AUDIO_SPEED = .85, 1.15, 1.


def display_path(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).split())


def execute(args):
    return subprocess.run(args, capture_output=True, text=True)


def probe(path):
    result = execute([shutil.which('ffprobe'), '-v', 'error', '-show_format', '-show_streams',
        '-show_chapters', '-of', 'json', str(path)])
    if result.returncode:
        raise ValueError('ffprobe failed to read final media')
    return json.loads(result.stdout)


def ready():
    try:
        manifest = json.loads((OUT/'manifest.json').read_text())
        storyboard = json.loads((WORK/'storyboard.json').read_text())
        narration = json.loads((WORK/'narration-manifest.json').read_text())
        expected_ids = [scene['id'] for scene in storyboard]
        video = OUT/(STEM+'.mp4')
        return bool(video.is_file() and video.stat().st_size > 0 and
            expected_ids and len(set(expected_ids)) == len(expected_ids) and
            [chapter['id'] for chapter in manifest['chapters']] == expected_ids and
            [chapter['chapter'] for chapter in narration['chapters']] == expected_ids and
            video.stat().st_size == manifest['bytes'] and
            video.stat().st_mtime <= (OUT/'manifest.json').stat().st_mtime + 1)
    except (FileNotFoundError, ValueError, KeyError):
        return False


def stamp(value):
    hours, minutes, seconds = value.replace(',', '.').split(':')
    return int(hours)*3600 + int(minutes)*60 + float(seconds)


def parse_captions(path, kind):
    source = path.read_text()
    blocks = re.split(r'\n\s*\n', source.strip())
    if kind == 'vtt':
        if not blocks or blocks[0].strip() != 'WEBVTT':
            raise ValueError('WebVTT header missing')
        blocks = blocks[1:]
    cues = []
    for index, block in enumerate(blocks, 1):
        lines = block.splitlines()
        if kind == 'srt':
            if int(lines.pop(0)) != index:
                raise ValueError('SRT sequence is not contiguous')
        timing = re.fullmatch(r'(\d{2}:\d{2}:\d{2}[.,]\d{3}) --> (\d{2}:\d{2}:\d{2}[.,]\d{3})', lines.pop(0))
        if not timing:
            raise ValueError('Caption timing syntax is invalid')
        text = '\n'.join(lines).strip()
        if not text:
            raise ValueError('Caption text is empty')
        cues.append({'start': stamp(timing[1]), 'end': stamp(timing[2]), 'text': text})
    return cues


def exact_secret_scan(video, ffprobe_metadata, key):
    findings = []
    h = hashlib.sha256()
    previous = b''
    needle = key.encode() if key else None
    with video.open('rb') as file:
        for chunk in iter(lambda: file.read(1024*1024), b''):
            h.update(chunk)
            if needle and needle in previous+chunk:
                findings.append({'file': display_path(video), 'reason': 'exact_private_credential_in_media_bytes'})
            previous = chunk[-max(len(needle or b'')-1, 0):] if needle and len(needle) > 1 else b''
    files = sorted({p for folder in [ROOT/'scripts/video', WORK, OUT] for p in folder.rglob('*')
        if p.is_file() and p.suffix.lower() in {'.py', '.json', '.jsonl', '.txt', '.md', '.srt', '.vtt', '.ass', '.ffmeta', '.log', '.csv', '.html'}
        and p.name != 'verification.json' and '__pycache__' not in p.parts})
    if needle:
        for path in files:
            if needle in path.read_bytes():
                findings.append({'file': display_path(path), 'reason': 'exact_private_credential_in_text_metadata'})
        if key in json.dumps(ffprobe_metadata, ensure_ascii=False):
            findings.append({'file': 'final_mp4_ffprobe_metadata', 'reason': 'exact_private_credential_in_probed_tags'})
    return h.hexdigest(), {'status': 'passed' if key and not findings else 'failed' if findings else 'blocked',
        'text_files_scanned': len(files), 'final_media_bytes_scanned': video.stat().st_size,
        'exact_credential_loaded_in_memory': bool(key), 'private_credential_source_excluded': True,
        'credential_or_credential_fingerprint_recorded': False, 'findings': findings,
        'limitation': 'Exact currently provided credential only; older or transformed secrets are outside this check.'}


def main():
    global WORK, OUT, STEM, LEAD, TAIL, AUDIO_SPEED
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-dir', type=Path, default=WORK)
    parser.add_argument('--output-dir', type=Path, default=OUT)
    parser.add_argument('--stem', default=STEM)
    parser.add_argument('--lead', type=float, default=LEAD)
    parser.add_argument('--tail', type=float, default=TAIL)
    parser.add_argument('--audio-speed', type=float, default=AUDIO_SPEED)
    parser.add_argument('--wait', action='store_true')
    parser.add_argument('--timeout', type=int, default=1500)
    parser.add_argument('--ready-file', help='Optional owner-controlled marker after final manifest corrections are complete')
    args = parser.parse_args()
    custom_work = args.work_dir.resolve() != WORK.resolve()
    WORK, OUT, STEM = args.work_dir.resolve(), args.output_dir.resolve(), args.stem
    LEAD, TAIL, AUDIO_SPEED = args.lead, args.tail, args.audio_speed
    if not (math.isfinite(LEAD) and math.isfinite(TAIL) and math.isfinite(AUDIO_SPEED) and
            0 <= LEAD <= 2 and 0 <= TAIL <= 3 and .85 <= AUDIO_SPEED <= 1.2):
        parser.error('Media settings are outside the renderer timing bounds.')
    if not STEM or Path(STEM).name != STEM:
        parser.error('--stem must be a plain output filename stem.')
    # Keep v1 behavior; a separate work directory must have its own owner gate.
    ready_file = Path(args.ready_file).resolve() if args.ready_file else WORK/'final-qc-ready' if custom_work else None
    deadline, announced = time.monotonic()+args.timeout, 0.
    while not ready() or (ready_file and not ready_file.is_file()):
        if not args.wait or time.monotonic() > deadline:
            raise SystemExit('Final MP4 and completed delivery manifest are not ready; no verification result was written.')
        if time.monotonic()-announced > 45:
            print('Waiting for completed final MP4 and delivery manifest; verification is not yet run.', flush=True)
            announced = time.monotonic()
        time.sleep(3)

    started = datetime.now(timezone.utc).isoformat()
    manifest = json.loads((OUT/'manifest.json').read_text())
    narration = json.loads((WORK/'narration-manifest.json').read_text())
    storyboard = json.loads((WORK/'storyboard.json').read_text())
    expected_ids = [scene['id'] for scene in storyboard]
    chapter_count = len(expected_ids)
    expected_durations = [math.ceil((chapter['duration_seconds']/AUDIO_SPEED+LEAD+TAIL)*25-1e-7)/25
        for chapter in narration['chapters']]
    expected_unrounded = sum(chapter['duration_seconds']/AUDIO_SPEED+LEAD+TAIL for chapter in narration['chapters'])
    media = OUT/(STEM+'.mp4')
    info = probe(media)
    duration = float(info['format']['duration'])
    streams = info['streams']
    video = next(s for s in streams if s['codec_type'] == 'video')
    audio = next(s for s in streams if s['codec_type'] == 'audio')
    subs = [s for s in streams if s['codec_type'] == 'subtitle']
    actual_chapters = info.get('chapters', [])
    timeline = manifest['chapters']
    expected_total = sum(expected_durations)
    checks = {}
    checks['h264_1920x1080_25fps'] = video['codec_name'] == 'h264' and video['width'] == 1920 and video['height'] == 1080 and abs(float(Fraction(video['avg_frame_rate']))-25) < .001
    checks['aac_stereo_48000hz'] = audio['codec_name'] == 'aac' and audio['channels'] == 2 and int(audio['sample_rate']) == 48000
    checks['embedded_english_captions'] = len(subs) == 1 and subs[0]['codec_name'] == 'mov_text' and subs[0].get('tags', {}).get('language') == 'eng'
    checks['positive_consistent_duration'] = duration > 0 and abs(duration-expected_total) <= 1 and abs(duration-manifest['duration_seconds']) <= .05
    checks['expected_chapter_markers'] = len(actual_chapters) == len(timeline) == len(narration['chapters']) == chapter_count
    checks['chapter_sources_match_storyboard_order'] = [chapter['id'] for chapter in timeline] == expected_ids == [chapter['chapter'] for chapter in narration['chapters']]
    recorded_speed = manifest.get('narration', {}).get('post_tempo_factor', 1.)
    checks['recorded_audio_speed_matches_requested'] = abs(recorded_speed-AUDIO_SPEED) < .000001
    audio_qc = json.loads((WORK/'audio-qc.json').read_text()) if (WORK/'audio-qc.json').is_file() else None
    if audio_qc:
        checks['source_audio_qc_passed'] = audio_qc.get('status') == 'passed'
        target = audio_qc.get('projected_duration', {}).get('target_seconds')
        if target:
            checks['duration_within_declared_target'] = len(target) == 2 and target[0] <= duration <= target[1]
    chapter_checks = []
    for index, (expected, actual) in enumerate(zip(timeline, actual_chapters)):
        start, end = float(actual['start_time']), float(actual['end_time'])
        previous_end = float(actual_chapters[index-1]['end_time']) if index else 0.
        chapter_checks.append({'id': expected['id'], 'start_seconds': start, 'end_seconds': end,
            'title': actual.get('tags', {}).get('title'), 'passed': bool(0 <= start < end <= duration+.05 and
                abs(start-expected['start_seconds']) <= .002 and abs(end-expected['end_seconds']) <= .002 and
                abs(start-previous_end) <= .002 and abs(end-start-expected_durations[index]) <= .002 and
                actual.get('tags', {}).get('title') == expected['id']+' '+expected['title'])})
    checks['chapter_order_titles_and_bounds'] = len(chapter_checks) == chapter_count and all(c['passed'] for c in chapter_checks)

    srt = parse_captions(OUT/(STEM+'.srt'), 'srt')
    vtt = parse_captions(OUT/(STEM+'.vtt'), 'vtt')
    checks['captions_valid_nonempty_and_in_bounds'] = bool(srt) and all(0 <= c['start'] < c['end'] <= duration+.05 and
        (i == 0 or c['start'] >= srt[i-1]['end']-.002) for i,c in enumerate(srt))
    checks['srt_vtt_equivalent'] = len(srt) == len(vtt) and all(left['start'] == right['start'] and left['end'] == right['end'] and
        normalized(left['text']) == normalized(right['text']) for left,right in zip(srt,vtt))
    source_checks = []
    for chapter in timeline:
        path = WORK/(chapter['id']+'-alignment.json')
        source = json.loads(path.read_text())
        alignment = source.get('normalized_alignment') or source['alignment']
        reconstructed = ''.join(alignment['characters'])
        starts, ends = alignment['character_start_times_seconds'], alignment['character_end_times_seconds']
        arrays_valid = len(alignment['characters']) == len(starts) == len(ends) > 0 and all(
            math.isfinite(start) and math.isfinite(end) and 0 <= start <= end and
            (index == 0 or start >= starts[index-1] and end >= ends[index-1])
            for index, (start, end) in enumerate(zip(starts, ends)))
        cues = [c for c in srt if c['start'] >= chapter['start_seconds']-.002 and c['end'] <= chapter['end_seconds']+.002]
        # Verify the scaled timestamps against independent alignment word spans,
        # without copying the renderer's caption grouping implementation.
        words = list(re.finditer(r'\S+', reconstructed))
        cursor, timed_cues = 0, []
        for cue in cues:
            count = len(cue['text'].split())
            group = words[cursor:cursor+count]
            timing_passed = bool(arrays_valid and group and len(group) == count and
                normalized(' '.join(word.group() for word in group)) == normalized(cue['text']) and
                abs(cue['start']-(chapter['start_seconds']+LEAD+starts[group[0].start()]/AUDIO_SPEED)) <= .002 and
                abs(cue['end']-(chapter['start_seconds']+LEAD+ends[group[-1].end()-1]/AUDIO_SPEED)) <= .002)
            timed_cues.append(timing_passed)
            cursor += count
        scaled_alignment = bool(words and cursor == len(words) and timed_cues and all(timed_cues))
        capture, narration_path = ROOT/chapter['capture'], ROOT/chapter['audio']
        source_checks.append({'id': chapter['id'], 'alignment_file': display_path(path),
            'caption_count': len(cues), 'expected_caption_count': chapter['caption_count'],
            'capture_exists': capture.is_file(), 'narration_exists': narration_path.is_file(),
            'alignment_characters': len(alignment['characters']),
            'alignment_arrays_valid_and_monotonic': arrays_valid,
            'caption_timestamps_match_scaled_source_alignment': scaled_alignment,
            'caption_text_covers_alignment': normalized(' '.join(c['text'] for c in cues)) == normalized(reconstructed),
            'passed': bool(capture.is_file() and narration_path.is_file() and reconstructed.strip() and arrays_valid and scaled_alignment and
                len(cues) == chapter['caption_count'] and normalized(' '.join(c['text'] for c in cues)) == normalized(reconstructed))})
    checks['captions_cover_all_actual_sources'] = len(source_checks) == chapter_count and all(c['passed'] for c in source_checks)
    transcript = (OUT/(STEM+'_Transcript.txt')).read_text()
    checks['transcript_nonempty_and_all_narration_texts_covered'] = bool(transcript.strip()) and all(
        normalized((WORK/(c['chapter']+'-text.txt')).read_text()) in normalized(transcript) for c in narration['chapters'])

    decode_start = time.monotonic()
    decode = execute([shutil.which('ffmpeg'), '-hide_banner', '-nostdin', '-v', 'error', '-threads', '4', '-i', str(media),
        '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'])
    decode_elapsed = time.monotonic()-decode_start
    checks['complete_video_audio_decode_clean'] = decode.returncode == 0 and not decode.stderr.strip()
    voice_values = dotenv_values(ROOT/'.env_elevenlabs')
    key = next((value for name,value in voice_values.items() if value and name.lower() in {'elevenlabs_api','elevenlabs_api_key','xi_api_key'}),None)
    media_hash, secret_scan = exact_secret_scan(media, info, key)
    checks['final_media_and_text_metadata_secret_scan'] = secret_scan['status'] == 'passed'
    checks['final_video_hash_matches_delivery_manifest'] = media_hash == manifest['video_sha256']
    if manifest.get('visual_sync'):
        visual_path = OUT/'visual-sync-verification.json'
        visual = json.loads(visual_path.read_text()) if visual_path.is_file() else {}
        checks['semantic_visual_state_sync_verified'] = bool(visual.get('status') == 'passed' and
            visual.get('video_sha256') == media_hash and visual.get('all_cues_passed') and
            visual.get('checked_cues') == visual.get('expected_cues') and visual.get('checked_cues',0)>0)
        if manifest['visual_sync'].get('authored_verification_required'):
            authored_path = OUT/'authored-sync-verification.json'
            authored = json.loads(authored_path.read_text()) if authored_path.is_file() else {}
            checks['authored_visual_state_sync_verified'] = bool(authored.get('status') == 'passed' and
                authored.get('video_sha256') == media_hash and authored.get('all_cues_passed') and
                authored.get('checked_cues') == authored.get('expected_cues') and authored.get('checked_cues',0)>0)
    result = {'status': 'passed' if all(checks.values()) else 'review_required', 'started_at': started,
        'finished_at': datetime.now(timezone.utc).isoformat(), 'mode': 'local_ffprobe_ffmpeg_final_media_verification',
        'video': media.name, 'bytes': media.stat().st_size, 'video_sha256': media_hash, 'duration_seconds': duration,
        'narration_seconds': sum(c['duration_seconds'] for c in narration['chapters']),
        'expected_chapters': chapter_count,
        'timing': {'lead_seconds_per_chapter': LEAD, 'tail_seconds_per_chapter': TAIL,
            'audio_speed': AUDIO_SPEED, 'frames_per_second': 25},
        'expected_chapter_rounded_total_seconds': expected_total,
        'expected_unrounded_total_seconds': expected_unrounded,
        'narration_plus_two_seconds_per_chapter': sum(c['duration_seconds'] for c in narration['chapters'])+2*chapter_count if LEAD+TAIL == 2 and AUDIO_SPEED == 1 else None,
        'video_stream': {k:video.get(k) for k in ['codec_name','width','height','pix_fmt','avg_frame_rate']},
        'audio_stream': {k:audio.get(k) for k in ['codec_name','sample_rate','channels']},
        'checks': checks, 'chapter_checks': chapter_checks,
        'captions': {'srt_cues': len(srt), 'vtt_cues': len(vtt), 'source_checks': source_checks},
        'decode': {'exit_code': decode.returncode, 'error_output_empty': not decode.stderr.strip(),
            'elapsed_seconds': round(decode_elapsed,3), 'error_output_sha256': hashlib.sha256(decode.stderr.encode()).hexdigest()},
        'secret_scan': secret_scan, 'provider_calls': 0, 'application_state_changes': 0,
        'limits': ['Technical decode/timing/lineage checks do not replace a visual editorial review.',
            'No clinical validation or patient-outcome claim is implied.']}
    output = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
    if key:
        output = output.replace(key, '[REDACTED]')
    (OUT/'verification.json').write_text(output+'\n')
    print(json.dumps({'status':result['status'],'duration_seconds':duration,'chapters':len(actual_chapters),
        'caption_cues':len(srt),'failed_checks':[k for k,v in checks.items() if not v],
        'report':display_path(OUT/'verification.json')}, indent=2), flush=True)
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
