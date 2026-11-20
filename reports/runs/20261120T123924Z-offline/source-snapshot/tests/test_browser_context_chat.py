"""Actual, read-only workspace chat journeys on the isolated release stack.

The guard requires the explicit verification URLs and disabled model assistance
before a message can be submitted. Chat writes are confined to its own tables;
the Arabic-layout check restores the synthetic patient's language preference.
"""
import json
import os
from pathlib import Path
import re
import sys

import pytest
from playwright.sync_api import expect

sys.path.insert(0, str(Path(__file__).parent))
from test_browser import API, WEB, api_client, browser, browser_login, case_command


ARTIFACTS = Path('runtime/chat-ui/browser')


@pytest.fixture(scope='module', autouse=True)
def isolated_chat_only():
    assert os.environ.get('TEST_API_URL') == 'http://127.0.0.1:18001', 'Chat browser checks require the isolated API18001.'
    assert os.environ.get('TEST_WEB_URL') == 'http://127.0.0.1:3002', 'Chat browser checks require the isolated web3002.'
    client = api_client('navigator')
    try:
        response = client.get('/assistant/context')
        assert response.is_success
        assert response.json()['model_assistance']['enabled'] is False, 'Do not run browser chat checks with live inference enabled.'
    finally:
        client.close()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)


def read(context, path):
    response = context.request.get(API + path)
    assert response.ok, (response.status, path)
    return response.json()


def record(name, value):
    target = ARTIFACTS/'behavior.json'
    data = json.loads(target.read_text()) if target.exists() else {}
    data[name] = value
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')


def open_chat(page):
    page.get_by_role('button', name=re.compile(r'^(Ask Suhail|اسأل سهيل)$')).click()
    dialog = page.get_by_role('dialog', name=re.compile(r'^(Ask Suhail|اسأل سهيل)$'))
    expect(dialog).to_be_visible()
    expect(dialog.locator('#context-chat-question')).to_be_focused()
    return dialog


def ask(page, dialog, question):
    dialog.locator('#context-chat-question').fill(question)
    with page.expect_response(lambda response: response.request.method == 'POST' and '/api/assistant/conversations/' in response.url and response.url.endswith('/messages')) as result:
        dialog.get_by_role('button', name=re.compile(r'^(Send message|إرسال الرسالة)$')).click()
    assert result.value.ok, (result.value.status, result.value.text()[:400])
    payload = result.value.json()
    assert payload['answer']['mode'] == 'authorized_records'
    expect(dialog.locator('.cc-assistant-message').last).to_be_visible()
    expect(dialog.locator('.cc-thinking')).to_have_count(0)
    return payload


def no_overflow(page, dialog):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert dialog.evaluate('element => element.scrollWidth <= element.clientWidth + 1')


def test_context_chat_counts_history_and_readonly_case(browser):
    context = browser.new_context(viewport={'width': 1600, 'height': 950})
    page = browser_login(context, 'navigator', '/worklist')
    before = read(context, '/cases/SC-001')
    workspace = read(context, '/assistant/context')
    launcher = page.get_by_role('button', name='Ask Suhail', exact=True)
    launcher.focus()
    page.keyboard.press('Control+j')
    dialog = page.get_by_role('dialog', name='Ask Suhail', exact=True)
    expect(dialog).to_be_visible()
    expect(dialog.locator('#context-chat-question')).to_be_focused()
    payload = ask(page, dialog, 'How many requests do I have?')
    metric = payload['answer']['metrics'][0]
    assert metric['value'] == workspace['counts']['pending_requests']
    expect(dialog.locator('.cc-assistant-message').last.locator('.cc-answer-metrics strong').first).to_have_text(format(metric['value'], ','))
    assert read(context, '/cases/SC-001')['version'] == before['version']
    thread = read(context, '/assistant/conversations/' + payload['conversation_id'])
    assert any(message['id'] == payload['message']['id'] for message in thread['messages'])
    no_overflow(page, dialog)
    page.screenshot(path=str(ARTIFACTS/'navigator-grounded-answer.png'), full_page=False)

    page.keyboard.press('Escape')
    expect(dialog).not_to_be_visible()
    expect(launcher).to_be_focused()
    page.reload()
    with page.expect_response(lambda response: response.request.method == 'GET' and response.url.endswith('/api/assistant/conversations')) as history_loaded:
        dialog = open_chat(page)
    assert history_loaded.value.ok, (history_loaded.value.status, history_loaded.value.text()[:300])
    history_loaded.value.finished()
    dialog.get_by_role('button', name='Conversation history', exact=True).click()
    first = dialog.locator('.cc-history-list>button').first
    expect(first).to_contain_text(thread['conversation']['title'])
    with page.expect_response(lambda response: response.request.method == 'GET' and response.url.endswith('/api/assistant/conversations/' + payload['conversation_id'])) as restored:
        first.click()
    assert restored.value.ok, (restored.value.status, restored.value.text()[:300])
    restored.value.finished()
    expect(dialog.locator('.cc-user-message').filter(has_text='How many requests do I have?')).to_be_visible()
    expect(dialog.locator('.cc-answer-metrics strong').first).to_have_text(format(metric['value'], ','))
    guidance = ask(page, dialog, 'How does the workflow handle referral acceptance?')
    guidance_sources = [source for source in guidance['answer']['sources'] if source.get('field') in {'versioned_workflow_guidance', 'approved_workflow_guidance'}]
    assert guidance_sources, 'The versioned guidance answer must retain its linked source.'
    for source in guidance_sources:
        link = dialog.locator('.cc-assistant-message').last.locator('.cc-sources a[href="' + source['href'] + '"]')
        expect(link).to_be_visible()
        expect(link).to_have_attribute('rel', 'noopener noreferrer')
        if source['href'].startswith('/api/assistant/knowledge/'):
            assert context.request.get(WEB + source['href']).ok
    dialog.get_by_role('button', name='New conversation', exact=True).click()
    with page.expect_response(lambda response: response.request.method == 'POST' and '/api/assistant/conversations/' in response.url and response.url.endswith('/messages')) as episode_result:
        dialog.locator('.cc-workspace-counts button').filter(has_text='Authorized episodes').click()
    assert episode_result.value.ok
    episode_answer = episode_result.value.json()['answer']
    assert episode_answer['mode'] == 'authorized_records'
    assert workspace['counts']['episodes'] != workspace['counts']['pending_requests'], 'This fixture must distinguish episode counts from request counts.'
    assert episode_answer['metrics'][0]['value'] == workspace['counts']['episodes']
    expect(dialog.locator('.cc-thinking')).to_have_count(0)
    expect(dialog.locator('.cc-answer-metrics strong').first).to_have_text(format(workspace['counts']['episodes'], ','))
    selected = ask(page, dialog, 'What is the next step for SC-001?')
    assert {source.get('case_id') for source in selected['answer']['sources']} == {'SC-001'}
    ownership = ask(page, dialog, 'Who is responsible?')
    assert [card['id'] for card in ownership['answer']['cards']] == ['SC-001']
    assert {source.get('case_id') for source in ownership['answer']['sources']} == {'SC-001'}
    expect(dialog.locator('.cc-assistant-message').last.locator('.cc-answer-card')).to_have_count(1)
    expect(dialog.locator('.cc-assistant-message').last.locator('.cc-answer-card')).to_contain_text('SC-001')
    record('ownership_followup', {'first_question': 'What is the next step for SC-001?', 'followup': 'Who is responsible?', 'case_ids': [card['id'] for card in ownership['answer']['cards']], 'scoped_without_repeating_case_id': True})
    record('counts_history_readonly', {'conversation_id': payload['conversation_id'], 'pending_requests': metric['value'], 'authorized_episodes_from_actual_welcome_button': episode_answer['metrics'][0]['value'], 'case_version_before': before['version'], 'case_version_after': read(context, '/cases/SC-001')['version'], 'history_reloaded_from_server': True})
    context.close()


def test_context_chat_links_select_real_case_tabs_and_fields(browser):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    page = browser_login(context, 'clinician', '/clinical')
    before = read(context, '/cases/SC-001')
    dialog = open_chat(page)
    appointments = ask(page, dialog, 'Show appointments for SC-001')
    href = next(source['href'] for source in appointments['answer']['sources'] if '#case-appointments' in source['href'])
    dialog.locator('.cc-sources a').filter(has=page.locator('svg')).filter(has_text='SC-001').first.click()
    page.wait_for_url('**/cases/SC-001?tab=coordination#case-appointments')
    expect(page.get_by_role('tab', name='Coordination', exact=True)).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#case-appointments')).to_be_visible()
    page.wait_for_function("document.activeElement?.id === 'case-appointments'")
    assert page.locator('#case-appointments').evaluate('element => element.getBoundingClientRect().top >= 0 && element.getBoundingClientRect().top < innerHeight')

    # A restoring conversation keeps its composer focusable while the thread
    # response is pending; it becomes editable once that response completes.
    held_thread = []
    def hold_thread(route):
        held_thread.append(route)
    page.route('**/api/assistant/conversations/*', hold_thread)
    with page.expect_request('**/api/assistant/conversations/*'):
        dialog = open_chat(page)
    expect(dialog.locator('#context-chat-question')).to_have_attribute('readonly', '')
    expect(dialog.locator('#context-chat-question')).to_be_focused()
    assert held_thread
    held_thread[0].continue_()
    page.unroute('**/api/assistant/conversations/*', hold_thread)
    expect(dialog.locator('#context-chat-question')).to_be_editable()
    evidence = ask(page, dialog, 'What evidence is recorded for SC-001?')
    source = next(source for source in evidence['answer']['sources'] if '#case-evidence' in source['href'])
    dialog.locator('.cc-sources a[href="' + source['href'] + '"]').first.click()
    page.wait_for_url('**/cases/SC-001?tab=journey#case-evidence')
    expect(page.get_by_role('tab', name='Journey & evidence', exact=True)).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#case-evidence')).to_be_visible()
    page.wait_for_function("document.activeElement?.id === 'case-evidence'")
    assert read(context, '/cases/SC-001')['version'] == before['version']
    page.screenshot(path=str(ARTIFACTS/'source-link-opens-case-field.png'), full_page=False)
    record('record_links', {'appointments_href': href, 'evidence_href': source['href'], 'actual_tab_selection_and_field_focus': True, 'composer_focused_while_thread_restores': True, 'case_version_unchanged': True})
    context.close()


def test_context_chat_provider_scope_and_role_switch_clear_old_answers(browser):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = browser_login(context, 'navigator', '/worklist')
    all_cases = read(context, '/cases')
    dialog = open_chat(page)
    question = 'Who is responsible for SC-001?'
    original = ask(page, dialog, question)
    page.keyboard.press('Escape')
    page.get_by_label('Synthetic demo role', exact=True).select_option('receiver_a')
    page.wait_for_url('**/receiving')
    expect(page.get_by_role('heading', name='A clear handoff. Shared responsibility.')).to_be_visible()
    # Hold the fresh account-context response while a person starts typing.
    # The initialization response must not replace the newer draft.
    held_context = []
    def hold_context(route):
        held_context.append(route)
    page.route('**/api/assistant/context', hold_context)
    with page.expect_request('**/api/assistant/context'):
        dialog = open_chat(page)
    opening_draft = 'Keep this question while the workspace opens'
    dialog.locator('#context-chat-question').fill(opening_draft)
    assert held_context
    with page.expect_response(lambda response: response.request.method == 'GET' and response.url.endswith('/api/assistant/conversations')) as initialized:
        held_context[0].continue_()
        page.unroute('**/api/assistant/context', hold_context)
    initialized.value.finished()
    page.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    expect(dialog.locator('#context-chat-question')).to_have_value(opening_draft)
    expect(dialog.locator('.cc-user-message')).to_have_count(0)
    expect(dialog.locator('.cc-answer-card')).to_have_count(0)
    assert context.request.get(API+'/assistant/conversations/'+original['conversation_id']).status == 404
    packets = read(context, '/referrals')
    permitted = {packet['case_id'] for packet in packets}
    forbidden = next(case for case in all_cases if case['id'] not in permitted)
    denied = ask(page, dialog, 'Tell me about ' + forbidden['id'])
    assert denied['answer']['cards'] == [] and denied['answer']['sources'] == []
    assert forbidden['patient_name'] not in denied['answer']['summary']
    answer = ask(page, dialog, 'Show my recorded appointments')
    links = [source['href'] for source in answer['answer']['sources']]
    assert links and all(link.startswith('/receiving#referral-') for link in links)
    assert not dialog.locator('a[href^="/cases/"]').count()
    target = answer['answer']['sources'][0]['href']
    dialog.locator('.cc-sources a[href="' + target + '"]').first.click()
    page.wait_for_url('**' + target)
    field = page.locator('#' + target.split('#')[1])
    expect(field).to_be_visible()
    page.wait_for_function('(id) => document.activeElement?.id === id', arg=target.split('#')[1])
    record('provider_scope', {'old_thread_denied_after_role_switch': True, 'previous_ui_answers_cleared': True, 'typing_preserved_during_context_initialization': True, 'forbidden_case_probe_returned_no_record': True, 'provider_source_links': links, 'actual_referral_field_focused': True})
    context.close()


def test_context_chat_mobile_patient_rtl_keyboard_and_no_overflow(browser):
    client = api_client('patient')
    initial = client.get('/cases/SC-001').json()
    original_language = initial.get('language') or 'en'
    case_command(client, 'SC-001', '/cases/SC-001/preferences', {'language': 'en', 'channel': 'portal'})
    context = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, reduced_motion='reduce')
    page = browser_login(context, 'patient', '/patient')
    try:
        expect(page.locator('.patient-view')).to_have_attribute('lang', 'en')
        dialog = open_chat(page)
        expect(dialog).to_have_attribute('dir', 'ltr')
        no_overflow(page, dialog)
        page.keyboard.press('Escape')
        page.locator('.pt-language').click()
        expect(page.locator('.patient-view')).to_have_attribute('lang', 'ar')
        expect(page.get_by_role('button', name='اسأل سهيل', exact=True)).to_be_visible()
        before = read(context, '/cases/SC-001')['version']
        dialog = open_chat(page)
        expect(dialog).to_have_attribute('dir', 'rtl')
        answer = ask(page, dialog, 'من هو فريق رعايتي؟')
        expect(dialog.locator('.cc-answer-text').last).to_have_attribute('dir', 'auto')
        no_overflow(page, dialog)
        assert all(source['href'].startswith('/patient#') for source in answer['answer']['sources'])
        assert read(context, '/cases/SC-001')['version'] == before
        page.screenshot(path=str(ARTIFACTS/'patient-chat-arabic-mobile.png'), full_page=False)
        page.keyboard.press('Escape')
        expect(page.get_by_role('button', name='اسأل سهيل', exact=True)).to_be_focused()
        record('patient_mobile', {'viewport': {'width': 390, 'height': 844}, 'arabic_dialog_direction': 'rtl', 'answer_uses_recorded_language_with_dir_auto': True, 'horizontal_overflow': False, 'chat_did_not_change_case_version': True})
    finally:
        context.close()
        case_command(client, 'SC-001', '/cases/SC-001/preferences', {'language': original_language, 'channel': initial.get('preferred_channel') or 'portal'})
        client.close()


def test_context_chat_failed_send_preserves_a_newer_draft(browser):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    page = browser_login(context, 'navigator', '/worklist')
    before = read(context, '/cases/SC-001')['version']
    dialog = open_chat(page)
    held_message = []
    def hold_message(route):
        held_message.append(route)
    page.route('**/api/assistant/conversations/*/messages', hold_message)
    question = dialog.locator('#context-chat-question')
    question.fill('Show my open tasks')
    with page.expect_request('**/api/assistant/conversations/*/messages'):
        dialog.get_by_role('button', name='Send message', exact=True).click()
    expect(dialog.locator('.cc-thinking')).to_be_visible()
    newer_draft = 'Show my recorded appointments'
    question.fill(newer_draft)
    assert held_message
    held_message[0].fulfill(status=503, content_type='application/json', body=json.dumps({'detail': 'Controlled connection interruption for verification.'}))
    expect(dialog.locator('.cc-thinking')).to_have_count(0)
    expect(dialog.locator('.cc-error')).to_contain_text('Controlled connection interruption')
    expect(question).to_have_value(newer_draft)
    expect(dialog.get_by_role('button', name='Send message', exact=True)).to_be_enabled()
    assert read(context, '/cases/SC-001')['version'] == before
    record('failed_send_draft', {'newer_draft_preserved': True, 'error_visible': True, 'automatic_message_retry': False, 'case_version_unchanged': True, 'fault_injection': 'Local browser503 before the message reaches the API'})
    context.close()
