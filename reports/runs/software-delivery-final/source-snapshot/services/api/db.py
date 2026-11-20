from datetime import datetime, timezone
import uuid
from sqlalchemy import create_engine, String, Integer, Boolean, Text, JSON, ForeignKey, UniqueConstraint, select, insert, text
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, sessionmaker
from .config import settings


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix='rec'):
    return prefix + '-' + uuid.uuid4().hex[:16]


class Base(DeclarativeBase):
    pass


class Case(Base):
    __tablename__ = 'cases'
    __table_args__ = (UniqueConstraint('source_organization', 'patient_id', 'order_id'),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset: Mapped[str] = mapped_column(String, default='demo-v1', index=True)
    patient_id: Mapped[str] = mapped_column(String, index=True)
    patient_name: Mapped[str] = mapped_column(String)
    source_organization: Mapped[str] = mapped_column(String)
    order_id: Mapped[str] = mapped_column(String)
    result_version: Mapped[int] = mapped_column(Integer)
    test_code: Mapped[str] = mapped_column(String)
    pathway: Mapped[str] = mapped_column(String, default='colorectal-fit')
    policy_version: Mapped[str] = mapped_column(String, default='demo-fit-v1')
    owner: Mapped[str] = mapped_column(String, default='navigation-team')
    backup_queue: Mapped[str] = mapped_column(String, default='screening-exceptions')
    disposition: Mapped[str] = mapped_column(String, default='open')
    residual_need: Mapped[str] = mapped_column(Text, default='Diagnostic follow-up pending')
    version: Mapped[int] = mapped_column(Integer, default=1)
    quarantine_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    identity_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_onward: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String, default='en')
    channel: Mapped[str] = mapped_column(String, default='portal')
    issued_at: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
    closed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    delay_reasons: Mapped[list] = mapped_column(JSON, default=list)


class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('task'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='required')
    assignee: Mapped[str] = mapped_column(String)
    next_action: Mapped[str] = mapped_column(String)
    due_at: Mapped[str] = mapped_column(String, index=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
    completed_at: Mapped[str | None] = mapped_column(String, nullable=True)


class Milestone(Base):
    __tablename__ = 'milestones'
    __table_args__ = (UniqueConstraint('case_id', 'type'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('ms'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='required')
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)


class Communication(Base):
    __tablename__ = 'communications'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('msg'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    language: Mapped[str] = mapped_column(String)
    channel: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    template_version: Mapped[str] = mapped_column(String, default='demo-fit-message-v1')
    delivery_status: Mapped[str] = mapped_column(String, default='queued')
    acknowledged_at: Mapped[str | None] = mapped_column(String, nullable=True)
    understanding: Mapped[str] = mapped_column(String, default='unknown')
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
    delivered_at: Mapped[str | None] = mapped_column(String, nullable=True)


class Consultation(Base):
    __tablename__ = 'consultations'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('consult'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    type: Mapped[str] = mapped_column(String)
    question: Mapped[str] = mapped_column(Text)
    recipient: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='awaiting_reply')
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    agreed_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_owner: Mapped[str | None] = mapped_column(String, nullable=True)
    human_author: Mapped[str | None] = mapped_column(String, nullable=True)
    requester: Mapped[str] = mapped_column(String)
    due_at: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
    replied_at: Mapped[str | None] = mapped_column(String, nullable=True)


class Handoff(Base):
    __tablename__ = 'handoffs'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('handoff'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    scope: Mapped[str] = mapped_column(String)
    sender: Mapped[str] = mapped_column(String)
    receiver: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='requested')
    reason: Mapped[str] = mapped_column(Text, default='')
    requested_at: Mapped[str] = mapped_column(String, default=now_iso)
    due_at: Mapped[str] = mapped_column(String)
    decided_at: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_actor: Mapped[str | None] = mapped_column(String, nullable=True)


class AccessGrant(Base):
    __tablename__ = 'access_grants'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('grant'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    handoff_id: Mapped[str] = mapped_column(ForeignKey('handoffs.id'), index=True)
    organization: Mapped[str] = mapped_column(String)
    scope: Mapped[str] = mapped_column(String, default='referral_packet')
    purpose: Mapped[str] = mapped_column(String, default='synthetic-care-coordination')
    granted_by: Mapped[str] = mapped_column(String)
    expires_at: Mapped[str] = mapped_column(String)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Appointment(Base):
    __tablename__ = 'appointments'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('appt'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    provider: Mapped[str] = mapped_column(String)
    scheduled_at: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='booked')
    events: Mapped[list] = mapped_column(JSON, default=list)


class Evidence(Base):
    __tablename__ = 'evidence'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('ev'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    type: Mapped[str] = mapped_column(String)
    reference: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    patient_id: Mapped[str] = mapped_column(String)
    order_id: Mapped[str] = mapped_column(String)
    result_version: Mapped[int] = mapped_column(Integer)
    verification: Mapped[str] = mapped_column(String, default='pending')
    status: Mapped[str] = mapped_column(String, default='current')
    effective_at: Mapped[str] = mapped_column(String, default=now_iso)
    received_at: Mapped[str] = mapped_column(String, default=now_iso)
    verified_by: Mapped[str | None] = mapped_column(String, nullable=True)
    verification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_onward: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_owner: Mapped[str | None] = mapped_column(String, nullable=True)
    recall_date: Mapped[str | None] = mapped_column(String, nullable=True)


class SourceArtifact(Base):
    """Actual registered document/resource body, distinct from a claimed evidence URI."""
    __tablename__ = 'source_artifacts'
    reference: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    source: Mapped[str] = mapped_column(String)
    authority: Mapped[str] = mapped_column(String)
    content_hash: Mapped[str] = mapped_column(String)
    content: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[str] = mapped_column(String, default=now_iso)


class PatientExperience(Base):
    __tablename__ = 'patient_experience'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('experience'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    patient_id: Mapped[str] = mapped_column(String)
    confidence: Mapped[int] = mapped_column(Integer)
    reassurance: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default='')
    captured_at: Mapped[str] = mapped_column(String, default=now_iso)


class Escalation(Base):
    __tablename__ = 'escalations'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('esc'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    trigger: Mapped[str] = mapped_column(String)
    recipient: Mapped[str] = mapped_column(String, default='clinician')
    backup: Mapped[str] = mapped_column(String, default='on-call-clinician')
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
    due_at: Mapped[str] = mapped_column(String)
    acknowledged_at: Mapped[str | None] = mapped_column(String, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String, nullable=True)
    disposition: Mapped[str | None] = mapped_column(Text, nullable=True)
    disposition_by: Mapped[str | None] = mapped_column(String, nullable=True)
    disposition_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalated_at: Mapped[str | None] = mapped_column(String, nullable=True)


class Disposition(Base):
    __tablename__ = 'dispositions'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('disp'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    category: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    residual_need: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String)
    endpoint: Mapped[str] = mapped_column(String)
    policy_version: Mapped[str] = mapped_column(String)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('audit'))
    case_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    actor_id: Mapped[str] = mapped_column(String)
    organization: Mapped[str] = mapped_column(String)
    event_type: Mapped[str] = mapped_column(String)
    correlation_id: Mapped[str] = mapped_column(String)
    before_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    after_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)


class Outbox(Base):
    __tablename__ = 'outbox'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('out'))
    case_id: Mapped[str] = mapped_column(ForeignKey('cases.id'), index=True)
    kind: Mapped[str] = mapped_column(String)
    destination: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default='pending', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    owner: Mapped[str] = mapped_column(String, default='integration-operations')
    next_attempt_at: Mapped[str] = mapped_column(String, default=now_iso)
    lease_until: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)


class Receipt(Base):
    __tablename__ = 'command_receipts'
    key: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(String)
    command: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str] = mapped_column(String)
    fingerprint: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer)


class SourceEvent(Base):
    __tablename__ = 'source_events'
    key: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(String)
    source_organization: Mapped[str] = mapped_column(String)
    event_id: Mapped[str] = mapped_column(String)
    result_version: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[str] = mapped_column(String)
    received_at: Mapped[str] = mapped_column(String, default=now_iso)
    provenance: Mapped[dict] = mapped_column(JSON)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    organization: Mapped[str] = mapped_column(String)
    patient_id: Mapped[str | None] = mapped_column(String, nullable=True)
    password_hash: Mapped[str] = mapped_column(String)


class SessionToken(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[str] = mapped_column(String)


class Setting(Base):
    __tablename__ = 'settings'
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


url = settings()['database_url']
engine = create_engine(url, pool_pre_ping=True, **({'connect_args': {'check_same_thread': False}} if url.startswith('sqlite') else {}))
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    with engine.begin() as connection:
        if engine.dialect.name == 'postgresql':
            # API/worker startup may race on a fresh Compose volume.
            connection.execute(text('SELECT pg_advisory_xact_lock(91604932450636)'))
        Base.metadata.create_all(connection)
        if not connection.execute(select(Setting.key).where(Setting.key == 'schema_version')).first():
            connection.execute(insert(Setting).values(key='schema_version', value={'version': 1}))


def get_db():
    with SessionLocal() as db:
        yield db
