"""Small audience and demo-role UI checks on the isolated stack only."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import pytest
from playwright.sync_api import expect

sys.path.insert(0, str(Path(__file__).parent))
from test_browser import API, WEB, api_client, browser, browser_login

ARTIFACTS = Path('runtime/submission-ui')
ROLES = [
    ('navigator', 'Care navigator', '/worklist'),
    ('clinician', 'Clinician', '/clinical'),
    ('specialist', 'Specialist', '/clinical'),
    ('receiver_a', 'Provider A', '/receiving'),
    ('receiver_b', 'Provider B', '/receiving'),
    ('patient', 'Patient', '/patient'),
    ('admin', 'Operations administrator', '/operations'),
]


@pytest.fixture(scope='module', autouse=True)
def isolated_only():
    assert os.environ.get('TEST_API_URL') == 'http://127.0.0.1:18001'
    assert os.environ.get('TEST_WEB_URL') == 'http://127.0.0.1:3002'
    client = api_client('navigator')
    try:
        result = client.get('/assistant/context')
        result.raise_for_status()
        assert result.json()['model_assistance']['enabled'] is False
    finally:
        client.close()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)


def record(key, value):
    target = ARTIFACTS/'browser-evidence.json'
    data = json.loads(target.read_text()) if target.exists() else {}
    data[key] = value
    target.write_text(json.dumps(data, indent=2)+'\n')


def screenshot(page, filename):
    path = ARTIFACTS/filename
    page.screenshot(path=str(path), full_page=False)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def no_overflow(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def test_submission_landing_explains_organizations_and_workflow_people(browser):
    images = []
    for width, height in [(1600, 900), (390, 844)]:
        context = browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce')
        page = context.new_page()
        page.goto(WEB)
        expect(page.get_by_role('heading', name='Guiding every result to care.', exact=True)).to_be_visible()
        expect(page.locator('.lp-hero-body')).to_contain_text('hospitals, clinics and organizations running screening programs')
        audience = page.get_by_role('list', name='Organizations Suhail supports', exact=True)
        expect(audience.locator('li')).to_have_text(['Hospitals', 'Clinics', 'Organizational screening'])
        assert audience.evaluate('element => element.getBoundingClientRect().top >= 0 && element.getBoundingClientRect().bottom <= innerHeight'), 'The primary audience should be visible in the first screen.'
        no_overflow(page)
        images.append(screenshot(page, 'landing-audience-desktop.png' if width > 760 else 'landing-audience-mobile.png'))
        people = page.locator('.lp-people-copy>p').last
        for label in ['Patients', 'care navigators', 'clinicians', 'specialists', 'receiving providers', 'operations teams']:
            expect(people).to_contain_text(label)
        context.close()
    record('audience', {'organizations': ['Hospitals', 'Clinics', 'Organizations running screening programs'], 'workflow_people': ['Patients', 'Care navigators', 'Clinicians', 'Specialists', 'Receiving providers', 'Operations teams'], 'first_screen_visible_desktop_and_mobile': True, 'screenshots': images})


def test_submission_demo_roles_are_recordable_keyboard_accessible_and_switch_actual_actor(browser):
    observer = api_client('navigator')
    before = observer.get('/cases/SC-001').json()['version']
    context = browser.new_context(viewport={'width': 1600, 'height': 900}, reduced_motion='reduce')
    page = browser_login(context, 'navigator', '/worklist')
    select = page.get_by_label('Synthetic demo role', exact=True)
    expect(select.locator('option')).to_have_count(7)
    assert select.locator('option').evaluate_all('options => options.map(option => option.value)') == [role[0] for role in ROLES]
    trigger = page.get_by_role('button', name='Explore demo roles', exact=True)
    auth_requests = []
    page.on('request', lambda request: auth_requests.append(request.url) if request.method == 'POST' and request.url.endswith('/api/auth/demo') else None)
    trigger.focus()
    page.keyboard.press('Enter')
    dialog = page.get_by_role('dialog', name='Explore all 7 demo roles', exact=True)
    expect(dialog).to_be_visible()
    for value, label, _ in ROLES:
        button = dialog.get_by_role('button', name='Use '+label+' demo role', exact=True)
        expect(button).to_be_visible()
        assert button.evaluate('element => element.getBoundingClientRect().top >= 0 && element.getBoundingClientRect().bottom <= innerHeight'), label
        assert dialog.locator('#demo-role-description-'+value).inner_text().strip()
    expect(dialog.get_by_role('button', name='Use Care navigator demo role', exact=True)).to_be_focused()
    page.keyboard.press('End')
    expect(dialog.get_by_role('button', name='Use Operations administrator demo role', exact=True)).to_be_focused()
    page.keyboard.press('Home')
    page.keyboard.press('ArrowDown')
    expect(dialog.get_by_role('button', name='Use Clinician demo role', exact=True)).to_be_focused()
    page.keyboard.press('Escape')
    expect(dialog).not_to_be_visible()
    expect(trigger).to_be_focused()
    trigger.click()
    dialog.get_by_role('button', name='Use Care navigator demo role', exact=True).click()
    expect(dialog).not_to_be_visible()
    page.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    assert auth_requests == [], 'Choosing the current role should simply close the explorer.'
    trigger.click()
    desktop_image = screenshot(page, 'demo-roles-seven-desktop.png')
    switched = []
    for value, label, target in ROLES[1:]+ROLES[:1]:
        if not dialog.is_visible():
            trigger.click()
        with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/api/auth/demo')) as response:
            dialog.get_by_role('button', name='Use '+label+' demo role', exact=True).click()
        assert response.value.ok, (response.value.status, response.value.text()[:300])
        response.value.finished()
        expect(select).to_have_value(value)
        expect(select).to_be_enabled()
        page.wait_for_url('**'+target)
        actual = context.request.get(API+'/auth/me')
        assert actual.ok and actual.json()['role'] == value
        switched.append({'role': value, 'label': label, 'home': target, 'actual_actor_verified': True})
    assert len(auth_requests) == 7
    with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/api/auth/demo')) as response:
        select.select_option('receiver_b')
    assert response.value.ok
    expect(select).to_have_value('receiver_b')
    page.wait_for_url('**/receiving')
    assert context.request.get(API+'/auth/me').json()['role'] == 'receiver_b'
    no_overflow(page)
    context.close()

    mobile = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, reduced_motion='reduce')
    page = browser_login(mobile, 'navigator', '/worklist')
    page.get_by_role('button', name='Explore demo roles', exact=True).click()
    dialog = page.get_by_role('dialog', name='Explore all 7 demo roles', exact=True)
    expect(dialog).to_be_visible()
    expect(dialog.locator('button[data-demo-role]')).to_have_count(7)
    no_overflow(page)
    assert dialog.evaluate('element => element.scrollWidth <= element.clientWidth + 1')
    mobile_image = screenshot(page, 'demo-roles-seven-mobile.png')
    dialog.get_by_role('button', name='Close demo roles', exact=True).click()
    expect(dialog).not_to_be_visible()
    mobile.close()
    after = observer.get('/cases/SC-001').json()['version']
    observer.close()
    assert after == before
    record('demo_roles', {'roles': switched, 'all_seven_visible_in_desktop_frame': True, 'native_select_retained_and_actual_switch_passed': True, 'keyboard': ['Enter', 'Home', 'End', 'ArrowDown', 'Escape', 'Focus return'], 'current_role_causes_no_auth_request': True, 'mobile_horizontal_overflow': False, 'case_version_before': before, 'case_version_after': after, 'screenshots': [desktop_image, mobile_image]})
