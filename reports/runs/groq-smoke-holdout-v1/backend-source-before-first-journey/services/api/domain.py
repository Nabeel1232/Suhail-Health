"""Transactional coordination ledger; no model has clinical authority here."""
from datetime import datetime, timedelta, timezone, date
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select, text
from .config import settings
from .policy import load_policy
from .db import (Case, Task, Milestone, Communication, Consultation, Handoff, AccessGrant,
                 Appointment, Evidence, Escalation, Disposition, AuditEvent, Outbox,
                 Receipt, SourceEvent, SourceArtifact, PatientExperience, Setting, uid, now_iso)

POLICY = load_policy().version
CORE_ORG = 'source-clinic'
STAFF = {'navigator', 'clinician', 'admin'}
GATES = {'result_ingested', 'identity', 'notification', 'acknowledgement', 'understanding',
         'referral', 'appointment', 'attendance', 'investigation', 'reviewed_outcome',
         'patient_updated', 'treatment_initiated', 'surveillance_plan', 'urgent_review',
         'consultation', 'quarantine', 'policy_review'}
MILESTONES = load_policy().milestones
CHILDREN = {'tasks': Task, 'milestones': Milestone, 'communications': Communication,
            'consultations': Consultation, 'handoffs': Handoff, 'appointments': Appointment,
            'evidence': Evidence, 'escalations': Escalation, 'dispositions': Disposition,
            'audit': AuditEvent, 'experience': PatientExperience, 'access_grants': AccessGrant}


def clock(db):
    if not settings()['demo_mode']:
        return datetime.now(timezone.utc)
    offset = db.get(Setting, 'demo_clock')
    hours = (offset.value.get('hours', 0) if offset else 0)
    base = offset.value.get('base') if offset else None
    instant = datetime.fromisoformat(base) if base else datetime.now(timezone.utc)
    return instant + timedelta(hours=hours)


def due(db, hours=None):
    return (clock(db) + timedelta(hours=load_policy().service_windows.routine_hours if hours is None else hours)).isoformat()


def rows(db, model, case_id):
    return list(db.scalars(select(model).where(model.case_id == case_id)))


def asdict(record):
    return {col.name: getattr(record, col.name) for col in record.__table__.columns}


def fail(status, message):
    raise HTTPException(status_code=status, detail=message)


def audit(db, actor, case, event_type, detail=None, before=None, correlation_id=None):
    db.add(AuditEvent(case_id=case.id if case else None, actor_id=actor['id'],
        organization=actor['organization'], event_type=event_type,
        correlation_id=correlation_id or uid('corr'), before_version=before,
        after_version=case.version if case else None, detail=detail or {}))


def require_role(actor, roles):
    if actor['role'] not in roles:
        fail(403, 'This action requires an authorized ' + ', '.join(sorted(roles)) + ' role.')


def permitted_grant(db, actor, case_id, handoff_id=None):
    query = select(AccessGrant).where(AccessGrant.case_id == case_id,
        AccessGrant.organization == actor['organization'], AccessGrant.revoked == False,
        AccessGrant.expires_at > clock(db).isoformat())
    if handoff_id:
        query = query.where(AccessGrant.handoff_id == handoff_id)
    return db.scalar(query)


def authorize_case(db, actor, case_id, packet=False):
    case = db.get(Case, case_id)
    if not case:
        fail(404, 'Case not found.')
    allowed = False
    role = actor['role']
    if role == 'patient':
        allowed = actor.get('patient_id') == case.patient_id and case.identity_verified
    elif role in STAFF:
        allowed = actor['organization'] == case.source_organization
    elif role == 'specialist':
        allowed = actor['organization'] == settings()['specialist_organization'] and any(
            c.recipient in {actor['id'], 'specialist'} for c in rows(db, Consultation, case_id))
    elif role.startswith('receiver') or role == 'connector':
        allowed = bool(packet and permitted_grant(db, actor, case_id))
    if not allowed:
        audit(db, actor, case, 'access_denied', {'scope': 'packet' if packet else 'case'})
        db.commit()
        fail(403, 'No authorized access to this case scope.')
    return case


def milestone(db, case, kind, status='completed', evidence_id=None, required=True):
    record = db.scalar(select(Milestone).where(Milestone.case_id == case.id, Milestone.type == kind))
    if not record:
        record = Milestone(case_id=case.id, type=kind, status=status, required=required, evidence_ids=[])
        db.add(record)
    record.status = status
    if evidence_id:
        record.evidence_ids = list(dict.fromkeys([*(record.evidence_ids or []), evidence_id]))


def task(db, case, kind, action, assignee=None, required=True, hours=None, reason=''):
    assignee = assignee.strip() if isinstance(assignee, str) else assignee
    action = action.strip() if isinstance(action, str) else action
    if not action:
        fail(422, 'An owned task requires a concrete next action.')
    existing = db.scalar(select(Task).where(Task.case_id == case.id, Task.type == kind,
        Task.status.notin_(['completed', 'cancelled'])))
    if existing:
        return existing
    record = Task(case_id=case.id, type=kind, next_action=action,
        assignee=assignee or case.owner or case.backup_queue, required=required,
        due_at=due(db, hours), reason=reason)
    db.add(record)
    return record


def complete(db, case, kind):
    for item in rows(db, Task, case.id):
        if item.type == kind and item.status != 'cancelled':
            item.status = 'completed'
            item.completed_at = clock(db).isoformat()


def outbox(db, case, kind, destination, payload):
    db.add(Outbox(case_id=case.id, kind=kind, destination=destination, payload=payload,
        next_attempt_at=clock(db).isoformat()))


def add_delay(case, reason):
    case.delay_reasons = list(dict.fromkeys([*(case.delay_reasons or []), reason]))


def active_urgent(db, case):
    return any(e.disposition is None for e in rows(db, Escalation, case.id))


def progression_gate(db, case):
    if case.quarantine_reason:
        fail(409, 'Case is quarantined: ' + case.quarantine_reason + '. Use authorized reconciliation.')
    if active_urgent(db, case):
        fail(409, 'Routine progression is paused pending clinician urgent disposition.')


def urgent(db, case, actor, source):
    case.urgent = True
    if not any(e.disposition is None for e in rows(db, Escalation, case.id)):
        urgent_hours = load_policy().service_windows.urgent_ack_minutes / 60
        record = Escalation(case_id=case.id, trigger=source, due_at=due(db, urgent_hours))
        db.add(record)
        db.flush()
        task(db, case, 'urgent_review', 'Acknowledge and clinically review trusted urgent signal',
             assignee='clinician', hours=urgent_hours, reason=source)
        outbox(db, case, 'urgent_alert', 'staff-simulator', {'escalation_id': record.id, 'source': source})
        audit(db, actor, case, 'trusted_urgent_routed', {'source': source, 'escalation_id': record.id})


def initialize_work(db, case):
    for kind in MILESTONES:
        done = kind == 'result_ingested' or (kind == 'identity' and not case.quarantine_reason)
        milestone(db, case, kind, 'completed' if done else ('blocked' if case.quarantine_reason else 'required'))
    if case.quarantine_reason:
        task(db, case, 'quarantine', 'Reconcile identity/pathway from source evidence',
             assignee=case.backup_queue, reason=case.quarantine_reason)
        return
    actions = {
      'notification': 'Send approved result notification',
      'acknowledgement': 'Obtain patient acknowledgement',
      'understanding': 'Confirm the patient understands the next step',
      'referral': 'Obtain receiving-service acceptance',
      'appointment': 'Confirm an available appointment',
      'attendance': 'Confirm attendance from the receiving service',
      'investigation': 'Obtain verified completed-investigation evidence',
      'reviewed_outcome': 'Obtain clinician-reviewed assessment and next plan',
      'patient_updated': 'Record that the patient received the reviewed outcome and plan',
    }
    for kind, action in actions.items():
        task(db, case, kind, action)
    for kind in load_policy().required_evidence:
        if kind not in actions:
            task(db, case, kind, 'Obtain verified configured evidence: ' + kind)


def intake(db, actor, data):
    require_role(actor, {'connector', 'navigator', 'clinician', 'admin'})
    source = data['source_organization']
    if source != actor['organization']:
        fail(403, 'Authenticated source organization does not match event source.')
    event_key = source + ':' + data['event_id']
    event_fingerprint = hashlib.sha256(json.dumps({k: data.get(k) for k in
        ['source_organization', 'patient_id', 'order_id', 'result_version', 'test_code', 'issued_at', 'identity_verified', 'trusted_urgent']},
        sort_keys=True).encode()).hexdigest()
    if db.bind.dialect.name == 'postgresql':
        lock_key = int.from_bytes(hashlib.sha256((source + ':' + data['patient_id'] + ':' + data['order_id']).encode()).digest()[:8], 'big', signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:lock_key)'), {'lock_key': lock_key})
    prior = db.get(SourceEvent, event_key)
    if prior:
        original_case = db.get(Case, prior.case_id)
        if (original_case.patient_id != data['patient_id'] or original_case.order_id != data['order_id'] or
            prior.result_version != data.get('result_version', 1) or
            prior.provenance.get('event_fingerprint', event_fingerprint) != event_fingerprint):
            fail(409, 'This source event identity was already used for a different result payload.')
        return serialize_case(db, db.get(Case, prior.case_id), actor, internal=True)
    case = db.scalar(select(Case).where(Case.source_organization == source,
        Case.patient_id == data['patient_id'], Case.order_id == data['order_id']).with_for_update().execution_options(populate_existing=True))
    incoming_version = data.get('result_version', 1)
    if not case:
        if data.get('case_id') and db.get(Case, data['case_id']):
            fail(409, 'The proposed case identity already belongs to another patient/order episode.')
        quarantine = None
        if not data.get('identity_verified'):
            quarantine = 'identity_conflict'
        elif not load_policy().supports(data['test_code']):
            quarantine = 'unsupported_pathway'
        elif data.get('staffing_available') is False:
            quarantine = 'missing_staffing_mapping'
        case = Case(id=data.get('case_id') or uid('case'), dataset=data.get('dataset', 'demo-v1'),
            patient_id=data['patient_id'], patient_name=data['patient_name'],
            source_organization=source, order_id=data['order_id'], result_version=incoming_version,
            test_code=data['test_code'], pathway='colorectal-fit', policy_version=load_policy().version,
            owner=load_policy().backup_queue if quarantine == 'missing_staffing_mapping' else load_policy().default_owner,
            backup_queue=load_policy().backup_queue, quarantine_reason=quarantine,
            identity_verified=bool(data.get('identity_verified')), urgent=False,
            requires_onward=bool(data.get('requires_onward', False)), language=data.get('language', 'en'),
            issued_at=data['issued_at'], created_at=clock(db).isoformat(), version=1)
        db.add(case)
        db.flush()
        initialize_work(db, case)
        audit(db, actor, case, 'result_ingested', {'source_version': incoming_version})
    elif incoming_version > case.result_version:
        previous = case.version
        case.result_version = incoming_version
        case.version += 1
        case.disposition = 'open'
        case.closed_at = None
        case.residual_need = 'Corrected result requires fresh clinical review and patient update'
        for item in rows(db, Evidence, case.id):
            item.status = 'superseded'
        for item in rows(db, Milestone, case.id):
            if item.type not in {'result_ingested', 'identity'}:
                item.status = 'required'
        for kind in ['notification', 'acknowledgement', 'understanding', 'investigation', 'reviewed_outcome', 'patient_updated']:
            task(db, case, kind, 'Fresh review after corrected result: ' + kind)
        if case.requires_onward:
            task(db, case, 'treatment_initiated', 'Recheck onward care after corrected result')
        add_delay(case, 'corrected_result')
        audit(db, actor, case, 'corrected_result_reopened', {'source_version': incoming_version}, before=previous)
    elif incoming_version < case.result_version:
        audit(db, actor, case, 'out_of_order_result_ignored', {'source_version': incoming_version})
    if data.get('trusted_urgent'):
        urgent(db, case, actor, 'trusted_source_critical_flag')
    db.add(SourceEvent(key=event_key, case_id=case.id, source_organization=source,
        event_id=data['event_id'], result_version=incoming_version, occurred_at=data['issued_at'],
        received_at=clock(db).isoformat(), provenance={'kind': 'synthetic_result',
            'event_fingerprint': event_fingerprint,
            'source_reference': data.get('source_reference', 'FHIR/Observation/' + data['order_id'])}))
    db.commit()
    return serialize_case(db, case, actor, internal=True)


def valid_evidence(db, case):
    return [e for e in rows(db, Evidence, case.id) if e.verification == 'verified' and
        e.status == 'current' and e.patient_id == case.patient_id and e.order_id == case.order_id and
        e.result_version == case.result_version]


def register_artifact(db, case, source, reference, content, authority):
    """Connectors/project generators retain actual source bodies, not an invented pointer."""
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    old = db.get(SourceArtifact, reference)
    if old and (old.content_hash != digest or old.case_id != case.id or old.source != source):
        fail(409, 'A source reference already identifies a different immutable document.')
    if not old:
        db.add(SourceArtifact(reference=reference, case_id=case.id, source=source,
            authority=authority, content_hash=digest, content=content))


def closure_check(db, case):
    db.flush()
    missing = []
    if case.quarantine_reason:
        missing.append('quarantine:' + case.quarantine_reason)
    if case.policy_version != load_policy().version:
        missing.append('policy_version_review')
    if active_urgent(db, case):
        missing.append('urgent_clinician_disposition')
    evidences = valid_evidence(db, case)
    types = {e.type for e in evidences}
    for kind in load_policy().required_evidence:
        if kind not in types:
            missing.append('verified_current_evidence:' + kind)
    if case.requires_onward and 'treatment_initiated' not in types and 'surveillance_plan' not in types:
        missing.append('declared_onward_care_endpoint')
    if case.requires_onward:
        for kind in set(load_policy().conditional_evidence) - {'treatment_initiated', 'surveillance_plan'}:
            if kind not in types:
                missing.append('verified_current_onward_evidence:' + kind)
    for item in rows(db, Task, case.id):
        if item.required and item.status != 'completed':
            missing.append('open_required_task:' + item.type)
    return {'allowed': not missing, 'missing': list(dict.fromkeys(missing)),
        'endpoint': 'treatment_initiation_or_authorized_surveillance' if case.requires_onward else 'diagnostic_followup_review_and_patient_plan',
        'policy_version': case.policy_version, 'evidence_ids': [e.id for e in evidences],
        'case_id': case.id, 'version': case.version}


def phase(db, case):
    if case.quarantine_reason:
        return 'Quarantined — source reconciliation required'
    if active_urgent(db, case):
        return 'Urgent clinician review'
    if case.disposition != 'open':
        return case.disposition.replace('_', ' ').capitalize()
    missing = [t for t in rows(db, Task, case.id) if t.required and t.status != 'completed']
    if case.requires_onward and any(t.type == 'treatment_initiated' for t in missing):
        return 'Onward care remains open'
    return missing[0].next_action if missing else 'Ready for authorized closure review'


def serialize_case(db, case, actor, internal=False):
    db.flush()
    data = asdict(case)
    data['phase'] = phase(db, case)
    open_tasks = [t for t in rows(db, Task, case.id) if t.status not in {'completed', 'cancelled'}]
    open_tasks.sort(key=lambda x: x.due_at)
    data['next_action'] = open_tasks[0].next_action if open_tasks else 'Review closure evidence'
    data['due_at'] = open_tasks[0].due_at if open_tasks else None
    for key, cls in CHILDREN.items():
        data[key] = [asdict(r) for r in rows(db, cls, case.id)]
    current = clock(db).isoformat()
    for item in data['tasks']:
        if item['status'] not in {'completed', 'cancelled'} and item['due_at'] < current:
            item['status'] = 'overdue'
    if not internal and actor['role'] == 'patient':
        outcome = next((e for e in reversed(rows(db, Evidence, case.id)) if e.type == 'reviewed_outcome' and
            e.verification == 'verified' and e.status == 'current' and e.result_version == case.result_version), None)
        data['care_plan'] = ({'summary': outcome.verification_reason,
            'source': outcome.source, 'reference': outcome.reference,
            'approved_by': outcome.verified_by, 'requires_onward': case.requires_onward}
            if outcome else None)
        for key in ['audit', 'evidence', 'handoffs', 'dispositions', 'access_grants']:
            data.pop(key, None)
        data['tasks'] = [t for t in data['tasks'] if t['type'] in {'understanding_help', 'barrier', 'appointment_recovery'}]
        data['consultations'] = [c for c in data['consultations'] if c['type'] == 'patient_to_clinician']
        data['escalations'] = [{'id': e['id'], 'status': 'reviewed' if e['disposition'] else 'care_team_review'} for e in data['escalations']]
    elif not internal and actor['role'] == 'specialist':
        data['audit'] = []
        data.pop('access_grants', None)
        data['consultations'] = [c for c in data['consultations'] if c['recipient'] in {actor['id'], 'specialist'}]
    return data


def referral_packet(db, handoff):
    case = db.get(Case, handoff.case_id)
    return {**asdict(handoff), 'case_id': case.id, 'version': case.version,
        'patient_id': case.patient_id, 'patient_name': case.patient_name,
        'order_id': case.order_id, 'result_version': case.result_version,
        'pathway': case.pathway, 'reason_for_referral': 'Actionable FIT follow-up; demonstration pathway',
        'owner': case.owner, 'urgent': case.urgent,
        'appointments': [asdict(a) for a in rows(db, Appointment, case.id) if a.provider == handoff.receiver],
        'scope_notice': 'Minimum referral packet only. Source chart access is not granted.'}


def command(db, actor, case_id, kind, data):
    data = dict(data)
    for field in ['assignee', 'action_owner', 'next_action', 'reason', 'question', 'reply',
                  'agreed_action', 'source_reference', 'plan_owner', 'decision', 'barrier', 'residual_need']:
        if isinstance(data.get(field), str):
            data[field] = data[field].strip()
    packet_kinds = {'handoff_accept', 'handoff_reject', 'appointment_create', 'appointment_event', 'capacity', 'evidence_add'}
    case = authorize_case(db, actor, case_id, packet=kind in packet_kinds)
    case = db.scalar(select(Case).where(Case.id == case_id).with_for_update().execution_options(populate_existing=True))
    key = data.get('idempotency_key')
    if not key or len(key) < 4:
        fail(422, 'A nonempty idempotency_key of at least four characters is required.')
    fingerprint = hashlib.sha256(json.dumps({k:v for k,v in data.items() if k != 'expected_version'}, sort_keys=True, default=str).encode()).hexdigest()
    receipt = db.get(Receipt, key)
    if receipt:
        if receipt.case_id != case.id or receipt.actor_id != actor['id'] or receipt.command != kind or receipt.fingerprint != fingerprint:
            fail(409, 'Idempotency key was already used for a different command.')
        if actor['role'] in {'connector', 'receiver_a', 'receiver_b'}:
            original = db.scalar(select(AuditEvent).where(AuditEvent.case_id == case.id,
                AuditEvent.event_type == kind, AuditEvent.after_version == receipt.version))
            return {'case_id': case.id, 'version': case.version, 'replayed': True,
                'record_id': original.detail.get('record_id') if original else None}
        return serialize_case(db, case, actor)
    if data.get('expected_version') != case.version:
        fail(409, {'message': 'Case version conflict. Reload and retry with a new command key.', 'current_version': case.version})
    previous = case.version
    record_id = None

    if kind == 'reconciliation':
        require_role(actor, {'navigator', 'clinician'})
        was_quarantined = bool(case.quarantine_reason)
        policy_changed = case.policy_version != load_policy().version
        if policy_changed:
            require_role(actor, {'clinician'})
        if not data.get('identity_verified') or data.get('pathway') != 'colorectal-fit' or not data.get('source_reference') or not data.get('reason'):
            fail(422, 'Verified identity, supported pathway, source reference and reconciliation reason are required.')
        case.identity_verified = True
        case.quarantine_reason = None
        case.pathway = 'colorectal-fit'
        case.policy_version = load_policy().version
        if case.owner == 'screening-exceptions':
            case.owner = load_policy().default_owner
        complete(db, case, 'quarantine')
        complete(db, case, 'policy_review')
        if was_quarantined:
            initialize_work(db, case)
        elif policy_changed:
            types = {e.type for e in valid_evidence(db, case)}
            for evidence_type in load_policy().required_evidence:
                if evidence_type not in types:
                    task(db, case, evidence_type, 'Obtain verified configured evidence: ' + evidence_type)
                    milestone(db, case, evidence_type, status='required')
    elif kind == 'task':
        require_role(actor, {'navigator', 'clinician'})
        if data.get('task_id'):
            item = db.get(Task, data['task_id'])
            if not item or item.case_id != case.id:
                fail(404, 'Task not found in case.')
            protected_types = GATES | set(load_policy().required_evidence) | set(load_policy().conditional_evidence) | set(load_policy().milestones)
            if data.get('status') == 'completed' and (item.type in protected_types or item.type.startswith(('consultation:', 'evidence_review:', 'urgent_backup:'))):
                fail(409, 'This task requires its dedicated evidence or authorization command.')
            if data.get('status') == 'completed':
                if not data.get('reason'):
                    fail(422, 'A completion reason is required.')
                item.status = 'completed'
                item.reason = data['reason']
                item.completed_at = clock(db).isoformat()
                if item.type == 'understanding_help':
                    complete(db, case, 'understanding')
                    milestone(db, case, 'understanding', evidence_id=item.id)
            elif 'assignee' in data:
                item.assignee = data['assignee'] or case.backup_queue
        else:
            if not data.get('type') or not data.get('next_action'):
                fail(422, 'Task type and next action are required.')
            item = task(db, case, data['type'], data['next_action'], data.get('assignee') or case.backup_queue,
                required=data.get('required', True), reason=data.get('reason', ''))
        db.flush()
        record_id = item.id
    elif kind == 'communication':
        require_role(actor, {'navigator', 'clinician'})
        progression_gate(db, case)
        language = data.get('language', case.language)
        channel = data.get('channel', case.channel)
        if language not in {'en', 'ar'} or channel not in {'portal', 'sms_simulator', 'email_simulator'}:
            fail(422, 'Supported languages en/ar and local simulated channels only.')
        body = ('نتيجة فحص البراز تحتاج إلى متابعة. فريق الرعاية سيشرح الخطوة التالية ويرتب التقييم. يرجى تأكيد الاستلام وطلب المساعدة عند الحاجة.' if language == 'ar' else
                'Your stool screening result needs follow-up. Your care team will explain the next step and arrange an assessment. Please confirm receipt and ask for help if anything is unclear.')
        msg = Communication(case_id=case.id, language=language, channel=channel, body=body)
        db.add(msg)
        db.flush()
        outbox(db, case, 'notification', 'local-notification-simulator', {'communication_id': msg.id,
            'result_version': case.result_version,
            'message': 'A care-team update is available in your secure portal.'})
        record_id = msg.id
    elif kind in {'acknowledgement', 'understanding'}:
        require_role(actor, {'patient'})
        msg = db.get(Communication, data['communication_id'])
        if not msg or msg.case_id != case.id:
            fail(404, 'Communication not found.')
        linked = next((o for o in rows(db, Outbox, case.id) if o.payload.get('communication_id') == msg.id), None)
        if linked and linked.payload.get('result_version', 1) != case.result_version:
            fail(409, 'This communication belongs to a superseded result. A fresh patient update is required.')
        if msg.delivery_status != 'delivered':
            fail(409, 'The notification has not been delivered yet.')
        if kind == 'acknowledgement':
            msg.acknowledged_at = clock(db).isoformat()
            complete(db, case, 'acknowledgement')
            milestone(db, case, 'acknowledgement', evidence_id=msg.id)
        else:
            outcome = data.get('outcome')
            if outcome not in {'passed', 'needs_help', 'unknown'}:
                fail(422, 'Understanding outcome must be passed, needs_help or unknown.')
            msg.understanding = outcome
            if outcome == 'passed':
                complete(db, case, 'understanding')
                complete(db, case, 'understanding_help')
                milestone(db, case, 'understanding', evidence_id=msg.id)
            else:
                milestone(db, case, 'understanding', status='blocked')
                task(db, case, 'understanding_help', 'Contact patient for an accessible explanation', reason=outcome)
    elif kind == 'preferences':
        require_role(actor, {'patient'})
        if data.get('language') not in {'en', 'ar'} or data.get('channel') not in {'portal', 'sms_simulator', 'email_simulator'}:
            fail(422, 'Unsupported language or channel.')
        case.language, case.channel = data['language'], data['channel']
    elif kind == 'barrier':
        require_role(actor, {'patient', 'navigator'})
        if not data.get('barrier'):
            fail(422, 'Please choose a barrier.')
        add_delay(case, 'barrier:' + data['barrier'])
        task(db, case, 'barrier', 'Arrange practical help: ' + data['barrier'], reason=data.get('detail', ''))
    elif kind == 'experience':
        require_role(actor, {'patient'})
        if any(isinstance(data.get(k), bool) or not isinstance(data.get(k), int) or not 1 <= data[k] <= 5 for k in ['confidence', 'reassurance']):
            fail(422, 'Confidence and reassurance ratings must be integers from one to five.')
        item = PatientExperience(case_id=case.id, patient_id=case.patient_id,
            confidence=data['confidence'], reassurance=data['reassurance'],
            comment=data.get('comment', ''), captured_at=clock(db).isoformat())
        db.add(item)
        db.flush()
        record_id = item.id
    elif kind == 'consultation':
        type_ = data.get('type')
        if type_ == 'patient_to_clinician':
            require_role(actor, {'patient', 'navigator', 'clinician'})
            recipient = 'clinician'
        elif type_ == 'clinician_to_specialist':
            require_role(actor, {'clinician'})
            recipient = 'specialist'
        else:
            fail(422, 'Unsupported consultation type.')
        if not str(data.get('question', '')).strip():
            fail(422, 'A question is required.')
        item = Consultation(case_id=case.id, type=type_, question=data['question'], recipient=recipient,
            requester=actor['id'], due_at=due(db, load_policy().service_windows.consultation_hours))
        db.add(item)
        db.flush()
        task(db, case, 'consultation:' + item.id, 'Human reply and agreed next action', assignee=recipient,
            hours=load_policy().service_windows.consultation_hours)
        record_id = item.id
    elif kind == 'consultation_reply':
        item = db.get(Consultation, data['consultation_id'])
        if not item or item.case_id != case.id:
            fail(404, 'Consultation not found.')
        required = 'specialist' if item.type == 'clinician_to_specialist' else 'clinician'
        require_role(actor, {required})
        if item.recipient not in {actor['id'], actor['role']}:
            fail(403, 'Only the assigned clinician may reply.')
        if not all(data.get(f) for f in ['reply', 'agreed_action', 'action_owner']):
            fail(422, 'Human reply, agreed action and action owner are required.')
        item.reply, item.agreed_action, item.action_owner = data['reply'], data['agreed_action'], data['action_owner']
        item.human_author = actor['id']
        item.status = 'replied'
        item.replied_at = clock(db).isoformat()
        complete(db, case, 'consultation:' + item.id)
        task(db, case, 'agreed_action:' + item.id, data['agreed_action'], assignee=data['action_owner'])
    elif kind == 'handoff':
        require_role(actor, {'navigator', 'clinician'})
        progression_gate(db, case)
        if data.get('receiver') not in {'provider-a', 'provider-b'} or data.get('scope') not in {'episode', 'task'}:
            fail(422, 'A supported receiver and explicit episode/task scope are required.')
        existing = db.scalar(select(Handoff).where(Handoff.case_id == case.id,
            Handoff.receiver == data['receiver'], Handoff.scope == data['scope'],
            Handoff.status.in_(['requested', 'accepted'])))
        if existing:
            fail(409, 'An active handoff already exists for this destination and scope.')
        item = Handoff(case_id=case.id, scope=data['scope'], sender=case.owner,
            receiver=data['receiver'], reason=data.get('reason', ''), due_at=due(db, load_policy().service_windows.handoff_hours))
        db.add(item)
        db.flush()
        db.add(AccessGrant(case_id=case.id, handoff_id=item.id, organization=item.receiver,
            granted_by=actor['id'], expires_at=due(db, 24 * 30)))
        packet = referral_packet(db, item)
        outbox(db, case, 'referral', item.receiver, packet)
        record_id = item.id
    elif kind in {'handoff_accept', 'handoff_reject'}:
        require_role(actor, {'receiver_a', 'receiver_b', 'connector'})
        item = db.get(Handoff, data['handoff_id'])
        if not item or item.case_id != case.id:
            fail(404, 'Handoff not found.')
        if item.receiver != actor['organization'] or not permitted_grant(db, actor, case.id, item.id):
            fail(403, 'Only the authorized destination may decide this handoff.')
        if item.status != 'requested':
            fail(409, 'Handoff is no longer awaiting a decision.')
        if item.due_at <= clock(db).isoformat():
            fail(409, 'The handoff acceptance service window elapsed. The sending owner remains accountable; request a fresh handoff.')
        if kind == 'handoff_reject' and not str(data.get('reason', '')).strip():
            fail(422, 'A rejection reason is required for owned recovery.')
        if kind == 'handoff_accept' and active_urgent(db, case):
            fail(409, 'Urgent clinician disposition is required before routine acceptance.')
        item.status = 'accepted' if kind == 'handoff_accept' else 'rejected'
        item.decided_at, item.decision_actor = clock(db).isoformat(), actor['id']
        item.reason = data.get('reason', item.reason)
        if kind == 'handoff_accept':
            if item.scope == 'episode':
                case.owner = item.receiver
            else:
                for t in rows(db, Task, case.id):
                    if t.type in {'investigation', 'appointment', 'attendance'} and t.status != 'completed':
                        t.assignee = item.receiver
            complete(db, case, 'referral')
            milestone(db, case, 'referral', evidence_id=item.id)
        else:
            add_delay(case, 'handoff_rejected')
            task(db, case, 'referral_recovery', 'Find another receiving service', reason=item.reason)
    elif kind == 'appointment_create':
        require_role(actor, {'receiver_a', 'receiver_b', 'connector'})
        progression_gate(db, case)
        provider = data.get('provider')
        if provider != actor['organization'] or not any(h.receiver == provider and h.status == 'accepted' for h in rows(db, Handoff, case.id)):
            fail(403, 'An accepted handoff to this authenticated provider is required.')
        item = Appointment(case_id=case.id, provider=provider, scheduled_at=data['scheduled_at'],
            status='booked', events=[{'status': 'booked', 'occurred_at': clock(db).isoformat(), 'source': provider}])
        db.add(item)
        db.flush()
        complete(db, case, 'appointment')
        milestone(db, case, 'appointment', evidence_id=item.id)
        record_id = item.id
    elif kind == 'capacity':
        require_role(actor, {'receiver_a', 'receiver_b', 'connector'})
        if actor['organization'] not in {'provider-a', 'provider-b'} or not any(
                h.receiver == actor['organization'] and h.status == 'accepted' for h in rows(db, Handoff, case.id)):
            fail(403, 'An accepted care task for the authenticated receiving service is required.')
        if data.get('status') != 'no_slots' or not str(data.get('reason', '')).strip():
            fail(422, 'Report unavailable capacity with a recorded reason.')
        add_delay(case, 'no_slots')
        item = task(db, case, 'appointment_recovery', 'Find available capacity and confirm an appointment with the patient',
            assignee=case.owner, reason=actor['organization'] + ': ' + data['reason'])
        db.flush()
        record_id = item.id
    elif kind == 'appointment_event':
        require_role(actor, {'receiver_a', 'receiver_b', 'connector'})
        item = db.get(Appointment, data['appointment_id'])
        if not item or item.case_id != case.id:
            fail(404, 'Appointment not found.')
        if item.provider != actor['organization']:
            fail(403, 'Appointment source does not match authenticated provider.')
        status = data.get('status')
        if status not in {'booked', 'cancelled', 'no_show', 'attended', 'no_slots'}:
            fail(422, 'Unsupported appointment event.')
        occurred_at = data.get('occurred_at') or clock(db).isoformat()
        event_id = data.get('source_event_id') or key
        if any(e.get('source_event_id') == event_id for e in item.events):
            fail(409, 'This source appointment event was already applied.')
        latest = max((e['occurred_at'] for e in item.events), default='')
        event = {'status': status, 'occurred_at': occurred_at, 'source': actor['organization'], 'source_event_id': event_id}
        item.events = [*item.events, event]
        if occurred_at >= latest:
            item.status = status
            if status == 'attended':
                complete(db, case, 'attendance')
                complete(db, case, 'appointment_recovery')
                milestone(db, case, 'attendance', evidence_id=item.id)
            elif status in {'cancelled', 'no_show', 'no_slots'}:
                add_delay(case, status)
                task(db, case, 'appointment_recovery', 'Contact patient and arrange a confirmed appointment', reason=status)
                task(db, case, 'attendance', 'Obtain current receiving-service attendance confirmation', assignee=item.provider)
                milestone(db, case, 'attendance', status='blocked')
    elif kind == 'evidence_add':
        require_role(actor, {'clinician', 'navigator', 'receiver_a', 'receiver_b', 'connector'})
        allowed = set(load_policy().required_evidence) | set(load_policy().conditional_evidence) | {'outreach', 'exception_review'}
        if data.get('type') not in allowed or not data.get('reference'):
            fail(422, 'A supported evidence type and source reference are required.')
        if data.get('document_text') is not None and len(data['document_text'].strip()) < 10:
            fail(422, 'An actual nonblank source document is required for manual evidence upload.')
        if actor['organization'] in {'provider-a', 'provider-b'} and not any(h.receiver == actor['organization'] and h.status == 'accepted' for h in rows(db, Handoff, case.id)):
            fail(403, 'Evidence return requires an accepted care task for this authenticated provider.')
        if actor['role'] == 'connector':
            if not data['reference'].startswith('synthetic://' + actor['organization'] + '/'):
                fail(422, 'Provider source references must use the authenticated provider namespace.')
            register_artifact(db, case, actor['organization'], data['reference'],
                {k: data[k] for k in ['type', 'patient_id', 'order_id', 'result_version', 'reference']}, 'authenticated_provider')
        elif data.get('document_text'):
            register_artifact(db, case, actor['organization'], data['reference'],
                {k: data[k] for k in ['type', 'patient_id', 'order_id', 'result_version', 'document_text']}, 'uploaded_pending_human_source_check')
        item = Evidence(case_id=case.id, type=data['type'], reference=data['reference'],
            source=actor['organization'], patient_id=data['patient_id'], order_id=data['order_id'],
            result_version=data['result_version'], requires_onward=bool(data.get('requires_onward', False)),
            effective_at=data.get('effective_at') or clock(db).isoformat(), received_at=clock(db).isoformat(),
            plan_owner=data.get('plan_owner'), recall_date=data.get('recall_date'))
        db.add(item)
        db.flush()
        task(db, case, 'evidence_review:' + item.id, 'Verify source and patient/order match for uploaded evidence', assignee='clinician')
        record_id = item.id
    elif kind == 'evidence_verify':
        require_role(actor, {'clinician'})
        item = db.get(Evidence, data['evidence_id'])
        if not item or item.case_id != case.id:
            fail(404, 'Evidence not found.')
        if not data.get('reason'):
            fail(422, 'Source verification and matching rationale is required.')
        if data.get('verified'):
            if item.patient_id != case.patient_id or item.order_id != case.order_id or item.result_version != case.result_version or item.status != 'current':
                fail(409, 'Evidence does not match the current patient, order and result version.')
            artifact = db.get(SourceArtifact, item.reference)
            if not artifact or artifact.case_id != case.id:
                fail(409, 'The source document/resource is unavailable. Return authenticated provider evidence or upload the actual document for source verification.')
            if any(artifact.content.get(k) != getattr(item, k) for k in ['type', 'patient_id', 'order_id', 'result_version']):
                fail(409, 'The retained source artifact does not match the claimed evidence fields.')
            if item.type == 'surveillance_plan' and (not item.plan_owner or not item.recall_date):
                fail(422, 'An accepted surveillance plan requires a recall date and accountable owner.')
            if item.type == 'surveillance_plan':
                try:
                    recall = date.fromisoformat(item.recall_date)
                except (TypeError, ValueError):
                    fail(422, 'The surveillance recall must be an ISO calendar date.')
                if not item.plan_owner.strip() or recall < clock(db).date():
                    fail(422, 'The surveillance plan needs an accountable owner and a current or future recall date.')
            item.verification = 'verified'
            item.verified_by = actor['id']
            item.verification_reason = data['reason']
            complete(db, case, item.type)
            milestone(db, case, item.type, evidence_id=item.id)
            if item.type == 'reviewed_outcome' and item.requires_onward:
                case.requires_onward = True
                case.residual_need = 'Treatment initiation or accepted surveillance endpoint remains open'
                task(db, case, 'treatment_initiated', 'Obtain verified treatment initiation or accepted surveillance plan', assignee='provider-b')
                milestone(db, case, 'treatment_initiated', status='required')
            if item.type == 'surveillance_plan':
                complete(db, case, 'treatment_initiated')
                milestone(db, case, 'treatment_initiated', evidence_id=item.id)
        else:
            item.verification = 'rejected'
            item.verification_reason = data['reason']
            add_delay(case, 'evidence_rejected')
        complete(db, case, 'evidence_review:' + item.id)
    elif kind == 'escalation_ack':
        require_role(actor, {'clinician', 'navigator'})
        item = db.get(Escalation, data['escalation_id'])
        if not item or item.case_id != case.id:
            fail(404, 'Escalation not found.')
        item.acknowledged_at, item.acknowledged_by = clock(db).isoformat(), actor['id']
    elif kind == 'access_revoke':
        require_role(actor, {'navigator', 'admin'})
        item = db.get(AccessGrant, data['grant_id'])
        if not item or item.case_id != case.id:
            fail(404, 'Access grant not found.')
        if not data.get('reason'):
            fail(422, 'A revocation reason is required.')
        item.revoked = True
        task(db, case, 'access_recovery', 'Review coordination after referral-packet access revocation',
            assignee=case.backup_queue, reason=data['reason'])
    elif kind == 'escalation_disposition':
        require_role(actor, {'clinician'})
        item = db.get(Escalation, data['escalation_id'])
        if not item or item.case_id != case.id:
            fail(404, 'Escalation not found.')
        if not item.acknowledged_at or not data.get('decision') or not data.get('reason'):
            fail(422, 'Staff acknowledgement, clinician decision and rationale are required.')
        item.disposition, item.disposition_by = data['decision'], actor['id']
        item.disposition_reason = data['reason']
        complete(db, case, 'urgent_review')
        complete(db, case, 'urgent_backup:' + item.id)
    elif kind == 'disposition':
        require_role(actor, {'clinician'})
        category = data.get('category')
        if category not in {'completed_required_care', 'clinically_resolved', 'informed_decline', 'unable_to_contact', 'accepted_transfer_open', 'other_exception'}:
            fail(422, 'Unsupported disposition category.')
        if not data.get('reason'):
            fail(422, 'A clinical rationale is required.')
        check = closure_check(db, case)
        if category == 'completed_required_care' and not check['allowed']:
            fail(409, {'message': 'Required care cannot close yet.', 'missing': check['missing']})
        if category != 'completed_required_care':
            if active_urgent(db, case) or case.quarantine_reason:
                fail(409, 'Resolve identity/pathway gates and urgent clinical review before disposition.')
            if not data.get('residual_need'):
                fail(422, 'An exception disposition requires an explicit residual care need.')
            if category in {'informed_decline', 'unable_to_contact'}:
                ev = valid_evidence(db, case)
                if not any(e.type == 'outreach' for e in ev) or not any(e.type == 'exception_review' for e in ev):
                    fail(409, 'Verified outreach and authorized handling evidence are required for this exception.')
            if category == 'accepted_transfer_open' and not any(h.status == 'accepted' for h in rows(db, Handoff, case.id)):
                fail(409, 'An explicitly accepted transfer is required.')
        case.disposition = category
        case.residual_need = '' if category == 'completed_required_care' else data['residual_need']
        case.closed_at = clock(db).isoformat() if category in {'completed_required_care', 'clinically_resolved', 'informed_decline', 'unable_to_contact', 'other_exception'} else None
        db.add(Disposition(case_id=case.id, category=category, reason=data['reason'], residual_need=case.residual_need,
            reviewer=actor['id'], endpoint=check['endpoint'], policy_version=case.policy_version,
            evidence_ids=check['evidence_ids']))
    else:
        fail(422, 'Unknown application command.')

    reopened_missing = None
    if case.disposition == 'completed_required_care' and kind != 'disposition':
        changed_check = closure_check(db, case)
        if not changed_check['allowed']:
            case.disposition, case.closed_at = 'open', None
            case.residual_need = 'New required work needs review: ' + ', '.join(changed_check['missing'])
            reopened_missing = changed_check['missing']
    case.version += 1
    db.flush()
    audit(db, actor, case, kind, {'record_id': record_id}, before=previous, correlation_id=data.get('correlation_id'))
    if reopened_missing:
        audit(db, actor, case, 'episode_reopened_by_new_required_work', {'missing': reopened_missing}, before=previous)
    db.add(Receipt(key=key, case_id=case.id, command=kind, actor_id=actor['id'], fingerprint=fingerprint, version=case.version))
    db.commit()
    if actor['role'] in {'receiver_a', 'receiver_b', 'connector'}:
        result = {'case_id': case.id, 'version': case.version, 'record_id': record_id}
        if kind.startswith('handoff'):
            result['handoff_id'] = data.get('handoff_id')
        return result
    result = serialize_case(db, case, actor)
    result['record_id'] = record_id
    return result
