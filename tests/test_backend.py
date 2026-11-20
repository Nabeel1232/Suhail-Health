"""Independent persisted authorization, recovery and endpoint acceptance assertions."""
import copy
import uuid
from datetime import timedelta
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from services.api.db import (Base, Case, Task, Communication, Consultation, Handoff,
    Appointment, Evidence, Escalation, Outbox, Setting, User, SourceEvent, SourceArtifact, AccessGrant, get_db)
from services.api import domain as d
from services.api.worker import run_once
from services.api.seed import actor
from services.api.auth import password_hash


@pytest.fixture
def store(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'acceptance.db'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        yield db, Session
    engine.dispose()


def create(db, suffix='one', **overrides):
    data = {'case_id': 'accept-' + suffix, 'dataset': 'acceptance', 'event_id': 'result-' + suffix,
        'source_organization': 'source-clinic', 'patient_id': 'patient-' + suffix,
        'patient_name': 'Fictional ' + suffix, 'order_id': 'order-' + suffix,
        'result_version': 1, 'test_code': 'FIT_POSITIVE',
        'issued_at': (d.clock(db) - timedelta(hours=2)).isoformat(),
        'identity_verified': True, 'trusted_urgent': False, **overrides}
    result = d.intake(db, actor('navigator'), data)
    return db.get(Case, result['id'])


def cmd(db, case, kind, role='navigator', **fields):
    db.refresh(case)
    a = actor(role, case.patient_id)
    return d.command(db, a, case.id, kind, {'expected_version': case.version,
        'idempotency_key': uuid.uuid4().hex, **fields})


def denied(db, expected, fn, *args, **kwargs):
    with pytest.raises(HTTPException) as result:
        fn(*args, **kwargs)
    assert result.value.status_code == expected
    db.rollback()


def evidence(db, case, kind, verify=True, **extra):
    result = cmd(db, case, 'evidence_add', role='clinician', type=kind,
        reference='synthetic://accept/' + uuid.uuid4().hex,
        patient_id=case.patient_id, order_id=case.order_id, result_version=case.result_version,
        document_text='Actual project synthetic source fixture for this evidence type: ' + kind, **extra)
    if verify:
        cmd(db, case, 'evidence_verify', role='clinician', evidence_id=result['record_id'],
            verified=True, reason='Source body and patient/order/current version checked; recorded clinical plan reviewed')
    return db.get(Evidence, result['record_id'])


def notify(db, case, understanding='passed'):
    result = cmd(db, case, 'communication', language='en', channel='portal')
    run_once(db, deliver_external=False, case_id=case.id)
    cmd(db, case, 'acknowledgement', role='patient', communication_id=result['record_id'])
    cmd(db, case, 'understanding', role='patient', communication_id=result['record_id'], outcome=understanding)
    return db.get(Communication, result['record_id'])


def accepted(db, case, receiver='provider-a', scope='task'):
    result = cmd(db, case, 'handoff', receiver=receiver, scope=scope, reason='Diagnostic follow-up')
    cmd(db, case, 'handoff_accept', role='receiver_a' if receiver == 'provider-a' else 'receiver_b', handoff_id=result['record_id'])
    return db.get(Handoff, result['record_id'])


def ready(db, case):
    notify(db, case)
    accepted(db, case)
    result = cmd(db, case, 'appointment_create', role='receiver_a', provider='provider-a', scheduled_at=d.clock(db).isoformat())
    cmd(db, case, 'appointment_event', role='receiver_a', appointment_id=result['record_id'], status='attended')
    for kind in ['investigation', 'reviewed_outcome', 'patient_updated']:
        evidence(db, case, kind)


def test_AT01_source_linked_owned_case_and_persistence(store):
    db, Session = store
    case = create(db)
    assert case.owner == 'navigation-team'
    assert case.issued_at < case.created_at
    assert len(d.rows(db, Task, case.id)) >= 9
    assert all(t.assignee and t.next_action and t.due_at for t in d.rows(db, Task, case.id))
    assert db.scalar(select(SourceEvent).where(SourceEvent.case_id == case.id)).result_version == 1
    db.close()
    with Session() as reopened:
        assert reopened.get(Case, case.id).owner == 'navigation-team'


@pytest.mark.parametrize('overrides,reason', [({'identity_verified': False}, 'identity_conflict'),
    ({'test_code': 'UNKNOWN'}, 'unsupported_pathway'), ({'staffing_available': False}, 'missing_staffing_mapping')])
def test_AT02_owned_quarantine_and_authorized_recovery(store, overrides, reason):
    db, _ = store
    case = create(db, **overrides)
    assert case.quarantine_reason == reason
    assert all(t.assignee for t in d.rows(db, Task, case.id))
    denied(db, 409, cmd, db, case, 'communication', language='en', channel='portal')
    gate = d.rows(db, Task, case.id)[0]
    denied(db, 409, cmd, db, case, 'task', task_id=gate.id, status='completed', reason='Bypass attempt')
    denied(db, 403, cmd, db, case, 'reconciliation', role='admin', identity_verified=True,
        pathway='colorectal-fit', source_reference='synthetic://identity', reason='Must be qualified')
    cmd(db, case, 'reconciliation', identity_verified=True, pathway='colorectal-fit',
        source_reference='synthetic://source/identity', reason='Explicit source matching evidence reviewed')
    assert case.quarantine_reason is None
    assert len(d.rows(db, Task, case.id)) >= 10


def test_AT03_delivery_acknowledgement_understanding_separate(store, monkeypatch):
    db, _ = store
    from services.api.auth import require_actor
    from services.api.db import AuditEvent
    from services.api.main import app
    case = create(db)
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db)
    monkeypatch.setitem(app.dependency_overrides, require_actor, lambda: actor('navigator'))
    client = TestClient(app)
    response = client.get('/cases/' + case.id)
    assert response.status_code == 200
    previews = response.json()['notification_templates']
    assert set(previews) == {'en', 'ar'}
    result = cmd(db, case, 'communication', language='ar', channel='portal')
    msg = db.get(Communication, result['record_id'])
    assert msg.body == previews['ar']
    assert msg.delivery_status == 'queued' and msg.acknowledged_at is None
    denied(db, 409, cmd, db, case, 'acknowledgement', role='patient', communication_id=msg.id)
    run_once(db, deliver_external=False, case_id=case.id)
    assert msg.delivery_status == 'delivered' and msg.acknowledged_at is None and msg.understanding == 'unknown'
    cmd(db, case, 'acknowledgement', role='patient', communication_id=msg.id)
    assert msg.understanding == 'unknown'
    monkeypatch.setitem(app.dependency_overrides, require_actor, lambda: actor('patient', case.patient_id))
    assert 'notification_templates' not in client.get('/cases/' + case.id).json()
    answers = {'next_step': 'wait', 'meaning': 'needs_follow_up'}
    response = client.post(f'/communications/{msg.id}/understanding', json={
        'expected_version': case.version, 'idempotency_key': uuid.uuid4().hex,
        'outcome': 'needs_help', 'answers': answers})
    assert response.status_code == 200 and 'audit' not in response.json()
    assert any(event.event_type == 'understanding' and event.detail['answers'] == answers
        for event in d.rows(db, AuditEvent, case.id))
    assert any(t.type == 'understanding_help' and t.assignee and t.status != 'completed' for t in d.rows(db, Task, case.id))


def test_AT04_both_human_consultations_and_agreed_owned_action(store):
    db, _ = store
    case = create(db)
    question = cmd(db, case, 'consultation', role='patient', type='patient_to_clinician', question='What happens next?', recipient='clinician')
    denied(db, 403, cmd, db, case, 'consultation_reply', role='navigator', consultation_id=question['record_id'],
        reply='Pretend clinical reply', agreed_action='act', action_owner='navigation-team')
    cmd(db, case, 'consultation_reply', role='clinician', consultation_id=question['record_id'],
        reply='We will explain the documented follow-up assessment.', agreed_action='Arrange the assessment discussion', action_owner='navigation-team')
    consult = cmd(db, case, 'consultation', role='clinician', type='clinician_to_specialist', question='Please review the documented next coordination step.', recipient='specialist')
    cmd(db, case, 'consultation_reply', role='specialist', consultation_id=consult['record_id'],
        reply='Return the investigation report for review.', agreed_action='Obtain report', action_owner='navigation-team')
    assert len(d.rows(db, Consultation, case.id)) == 2
    assert all(c.human_author and c.agreed_action and c.action_owner for c in d.rows(db, Consultation, case.id))
    assert sum(t.type.startswith('agreed_action:') and t.status != 'completed' for t in d.rows(db, Task, case.id)) == 2


def test_AT05_rejection_preserves_owner_and_acceptance_has_scope(store):
    db, _ = store
    case = create(db)
    original = case.owner
    proposed = cmd(db, case, 'handoff', receiver='provider-a', scope='episode', reason='Request')
    assert case.owner == original
    cmd(db, case, 'handoff_reject', role='receiver_a', handoff_id=proposed['record_id'], reason='No capacity')
    assert case.owner == original
    accepted(db, case, 'provider-b', 'task')
    assert case.owner == original
    accepted(db, case, 'provider-a', 'episode')
    assert case.owner == 'provider-a'


def test_AT06_timeouts_no_show_and_cancellation_have_recovery(store):
    db, _ = store
    case = create(db)
    result = cmd(db, case, 'handoff', receiver='provider-a', scope='episode', reason='Await reply')
    db.add(Setting(key='demo_clock', value={'hours': 25})); db.commit()
    run_once(db, deliver_external=False, case_id=case.id)
    assert db.get(Handoff, result['record_id']).status == 'expired'
    assert case.owner == 'navigation-team'
    assert 'handoff_timeout' in case.delay_reasons
    accepted(db, case, 'provider-b')
    result = cmd(db, case, 'appointment_create', role='receiver_b', provider='provider-b', scheduled_at=d.clock(db).isoformat())
    cmd(db, case, 'appointment_event', role='receiver_b', appointment_id=result['record_id'], status='no_show')
    assert 'no_show' in case.delay_reasons
    assert any(t.type == 'appointment_recovery' and t.assignee for t in d.rows(db, Task, case.id))


def test_AT07_urgent_independent_of_model_and_ack_separate(store, monkeypatch):
    db, _ = store
    monkeypatch.setenv('GROQ_API_KEY', '')
    case = create(db, trusted_urgent=True)
    escalation = d.rows(db, Escalation, case.id)[0]
    assert case.urgent and escalation.recipient == 'clinician'
    db.add(Setting(key='demo_clock', value={'hours': 2})); db.commit()
    run_once(db, deliver_external=False, case_id=case.id)
    assert escalation.escalated_at
    cmd(db, case, 'escalation_ack', role='clinician', escalation_id=escalation.id)
    denied(db, 409, cmd, db, case, 'communication', language='en', channel='portal')
    assert escalation.disposition is None
    cmd(db, case, 'escalation_disposition', role='clinician', escalation_id=escalation.id,
        decision='Reviewed and resume configured follow-up', reason='Clinician assessed source flag')
    assert case.urgent  # source flag is retained, never model-downgraded
    cmd(db, case, 'communication', language='en', channel='portal')


def test_AT08_booking_attendance_and_verified_assessment_separate(store):
    db, _ = store
    case = create(db)
    accepted(db, case)
    result = cmd(db, case, 'appointment_create', role='receiver_a', provider='provider-a', scheduled_at=d.clock(db).isoformat())
    assert not any(e.type == 'investigation' for e in d.rows(db, Evidence, case.id))
    assert next(t for t in d.rows(db, Task, case.id) if t.type == 'attendance').status != 'completed'
    cmd(db, case, 'appointment_event', role='receiver_a', appointment_id=result['record_id'], status='attended')
    assert not any(e.type == 'investigation' for e in d.rows(db, Evidence, case.id))
    ev = evidence(db, case, 'investigation', verify=False)
    assert ev.verification == 'pending'
    assert not d.closure_check(db, case)['allowed']


@pytest.mark.parametrize('invalid', ['wrong_patient', 'wrong_order', 'stale', 'fabricated', 'unverified'])
def test_AT09_invalid_evidence_cannot_clear_endpoint(store, invalid):
    db, _ = store
    case = create(db)
    fields = {'type': 'investigation', 'reference': 'synthetic://claim/' + invalid,
        'patient_id': case.patient_id, 'order_id': case.order_id, 'result_version': case.result_version}
    if invalid != 'fabricated': fields['document_text'] = 'Retained synthetic source body for matching checks'
    if invalid == 'wrong_patient': fields['patient_id'] = 'wrong'
    if invalid == 'wrong_order': fields['order_id'] = 'wrong'
    if invalid == 'stale': fields['result_version'] = 0
    result = cmd(db, case, 'evidence_add', role='clinician', **fields)
    if invalid != 'unverified':
        denied(db, 409, cmd, db, case, 'evidence_verify', role='clinician',
            evidence_id=result['record_id'], verified=True, reason='Attempt invalid source verification')
    assert not d.closure_check(db, case)['allowed']
    assert next(t for t in d.rows(db, Task, case.id) if t.type == 'investigation').status != 'completed'


def test_AT09_valid_uploaded_source_requires_authorized_verification(store):
    db, _ = store
    case = create(db)
    ev = evidence(db, case, 'investigation', verify=False)
    denied(db, 403, cmd, db, case, 'evidence_verify', role='navigator', evidence_id=ev.id, verified=True, reason='Wrong role')
    cmd(db, case, 'evidence_verify', role='clinician', evidence_id=ev.id, verified=True, reason='Retained document and current patient/order source matching reviewed')
    assert ev.verification == 'verified'
    assert db.get(SourceArtifact, ev.reference).content_hash


def test_AT10_onward_endpoint_blocks_even_after_referral_acceptance(store):
    db, _ = store
    case = create(db)
    ready(db, case)
    evidence(db, case, 'reviewed_outcome', requires_onward=True)
    accepted(db, case, 'provider-b')
    denied(db, 409, cmd, db, case, 'disposition', role='clinician', category='completed_required_care', reason='Attempt before treatment')
    assert case.requires_onward
    assert any(t.type == 'treatment_initiated' and t.status != 'completed' for t in d.rows(db, Task, case.id))
    evidence(db, case, 'treatment_initiated')
    assert d.closure_check(db, case)['allowed']
    cmd(db, case, 'disposition', role='clinician', category='completed_required_care', reason='Current endpoint complete')
    assert case.disposition == 'completed_required_care' and not case.residual_need


def test_AT11_corrected_result_reopens_closed_case_and_old_version_stays_old(store):
    db, _ = store
    case = create(db)
    ready(db, case)
    cmd(db, case, 'disposition', role='clinician', category='completed_required_care', reason='Care completed')
    create(db, event_id='correction', result_version=2)
    assert case.disposition == 'open' and case.closed_at is None and case.result_version == 2
    assert all(e.status == 'superseded' for e in d.rows(db, Evidence, case.id))
    create(db, event_id='delayed-old', result_version=1)
    assert case.result_version == 2
    assert not d.closure_check(db, case)['allowed']


@pytest.mark.parametrize('category', ['informed_decline', 'unable_to_contact', 'clinically_resolved', 'other_exception'])
def test_AT12_exception_category_and_residual_need_preserved(store, category):
    db, _ = store
    case = create(db)
    if category in {'informed_decline', 'unable_to_contact'}:
        denied(db, 409, cmd, db, case, 'disposition', role='clinician', category=category,
            reason='Attempt without outreach', residual_need='Diagnostic assessment remains needed')
        evidence(db, case, 'outreach'); evidence(db, case, 'exception_review')
    cmd(db, case, 'disposition', role='clinician', category=category, reason='Authorized human rationale', residual_need='Diagnostic assessment remains needed')
    assert case.disposition == category and case.residual_need


def test_AT13_minimum_packet_crosspatient_and_admin_limits(store):
    db, _ = store
    case = create(db)
    other = create(db, suffix='other')
    handoff = accepted(db, case)
    packet = d.referral_packet(db, handoff)
    assert 'audit' not in packet and 'evidence' not in packet and 'communications' not in packet
    denied(db, 403, d.authorize_case, db, actor('receiver_a'), case.id)
    denied(db, 403, d.authorize_case, db, actor('receiver_b'), case.id, packet=True)
    denied(db, 403, d.authorize_case, db, actor('patient', case.patient_id), other.id)
    denied(db, 403, cmd, db, case, 'disposition', role='admin', category='completed_required_care', reason='Admin is not clinician')


def test_AT14_replay_has_one_handoff_and_worker_restart_preserves_due(store):
    db, Session = store
    case = create(db)
    envelope = {'expected_version': case.version, 'idempotency_key': 'stable-referral-command',
        'receiver': 'provider-a', 'scope': 'episode', 'reason': 'Replay-safe'}
    d.command(db, actor('navigator'), case.id, 'handoff', envelope)
    d.command(db, actor('navigator'), case.id, 'handoff', envelope)
    assert len(d.rows(db, Handoff, case.id)) == 1
    original_due = d.rows(db, Handoff, case.id)[0].due_at
    db.close()
    with Session() as restarted:
        restarted.add(Setting(key='demo_clock', value={'hours': 25})); restarted.commit()
        run_once(restarted, deliver_external=False, case_id=case.id)
        handoff = d.rows(restarted, Handoff, case.id)[0]
        assert handoff.due_at == original_due and handoff.status == 'expired'


def test_AT14_bounded_failure_enters_owned_deadletter(store):
    db, _ = store
    case = create(db)
    cmd(db, case, 'communication', language='en', channel='portal')
    job = d.rows(db, Outbox, case.id)[0]
    job.payload = {**job.payload, 'simulate_failure': True}; db.commit()
    for _ in range(3):
        job.next_attempt_at = '2000-01-01T00:00:00+00:00'; db.commit()
        run_once(db, deliver_external=False, case_id=case.id)
    assert job.status == 'dead_letter' and job.attempts == 3 and job.owner
    assert any(t.type.startswith('integration_recovery:') and t.assignee for t in d.rows(db, Task, case.id))


def test_AT17_overdue_unassigned_fallback_and_rejected_visible(store):
    db, _ = store
    case = create(db)
    result = cmd(db, case, 'task', type='transport_help', assignee='', next_action='Arrange accessible transport')
    assert db.get(Task, result['record_id']).assignee == case.backup_queue
    db.add(Setting(key='demo_clock', value={'hours': 49})); db.commit()
    run_once(db, deliver_external=False, case_id=case.id)
    snapshot = d.serialize_case(db, case, actor('navigator'))
    assert any(t['status'] == 'overdue' and t['due_at'] and t['assignee'] for t in snapshot['tasks'])
    backup_type = 'overdue_escalation:' + result['record_id']
    backups = [item for item in d.rows(db, Task, case.id) if item.type == backup_type]
    assert len(backups) == 1
    backup = backups[0]
    assert backup.assignee == case.backup_queue and not backup.required
    assert backup.next_action == 'Review overdue transport help and reassign or act'
    cmd(db, case, 'task', task_id=backup.id, status='completed', reason='Backup team reviewed this overdue work')
    cmd(db, case, 'task', task_id=result['record_id'], status='in_progress')
    for _ in range(2):
        run_once(db, deliver_external=False, case_id=case.id)
    assert db.get(Task, result['record_id']).status == 'overdue'
    assert [item.id for item in d.rows(db, Task, case.id) if item.type == backup_type] == [backup.id]


def test_authenticated_API_cookies_versions_patient_scope_and_AT20_metrics(store):
    db, _ = store
    from services.api.main import app
    create(db)
    create(db, suffix='other', identity_verified=False)
    for role in ['navigator', 'clinician', 'patient', 'admin', 'receiver_a']:
        a = actor(role, 'patient-one')
        db.add(User(id='demo-' + role, email=role+'@demo.local', name=a['name'], role=role,
            organization=a['organization'], patient_id=a['patient_id'], password_hash=password_hash('test-pass-long-enough')))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        assert client.get('/cases').status_code == 401
        assert client.post('/auth/demo', json={'role': 'patient'}).status_code == 200
        assert client.get('/cases').json()[0]['id'] == 'accept-one'
        assert client.get('/cases/accept-other').status_code == 403
        assert client.post('/auth/demo', json={'role': 'admin'}).status_code == 200
        metrics = client.get('/metrics').json()
        assert metrics['denominator'] == 2 and metrics['care_completed'] == 0 and metrics['residual_need'] == 2
        assert metrics['reassurance'] is None
        assert client.post('/auth/logout').status_code == 200
        assert client.get('/auth/me').status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_outcome_metrics_use_episode_denominators_server_clock_and_completed_tasks(store, monkeypatch):
    db, _ = store
    from services.api.auth import require_actor
    from services.api.main import app
    monkeypatch.setattr(d, 'settings', lambda: {'demo_mode': True})
    db.add(Setting(key='demo_clock', value={'base': '2026-11-15T08:00:00+00:00', 'hours': 0}))
    db.commit()
    now = d.clock(db)
    closed = create(db, suffix='closed', issued_at=(now - timedelta(days=3)).isoformat())
    ready(db, closed)
    cmd(db, closed, 'disposition', role='clinician', category='completed_required_care', reason='Verified required care')
    missed = create(db, suffix='missed', issued_at=(now - timedelta(days=9)).date().isoformat())
    notify(db, missed, understanding='needs_help')
    accepted(db, missed)
    booking = cmd(db, missed, 'appointment_create', role='receiver_a', provider='provider-a', scheduled_at=now.isoformat())
    cmd(db, missed, 'appointment_event', role='receiver_a', appointment_id=booking['record_id'], status='no_show')
    oldest = create(db, suffix='oldest', issued_at='unknown legacy issue date')
    oldest.created_at = (now - timedelta(days=34)).isoformat()
    for task in d.rows(db, Task, oldest.id):
        if task.type == 'notification':
            task.due_at = (now - timedelta(hours=1)).isoformat()
        if task.type == 'appointment':
            task.due_at = (now + timedelta(hours=12)).isoformat()
        if task.type == 'acknowledgement':
            task.status = 'completed'
            task.completed_at = now.isoformat()
    outside = create(db, suffix='outside')
    outside.source_organization = 'outside-clinic'
    db.commit()

    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db)
    monkeypatch.setitem(app.dependency_overrides, require_actor, lambda: actor('navigator'))
    response = TestClient(app).get('/metrics')
    assert response.status_code == 200
    result = response.json()
    outcomes = result['outcomes']
    assert result['denominator'] == outcomes['episodes'] == 3
    assert outcomes['as_of'] == now.isoformat()
    assert outcomes['time_to']['notification'] == {'median_hours': 148, 'p90_hours': 224, 'n': 2,
        'target_hours': 48, 'within_target': 2}
    assert outcomes['time_to']['acknowledgement']['n'] == 2
    assert outcomes['time_to']['closure'] == {'median_hours': 72, 'p90_hours': 72, 'n': 1,
        'target_hours': None, 'within_target': None}
    assert outcomes['rates']['appointment_attended_of_booked'] == {'numerator': 1, 'denominator': 2}
    assert outcomes['rates']['documented_closure'] == {'numerator': 1, 'denominator': 3}
    assert outcomes['unresolved'] == {'open': 2, 'age_days': {'0-2': 0, '3-7': 0, '8-30': 1, '30+': 1},
        'cases_with_overdue_work': 1}
    assert outcomes['sla']['due_within_24h'] == outcomes['sla']['overdue'] == 1
    assert sum(owner['open_tasks'] for owner in outcomes['by_owner']) == sum(outcomes['sla'].values())
    assert {'no_show', 'understanding_needs_help'} <= {row['code'] for row in outcomes['drop_off']}


def test_impact_report_requires_staff_and_returns_the_optional_artifact(tmp_path, monkeypatch):
    import json
    from services.api import main
    from services.api.auth import require_actor
    monkeypatch.setattr(main, 'ROOT', tmp_path)
    client = TestClient(main.app)
    # The unauthenticated auth dependency still requires a database session.
    monkeypatch.setitem(main.app.dependency_overrides, get_db, lambda: None)
    assert client.get('/impact').status_code == 401
    monkeypatch.setitem(main.app.dependency_overrides, require_actor, lambda: actor('navigator'))
    assert client.get('/impact').status_code == 404
    assert client.get('/impact/method').status_code == 404
    report = {'schema': 'suhail-impact-v1', 'label': 'Simulated cohort', 'cohort': {'n': 12}}
    artifact = tmp_path / 'reports' / 'impact' / 'impact-summary.json'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps(report), encoding='utf-8')
    method = tmp_path / 'docs' / 'IMPACT_MODEL.md'
    method.parent.mkdir()
    method.write_text('# Simulated cohort method\n', encoding='utf-8')
    for role in ('navigator', 'clinician', 'admin'):
        monkeypatch.setitem(main.app.dependency_overrides, require_actor, lambda role=role: actor(role))
        response = client.get('/impact')
        assert response.status_code == 200 and response.json() == report
    response = client.get('/impact/method')
    assert response.status_code == 200 and response.text == '# Simulated cohort method\n'
    assert response.headers['content-type'].startswith('text/plain')
    monkeypatch.setitem(main.app.dependency_overrides, require_actor, lambda: actor('patient'))
    assert client.get('/impact').status_code == 403
    assert client.get('/impact/method').status_code == 403


def test_patient_experience_is_scoped_observed_and_separate_from_understanding(store):
    db, _ = store
    case = create(db)
    denied(db, 403, cmd, db, case, 'experience', role='clinician', confidence=4, reassurance=3)
    denied(db, 422, cmd, db, case, 'experience', role='patient', confidence=6, reassurance=3)
    cmd(db, case, 'experience', role='patient', confidence=4, reassurance=3, comment='Synthetic patient self-report')
    data = d.serialize_case(db, case, actor('patient', case.patient_id))
    assert len(data['experience']) == 1 and data['experience'][0]['confidence'] == 4
    assert next(t for t in d.rows(db, Task, case.id) if t.type == 'understanding').status != 'completed'


def test_corrected_result_rejects_old_acknowledgement_and_supersedes_old_queued_notice(store):
    db, _ = store
    case = create(db)
    result = cmd(db, case, 'communication', language='en', channel='portal')
    create(db, event_id='corrected-result-before-delivery', result_version=2)
    run_once(db, deliver_external=False, case_id=case.id)
    assert db.get(Communication, result['record_id']).delivery_status == 'superseded'
    denied(db, 409, cmd, db, case, 'acknowledgement', role='patient', communication_id=result['record_id'])
    assert next(t for t in d.rows(db, Task, case.id) if t.type == 'notification').status != 'completed'


def test_demo_clock_has_reproducible_frozen_base_and_persisted_advances(store):
    db, Session = store
    db.add(Setting(key='demo_clock', value={'base': '2026-11-15T08:00:00+00:00', 'hours': 2})); db.commit()
    assert d.clock(db).isoformat() == '2026-11-15T10:00:00+00:00'
    db.close()
    with Session() as reopened:
        assert d.clock(reopened).isoformat() == '2026-11-15T10:00:00+00:00'


def test_dated_seed_waits_for_notification_claimed_by_live_worker(store, tmp_path, monkeypatch):
    from services.api import seed as seeding

    db, Session = store
    monkeypatch.setattr(seeding, 'ROOT', tmp_path)
    monkeypatch.setattr(seeding, 'NAMES', {'SC-008': 'Hamad Faris'})
    notification_time = seeding.DEMO_BASE - timedelta(hours=335)
    claimed = []

    def seed_worker(session, *, deliver_external, case_id):
        job = session.scalar(select(Outbox).where(Outbox.case_id == case_id,
            Outbox.kind == 'notification', Outbox.status == 'pending'))
        if job is None:
            return run_once(session, deliver_external=deliver_external, case_id=case_id)
        job.status = 'processing'
        job.lease_until = (notification_time + timedelta(minutes=2)).isoformat()
        claimed.append(job.id)
        session.commit()
        return run_once(session, deliver_external=deliver_external, case_id=case_id)

    def complete_live_delivery(_):
        with Session() as live:
            assert d.clock(live) == notification_time
            job = live.get(Outbox, claimed[0])
            job.lease_until = notification_time.isoformat()
            live.commit()
            run_once(live, deliver_external=False, case_id=job.case_id)

    monkeypatch.setattr(seeding, 'run_once', seed_worker)
    monkeypatch.setattr(seeding, 'sleep', complete_live_delivery)
    seeding.seed(db)
    assert len(claimed) == 1
    message = db.scalar(select(Communication).where(Communication.case_id == 'SC-008'))
    assert message.delivered_at == notification_time.isoformat()
    assert message.acknowledged_at == (seeding.DEMO_BASE - timedelta(hours=330)).isoformat()
    assert db.get(Case, 'SC-008').disposition == 'completed_required_care'
    assert d.clock(db) == seeding.DEMO_BASE


def test_org_bound_connector_credentials_reject_impersonation_and_foreign_provider(store):
    db, _ = store
    from services.api.main import app
    from services.api.config import settings
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        tokens = settings()['connector_tokens']
        assert len(set(tokens.values())) == 3
        me = client.get('/auth/me', headers={'X-Connector-Token': tokens['provider-a']})
        assert me.status_code == 200 and me.json()['organization'] == 'provider-a'
        assert client.get('/auth/me', headers={'X-Connector-Token': tokens['provider-a'], 'X-Organization': 'source-clinic'}).status_code == 403
        assert client.get('/auth/me', headers={'X-Connector-Token': tokens['provider-a'], 'X-Organization': 'provider-b'}).status_code == 403
        assert client.get('/auth/me', headers={'X-Connector-Token': 'invalid-token'}).status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_packet_revocation_removes_grant_without_rewriting_ownership(store):
    db, _ = store
    case = create(db)
    accepted(db, case, scope='episode')
    grant = d.rows(db, AccessGrant, case.id)[0]
    assert d.permitted_grant(db, actor('receiver_a'), case.id)
    cmd(db, case, 'access_revoke', grant_id=grant.id, reason='Authorized sharing basis withdrawn')
    assert case.owner == 'provider-a'
    assert not d.permitted_grant(db, actor('receiver_a'), case.id)
    denied(db, 403, d.authorize_case, db, actor('receiver_a'), case.id, packet=True)


def test_source_event_identity_cannot_be_reused_for_another_payload(store):
    db, _ = store
    case = create(db)
    denied(db, 409, create, db, patient_id='different-patient')
    assert db.get(Case, case.id).patient_id == 'patient-one'


def test_proposed_case_identity_cannot_overwrite_another_order(store):
    db, _ = store
    case = create(db)
    denied(db, 409, create, db, suffix='other', case_id=case.id)
    assert db.get(Case, case.id).order_id == 'order-one'


def test_cancelled_required_task_cannot_waive_declared_endpoint(store):
    db, _ = store
    case = create(db)
    ready(db, case)
    attendance = next(t for t in d.rows(db, Task, case.id) if t.type == 'attendance')
    # Simulate a historical integration/admin cancellation; it is not a clinical waiver.
    attendance.status = 'cancelled'; db.commit()
    check = d.closure_check(db, case)
    assert not check['allowed'] and 'open_required_task:attendance' in check['missing']
    denied(db, 409, cmd, db, case, 'disposition', role='clinician', category='completed_required_care', reason='Cancelled is not completed')


def test_specialist_service_grant_cannot_be_used_by_an_unrelated_organization(store):
    db, _ = store
    case = create(db)
    result = cmd(db, case, 'consultation', role='clinician', type='clinician_to_specialist',
        question='Please review the documented evidence', recipient='specialist')
    unrelated = {**actor('specialist'), 'organization': 'unrelated-specialist-service', 'id': 'other-specialist'}
    denied(db, 403, d.authorize_case, db, unrelated, case.id)
    assert d.authorize_case(db, actor('specialist'), case.id).id == case.id
    denied(db, 403, d.command, db, unrelated, case.id, 'consultation_reply',
        {'expected_version': case.version, 'idempotency_key': uuid.uuid4().hex,
         'consultation_id': result['record_id'], 'reply': 'Unauthorized reply', 'agreed_action': 'Proceed', 'action_owner': 'navigation-team'})


def test_normal_deployment_ignores_persisted_demonstration_clock(store, monkeypatch):
    db, _ = store
    from datetime import datetime, timezone
    db.add(Setting(key='demo_clock', value={'base': '2000-01-01T00:00:00+00:00', 'hours': 9000})); db.commit()
    monkeypatch.setattr(d, 'settings', lambda: {'demo_mode': False})
    assert abs((d.clock(db) - datetime.now(timezone.utc)).total_seconds()) < 2


@pytest.mark.parametrize('recall_date,plan_owner', [('not-a-date', 'navigation-team'), ('2000-01-01', 'navigation-team'), ('2099-01-01', '   ')])
def test_invalid_surveillance_recall_or_owner_cannot_clear_care_endpoint(store, recall_date, plan_owner):
    db, _ = store
    case = create(db)
    ev = evidence(db, case, 'surveillance_plan', verify=False, recall_date=recall_date, plan_owner=plan_owner)
    denied(db, 422, cmd, db, case, 'evidence_verify', role='clinician', evidence_id=ev.id,
        verified=True, reason='Attempt invalid surveillance acceptance')
    assert ev.verification == 'pending'


def test_configured_policy_drives_codes_evidence_and_service_windows(store, monkeypatch):
    db, _ = store
    from services.api.policy import load_policy, PathwayPolicy
    original = load_policy().model_dump()
    original['test_codes'] = ['DEMO_CONFIGURED_FIT']
    original['required_evidence'].append('additional_clinician_review')
    original['service_windows']['routine_hours'] = 12
    original['service_windows']['consultation_hours'] = 8
    original['service_windows']['handoff_hours'] = 6
    original['service_windows']['step_hours']['notification'] = 4
    policy = PathwayPolicy.model_validate(original)
    monkeypatch.setattr(d, 'load_policy', lambda: policy)
    blocked = create(db, suffix='unconfigured')
    assert blocked.quarantine_reason == 'unsupported_pathway'
    case = create(db, test_code='DEMO_CONFIGURED_FIT')
    extra = next(t for t in d.rows(db, Task, case.id) if t.type == 'additional_clinician_review')
    from datetime import datetime
    assert 11.99 <= (datetime.fromisoformat(extra.due_at)-datetime.fromisoformat(case.created_at)).total_seconds()/3600 <= 12.01
    notification = next(t for t in d.rows(db, Task, case.id) if t.type == 'notification')
    assert 3.99 <= (datetime.fromisoformat(notification.due_at)-datetime.fromisoformat(case.created_at)).total_seconds()/3600 <= 4.01
    denied(db, 409, cmd, db, case, 'task', task_id=extra.id, status='completed', reason='Cannot waive extra configured clinical evidence')
    assert 'verified_current_evidence:additional_clinician_review' in d.closure_check(db, case)['missing']


def test_policy_configuration_cannot_remove_evidence_or_human_authority():
    from services.api.policy import load_policy, PathwayPolicy
    from pydantic import ValidationError
    original = load_policy().model_dump()
    for mutation in [{'required_evidence':['investigation']}, {'allow_autonomous_closure':True}, {'closure_roles':['admin']}, {'milestones':['result_ingested']}]:
        with pytest.raises(ValidationError):
            PathwayPolicy.model_validate({**original, **mutation})


def test_no_slots_capacity_before_booking_creates_owned_work_without_fake_appointment(store):
    db, _ = store
    case = create(db)
    denied(db, 403, cmd, db, case, 'capacity', role='receiver_a', status='no_slots', reason='No current capacity')
    accepted(db, case)
    cmd(db, case, 'capacity', role='receiver_a', status='no_slots', reason='No available assessment slots in the requested demonstration window')
    assert not d.rows(db, Appointment, case.id)
    assert next(t for t in d.rows(db, Task, case.id) if t.type == 'appointment').status != 'completed'
    assert any(t.type == 'appointment_recovery' and t.assignee and t.reason for t in d.rows(db, Task, case.id))
    assert 'no_slots' in case.delay_reasons


def test_new_required_work_reopens_completed_care_instead_of_preserving_false_completion(store):
    db, _ = store
    case = create(db)
    ready(db, case)
    cmd(db, case, 'disposition', role='clinician', category='completed_required_care', reason='Completed evidenced care')
    cmd(db, case, 'capacity', role='receiver_a', status='no_slots', reason='A new required coordination issue needs review')
    assert case.disposition == 'open' and case.closed_at is None and case.residual_need
    assert not d.closure_check(db, case)['allowed']


def test_whitespace_task_owner_falls_back_and_consultation_owner_cannot_be_blank(store):
    db, _ = store
    case = create(db)
    result = cmd(db, case, 'task', type='transport', assignee='   ', next_action='  Arrange transport  ')
    item = db.get(Task, result['record_id'])
    assert item.assignee == case.backup_queue and item.next_action == 'Arrange transport'
    result = cmd(db, case, 'consultation', role='patient', type='patient_to_clinician', question='Please explain the next step', recipient='clinician')
    denied(db, 422, cmd, db, case, 'consultation_reply', role='clinician', consultation_id=result['record_id'],
        reply='Discuss the documented assessment', agreed_action='Arrange follow-up', action_owner='   ')


def test_policy_version_change_creates_owned_review_and_reconciliation_preserves_existing_due_dates(store, monkeypatch):
    db, _ = store
    import services.api.worker as worker
    from services.api.policy import load_policy, PathwayPolicy
    case = create(db)
    original_due = {t.id: t.due_at for t in d.rows(db, Task, case.id)}
    changed = load_policy().model_dump()
    changed['version'] = 'stricter-policy-v2'
    changed['required_evidence'].append('additional_clinician_review')
    policy = PathwayPolicy.model_validate(changed)
    monkeypatch.setattr(d, 'load_policy', lambda: policy)
    monkeypatch.setattr(worker, 'load_policy', lambda: policy)
    assert 'policy_version_review' in d.closure_check(db, case)['missing']
    run_once(db, deliver_external=False, case_id=case.id)
    review = next(t for t in d.rows(db, Task, case.id) if t.type == 'policy_review')
    assert review.assignee == 'clinician'
    denied(db, 409, cmd, db, case, 'task', task_id=review.id, status='completed', reason='Ordinary work cannot waive policy review')
    cmd(db, case, 'reconciliation', role='clinician', identity_verified=True, pathway='colorectal-fit',
        source_reference='synthetic://policy/source', reason='Qualified clinician reviewed the new configured requirements')
    assert case.policy_version == 'stricter-policy-v2' and review.status == 'completed'
    assert all(db.get(Task, task_id).due_at == deadline for task_id, deadline in original_due.items())
    assert any(t.type == 'additional_clinician_review' and t.status != 'completed' for t in d.rows(db, Task, case.id))


def test_fresh_trusted_urgent_source_event_reopens_a_previously_completed_episode(store):
    db, _ = store
    case = create(db)
    ready(db, case)
    cmd(db, case, 'disposition', role='clinician', category='completed_required_care', reason='Previously evidenced required care')
    create(db, event_id='new-trusted-urgent-source-event', result_version=1, trusted_urgent=True)
    assert case.disposition == 'open' and case.closed_at is None and case.urgent
    assert case.residual_need and d.rows(db, Escalation, case.id)
    assert 'urgent_clinician_disposition' in d.closure_check(db, case)['missing']


def test_patient_care_plan_uses_approved_source_text_not_source_verification_attestation(store):
    db, _ = store
    case = create(db)
    plan = 'Your clinician reviewed your assessment. Please discuss the documented follow-up plan with your responsible care team at your next arranged visit.'
    result = cmd(db, case, 'evidence_add', role='clinician', type='reviewed_outcome',
        reference='synthetic://approved-plan/source', patient_id=case.patient_id, order_id=case.order_id,
        result_version=case.result_version, document_text=plan)
    reason = 'Checked source authenticity, patient/order identifiers and current version; internal verification attestation.'
    cmd(db, case, 'evidence_verify', role='clinician', evidence_id=result['record_id'], verified=True, reason=reason)
    patient = d.serialize_case(db, case, actor('patient', case.patient_id))
    assert patient['care_plan']['summary'] == plan
    assert reason not in patient['care_plan']['summary']
    communicated = 'Your care team has explained the reviewed assessment and agreed next visit. Please contact the team if you need help with the arrangements.'
    result = cmd(db, case, 'evidence_add', role='clinician', type='patient_updated',
        reference='synthetic://approved-plan/communicated', patient_id=case.patient_id, order_id=case.order_id,
        result_version=case.result_version, document_text=communicated)
    cmd(db, case, 'evidence_verify', role='clinician', evidence_id=result['record_id'], verified=True, reason=reason)
    assert d.serialize_case(db, case, actor('patient', case.patient_id))['care_plan']['summary'] == communicated


def test_patient_care_plan_does_not_display_technical_json_or_invent_from_attestation(store):
    db, _ = store
    case = create(db)
    result = cmd(db, case, 'evidence_add', role='clinician', type='reviewed_outcome',
        reference='synthetic://approved-plan/technical-resource', patient_id=case.patient_id, order_id=case.order_id,
        result_version=case.result_version, document_text='{"resourceType":"DiagnosticReport","status":"final"}')
    cmd(db, case, 'evidence_verify', role='clinician', evidence_id=result['record_id'], verified=True,
        reason='Internal source-matching attestation must not become a fabricated patient plan.')
    assert d.serialize_case(db, case, actor('patient', case.patient_id))['care_plan'] is None


def test_completed_care_next_step_points_to_the_documented_plan(store):
    db, _ = store
    case = create(db)
    ready(db, case)
    cmd(db, case, 'disposition', role='clinician', category='completed_required_care', reason='All evidenced care and patient communication completed')
    patient = d.serialize_case(db, case, actor('patient', case.patient_id))
    assert patient['next_action'] == 'Care endpoint documented; follow the approved plan'
    assert patient['due_at'] is None


def test_amendment_preserves_factual_referral_booking_and_attendance_milestones(store):
    db, _ = store
    case = create(db)
    ready(db, case)
    original = {m.type: m.status for m in d.rows(db, d.Milestone, case.id)}
    assert all(original[k] == 'completed' for k in ['referral', 'appointment', 'attendance'])
    create(db, event_id='milestone-amendment-v2', result_version=2)
    current = {m.type: m.status for m in d.rows(db, d.Milestone, case.id)}
    assert all(current[k] == 'completed' for k in ['referral', 'appointment', 'attendance'])
    assert all(current[k] == 'required' for k in ['notification', 'acknowledgement', 'understanding', 'investigation', 'reviewed_outcome', 'patient_updated'])
    assert all(e.status == 'superseded' for e in d.rows(db, Evidence, case.id))


def test_amended_unsupported_source_code_updates_current_mapping_and_creates_owned_quarantine(store):
    db, _ = store
    case = create(db)
    create(db, event_id='unsupported-amendment-v2', result_version=2, test_code='UNSUPPORTED_CORRECTED_TEST')
    assert case.test_code == 'UNSUPPORTED_CORRECTED_TEST'
    assert case.quarantine_reason == 'unsupported_pathway'
    assert case.pathway == 'unresolved'
    assert any(t.type == 'quarantine' and t.assignee and t.status != 'completed' for t in d.rows(db, Task, case.id))
    denied(db, 409, cmd, db, case, 'communication', language='en', channel='portal')


def test_amended_identity_conflict_removes_patient_access_and_requires_source_reconciliation(store):
    db, _ = store
    case = create(db)
    create(db, event_id='identity-amendment-v2', result_version=2, test_code='FIT+', identity_verified=False)
    assert case.test_code == 'FIT+' and case.identity_verified is False
    assert case.quarantine_reason == 'identity_conflict'
    assert next(m for m in d.rows(db, d.Milestone, case.id) if m.type == 'identity').status == 'blocked'
    assert any(t.type == 'quarantine' and t.assignee for t in d.rows(db, Task, case.id))
    denied(db, 403, d.authorize_case, db, actor('patient', case.patient_id), case.id)


def test_amendment_fresh_review_can_close_without_recreating_factual_service_history(store):
    db, _ = store
    case = create(db)
    ready(db, case)
    create(db, event_id='review-recovery-amendment-v2', result_version=2, test_code='FIT_POS')
    assert not d.closure_check(db, case)['allowed']
    notify(db, case)
    for kind in ['investigation', 'reviewed_outcome', 'patient_updated']:
        evidence(db, case, kind)
    assert d.closure_check(db, case)['allowed']
    assert all(m.status == 'completed' for m in d.rows(db, d.Milestone, case.id) if m.required)
    assert len(d.rows(db, Handoff, case.id)) == 1 and len(d.rows(db, Appointment, case.id)) == 1
    cmd(db, case, 'disposition', role='clinician', category='completed_required_care', reason='Fresh amended-source assessment review and patient plan evidenced; factual service history retained')
    assert case.disposition == 'completed_required_care'


def test_retained_source_endpoint_shows_actual_document_provenance_and_records_read_audit(store):
    db, _ = store
    import hashlib, json
    from services.api.main import app
    from services.api.auth import require_actor
    from services.api.db import AuditEvent
    case = create(db)
    ev = evidence(db, case, 'investigation', verify=False)
    original_version = case.version
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_actor] = lambda: actor('clinician')
    try:
        response = TestClient(app).get('/evidence/' + ev.id + '/source')
        assert response.status_code == 200
        source = response.json()
        assert source['content']['document_text'] == 'Actual project synthetic source fixture for this evidence type: investigation'
        assert source['content_hash'] == hashlib.sha256(json.dumps(source['content'], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        assert all(source['matching'].values()) and source['verification'] == 'pending'
        assert source['authority'] == 'uploaded_pending_human_source_check' and case.version == original_version
        assert any(a.event_type == 'source_document_read' and a.detail['evidence_id'] == ev.id for a in d.rows(db, AuditEvent, case.id))
        assert source['content']['document_text'] not in json.dumps(d.serialize_case(db, case, actor('clinician')))
        cmd(db, case, 'consultation', role='clinician', type='clinician_to_specialist', question='Please review this retained source', recipient='specialist')
        app.dependency_overrides[require_actor] = lambda: actor('specialist')
        assert TestClient(app).get('/evidence/' + ev.id + '/source').status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_retained_source_endpoint_denies_patient_receiver_and_ungranted_or_foreign_reviewer(store):
    db, _ = store
    from services.api.main import app
    from services.api.auth import require_actor
    case = create(db)
    ev = evidence(db, case, 'investigation', verify=False)
    accepted(db, case)  # Even an accepted packet grant does not include document bodies.
    app.dependency_overrides[get_db] = lambda: db
    try:
        for a in [actor('patient', case.patient_id), actor('receiver_a'), actor('navigator'), actor('admin'),
                  actor('specialist'), {**actor('clinician'), 'organization': 'unrelated-clinic'}]:
            app.dependency_overrides[require_actor] = lambda a=a: a
            response = TestClient(app).get('/evidence/' + ev.id + '/source')
            assert response.status_code == 403 and 'document_text' not in response.text
    finally:
        app.dependency_overrides.clear()


def test_retained_source_endpoint_guards_missing_cross_case_and_patient_order_mismatches_but_allows_history(store):
    db, _ = store
    from services.api.main import app
    from services.api.auth import require_actor
    case = create(db)
    other = create(db, suffix='other-source')
    ev = evidence(db, case, 'investigation', verify=False)
    artifact = db.get(SourceArtifact, ev.reference)
    artifact_data = d.asdict(artifact)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_actor] = lambda: actor('clinician')
    try:
        client = TestClient(app)
        db.delete(artifact); db.commit()
        assert client.get('/evidence/' + ev.id + '/source').status_code == 404
        artifact = SourceArtifact(**artifact_data); db.add(artifact); db.commit()
        artifact.case_id = other.id; db.commit()
        assert client.get('/evidence/' + ev.id + '/source').status_code == 403
        artifact.case_id = case.id; artifact.source = 'unrelated-source'; db.commit()
        assert client.get('/evidence/' + ev.id + '/source').status_code == 403
        artifact.source = ev.source; ev.patient_id = 'wrong-patient'; db.commit()
        mismatch = client.get('/evidence/' + ev.id + '/source')
        assert mismatch.status_code == 409 and 'document_text' not in mismatch.text
        assert mismatch.json()['detail']['matching']['patient_match'] is False
        ev.patient_id = case.patient_id; ev.order_id = 'wrong-order'; db.commit()
        assert client.get('/evidence/' + ev.id + '/source').status_code == 409
        ev.order_id = case.order_id; db.commit()
        create(db, event_id='source-history-amendment-v2', result_version=2)
        historical = client.get('/evidence/' + ev.id + '/source')
        assert historical.status_code == 200 and historical.json()['status'] == 'superseded'
        assert historical.json()['matching']['result_version_match'] is False
    finally:
        app.dependency_overrides.clear()


def test_owned_coordination_task_in_progress_persists_without_extending_deadline(store):
    db, Session = store
    case = create(db, suffix='task-progress')
    created = cmd(db, case, 'task', type='navigation_followup', assignee='navigation-team',
        next_action='Coordinate the recorded follow-up', required=False)
    task_id = created['record_id']
    initial = db.get(Task, task_id)
    original_due = initial.due_at
    updated = cmd(db, case, 'task', task_id=task_id, status='in_progress',
        reason='Navigator started the owned coordination action')
    assert next(t for t in updated['tasks'] if t['id'] == task_id)['status'] == 'in_progress'
    with Session() as after_restart:
        persisted = after_restart.get(Task, task_id)
        assert persisted.status == 'in_progress'
        assert persisted.assignee == 'navigation-team'
        assert persisted.due_at == original_due
        assert persisted.completed_at is None
