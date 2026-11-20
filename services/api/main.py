from contextlib import asynccontextmanager
from collections import Counter
from pathlib import Path
import csv
import hashlib
import io
import json
from math import ceil
import secrets
from datetime import datetime, timedelta, timezone
from statistics import median
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic import ValidationError
from sqlalchemy import select, delete
from . import schemas as s
from .auth import require_actor, create_session, password_verify, user_dict, COOKIE
from .config import settings, ROOT
from .policy import load_policy
from .db import (get_db, init_db, User, SessionToken, Case, Task, Communication, Consultation,
    Handoff, Appointment, Evidence, SourceArtifact, Escalation, Outbox, AuditEvent, AccessGrant, Setting, PatientExperience, now_iso)
from .domain import (intake, command, authorize_case, require_role, serialize_case, closure_check,
    asdict, rows, audit, permitted_grant, referral_packet, clock, complete, recorded_datetime,
    APPROVED_NOTIFICATION_TEMPLATES)


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title='Suhail Health coordination API', version='1.0.0', lifespan=lifespan,
    description='Synthetic demonstration. Independent milestones, human authority, source evidence.')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000', 'http://127.0.0.1:3000'],
    allow_credentials=True, allow_methods=['GET', 'POST'], allow_headers=['Content-Type', 'X-Connector-Token', 'X-Organization'])


@app.middleware('http')
async def response_security(request, call_next):
    # SameSite cookie plus origin checks protect cookie-authenticated state-changing requests.
    origin = request.headers.get('origin')
    if request.method == 'POST' and request.cookies.get(COOKIE) and origin:
        from urllib.parse import urlsplit
        if urlsplit(origin).hostname != request.url.hostname and urlsplit(origin).hostname not in {'localhost', '127.0.0.1'}:
            return JSONResponse(status_code=403, content={'detail': 'Origin is not authorized.'})
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    if request.url.path not in {'/health'}:
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/health')
def health(db=Depends(get_db)):
    db.execute(select(Setting).limit(1))
    return {'status': 'ok', 'database': db.bind.dialect.name, 'synthetic_only': True,
            'policy_version': 'demo-fit-v1', 'notifications': 'local simulator'}


@app.get('/auth/config')
def auth_config():
    return {'demo_mode': settings()['demo_mode']}


class Login(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=500)


@app.post('/auth/login')
def login(data: Login, response: Response, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not password_verify(data.password, user.password_hash):
        raise HTTPException(401, 'Email or password was not recognized.')
    return create_session(db, user, response)


class DemoLogin(BaseModel):
    role: str


@app.post('/auth/demo')
def demo_login(data: DemoLogin, response: Response, db=Depends(get_db)):
    if not settings()['demo_mode']:
        raise HTTPException(403, 'Demonstration role switching is disabled.')
    user = db.scalar(select(User).where(User.id == 'demo-' + data.role))
    if not user:
        raise HTTPException(422, 'Unknown demonstration role. Run make seed first.')
    return create_session(db, user, response)


@app.get('/auth/me')
def me(actor=Depends(require_actor)):
    return actor


@app.post('/auth/logout')
def logout(request: Request, response: Response, db=Depends(get_db)):
    token = request.cookies.get(COOKIE)
    if token:
        db.execute(delete(SessionToken).where(SessionToken.token_hash == hashlib.sha256(token.encode()).hexdigest()))
        db.commit()
    response.delete_cookie(COOKIE, path='/')
    return {'signed_out': True}


@app.get('/cases')
def case_list(actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'patient', 'navigator', 'clinician', 'specialist', 'admin'})
    records = list(db.scalars(select(Case).order_by(Case.created_at)))
    if actor['role'] == 'patient':
        records = [c for c in records if c.patient_id == actor['patient_id'] and c.identity_verified]
    elif actor['role'] == 'specialist':
        if actor['organization'] != settings()['specialist_organization']:
            records = []
        else:
            consultations = list(db.scalars(select(Consultation).where(Consultation.recipient.in_([actor['id'], 'specialist']))))
            records = [c for c in records if c.id in {x.case_id for x in consultations}]
    else:
        records = [c for c in records if c.source_organization == actor['organization']]
    result = [serialize_case(db, c, actor) for c in records]
    audit(db, actor, None, 'queue_access_granted', {'scope': actor['role'], 'visible_episode_count': len(result)})
    db.commit()
    return result


@app.get('/cases/{case_id}')
def case_detail(case_id: str, actor=Depends(require_actor), db=Depends(get_db)):
    case = authorize_case(db, actor, case_id)
    audit(db, actor, case, 'access_granted', {'scope': 'patient_view' if actor['role'] == 'patient' else 'case'})
    db.commit()
    data = serialize_case(db, case, actor)
    if actor['role'] in {'navigator', 'clinician'}:
        data['notification_templates'] = APPROVED_NOTIFICATION_TEMPLATES.copy()
    return data


@app.post('/events/results')
def result_event(data: s.ResultEvent, actor=Depends(require_actor), db=Depends(get_db)):
    return intake(db, actor, data.model_dump(exclude_none=True))


def run(db, actor, case_id, kind, data, **extra):
    body = data.model_dump(exclude_none=True)
    body.update(extra)
    return command(db, actor, case_id, kind, body)


def linked_case(db, cls, record_id):
    item = db.get(cls, record_id)
    if not item:
        raise HTTPException(404, 'Record not found.')
    return item.case_id


@app.post('/cases/{case_id}/reconciliation')
def reconciliation(case_id: str, data: s.Reconciliation, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, case_id, 'reconciliation', data)


@app.post('/cases/{case_id}/tasks')
def tasks(case_id: str, data: s.TaskCommand, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, case_id, 'task', data)


@app.post('/communications')
def communications(data: s.CommunicationCommand, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, data.case_id, 'communication', data)


@app.post('/communications/{record_id}/acknowledgement')
def acknowledgement(record_id: str, data: s.Envelope, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Communication, record_id), 'acknowledgement', data, communication_id=record_id)


@app.post('/communications/{record_id}/understanding')
def understanding(record_id: str, data: s.Understanding, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Communication, record_id), 'understanding', data, communication_id=record_id)


@app.post('/cases/{case_id}/preferences')
def preferences(case_id: str, data: s.Preferences, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, case_id, 'preferences', data)


@app.post('/cases/{case_id}/barriers')
def barriers(case_id: str, data: s.Barrier, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, case_id, 'barrier', data)


@app.post('/cases/{case_id}/experience')
def experience(case_id: str, data: s.Experience, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, case_id, 'experience', data)


@app.post('/consultations')
def consultations(data: s.ConsultationCommand, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, data.case_id, 'consultation', data)


@app.post('/consultations/{record_id}/reply')
def consultation_reply(record_id: str, data: s.ConsultationReply, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Consultation, record_id), 'consultation_reply', data, consultation_id=record_id)


@app.post('/handoffs')
def handoffs(data: s.HandoffCommand, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, data.case_id, 'handoff', data)


@app.get('/referrals')
def referrals(actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'receiver_a', 'receiver_b', 'connector'})
    result = []
    for item in db.scalars(select(Handoff).where(Handoff.receiver == actor['organization'])):
        if permitted_grant(db, actor, item.case_id, item.id):
            result.append(referral_packet(db, item))
            audit(db, actor, db.get(Case, item.case_id), 'access_granted', {'scope': 'referral_packet', 'handoff_id': item.id})
    db.commit()
    return result


@app.get('/integrations/providers/{provider}/referrals/{record_id}')
def provider_packet(provider: str, record_id: str, actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'receiver_a', 'receiver_b', 'connector'})
    item = db.get(Handoff, record_id)
    if not item or item.receiver != provider or actor['organization'] != provider:
        raise HTTPException(403, 'No referral packet grant for this destination.')
    if not permitted_grant(db, actor, item.case_id, item.id):
        raise HTTPException(403, 'This referral packet grant expired or was revoked.')
    authorize_case(db, actor, item.case_id, packet=True)
    packet = referral_packet(db, item)
    audit(db, actor, db.get(Case, item.case_id), 'access_granted', {'scope': 'referral_packet', 'handoff_id': item.id})
    db.commit()
    return packet


@app.post('/handoffs/{record_id}/accept')
def handoff_accept(record_id: str, data: s.Decision, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Handoff, record_id), 'handoff_accept', data, handoff_id=record_id)


@app.post('/handoffs/{record_id}/reject')
def handoff_reject(record_id: str, data: s.Decision, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Handoff, record_id), 'handoff_reject', data, handoff_id=record_id)


@app.post('/access-grants/{record_id}/revoke')
def revoke_packet(record_id: str, data: s.Decision, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, AccessGrant, record_id), 'access_revoke', data, grant_id=record_id)


@app.post('/cases/{case_id}/appointments')
def appointment_create(case_id: str, data: s.AppointmentCommand, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, case_id, 'appointment_create', data)


@app.post('/cases/{case_id}/capacity')
def capacity(case_id: str, data: s.Capacity, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, case_id, 'capacity', data)


@app.post('/appointments/{record_id}/events')
def appointment_event(record_id: str, data: s.AppointmentEvent, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Appointment, record_id), 'appointment_event', data, appointment_id=record_id)


@app.post('/cases/{case_id}/evidence')
def evidence_add(case_id: str, data: s.EvidenceCommand, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, case_id, 'evidence_add', data)


@app.post('/evidence/{record_id}/verification')
def evidence_verify(record_id: str, data: s.Verification, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Evidence, record_id), 'evidence_verify', data, evidence_id=record_id)


@app.get('/evidence/{record_id}/source')
def evidence_source(record_id: str, actor=Depends(require_actor), db=Depends(get_db)):
    """Human source review only; document bodies never expand the model case payload."""
    if actor['role'] not in {'clinician', 'specialist'}:
        audit(db, actor, None, 'source_access_denied', {'evidence_id': record_id, 'reason': 'reviewer_role_required'})
        db.commit()
        raise HTTPException(403, 'A scoped clinician or specialist source review is required.')
    item = db.get(Evidence, record_id)
    if not item:
        raise HTTPException(404, 'Evidence not found.')
    case = authorize_case(db, actor, item.case_id)
    artifact = db.get(SourceArtifact, item.reference)

    def denied_source(status, reason, message, matching=None):
        audit(db, actor, case, 'source_access_denied', {'evidence_id': item.id, 'reason': reason})
        db.commit()
        raise HTTPException(status, {'message': message, **({'matching': matching} if matching else {})})

    if not artifact:
        denied_source(404, 'artifact_unavailable', 'The retained source document is unavailable.')
    if artifact.case_id != case.id or artifact.reference != item.reference or artifact.source != item.source:
        denied_source(403, 'artifact_scope_mismatch', 'The retained source is outside this evidence scope.')
    matching = {
        'patient_match': item.patient_id == case.patient_id and artifact.content.get('patient_id') == case.patient_id,
        'order_match': item.order_id == case.order_id and artifact.content.get('order_id') == case.order_id,
        'result_version_match': item.result_version == case.result_version and artifact.content.get('result_version') == case.result_version,
        'type_match': artifact.content.get('type') == item.type,
    }
    if not matching['patient_match'] or not matching['order_match']:
        denied_source(409, 'patient_order_mismatch', 'Patient/order matching failed. Review the mismatch metadata and reject or reconcile the evidence.', matching)
    actual_hash = hashlib.sha256(json.dumps(artifact.content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if actual_hash != artifact.content_hash:
        denied_source(409, 'artifact_integrity_mismatch', 'The retained source failed its integrity check.')
    result = {'evidence_id': item.id, 'case_id': case.id, 'case_version': case.version,
        'reference': item.reference, 'type': item.type, 'source': artifact.source,
        'authority': artifact.authority, 'content': artifact.content, 'content_hash': artifact.content_hash,
        'artifact_received_at': artifact.received_at, 'patient_id': item.patient_id,
        'order_id': item.order_id, 'result_version': item.result_version,
        'effective_at': item.effective_at, 'verification': item.verification, 'status': item.status,
        'matching': matching}
    audit(db, actor, case, 'source_document_read', {'evidence_id': item.id,
        'reference': item.reference, 'content_hash': artifact.content_hash, 'status': item.status})
    db.commit()
    return result


@app.post('/escalations/{record_id}/acknowledge')
def escalation_ack(record_id: str, data: s.Envelope, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Escalation, record_id), 'escalation_ack', data, escalation_id=record_id)


@app.post('/escalations/{record_id}/disposition')
def escalation_disposition(record_id: str, data: s.UrgentDisposition, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Escalation, record_id), 'escalation_disposition', data, escalation_id=record_id)


@app.get('/cases/{case_id}/closure-check')
def check_closure(case_id: str, actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'navigator', 'clinician', 'admin'})
    return closure_check(db, authorize_case(db, actor, case_id))


@app.post('/cases/{case_id}/dispositions')
def case_disposition(case_id: str, data: s.CaseDisposition, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, case_id, 'disposition', data)


@app.post('/integrations/providers/{provider}/events')
def provider_callback(provider: str, data: s.ProviderCallback, actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'connector'})
    if provider not in {'provider-a', 'provider-b'} or actor['organization'] != provider:
        raise HTTPException(403, 'Connector is not authorized for this provider.')
    permitted_fields = {
        'handoff_accept': {'handoff_id', 'reason'}, 'handoff_reject': {'handoff_id', 'reason'},
        'appointment_create': {'provider', 'scheduled_at'},
        'appointment_event': {'appointment_id', 'status', 'occurred_at', 'source_event_id'},
        'evidence_add': {'type', 'reference', 'patient_id', 'order_id', 'result_version', 'requires_onward', 'effective_at', 'plan_owner', 'recall_date'},
    }
    if set(data.data) - permitted_fields[data.kind]:
        raise HTTPException(422, 'Unsupported callback fields.')
    body = {**data.data, 'expected_version': data.expected_version,
        'idempotency_key': provider + ':' + data.event_id, 'correlation_id': data.event_id}
    validators = {'handoff_accept': s.CallbackHandoff, 'handoff_reject': s.CallbackHandoff,
        'appointment_create': s.AppointmentCommand, 'appointment_event': s.CallbackAppointmentEvent,
        'evidence_add': s.EvidenceCommand}
    try:
        body = validators[data.kind].model_validate(body).model_dump(exclude_none=True)
    except ValidationError:
        raise HTTPException(422, 'Provider callback does not satisfy the supported command schema.')
    return command(db, actor, data.case_id, data.kind, body)


class IntakeFile(BaseModel):
    format: str
    content: str = Field(max_length=500000)


@app.post('/integrations/files/intake')
def file_intake(data: IntakeFile, actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'navigator', 'clinician'})
    try:
        records = json.loads(data.content) if data.format == 'json' else list(csv.DictReader(io.StringIO(data.content))) if data.format == 'csv' else None
        if not isinstance(records, list) or not 1 <= len(records) <= 100:
            raise ValueError('A list of 1–100 synthetic source records is required.')
        validated = [s.ResultEvent.model_validate({**record, 'identity_verified': False}) for record in records]
    except Exception:
        raise HTTPException(422, 'File schema invalid. Use the documented synthetic CSV/JSON fields; uploads require source reconciliation.')
    if any(record.source_organization != actor['organization'] for record in validated):
        raise HTTPException(403, 'Every uploaded source record must belong to the authenticated source organization.')
    return {'cases': [intake(db, actor, r.model_dump(exclude_none=True)) for r in validated],
        'notice': 'Uploaded records remain quarantined until authorized source matching.'}


@app.get('/operations')
def operations(actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'navigator', 'clinician', 'admin'})
    allowed = {c.id for c in db.scalars(select(Case).where(Case.source_organization == actor['organization']))}
    overdue = [asdict(t) for t in db.scalars(select(Task)) if t.case_id in allowed and t.status != 'completed' and t.due_at < clock(db).isoformat()]
    return {'outbox': [asdict(o) for o in db.scalars(select(Outbox).order_by(Outbox.created_at.desc()).limit(200)) if o.case_id in allowed],
        'overdue': overdue, 'pending_escalations': [asdict(e) for e in db.scalars(select(Escalation).where(Escalation.disposition == None)) if e.case_id in allowed],
        'connectors': [{'name': 'Provider A', 'status': 'simulated', 'url': settings()['provider_a_url']},
            {'name': 'Provider B', 'status': 'simulated', 'url': settings()['provider_b_url']},
            {'name': 'FHIR R4 test server', 'status': 'simulated', 'url': settings()['fhir_url']},
            {'name': 'Notifications', 'status': 'local simulator'}, {'name': 'National exchanges', 'status': 'unavailable'}],
        'clock': clock(db).isoformat(), 'service_windows': load_policy().service_windows.model_dump(),
        'policy_version': load_policy().version}


@app.post('/operations/outbox/{record_id}/retry')
def retry_outbox(record_id: str, actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'admin', 'navigator'})
    record = db.get(Outbox, record_id)
    if not record:
        raise HTTPException(404, 'Outbox item not found.')
    case = authorize_case(db, actor, record.case_id)
    if record.status not in {'dead_letter', 'retry'}:
        raise HTTPException(409, 'Only a failed delivery can be retried.')
    record.status, record.attempts = 'pending', 0
    record.next_attempt_at = clock(db).isoformat()
    complete(db, case, 'integration_recovery:' + record.id)
    audit(db, actor, case, 'outbox_retry_requested', {'outbox_id': record.id})
    db.commit()
    return {'id': record.id, 'status': record.status}


OUTCOME_STEPS = ('notification', 'acknowledgement', 'understanding', 'referral', 'appointment',
    'attendance', 'investigation', 'reviewed_outcome', 'patient_updated')
DROP_OFF_LABELS = {'handoff_rejected': 'Referral rejected by provider',
    'handoff_timeout': 'Referral expired without a response', 'no_show': 'Appointment missed',
    'cancelled': 'Appointment cancelled', 'no_slots': 'No appointments available',
    'understanding_needs_help': 'Understanding check needs help'}


def outcome_metrics(cases, tasks, messages, handoffs, appointments, current):
    issues = {case.id: recorded_datetime(case.issued_at) for case in cases}
    service_windows = load_policy().service_windows
    completions = {kind: {} for kind in (*OUTCOME_STEPS, 'closure')}
    age_days = dict.fromkeys(('0-2', '3-7', '8-30', '30+'), 0)
    sla = dict.fromkeys(('on_track', 'due_within_24h', 'overdue'), 0)
    owners = {}
    overdue_ids = set()

    for task in tasks:
        due = datetime.fromisoformat(task.due_at)
        if task.status == 'completed' and task.completed_at and task.type in OUTCOME_STEPS and issues[task.case_id]:
            completed = datetime.fromisoformat(task.completed_at)
            previous = completions[task.type].get(task.case_id)
            if previous is None or completed >= previous[0]:
                completions[task.type][task.case_id] = (completed, due)
        if task.status in {'completed', 'cancelled'}:
            continue
        overdue = task.status == 'overdue' or due < current
        bucket = 'overdue' if overdue else 'due_within_24h' if due - current <= timedelta(hours=24) else 'on_track'
        sla[bucket] += 1
        owner = owners.setdefault(task.assignee, {'owner': task.assignee, 'open_tasks': 0, 'overdue': 0})
        owner['open_tasks'] += 1
        if overdue:
            owner['overdue'] += 1
            overdue_ids.add(task.case_id)

    delays = Counter()
    for case in cases:
        if case.disposition == 'completed_required_care' and case.closed_at and issues[case.id]:
            completions['closure'][case.id] = (datetime.fromisoformat(case.closed_at), None)
        if case.disposition in {'open', 'accepted_transfer_open'}:
            opened = issues[case.id] or datetime.fromisoformat(case.created_at)
            age = (current - opened).days
            age_days['0-2' if age <= 2 else '3-7' if age <= 7 else '8-30' if age <= 30 else '30+'] += 1
        # Recovery task codes can carry a record identifier, so group by step alone.
        reasons = {':'.join(reason.split(':', 2)[:2]) for reason in case.delay_reasons
            if reason in DROP_OFF_LABELS or reason.startswith(('overdue:', 'barrier:'))}
        delays.update(reasons)

    time_to = {}
    for kind, by_case in completions.items():
        values = sorted(max(0, (end - issues[case_id]).total_seconds() / 3600)
            for case_id, (end, _) in by_case.items())
        n = len(values)
        target = service_windows.step_hours.get(kind, service_windows.routine_hours) if kind != 'closure' else None
        time_to[kind] = {'median_hours': median(values) if n else None,
            'p90_hours': values[ceil(0.9 * n) - 1] if n else None, 'n': n, 'target_hours': target,
            'within_target': sum(end <= due for end, due in by_case.values()) if target is not None else None}

    def rate(numerator, denominator):
        return {'numerator': numerator, 'denominator': denominator}

    def delay_label(code):
        if code in DROP_OFF_LABELS:
            return DROP_OFF_LABELS[code]
        prefix, kind = code.split(':', 1)
        label = kind.replace('_', ' ').replace('-', ' ').capitalize()
        return label + (' overdue' if prefix == 'overdue' else ' barrier')

    notified = {m.case_id for m in messages if m.delivery_status == 'delivered'}
    acknowledged = {m.case_id for m in messages if m.acknowledged_at}
    understood = {m.case_id for m in messages if m.understanding == 'passed'}
    accepted = {h.case_id for h in handoffs if h.status == 'accepted'}
    attended = {a.case_id for a in appointments if a.status == 'attended'}
    needs_help = {m.case_id for m in messages if m.understanding == 'needs_help'}
    if needs_help:
        delays['understanding_needs_help'] = len(needs_help)
    rates = {
        'notified': rate(len(notified), len(cases)),
        'acknowledged_of_notified': rate(len(acknowledged & notified), len(notified)),
        'understood_of_acknowledged': rate(len(understood & acknowledged), len(acknowledged)),
        'referral_accepted_of_requested': rate(len(accepted), len({h.case_id for h in handoffs})),
        'appointment_attended_of_booked': rate(len(attended), len({a.case_id for a in appointments})),
        'care_completed': rate(sum(c.disposition == 'completed_required_care' for c in cases), len(cases)),
        'documented_closure': rate(sum(c.disposition != 'open' for c in cases), len(cases)),
    }
    return {'as_of': current.isoformat(), 'episodes': len(cases), 'time_to': time_to, 'rates': rates,
        'unresolved': {'open': sum(age_days.values()), 'age_days': age_days,
            'cases_with_overdue_work': len(overdue_ids)},
        'sla': sla, 'drop_off': [{'code': code, 'label': delay_label(code), 'cases': count}
            for code, count in sorted(delays.items(), key=lambda item: (-item[1], item[0]))],
        'by_owner': [owners[name] for name in sorted(owners)]}


@app.get('/metrics')
def metrics(actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'navigator', 'clinician', 'admin'})
    cases = list(db.scalars(select(Case).where(Case.source_organization == actor['organization'])))
    ids = {c.id for c in cases}
    messages = [m for m in db.scalars(select(Communication)) if m.case_id in ids]
    consultations = [m for m in db.scalars(select(Consultation)) if m.case_id in ids]
    handoffs = [m for m in db.scalars(select(Handoff)) if m.case_id in ids]
    appointments = [m for m in db.scalars(select(Appointment)) if m.case_id in ids]
    tasks = list(db.scalars(select(Task).where(Task.case_id.in_(ids)).order_by(Task.created_at, Task.id)))
    experience = [r for r in db.scalars(select(PatientExperience)) if r.case_id in ids]
    confidence_mean = sum(r.confidence for r in experience)/len(experience) if experience else None
    reassurance_mean = sum(r.reassurance for r in experience)/len(experience) if experience else None
    dispositions = dict(Counter(c.disposition for c in cases))
    stages = {
        'notified': len({m.case_id for m in messages if m.delivery_status == 'delivered'}),
        'acknowledged': len({m.case_id for m in messages if m.acknowledged_at}),
        'understood': len({m.case_id for m in messages if m.understanding == 'passed'}),
        'consultation_replied': len({m.case_id for m in consultations if m.human_author}),
        'referral_accepted': len({m.case_id for m in handoffs if m.status == 'accepted'}),
        'attended': len({m.case_id for m in appointments if m.status == 'attended'}),
        'care_completed': dispositions.get('completed_required_care', 0),
    }
    timings = {}
    for name, records, attr in [('notification', messages, 'delivered_at'), ('consultation', consultations, 'replied_at'), ('handoff_decision', handoffs, 'decided_at')]:
        first_by_case = {}
        for record in records:
            end = getattr(record, attr)
            if end:
                previous = first_by_case.get(record.case_id)
                first_by_case[record.case_id] = min(end, previous) if previous else end
        values = []
        for case_id, end in first_by_case.items():
            case = next(c for c in cases if c.id == case_id)
            values.append(max(0, (datetime.fromisoformat(end) - datetime.fromisoformat(case.created_at)).total_seconds()))
        timings[name] = {'mean_seconds': sum(values)/len(values) if values else None, 'measured_episodes': len(values)}
    return {'denominator': len(cases), 'actionable_cases': len(cases), 'stages': stages,
        **stages, 'dispositions': dispositions,
        'residual_need': sum(bool(c.residual_need) for c in cases),
        'understanding': dict(Counter(m.understanding for m in messages)),
        'delay_reasons': dict(Counter(d for c in cases for d in c.delay_reasons)),
        'stage_timings': timings, 'reassurance': reassurance_mean, 'confidence': confidence_mean,
        'outcomes': outcome_metrics(cases, tasks, messages, handoffs, appointments, clock(db)),
        'experience': {'responses': len(experience), 'responding_episodes': len({r.case_id for r in experience}),
            'actionable_episode_denominator': len(cases), 'confidence_mean': confidence_mean,
            'reassurance_mean': reassurance_mean, 'scale': '1–5',
            'method': 'Authenticated synthetic patient self-report. Response means, not improvement or a volunteer study.'},
        'expert_review': 'NOT_RUN',
        'definition': 'Denominator includes every ingested actionable episode, including quarantine, decline, unreachable and accepted transfer with downstream work open. Counts are distinct episodes except understanding response counts.'}


@app.get('/impact', responses={404: {'description': 'Impact report is not available.'}})
def impact(actor=Depends(require_actor)):
    require_role(actor, {'navigator', 'clinician', 'admin'})
    try:
        return json.loads((ROOT / 'reports' / 'impact' / 'impact-summary.json').read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise HTTPException(404, 'Impact report is not available.') from None


@app.get('/impact/method', response_class=PlainTextResponse, responses={404: {'description': 'Impact method is not available.'}})
def impact_method(actor=Depends(require_actor)):
    require_role(actor, {'navigator', 'clinician', 'admin'})
    try:
        return (ROOT / 'docs' / 'IMPACT_MODEL.md').read_text(encoding='utf-8')
    except FileNotFoundError:
        raise HTTPException(404, 'Impact method is not available.') from None


class ClockAdvance(BaseModel):
    hours: float = Field(ge=0, le=720)


@app.post('/demo/clock')
def advance_clock(data: ClockAdvance, actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'admin'})
    if not settings()['demo_mode']:
        raise HTTPException(403, 'Demonstration clock is disabled.')
    record = db.get(Setting, 'demo_clock')
    if not record:
        record = Setting(key='demo_clock', value={'hours': 0})
        db.add(record)
    record.value = {**record.value, 'hours': record.value['hours'] + data.hours}
    audit(db, actor, None, 'demo_clock_advanced', {'hours': data.hours})
    db.commit()
    from .worker import run_once
    run_once(db)
    return {'clock': clock(db).isoformat(), 'notice': 'Demonstration operational windows; not clinical deadlines.'}


@app.post('/demo/reset')
def reset_demo(actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'admin'})
    if not settings()['demo_mode']:
        raise HTTPException(403, 'Demonstration reset is disabled.')
    from .seed import reset
    return reset(db)


@app.get('/reports')
def reports(actor=Depends(require_actor)):
    require_role(actor, {'admin'})
    result = []
    for path in sorted((ROOT / 'reports' / 'runs').glob('*/manifest.json'), reverse=True):
        try:
            manifest = json.loads(path.read_text())
            result.append({**manifest, 'run_id': path.parent.name})
        except (OSError, ValueError):
            continue
    return result


@app.get('/reports/{run_id}/{filename:path}')
def report_download(run_id: str, filename: str, actor=Depends(require_actor)):
    require_role(actor, {'admin'})
    root = (ROOT / 'reports' / 'runs').resolve()
    target = (root / run_id / filename).resolve()
    if not target.is_relative_to(root) or not target.is_file() or target.suffix not in {'.json', '.jsonl', '.csv', '.md', '.html', '.xml', '.png'}:
        raise HTTPException(404, 'Report artifact not found.')
    return FileResponse(target, filename=target.name)


# Root-owned bounded agent integration is optional during backend-only tests.
from services.agents.routes import router as agent_router
from integrations.routes import router as integration_router
app.include_router(agent_router)
app.include_router(integration_router)

# Additive assistant tables register on the shared Base before lifespan init_db.
from services.assistant.routes import router as workspace_assistant_router
app.include_router(workspace_assistant_router)
