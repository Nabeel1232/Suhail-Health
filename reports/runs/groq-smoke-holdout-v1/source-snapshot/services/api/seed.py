"""Repeatable synthetic-only seed. Every state transition uses the application commands."""
from datetime import timedelta
import json
import secrets
from sqlalchemy import select, delete
from fastapi import HTTPException
from .auth import password_hash
from .config import ROOT
from .db import (SessionLocal, init_db, User, Case, Setting, SourceEvent, Receipt,
    AccessGrant, Outbox, AuditEvent, SourceArtifact)
from .domain import intake, command, clock, rows, CHILDREN
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
}
ROLE_NAMES = {'navigator': 'Aisha · Navigator', 'clinician': 'Dr Samir · Clinician',
 'specialist': 'Dr Lina · Specialist', 'receiver_a': 'Provider A · Referral team',
 'receiver_b': 'Provider B · Referral team', 'patient': 'Mariam · Patient', 'admin': 'Operations administrator'}


def actor(role, patient_id=None):
    return {'id': 'demo-' + role, 'name': ROLE_NAMES.get(role, role), 'role': role,
        'organization': 'provider-a' if role == 'receiver_a' else 'provider-b' if role == 'receiver_b' else 'specialist-clinic' if role == 'specialist' else 'source-clinic',
        'patient_id': patient_id or ('patient-001' if role == 'patient' else None)}


def apply(db, case_id, role, kind, data=None, patient_id=None):
    case = db.get(Case, case_id)
    return command(db, actor(role, patient_id), case_id, kind,
        {**(data or {}), 'expected_version': case.version, 'idempotency_key': 'seed:' + secrets.token_hex(12)})


def add_verified(db, case_id, kind, **extra):
    case = db.get(Case, case_id)
    result = apply(db, case_id, 'clinician', 'evidence_add', {'type': kind,
        'reference': 'synthetic://seed/' + case_id + '/' + kind, 'patient_id': case.patient_id,
        'order_id': case.order_id, 'result_version': case.result_version,
        'document_text': 'Synthetic source document for ' + case_id + ' ' + kind + '. Patient/order/version are generated from the independent seed truth fixture.', **extra})
    apply(db, case_id, 'clinician', 'evidence_verify', {'evidence_id': result['record_id'],
        'verified': True, 'reason': 'Synthetic demonstration fixture; source, identity, order and current version checked'})


def complete_case(db, case_id):
    case = db.get(Case, case_id)
    apply(db, case_id, 'navigator', 'communication', {'language': case.language, 'channel': 'portal'})
    run_once(db, deliver_external=False, case_id=case_id)
    db.refresh(case)
    from .db import Communication, Handoff, Appointment
    message = rows(db, Communication, case_id)[-1]
    apply(db, case_id, 'patient', 'acknowledgement', {'communication_id': message.id}, case.patient_id)
    apply(db, case_id, 'patient', 'understanding', {'communication_id': message.id, 'outcome': 'passed'}, case.patient_id)
    handoff = apply(db, case_id, 'navigator', 'handoff', {'receiver': 'provider-a', 'scope': 'task', 'reason': 'Synthetic FIT assessment'})
    apply(db, case_id, 'receiver_a', 'handoff_accept', {'handoff_id': handoff['record_id']})
    result = apply(db, case_id, 'receiver_a', 'appointment_create', {'provider': 'provider-a', 'scheduled_at': clock(db).isoformat()})
    apply(db, case_id, 'receiver_a', 'appointment_event', {'appointment_id': result['record_id'], 'status': 'attended'})
    for kind in ['investigation', 'reviewed_outcome', 'patient_updated']:
        add_verified(db, case_id, kind)
    # Required premature-closure rejection is exercised and captured by the seed execution record.
    apply(db, case_id, 'clinician', 'disposition', {'category': 'completed_required_care', 'reason': 'Synthetic clinician reviewed investigation and outcome, communicated plan and no further required task remains'})


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
        created = []
        for case_id, name in NAMES.items():
            if db.get(Case, case_id):
                continue
            i = int(case_id[-3:])
            intake(db, actor('navigator'), {'event_id': 'seed-intake-' + case_id,
                'case_id': case_id, 'patient_id': f'patient-{i:03}', 'patient_name': name + ' (synthetic)',
                'source_organization': 'source-clinic', 'order_id': 'FIT-' + case_id,
                'result_version': 1, 'test_code': 'FIT_POSITIVE', 'issued_at': (clock(db) - timedelta(hours=2)).isoformat(),
                'identity_verified': case_id != 'SC-004', 'trusted_urgent': case_id == 'SC-003',
                'language': 'ar' if case_id == 'SC-001' else 'en', 'dataset': 'demo-v1'})
            created.append(case_id)
        if 'SC-001' in created:
            apply(db, 'SC-001', 'navigator', 'communication', {'language': 'en', 'channel': 'portal'})
            run_once(db, deliver_external=False, case_id='SC-001')
        if 'SC-002' in created:
            result = apply(db, 'SC-002', 'navigator', 'handoff', {'receiver': 'provider-a', 'scope': 'episode', 'reason': 'Assessment requested'})
            apply(db, 'SC-002', 'receiver_a', 'handoff_reject', {'handoff_id': result['record_id'], 'reason': 'No capacity in requested window'})
            result = apply(db, 'SC-002', 'navigator', 'handoff', {'receiver': 'provider-b', 'scope': 'task', 'reason': 'Alternative capacity requested'})
            apply(db, 'SC-002', 'receiver_b', 'handoff_accept', {'handoff_id': result['record_id']})
            result = apply(db, 'SC-002', 'receiver_b', 'appointment_create', {'provider': 'provider-b', 'scheduled_at': clock(db).isoformat()})
            apply(db, 'SC-002', 'receiver_b', 'appointment_event', {'appointment_id': result['record_id'], 'status': 'no_show'})
        if 'SC-005' in created:
            add_verified(db, 'SC-005', 'investigation')
            case = db.get(Case, 'SC-005')
            intake(db, actor('navigator'), {'event_id': 'seed-correction-SC-005', 'case_id': 'SC-005',
                'patient_id': case.patient_id, 'patient_name': case.patient_name, 'source_organization': 'source-clinic',
                'order_id': case.order_id, 'result_version': 2, 'test_code': 'FIT_POSITIVE',
                'issued_at': clock(db).isoformat(), 'identity_verified': True, 'trusted_urgent': False})
        if 'SC-006' in created:
            for kind in ['outreach', 'exception_review']:
                add_verified(db, 'SC-006', kind)
            apply(db, 'SC-006', 'clinician', 'disposition', {'category': 'informed_decline',
                'reason': 'Synthetic patient declined after clinician explanation and documented outreach',
                'residual_need': 'Diagnostic follow-up remains indicated; navigation team owns re-engagement'})
        if 'SC-007' in created:
            add_verified(db, 'SC-007', 'reviewed_outcome', requires_onward=True)
            result = apply(db, 'SC-007', 'navigator', 'handoff', {'receiver': 'provider-b', 'scope': 'task', 'reason': 'Onward care endpoint remains open'})
            apply(db, 'SC-007', 'receiver_b', 'handoff_accept', {'handoff_id': result['record_id']})
        if 'SC-008' in created:
            try:
                apply(db, 'SC-008', 'clinician', 'disposition', {'category': 'completed_required_care', 'reason': 'Synthetic premature closure challenge'})
                raise RuntimeError('Premature closure was incorrectly accepted')
            except HTTPException as exc:
                if exc.status_code != 409:
                    raise
                db.rollback()
            complete_case(db, 'SC-008')
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
    db.commit()
    return seed(db)


if __name__ == '__main__':
    init_db()
    print(json.dumps(seed(), indent=2))
