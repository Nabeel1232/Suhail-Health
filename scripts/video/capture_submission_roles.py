"""Record the short submission's new audience and seven-role chapter.

Only private-stack authentication and GETs are permitted. This writes one
chapter record and cue file, and never edits a shared or v4 capture manifest.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from capture_focus import FocusTour
from capture_ui import atomic_json, media_duration

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'runtime/video-3min'
BASE = 'http://127.0.0.1:3002'
API = 'http://127.0.0.1:18001'
ROLE_LABELS = ['Care navigator', 'Clinician', 'Specialist', 'Provider A', 'Provider B', 'Patient', 'Operations administrator']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(take):
    assert BASE.endswith(':3002') and API.endswith(':18001')
    os.environ.setdefault('TMPDIR', str(ROOT/'.runtime/showcase-tmp'))
    folder = WORK/'captures'/('02-'+take)
    folder.mkdir(parents=True, exist_ok=True)
    if any(folder.glob('*.webm')):
        raise ValueError('Preserve existing footage: choose a new --take name.')
    viewport = {'width': 1600, 'height': 760}
    record = {'id': '02', 'title': 'Explore the working prototype', 'scene': 'prototype_roles',
        'stack': 'isolated', 'role': 'navigator_then_patient', 'base_url': BASE, 'api_url': API,
        'viewport': viewport, 'status': 'recording', 'media_type': 'actual_application_capture',
        'actions': [], 'errors': [], 'non_get_requests': [],
        'started_at': datetime.now(timezone.utc).isoformat(),
        'policy': 'Private3002/18001 only. GETs and synthetic authentication only; no clinical commands, chat writes, model calls or reset.'}
    destination = WORK/'captures02.json'
    atomic_json(destination, record)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--renderer-process-limit=2'])
        context = browser.new_context(viewport=viewport, record_video_dir=str(folder), record_video_size=viewport)
        page = None
        tour = None
        try:
            # This API authentication precedes page/video creation and cannot
            # advance a care record. The scene still starts on the public page.
            response = context.request.post(API+'/auth/demo', data={'role': 'navigator'})
            record['non_get_requests'].append({'phase': 'preflight', 'method': 'POST', 'path': '/auth/demo', 'allowed': True, 'status': response.status})
            assert response.ok
            response = context.request.get(API+'/assistant/context')
            assert response.ok and response.json()['model_assistance']['enabled'] is False
            before = context.request.get(API+'/cases/SC-001')
            assert before.ok
            record['case_version_before'] = before.json()['version']
            record['model_assistance_enabled'] = False
            record['roles_seen'] = ['navigator']

            def guard(route):
                request = route.request
                parsed = urlsplit(request.url)
                origin = parsed.scheme+'://'+parsed.netloc
                if parsed.scheme in {'http', 'https'} and origin not in {BASE, API}:
                    record['errors'].append({'blocked_external_origin': origin})
                    route.abort(); return
                if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
                    allowed = request.method == 'POST' and origin in {BASE, API} and parsed.path in {'/auth/demo', '/api/auth/demo'}
                    record['non_get_requests'].append({'method': request.method, 'path': parsed.path, 'allowed': allowed})
                    if not allowed:
                        record['errors'].append({'blocked_request': parsed.path})
                        route.abort(); return
                route.continue_()
            context.route('**/*', guard)
            page = context.new_page()
            page.set_default_timeout(20000)
            page.on('pageerror', lambda error: record['errors'].append({'pageerror': str(error)}))
            page.on('response', lambda response: record['errors'].append({'http_status': response.status, 'path': urlsplit(response.url).path}) if '/api/' in response.url and response.status >= 400 else None)
            page.goto(BASE, wait_until='networkidle')
            expect(page.get_by_role('heading', name='Guiding every result to care.', exact=True)).to_be_visible()
            page.evaluate('document.fonts.ready')
            # Force an actual first application frame before starting the event
            # clock. Retained screenshots, rather than an assumed offset, are
            # the authority for the root editor's PTS/SSIM calibration.
            prime = folder/'recording-prime.png'
            page.screenshot(path=str(prime), full_page=False)
            page.wait_for_timeout(1000)
            tour = FocusTour(page, context, record, BASE, API, folder)
            tour.started = time.monotonic()
            record['event_clock_origin'] = 'After forced homepage calibration screenshot and1second video priming. Root source-frame calibration is authoritative.'
            record['priming_screenshot'] = {'path': str(prime.relative_to(ROOT)), 'sha256': sha(prime)}
            tour.log('recording_primed', screenshot_path=str(prime.relative_to(ROOT)))

            audience = page.locator('.lp-hero-body')
            expect(audience).to_contain_text('hospitals, clinics and organizations running screening programs')
            tour.ready('audiences', 'The homepage', audience, until='those audiences clear.', initial=True, scroll=False, hold=2.5, text_region=True)
            tour.goto('/worklist')
            page.get_by_role('button', name='Explore demo roles', exact=True).click()
            dialog = page.get_by_role('dialog', name='Explore all 7 demo roles', exact=True)
            expect(dialog).to_be_visible()
            for label in ROLE_LABELS:
                button = dialog.get_by_role('button', name='Use '+label+' demo role', exact=True)
                expect(button).to_be_visible()
                assert button.evaluate('element => element.getBoundingClientRect().top >= 0 && element.getBoundingClientRect().bottom <= innerHeight'), label
            tour.ready('demo-roles', 'Open Explore demo roles', dialog, until='operations administrator.', scroll=False, hold=1.5)
            for label in ROLE_LABELS:
                dialog.get_by_role('button', name='Use '+label+' demo role', exact=True).hover()
                tour.log('hover_demo_role', role_label=label)
                tour.pause(.25)
            tour.end()
            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/api/auth/demo')) as changed:
                dialog.get_by_role('button', name='Use Patient demo role', exact=True).click()
            assert changed.value.ok
            changed.value.finished()
            page.wait_for_url('**/patient')
            expect(page.get_by_label('Synthetic demo role', exact=True)).to_have_value('patient')
            actual = context.request.get(API+'/auth/me')
            assert actual.ok and actual.json()['role'] == 'patient'
            record['roles_seen'].append('patient')
            record['selected_role'] = {'value': 'patient', 'actual_actor_verified': True, 'path': '/patient', 'authentication_http_status': changed.value.status}
            page.locator('.pt-welcome').wait_for(state='visible')
            page.evaluate('document.fonts.ready')
            tour.pause(.5)
            tour.ready('selected-workspace', 'Select a role', page.locator('.pt-welcome'), until='working prototype.', scroll=False, hold=3)
            tour.end()
            after = context.request.get(API+'/cases/SC-001')
            assert after.ok
            record['case_version_after'] = after.json()['version']
            assert record['case_version_after'] == record['case_version_before']
            tour.log('final_postroll', seconds_to_hold=3)
            tour.pause(3)
            record['final_postroll_seconds'] = 3
            record['clinical_record_mutations'] = 0
            record['main_stack_requests'] = 0
            record['status'] = 'completed' if not record['errors'] else 'completed_with_errors'
            atomic_json(WORK/'new-rolemenu-cues.json', tour.cues)
        except Exception as error:
            record['status'] = 'failed'
            record['errors'].append({'type': type(error).__name__, 'message': str(error)[:2000]})
            if page is not None:
                page.screenshot(path=str(folder/'error.png'), full_page=False)
        finally:
            video = page.video if page is not None else None
            context.close()
            if video is not None:
                source = Path(video.path())
                record.update(video_path=str(source.relative_to(ROOT)), video_sha256=sha(source), duration_seconds=media_duration(source))
            record['finished_at'] = datetime.now(timezone.utc).isoformat()
            if tour:
                record['cue_count'] = len(tour.cues)
                record['all_cue_end_events_within_raw_duration'] = all(event.get('source_seconds', event.get('seconds',0)) < record['duration_seconds'] for event in record['actions'] if event['action'] in {'visual_ready','visual_end'})
            record['script_sha256'] = sha(Path(__file__))
            atomic_json(destination, record)
            browser.close()
    print(json.dumps({'status': record['status'], 'record': str(destination.relative_to(ROOT)), 'cues': record.get('cue_count',0), 'errors': record['errors']}))
    if record['status'] != 'completed':
        raise SystemExit(1)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--go', action='store_true')
    parser.add_argument('--take', default='roles-v1')
    args = parser.parse_args()
    assert re.fullmatch(r'[A-Za-z0-9_-]+', args.take)
    if not args.go:
        print(json.dumps({'id': '02', 'viewport': {'width':1600,'height':760}, 'web':BASE, 'api':API, 'cues':['audiences','demo-roles','selected-workspace'], 'allowed_posts':['/auth/demo','/api/auth/demo'], 'output':'runtime/video-3min/captures02.json'}, indent=2));return
    capture(args.take)


if __name__ == '__main__':
    main()
