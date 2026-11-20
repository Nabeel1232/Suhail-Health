"""Capture the final showcase UI and register separately authored illustrations.

Records actual pages with the existing read-only capture guard. It never issues
clinical decisions, resets data, or invokes a model. Dataset preparation is a
separate recorded step owned by the release coordinator.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

import capture_showcase as original
from capture_ui import atomic_json, media_duration


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'runtime/video-v3'
original_perform = original.perform


class FinalTour(original.ShowcaseTour):
    def scroll_to(self, locator, seconds=.9):
        locator.first.wait_for(state='visible', timeout=10000)
        # Keep the recorded content clear of the new sticky patient section bar.
        offset = 90 if self.record['viewport']['width'] < 700 else 105
        target = locator.first.evaluate('(element, offset) => element.getBoundingClientRect().top + window.scrollY - offset', offset)
        self.scroll_y(target, seconds)
        self.pause(.25)


def perform(tour, scene):
    page = tour.page
    if scene == 'public_evidence':
        tour.focus(page.locator('.ws-public-input'), 3)
        tour.snap('public-dataset-actual-agent-results')
        tour.focus(page.locator('.ws-evidence-card').last, 2)
        tour.snap('separate-public-model-rubric-layer')
        tour.focus(page.locator('.ws-public-input'), 2)
    elif scene == 'worklist_journey':
        tour.pause(1.3)
        tour.snap('persisted-worklist-summary')
        search = page.get_by_role('searchbox')
        search.fill('SC-')
        tour.button('Journey board').click()
        tour.log('view_change', view='journey_board', clinical_state_changed=False)
        tour.focus(page.locator('.care-board'), 1.5)
        tour.snap('dynamic-journey-board')
        tour.button('List view').click()
        tour.pause(.6)
        tour.button('Show cases needing reconciliation').click()
        tour.log('summary_filter', filter='needs_reconciliation')
        tour.pause(.7)
        tour.snap('real-summary-filtered-work')
        tour.button('Show all actionable cases').click()
        search.fill('Mariam')
        tour.pause(.7)
        search.fill('')
        tour.goto('/cases/SC-001')
        tour.pause(.8)
        tour.snap('accountable-case-and-milestones')
        milestone = page.locator('.care-milestone-selector').last
        if milestone.count():
            tour.focus(milestone, .5)
            milestone.click()
            tour.log('milestone_inspection', clinical_state_changed=False)
            tour.pause(1)
            tour.snap('actual-selected-milestone-record')
        tour.tab('Coordination')
        tour.pause(.7)
        tour.tab('Activity & provenance')
        tour.pause(.8)
    else:
        original_perform(tour, scene)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, default=WORK)
    parser.add_argument('--go', action='store_true')
    parser.add_argument('--scenes', nargs='+')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--register-motion', action='store_true')
    args = parser.parse_args()
    work = args.work_dir.resolve()
    chapters = json.loads((work/'storyboard.json').read_text())
    shots = json.loads((work/'shotlist.json').read_text())
    plans = {s['id']: s for s in shots['scenes']}
    assert [s['id'] for s in chapters] == [s['id'] for s in shots['scenes']]
    selected = set(args.scenes or plans)
    if selected - set(plans):
        parser.error('Unknown scene ID')
    original.OUTPUT = work/'captures'
    original.OUTPUT.mkdir(parents=True, exist_ok=True)
    original.perform = perform
    original.ShowcaseTour = FinalTour
    path = original.OUTPUT/'manifest.json'
    manifest = json.loads(path.read_text()) if path.exists() else {
        'version': '3', 'generated_at': datetime.now(timezone.utc).isoformat(),
        'storyboard_path': str((work/'storyboard.json').relative_to(ROOT)),
        'shotlist_path': str((work/'shotlist.json').relative_to(ROOT)),
        'capture_policy': 'Authored illustrations explicitly distinguished from actual persisted UI. UI writes restricted to synthetic authentication and isolated patient language preference. No clinical commands or inference.',
        'scenes': []}
    narration_path = work/'narration-manifest.json'
    narration = {c['chapter']: c for c in json.loads(narration_path.read_text())['chapters']} if narration_path.exists() else {}
    if args.register_motion:
        if any(record.get('status') == 'recording' for record in manifest['scenes']):
            parser.error('Wait for the UI recorder to finish before registering authored motion.')
        for chapter in chapters:
            if chapter['id'] not in selected or plans[chapter['id']]['stack'] != 'authored':
                continue
            source = work/'motion'/(chapter['id']+'.mp4')
            proof = source.with_suffix('.json')
            if not source.is_file() or not proof.is_file():
                parser.error('Authored motion and its provenance record are required')
            record = {'id': chapter['id'], 'title': chapter['title'], 'scene': chapter['scene'],
                'media_type': 'authored_motion_graphics', 'role': 'illustration', 'base_url': None,
                'status': 'completed', 'errors': [], 'trim_start_seconds': 0,
                'video_path': str(source.relative_to(ROOT)), 'duration_seconds': media_duration(source),
                'provenance': str(proof.relative_to(ROOT)), 'non_get_requests': [],
                'finished_at': datetime.now(timezone.utc).isoformat()}
            original.checkpoint(manifest, record)
        print('Authored motion registered separately from UI footage.')
        return
    if not args.go:
        print(json.dumps([plans[c['id']] for c in chapters if c['id'] in selected], indent=2))
        return
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--renderer-process-limit=2'])
        try:
            for chapter in chapters:
                ident = chapter['id']
                if ident not in selected or plans[ident]['stack'] == 'authored':
                    continue
                existing = next((r for r in manifest['scenes'] if r['id'] == ident), None)
                if args.resume and existing and existing['status'] == 'completed' and (ROOT/existing['video_path']).is_file():
                    continue
                seconds = max(20, narration.get(ident, {}).get('duration_seconds', 30)/1.10)
                record = original.capture(browser, chapter, plans[ident], shots['stacks'], manifest, seconds=seconds)
                record['media_type'] = 'actual_application_capture'
                original.checkpoint(manifest, record)
                if record['status'] != 'completed':
                    raise SystemExit(1)
        finally:
            browser.close()


if __name__ == '__main__':
    main()
