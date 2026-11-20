from contextlib import asynccontextmanager
from collections import Counter
from pathlib import Path
import csv
import hashlib
import io
import json
import secrets
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic import ValidationError
from sqlalchemy import select, delete
from . import schemas as s
from .auth import require_actor, create_session, password_verify, user_dict, COOKIE
from .config import settings, ROOT
from .db import (get_db, init_db, User, SessionToken, Case, Task, Communication, Consultation,
    Handoff, Appointment, Evidence, Escalation, Outbox, AuditEvent, AccessGrant, Setting, PatientExperience, now_iso)
from .domain import (intake, command, authorize_case, require_role, serialize_case, closure_check,
    asdict, rows, audit, permitted_grant, referral_packet, clock, complete)


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
        consultations = list(db.scalars(select(Consultation).where(Consultation.recipient.in_([actor['id'], 'specialist']))))
        records = [c for c in records if c.id in {x.case_id for x in consultations}]
    else:
        records = [c for c in records if c.source_organization == actor['organization']]
    result = [serialize_case(db, c, actor) for c in records]
    return result


@app.get('/cases/{case_id}')
def case_detail(case_id: str, actor=Depends(require_actor), db=Depends(get_db)):
    case = authorize_case(db, actor, case_id)
    audit(db, actor, case, 'access_granted', {'scope': 'patient_view' if actor['role'] == 'patient' else 'case'})
    db.commit()
    return serialize_case(db, case, actor)


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
        if permitted_grant(db, actor, item.case_id):
            result.append(referral_packet(db, item))
    return result


@app.get('/integrations/providers/{provider}/referrals/{record_id}')
def provider_packet(provider: str, record_id: str, actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'receiver_a', 'receiver_b', 'connector'})
    item = db.get(Handoff, record_id)
    if not item or item.receiver != provider or actor['organization'] != provider:
        raise HTTPException(403, 'No referral packet grant for this destination.')
    authorize_case(db, actor, item.case_id, packet=True)
    return referral_packet(db, item)


@app.post('/handoffs/{record_id}/accept')
def handoff_accept(record_id: str, data: s.Decision, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Handoff, record_id), 'handoff_accept', data, handoff_id=record_id)


@app.post('/handoffs/{record_id}/reject')
def handoff_reject(record_id: str, data: s.Decision, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Handoff, record_id), 'handoff_reject', data, handoff_id=record_id)


@app.post('/cases/{case_id}/appointments')
def appointment_create(case_id: str, data: s.AppointmentCommand, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, case_id, 'appointment_create', data)


@app.post('/appointments/{record_id}/events')
def appointment_event(record_id: str, data: s.AppointmentEvent, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Appointment, record_id), 'appointment_event', data, appointment_id=record_id)


@app.post('/cases/{case_id}/evidence')
def evidence_add(case_id: str, data: s.EvidenceCommand, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, case_id, 'evidence_add', data)


@app.post('/evidence/{record_id}/verification')
def evidence_verify(record_id: str, data: s.Verification, actor=Depends(require_actor), db=Depends(get_db)):
    return run(db, actor, linked_case(db, Evidence, record_id), 'evidence_verify', data, evidence_id=record_id)


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
        'clock': clock(db).isoformat(), 'service_windows': 'Demonstration policy only; 48h tasks / 24h handoff / 1h urgent review'}


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


@app.get('/metrics')
def metrics(actor=Depends(require_actor), db=Depends(get_db)):
    require_role(actor, {'navigator', 'clinician', 'admin'})
    cases = list(db.scalars(select(Case).where(Case.source_organization == actor['organization'])))
    ids = {c.id for c in cases}
    messages = [m for m in db.scalars(select(Communication)) if m.case_id in ids]
    consultations = [m for m in db.scalars(select(Consultation)) if m.case_id in ids]
    handoffs = [m for m in db.scalars(select(Handoff)) if m.case_id in ids]
    appointments = [m for m in db.scalars(select(Appointment)) if m.case_id in ids]
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
        'experience': {'responses': len(experience), 'responding_episodes': len({r.case_id for r in experience}),
            'actionable_episode_denominator': len(cases), 'confidence_mean': confidence_mean,
            'reassurance_mean': reassurance_mean, 'scale': '1–5',
            'method': 'Authenticated synthetic patient self-report. Response means, not improvement or a volunteer study.'},
        'expert_review': 'NOT_RUN',
        'definition': 'Denominator includes every ingested actionable episode, including quarantine, decline, unreachable and accepted transfer with downstream work open. Counts are distinct episodes except understanding response counts.'}


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
    record.value = {'hours': record.value['hours'] + data.hours}
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
