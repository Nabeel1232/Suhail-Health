"""Repeatable synthetic-only seed. Every state transition uses the application commands."""
from datetime import datetime, timedelta
from functools import partial
import json
import secrets
from time import monotonic, sleep
from sqlalchemy import select, delete
from fastapi import HTTPException
from .auth import password_hash
from .config import ROOT, settings
from .db import (SessionLocal, init_db, User, Case, Communication, Setting, SourceEvent, Receipt,
    AccessGrant, Outbox, SourceArtifact)
from .domain import intake, command, clock, CHILDREN
from .worker import run_once

NAMES = {
  'SC-001': 'Mariam Al Noor',
  'SC-002': 'Omar Saleh',
  'SC-003': 'Huda Mansour',
  'SC-004': 'Yousef Kareem',
  'SC-005': 'Layla Hassan',
  'SC-006': 'Khalid Nasser',
  'SC-007': 'Salma Amin',
  'SC-008': 'Hamad Faris',
  'SC-009': 'Noura Al Suwaidi',
  'SC-010': 'Saeed Al Mazrouei',
  'SC-011': 'Fatima Al Hashimi',
  'SC-012': 'Rashid Al Ketbi',
  'SC-013': 'Zayed Al Mansoori',
  'SC-014': 'Aisha Al Shamsi',
  'SC-015': 'Mansoor Al Qasimi',
  'SC-016': 'Amna Al Dhaheri',
}
ROLE_NAMES = {'navigator': 'Aisha · Navigator', 'clinician': 'Dr Samir · Clinician',
 'specialist': 'Dr Lina · Specialist', 'receiver_a': 'Provider A · Referral team',
 'receiver_b': 'Provider B · Referral team', 'patient': 'Mariam · Patient', 'admin': 'Operations administrator'}
DEMO_BASE = datetime.fromisoformat('2026-11-15T08:00:00+00:00')
COMPLETED_TIMING = {'SC-008': (-336, -46), 'SC-013': (-24 - 9 * 24 + 2, -24),
    'SC-014': (-60 - 16 * 24 + 2, -60), 'SC-015': (-120 - 23 * 24 + 2, -120)}
INTAKE_HOURS = {'SC-001': -26, 'SC-002': -40, 'SC-003': -0.5, 'SC-004': -20,
    'SC-005': -40, 'SC-006': -44, 'SC-007': -44, 'SC-009': -150, 'SC-010': -60,
    'SC-011': -30, 'SC-012': -30, 'SC-016': -90,
    **{case_id: start for case_id, (start, _) in COMPLETED_TIMING.items()}}


def actor(role, patient_id=None):
    return {'id': 'demo-' + role, 'name': ROLE_NAMES.get(role, role), 'role': role,
        'organization': 'provider-a' if role == 'receiver_a' else 'provider-b' if role == 'receiver_b' else 'specialist-clinic' if role == 'specialist' else 'source-clinic',
        'patient_id': patient_id or ('patient-001' if role == 'patient' else None)}


def apply(db, case_id, role, kind, data=None, patient_id=None):
    key = 'seed:' + secrets.token_hex(12)
    for attempt in range(4):
        case = db.get(Case, case_id, populate_existing=True)
        try:
            return command(db, actor(role, patient_id), case_id, kind,
                {**(data or {}), 'expected_version': case.version, 'idempotency_key': key})
        except HTTPException as exc:
            if exc.status_code != 409 or not isinstance(exc.detail, dict) or 'current_version' not in exc.detail:
                raise
            db.rollback()
            if attempt == 3:
                raise


def add_verified(db, case_id, kind, **extra):
    case = db.get(Case, case_id)
    result = apply(db, case_id, 'clinician', 'evidence_add', {'type': kind,
        'reference': 'synthetic://seed/' + case_id + '/' + kind, 'patient_id': case.patient_id,
        'order_id': case.order_id, 'result_version': case.result_version,
        'document_text': 'Synthetic source document for ' + case_id + ' ' + kind + '. Patient/order/version are generated from the independent seed truth fixture.', **extra})
    apply(db, case_id, 'clinician', 'evidence_verify', {'evidence_id': result['record_id'],
        'verified': True, 'reason': 'Synthetic demonstration fixture; source, identity, order and current version checked'})


def set_clock(db, hours):
    record = db.get(Setting, 'demo_clock')
    value = {'base': DEMO_BASE.isoformat(), 'hours': hours}
    if record is None:
        db.add(Setting(key='demo_clock', value=value))
    else:
        record.value = value
    db.commit()


def scheduled_at(db, hours):
    return (DEMO_BASE + timedelta(hours=hours) if settings()['demo_mode'] else clock(db)).isoformat()


def case_action(case_id, role, kind, data=None, *, record=None):
    def execute(db, state):
        payload = data(db, state) if callable(data) else data
        patient_id = db.get(Case, case_id).patient_id if role == 'patient' else None
        result = apply(db, case_id, role, kind, payload, patient_id)
        if record:
            state[record] = result['record_id']
    return execute


def wait_for_notification(db, notification_id):
    deadline = monotonic() + 10
    while True:
        # A concurrent worker may have leased the outbox row. Read each attempt
        # in a fresh transaction while the notification's demo time is held.
        db.rollback()
        notification = db.get(Communication, notification_id, populate_existing=True)
        status = notification.delivery_status if notification else None
        db.rollback()
        if status == 'delivered':
            return
        remaining = deadline - monotonic()
        if status != 'queued' or remaining <= 0:
            raise RuntimeError('Seed notification did not reach delivery: ' + notification_id)
        sleep(min(0.05, remaining))


def intake_case(db, case_id):
    i = int(case_id[-3:])
    intake(db, actor('navigator'), {'event_id': 'seed-intake-' + case_id,
        'case_id': case_id, 'patient_id': f'patient-{i:03}', 'patient_name': NAMES[case_id] + ' (synthetic)',
        'source_organization': 'source-clinic', 'order_id': 'FIT-' + case_id,
        'result_version': 1, 'test_code': 'FIT_POSITIVE', 'issued_at': (clock(db) - timedelta(hours=2)).isoformat(),
        'identity_verified': case_id != 'SC-004', 'trusted_urgent': case_id == 'SC-003',
        'language': 'ar' if case_id in {'SC-001', 'SC-011', 'SC-014'} else 'en', 'dataset': 'demo-v1'})


def check_premature_closure(db, case_id):
    try:
        apply(db, case_id, 'clinician', 'disposition', {'category': 'completed_required_care',
            'reason': 'Synthetic premature closure challenge'})
    except HTTPException as exc:
        if exc.status_code != 409 or not isinstance(exc.detail, dict) or not exc.detail.get('missing'):
            raise
        db.rollback()
    else:
        raise RuntimeError('Premature closure was incorrectly accepted')


def contact_events(case_id, notify_at, respond_at=None, outcome='passed'):
    action = partial(case_action, case_id)
    send = action('navigator', 'communication', lambda db, _: {
        'language': db.get(Case, case_id).language, 'channel': 'portal'}, record='notification')

    def notify(db, state):
        send(db, state)
        return state['notification']

    events = [(notify_at, notify)]
    if respond_at is not None:
        events.extend([
            (respond_at, action('patient', 'acknowledgement', lambda _, state: {
                'communication_id': state['notification']})),
            (respond_at, action('patient', 'understanding', lambda _, state: {
                'communication_id': state['notification'], 'outcome': outcome})),
        ])
    return events


def complete_case(case_id):
    action = partial(case_action, case_id)
    start, end = COMPLETED_TIMING[case_id]
    reference_start, reference_end = COMPLETED_TIMING['SC-008']

    def at(hours):
        return round(start + (hours - reference_start) * (end - start) / (reference_end - reference_start))

    return [
        (start, lambda db, _: check_premature_closure(db, case_id)),
        *contact_events(case_id, at(-335), at(-330)),
        (at(-312), action('navigator', 'handoff', {'receiver': 'provider-a', 'scope': 'task',
            'reason': 'Synthetic FIT assessment'}, record='handoff')),
        (at(-306), action('receiver_a', 'handoff_accept', lambda _, state: {'handoff_id': state['handoff']})),
        (at(-300), action('receiver_a', 'appointment_create', lambda db, _: {
            'provider': 'provider-a', 'scheduled_at': scheduled_at(db, at(-96))}, record='appointment')),
        (at(-96), action('receiver_a', 'appointment_event', lambda _, state: {
            'appointment_id': state['appointment'], 'status': 'attended'})),
        (at(-72), lambda db, _: add_verified(db, case_id, 'investigation')),
        (at(-48), lambda db, _: add_verified(db, case_id, 'reviewed_outcome')),
        (end, lambda db, _: add_verified(db, case_id, 'patient_updated')),
        (end, action('clinician', 'disposition', {'category': 'completed_required_care',
            'reason': 'Synthetic clinician reviewed investigation and outcome, communicated plan and no further required task remains'})),
    ]


def corrected_result(db, case_id):
    case = db.get(Case, case_id)
    intake(db, actor('navigator'), {'event_id': 'seed-correction-' + case_id, 'case_id': case_id,
        'patient_id': case.patient_id, 'patient_name': case.patient_name, 'source_organization': 'source-clinic',
        'order_id': case.order_id, 'result_version': 2, 'test_code': 'FIT_POSITIVE',
        'issued_at': clock(db).isoformat(), 'identity_verified': True, 'trusted_urgent': False})


def timer_event(_db, _state):
    """The event loop checks this case's persisted timers after setting the clock."""


def scenario(case_id):
    action = partial(case_action, case_id)
    if case_id == 'SC-001':
        return contact_events(case_id, -25)
    if case_id == 'SC-002':
        return [
            (-39, action('navigator', 'handoff', {'receiver': 'provider-a', 'scope': 'episode',
                'reason': 'Assessment requested'}, record='handoff')),
            (-30, action('receiver_a', 'handoff_reject', lambda _, state: {
                'handoff_id': state['handoff'], 'reason': 'No capacity in requested window'})),
            (-29, action('navigator', 'handoff', {'receiver': 'provider-b', 'scope': 'task',
                'reason': 'Alternative capacity requested'}, record='handoff')),
            (-20, action('receiver_b', 'handoff_accept', lambda _, state: {'handoff_id': state['handoff']})),
            (-19, action('receiver_b', 'appointment_create', lambda db, _: {
                'provider': 'provider-b', 'scheduled_at': scheduled_at(db, -4)}, record='appointment')),
            (-4, action('receiver_b', 'appointment_event', lambda _, state: {
                'appointment_id': state['appointment'], 'status': 'no_show'})),
        ]
    if case_id == 'SC-005':
        return [(-30, lambda db, _: add_verified(db, case_id, 'investigation')),
            (-6, lambda db, _: corrected_result(db, case_id))]
    if case_id == 'SC-006':
        return [
            (-20, lambda db, _: add_verified(db, case_id, 'outreach')),
            (-20, lambda db, _: add_verified(db, case_id, 'exception_review')),
            (-18, action('clinician', 'disposition', {'category': 'informed_decline',
                'reason': 'Synthetic patient declined after clinician explanation and documented outreach',
                'residual_need': 'Diagnostic follow-up remains indicated; navigation team owns re-engagement'})),
        ]
    if case_id == 'SC-007':
        return [
            (-20, lambda db, _: add_verified(db, case_id, 'reviewed_outcome', requires_onward=True)),
            (-18, action('navigator', 'handoff', {'receiver': 'provider-b', 'scope': 'task',
                'reason': 'Onward care endpoint remains open'}, record='handoff')),
            (-10, action('receiver_b', 'handoff_accept', lambda _, state: {'handoff_id': state['handoff']})),
        ]
    if case_id in COMPLETED_TIMING:
        return complete_case(case_id)
    if case_id == 'SC-009':
        return [*contact_events(case_id, -149), (0, timer_event)]
    if case_id == 'SC-010':
        return [
            *contact_events(case_id, -59, -50),
            (-30, action('navigator', 'handoff', {'receiver': 'provider-a', 'scope': 'episode',
                'reason': 'Synthetic FIT assessment requested'})),
            (0, timer_event),
        ]
    if case_id == 'SC-011':
        return contact_events(case_id, -29, -10, 'needs_help')
    if case_id == 'SC-012':
        return [
            *contact_events(case_id, -29, -20),
            (-8, action('patient', 'barrier', {'barrier': 'transport',
                'detail': 'Needs help getting to the follow-up assessment'})),
            (-7, action('patient', 'consultation', {'type': 'patient_to_clinician',
                'question': 'How can I arrange transport to the follow-up assessment?'})),
        ]
    if case_id == 'SC-016':
        return [
            *contact_events(case_id, -89, -80),
            (-70, action('navigator', 'handoff', {'receiver': 'provider-b', 'scope': 'task',
                'reason': 'Synthetic FIT assessment requested'}, record='handoff')),
            (-60, action('receiver_b', 'handoff_accept', lambda _, state: {'handoff_id': state['handoff']})),
            (-55, action('receiver_b', 'appointment_create', lambda db, _: {
                'provider': 'provider-b', 'scheduled_at': scheduled_at(db, 48)})),
        ]
    return []


def seed(db=None):
    own = db is None
    if own:
        db = SessionLocal()
    try:
        handoff_file = ROOT / '.runtime' / 'demo-credentials.json'
        creds = json.loads(handoff_file.read_text()) if handoff_file.exists() else {}
        for role, name in ROLE_NAMES.items():
            if not db.get(User, 'demo-' + role):
                password = secrets.token_urlsafe(22)
                email = role + '@demo.suhail.local'
                db.add(User(id='demo-' + role, email=email, name=name, role=role,
                    organization=actor(role)['organization'], patient_id=actor(role)['patient_id'],
                    password_hash=password_hash(password)))
                creds[role] = {'email': email, 'password': password}
        db.commit()
        handoff_file.parent.mkdir(mode=0o700, exist_ok=True)
        handoff_file.write_text(json.dumps(creds, indent=2, ensure_ascii=False))
        handoff_file.chmod(0o600)
        created = [case_id for case_id in NAMES if db.get(Case, case_id) is None]
        events = []
        for case_id in created:
            events.append((INTAKE_HOURS[case_id], case_id,
                lambda db, _, case_id=case_id: intake_case(db, case_id)))
            events.extend((hours, case_id, fn) for hours, fn in scenario(case_id))
        if events:
            demo_mode = settings()['demo_mode']
            previous_clock = db.get(Setting, 'demo_clock') if demo_mode else None
            previous_hours = previous_clock.value.get('hours', 0) if previous_clock else 0
            state = {case_id: {} for case_id in created}
            try:
                for hours, case_id, fn in sorted(events, key=lambda event: event[0]):
                    if demo_mode:
                        set_clock(db, hours)
                    notification_id = fn(db, state[case_id])
                    run_once(db, deliver_external=False, case_id=case_id)
                    if notification_id is not None:
                        wait_for_notification(db, notification_id)
            finally:
                if demo_mode:
                    db.rollback()
                    set_clock(db, previous_hours)
        return {'seeded_case_ids': created, 'dataset': 'demo-v1', 'accounts': list(ROLE_NAMES),
                'credentials_file': '.runtime/demo-credentials.json', 'synthetic_only': True}
    finally:
        if own:
            db.close()


def reset(db):
    ids = list(db.scalars(select(Case.id).where(Case.dataset == 'demo-v1')))
    # Deliberately restricted to the named dataset. Unrelated cases and user accounts survive.
    for model in [AccessGrant, Outbox, Receipt, SourceEvent, SourceArtifact, *CHILDREN.values()]:
        db.execute(delete(model).where(model.case_id.in_(ids)))
    db.execute(delete(Case).where(Case.id.in_(ids)))
    if not db.scalar(select(Case.id).limit(1)):
        db.execute(delete(Setting).where(Setting.key == 'demo_clock'))
    db.commit()
    return seed(db)


if __name__ == '__main__':
    init_db()
    print(json.dumps(seed(), indent=2))
