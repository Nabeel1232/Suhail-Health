"""Capture the frozen synthetic demonstration without changing episode state."""
from pathlib import Path
import argparse
import os

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports' / 'submission-screenshots'
API = os.environ.get('TEST_API_URL', 'http://127.0.0.1:18000')
WEB = os.environ.get('TEST_WEB_URL', 'http://127.0.0.1:3000')
SCREENS = {
    'worklist': ('navigator', '/worklist', '.sla-chip', None),
    'timeline': ('clinician', '/cases/SC-008?tab=journey#case-milestones', '.care-timeline-summary', '.care-timeline-summary'),
    'closure': ('clinician', '/cases/SC-007', '.care-closure-panel', '.care-closure-panel'),
    'receiving': ('receiver_a', '/receiving', '.ws-receiving', None),
    'operations': ('admin', '/operations', '.ws-kpi-row', None),
    'impact': ('admin', '/operations', '.ws-impact-panel', '.ws-impact-panel'),
    'patient-arabic': ('patient', '/patient', '.patient-view[dir=rtl] .pt-tracker', None),
    'patient-teachback': ('patient', '/patient', '.patient-view[dir=rtl] .pt-teachback', '.pt-teachback'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('screens', nargs='*')
    args = parser.parse_args()
    names = args.screens or [name for name in SCREENS if name != 'impact']
    if any(name not in SCREENS for name in names):
        parser.error('unknown screenshot name')
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
        for name in names:
            role, route, ready, focus = SCREENS[name]
            viewport = {'width': 390, 'height': 844} if role == 'patient' else {'width': 1440, 'height': 950}
            with browser.new_context(viewport=viewport, reduced_motion='reduce', device_scale_factor=1) as context:
                signed_in = context.request.post(API + '/auth/demo', data={'role': role})
                if not signed_in.ok:
                    raise RuntimeError(f'Demo authentication failed for {role} ({signed_in.status})')
                page = context.new_page()
                failures = []
                page.on('request', lambda request: failures.append(request.method) if request.method != 'GET' else None)
                page.on('pageerror', lambda _: failures.append('page error'))
                page.goto(WEB + route, wait_until='networkidle')
                page.locator('h1').first.wait_for(state='visible')
                page.locator(ready).first.wait_for(state='visible', timeout=12000)
                page.evaluate('document.fonts.ready')
                if focus:
                    page.locator(focus).first.evaluate('(node) => node.scrollIntoView({block: "center", behavior: "instant"})')
                page.screenshot(path=str(OUT / (name + '.png')), animations='disabled')
                if failures:
                    raise RuntimeError(f'Unexpected page error or write request during {name}')
                print(name, flush=True)
        browser.close()


if __name__ == '__main__':
    main()
