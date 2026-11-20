"""Actual dynamic UI behavior over the authorized persisted case records.

Run with TEST_API_URL/TEST_WEB_URL pointing to the isolated verification stack.
The first two checks are read-only; the patient check changes only the synthetic
patient's English/Arabic communication preference and restores it afterwards.
"""
import json
from pathlib import Path
import sys

from playwright.sync_api import expect

sys.path.insert(0, str(Path(__file__).parent))
from test_browser import API, WEB, browser, browser_login


ARTIFACTS = Path('runtime/ui-v3')


def save_record(name, record):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS/'dynamic-browser-record.json'
    data = json.loads(path.read_text()) if path.exists() else {}
    data[name] = record
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')


def screenshot(page, name):
    folder = ARTIFACTS/'screenshots'
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder/name), full_page=True)


def read(context, path):
    response = context.request.get(API+path)
    assert response.ok, (response.status, path)
    return response.json()


def link_ids(locator):
    return set(locator.evaluate_all("links => links.map(link => link.getAttribute('href').split('/').pop())"))


def test_dynamic_board_and_summary_filters_preserve_authorized_cases(browser):
    context = browser.new_context(viewport={'width': 1600, 'height': 1000})
    page = browser_login(context, 'navigator', '/worklist')
    expect(page.get_by_role('heading', name='Every case, a clear next step.')).to_be_visible()
    cases = read(context, '/cases')
    expected = {case['id'] for case in cases}
    expect(page.locator('.care-case-table tbody tr')).to_have_count(len(expected))
    assert link_ids(page.locator('.care-case-table .patient-link')) == expected
    before = read(context, '/cases/SC-001')

    page.get_by_role('button', name='Journey board', exact=True).click()
    expect(page.get_by_role('button', name='Journey board', exact=True)).to_have_attribute('aria-pressed', 'true')
    expect(page.locator('.care-board-card')).to_have_count(len(expected))
    assert link_ids(page.locator('.care-board-open')) == expected
    screenshot(page, 'journey-board-desktop.png')

    page.get_by_role('button', name='Show cases needing reconciliation', exact=True).click()
    expect(page.get_by_role('button', name='Quarantined', exact=True)).to_have_attribute('aria-pressed', 'true')
    quarantined = {case['id'] for case in cases if case.get('quarantine_reason')}
    expect(page.locator('.care-board-card')).to_have_count(len(quarantined))
    assert link_ids(page.locator('.care-board-open')) == quarantined
    page.get_by_role('button', name='Show all actionable cases', exact=True).click()
    expect(page.locator('.care-board-card')).to_have_count(len(expected))
    page.get_by_role('button', name='List view', exact=True).click()
    expect(page.locator('.care-case-table tbody tr')).to_have_count(len(expected))
    assert link_ids(page.locator('.care-case-table .patient-link')) == expected
    after = read(context, '/cases/SC-001')
    assert after['version'] == before['version']
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    save_record('board_and_filters', {'authorized_cases': len(expected), 'quarantined_cases': len(quarantined),
        'same_case_ids_in_both_views': True, 'case_version_before': before['version'],
        'case_version_after': after['version'], 'status': 'passed'})
    context.close()


def test_dynamic_milestone_inspection_reads_actual_state_without_mutation(browser):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    page = browser_login(context, 'clinician', '/cases/SC-001')
    case = read(context, '/cases/SC-001')
    milestone = next(item for item in case['milestones'] if item['type'] == 'investigation')
    label = 'Investigation completed'
    button = page.get_by_role('button', name=f'Inspect {label} milestone', exact=True)
    expect(button).to_be_visible()
    button.click()
    region = page.get_by_role('region', name=f'{label} milestone details', exact=True)
    expect(region).to_be_visible()
    expect(button).to_have_attribute('aria-expanded', 'true')
    expect(page.locator('.care-milestone-selected').get_by_text(milestone['status'].replace('_', ' '), exact=True).first).to_be_visible()
    expect(region.get_by_text('Recorded milestone', exact=True)).to_be_visible()
    for reference in milestone.get('evidence_ids', []):
        matching = next((e for e in case.get('evidence', []) if e['id'] == reference), None)
        expect(region.get_by_text(matching.get('reference') if matching and matching.get('reference') else reference, exact=True)).to_be_visible()
    screenshot(page, 'milestone-inspector-desktop.png')
    button.click()
    expect(region).to_have_count(0)
    after = read(context, '/cases/SC-001')
    assert after['version'] == case['version'] and after['milestones'] == case['milestones']
    save_record('milestone_inspection', {'type': milestone['type'], 'state': milestone['status'],
        'linked_reference_count': len(milestone.get('evidence_ids', [])), 'case_version_before': case['version'],
        'case_version_after': after['version'], 'status': 'passed'})
    context.close()


def test_dynamic_patient_sections_follow_scroll_without_page_jump_in_both_languages(browser):
    context = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True,
        has_touch=True, reduced_motion='reduce')
    page = browser_login(context, 'patient', '/patient')
    view = page.locator('.patient-view')
    expect(view).to_be_visible()
    initial = view.get_attribute('lang')
    observed = []
    try:
        for language in ['en', 'ar']:
            if view.get_attribute('lang') != language:
                page.locator('.pt-language').click()
                expect(view).to_have_attribute('lang', language)
            expect(view).to_have_attribute('dir', 'rtl' if language == 'ar' else 'ltr')
            page.evaluate('document.fonts.ready')
            nav = page.locator('.pt-following-nav')
            for section in ['patient-questions', 'patient-plan']:
                target = page.locator('#'+section).evaluate("element => Math.min(Math.max(0, element.getBoundingClientRect().top + scrollY - 150), document.documentElement.scrollHeight - innerHeight)")
                page.evaluate("y => window.scrollTo({top:y, behavior:'instant'})", target)
                expect(nav.locator('a[aria-current="location"]')).to_have_attribute('href', '#'+section)
                page.wait_for_timeout(150)
                actual = page.evaluate('scrollY')
                assert abs(actual-target) <= 2, (language, section, target, actual)
                observed.append({'language': language, 'section': section, 'requested_y': target, 'actual_y': actual})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            screenshot(page, 'patient-following-nav-'+language+'.png')
    finally:
        if view.get_attribute('lang') != initial:
            page.locator('.pt-language').click()
            expect(view).to_have_attribute('lang', initial)
    assert page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
    save_record('patient_following_navigation', {'checks': observed, 'status': 'passed',
        'restored_language': initial, 'reduced_motion': True, 'horizontal_overflow': False})
    context.close()
