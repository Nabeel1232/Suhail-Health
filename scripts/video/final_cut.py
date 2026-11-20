"""Capture and assemble the submission cut without changing the validated fallbacks."""
import argparse
import copy
import json
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

import prepare_authored_submission as authored
import prepare_submission_cut as shared
from capture_focus import FocusTour
from capture_ui import media_duration
from verify_authored_v4 import verify as verify_authored

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'runtime/video-final'
OUT = ROOT / 'reports/video-final'
PREVIOUS = ROOT / 'runtime/video-3min'
ASSET = ROOT / 'scripts/video/motion_assets/scene_final.js'
BASE, API = 'http://127.0.0.1:3000', 'http://127.0.0.1:18000'
LEAD, TAIL, TARGET = .4, .4, 175.
PLANS = {
    '02': ('navigator', '/worklist', False),
    '03': ('patient', '/patient', True),
    '06': ('clinician', '/cases/SC-003', False),
    '07': ('admin', '/operations', False),
}
MANIFEST = WORK / 'captures/manifest.json'


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def story():
    return {item['id']: item for item in read(WORK / 'storyboard.json')}


def clock():
    audio = read(WORK / 'narration-manifest.json')
    assert len(audio['chapters']) == len(story()) and all(row['status'] == 'generated' for row in audio['chapters'])
    seconds = sum(row['duration_seconds'] for row in audio['chapters'])
    padding = len(audio['chapters']) * (LEAD + TAIL)
    speed = round(seconds / (TARGET - padding), 8)
    if not .93 <= speed <= 1.07:
        # Use the full allowed duration window before retaking paid narration.
        speed = min(1.07, max(.93, speed))
    planned = sum(math.ceil((row['duration_seconds'] / speed + LEAD + TAIL) * 25 - 1e-7) / 25 for row in audio['chapters'])
    if not 172 <= planned <= 178:
        raise ValueError(f'Narration does not fit the approved tempo window. Audio {seconds:.2f}s, best candidate {planned:.2f}s.')
    config = {'audio_speed': speed, 'lead_seconds': LEAD, 'tail_seconds': TAIL, 'audio_seconds': seconds,
              'planned_video_seconds': planned, 'fps': 25, 'narration_chapters': len(story())}
    write(WORK / 'clock.json', config)
    print(json.dumps(config), flush=True)


def capture_beats(tour, ident):
    page = tour.page

    def beat(name, locator, first=False, label=None, scroll=True):
        tour.end()
        if scroll:
            tour.scroll_to(locator)
        tour.pause(1.2)
        tour.ready(name, name, locator, initial=first, scroll=False, hold=3.3, label=label)

    if ident == '02':
        page.locator('.sla-chip').first.wait_for()
        beat('worklist', page.locator('.care-queue-panel'), first=True, label='Owned follow-up and deadlines')
        beat('filters', page.locator('.care-filter-tabs'), label='Filter work that needs attention')
        tour.goto('/cases/SC-008')
        beat('timeline', page.locator('#case-milestones'), label='Dated evidence through case closure')
    elif ident == '03':
        page.wait_for_function("document.querySelector('.pt-view')?.dir === 'rtl'")
        page.locator('.pt-teachback').wait_for()
        beat('tracker', page.locator('.pt-tracker'), first=True, label='Steps to care in Arabic')
        beat('message', page.locator('.pt-message-bubble'), label='The delivered message')
        beat('teachback', page.locator('.pt-teachback'), label='Two questions to check understanding')
        beat('contact', page.locator('.pt-contact').filter(has_text='998'), label='How to reach the care team')
    elif ident == '06':
        page.locator('.care-urgent-panel').wait_for()
        beat('urgent', page.locator('.care-urgent-panel'), first=True, label='Clinician and backup on the urgent clock')
        tour.goto('/cases/SC-007')
        page.locator('.care-closure-panel').wait_for()
        beat('closure', page.locator('.care-closure-panel'), label='Verified evidence before closure')
    elif ident == '07':
        page.locator('.ws-impact-panel').wait_for(timeout=20_000)
        beat('measures', page.locator('.ws-kpi-row'), first=True, label='Observed synthetic workflow metrics')
        beat('impact', page.locator('.ws-impact-panel'), label='Simulated patient navigation impact')
    tour.end()
    tour.pause(.6)


def save_capture(record):
    manifest = read(MANIFEST) if MANIFEST.exists() else {
        'version': 'submission-final', 'scenes': [],
        'capture_policy': 'Authenticated synthetic role sign-in followed by read-only UI recording. No case commands.'}
    manifest['scenes'] = sorted([row for row in manifest['scenes'] if row['id'] != record['id']] + [record],
                                key=lambda row: row['id'])
    write(MANIFEST, manifest)


def capture(take, chapters):
    chapters = chapters or list(PLANS)
    if set(chapters) - PLANS.keys() or not re.fullmatch('[A-Za-z0-9_-]+', take):
        raise ValueError('Use a new named take and specify only recorded chapters.')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        for ident in chapters:
            role, route, mobile = PLANS[ident]
            viewport = {'width': 390, 'height': 844} if mobile else {'width': 1600, 'height': 760}
            target = WORK / 'captures' / f'{ident}-{take}'
            target.mkdir(parents=True, exist_ok=False)
            chapter = story()[ident]
            record = {'id': ident, 'title': chapter['title'], 'scene': chapter['scene'], 'stack': 'native',
                      'role': role, 'base_url': BASE, 'api_url': API, 'viewport': viewport,
                      'status': 'recording', 'media_type': 'actual_application_capture',
                      'actions': [], 'errors': [], 'non_get_requests': [],
                      'started_at': datetime.now(timezone.utc).isoformat()}
            context = browser.new_context(viewport=viewport, record_video_dir=str(target), record_video_size=viewport,
                                          is_mobile=mobile, has_touch=mobile, reduced_motion='reduce',
                                          device_scale_factor=1)

            def guard(interception):
                request = interception.request
                path = urlsplit(request.url).path
                if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
                    record['non_get_requests'].append({'method': request.method, 'path': path, 'allowed': False})
                    record['errors'].append({'blocked_request': path})
                    interception.abort()
                else:
                    interception.continue_()

            def check_response(response):
                path = urlsplit(response.url).path
                if path.startswith('/api/') and response.status >= 400:
                    record['errors'].append({'http_status': response.status, 'path': path})

            context.route('**/*', guard)
            began = time.monotonic()
            page = context.new_page()
            page.set_default_timeout(15_000)
            page.on('pageerror', lambda error: record['errors'].append({'pageerror': str(error)}))
            page.on('response', check_response)
            tour = FocusTour(page, context, record, BASE, API, target)
            tour.started = began
            save_capture(record)
            try:
                # The API request context performs only the demo sign-in. The recorded browser
                # page is guarded independently against any non-read request.
                tour.authenticate(role)
                tour.goto(route)
                capture_beats(tour, ident)
                record['status'] = 'completed' if not record['errors'] else 'completed_with_errors'
            except Exception as error:
                record['status'] = 'failed'
                record['errors'].append({'type': type(error).__name__, 'message': str(error)[:1200]})
                page.screenshot(path=str(target / 'error.png'))
            finally:
                video = page.video
                context.close()
                path = Path(video.path())
                record.update(video_path=str(path.relative_to(ROOT)), duration_seconds=media_duration(path),
                              finished_at=datetime.now(timezone.utc).isoformat())
                save_capture(record)
            print(json.dumps({'chapter': ident, 'status': record['status'], 'cues': len(tour.cues),
                              'errors': record['errors']}), flush=True)
            if record['status'] != 'completed':
                raise SystemExit(1)
        browser.close()


def reuse():
    original = {capture['id']: capture for capture in read(PREVIOUS / 'captures/manifest.json')['scenes']}
    previous_cues = read(PREVIOUS / 'ui-cues.json')
    for dest, source in [('04', '05'), ('05', '06')]:
        row = copy.deepcopy(original[source])
        first = previous_cues[source][0]['id']
        ready = next(event for event in row['actions'] if event.get('action') == 'visual_ready' and event.get('cue_id') == first)
        row.update(id=dest, title=story()[dest]['title'], scene=story()[dest]['scene'],
                   trim_start_seconds=ready['source_seconds'])
        assert row['status'] == 'completed' and not row['errors']
        save_capture(row)


def make_cues():
    rows = read(WORK / 'cue-phrases.json')
    previous_cues = read(PREVIOUS / 'ui-cues.json')
    captures = {entry['id']: entry for entry in read(MANIFEST)['scenes']}
    result = {'04': previous_cues['05'], '05': previous_cues['06']}
    for ident, cues in rows.items():
        actions = {(item['action'], item.get('cue_id')) for item in captures[ident]['actions']}
        result[ident] = []
        for index, cue in enumerate(cues):
            name = cue['id']
            assert ('visual_ready', name) in actions and ('visual_end', name) in actions
            result[ident].append({**cue, 'initial_state': index == 0,
                                  'visual_event': {'action': 'visual_ready', 'cue_id': name},
                                  'visual_end_event': {'action': 'visual_end', 'cue_id': name}})
    write(WORK / 'ui-cues.json', result)


def make_authored():
    config = read(WORK / 'clock.json')
    audio = {row['chapter']: row for row in read(WORK / 'narration-manifest.json')['chapters']}
    spec = read(WORK / 'authored-spec.json')['chapters']
    plans = [authored.prepare(ident, story()[ident], audio[ident], spec[ident], WORK,
                              config['audio_speed'], LEAD, TAIL) for ident in spec]
    with ThreadPoolExecutor(max_workers=2) as jobs:
        results = list(jobs.map(lambda plan: authored.render_one(plan, ASSET, True), plans))
    write(WORK / 'authored-sync-chapters.json', {
        'storyboard_sha256': authored.sha(WORK / 'storyboard.json'),
        'status': 'completed', 'preserve_source_timing': True,
        'captures': [capture for capture, _ in results],
        'chapters': [chapter for _, chapter in results]})


def plan():
    shared.WORK = WORK
    shared.merge_motion()
    shared.plan()
    sync = read(WORK / 'sync-plan.json')
    impact = next(cue for chapter in sync['chapters'] if chapter['id'] == '07'
                  for cue in chapter['cues'] if cue['id'] == 'impact')
    impact['label'] = 'Simulated cohort · Baseline ownership uses a noncompletion proxy'
    write(WORK / 'sync-plan.json', sync)


def check_motion():
    source = read(WORK / 'authored-sync-chapters.json')
    count = sum(len(chapter['cues']) for chapter in source['chapters'])
    report = verify_authored(WORK, OUT, threshold=.92, inset=8, expected_cues=count)
    print(json.dumps({key: report[key] for key in ('status', 'checked_cues', 'expected_cues', 'failures')}))
    return report['status'] == 'passed'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['clock', 'capture', 'reuse', 'cues', 'authored', 'plan', 'verify-authored'])
    parser.add_argument('--take', default='t1')
    parser.add_argument('--chapters', nargs='+')
    args = parser.parse_args()
    if args.stage == 'capture':
        capture(args.take, args.chapters)
    elif args.stage == 'verify-authored':
        raise SystemExit(0 if check_motion() else 1)
    else:
        {'clock': clock, 'reuse': reuse, 'cues': make_cues, 'authored': make_authored, 'plan': plan}[args.stage]()
