from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime, timezone


def utc_time(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('An explicit source timezone is required.')
    return parsed.astimezone(timezone.utc).isoformat()


class Envelope(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=4, max_length=160)
    correlation_id: str | None = Field(default=None, max_length=160)


class ResultEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_id: str = Field(min_length=1, max_length=160)
    source_organization: str = Field(min_length=1, max_length=120)
    patient_id: str = Field(min_length=1, max_length=120)
    patient_name: str = Field(min_length=1, max_length=160)
    order_id: str = Field(min_length=1, max_length=120)
    result_version: int = Field(ge=1)
    test_code: str = Field(min_length=1, max_length=80)
    issued_at: str = Field(min_length=10, max_length=50)
    identity_verified: bool
    trusted_urgent: bool = False
    language: Literal['en', 'ar'] = 'en'
    staffing_available: bool = True
    requires_onward: bool = False
    source_reference: str | None = Field(default=None, max_length=500)
    case_id: str | None = Field(default=None, max_length=80)
    dataset: str = Field(default='demo-v1', max_length=80)
    expected_version: int | None = None
    idempotency_key: str | None = None
    correlation_id: str | None = None
    _issued_utc = field_validator('issued_at')(utc_time)


class Reconciliation(Envelope):
    identity_verified: bool
    pathway: str
    source_reference: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=2000)


class TaskCommand(Envelope):
    task_id: str | None = None
    type: str | None = Field(default=None, max_length=120)
    status: Literal['completed', 'required', 'in_progress'] | None = None
    assignee: str | None = Field(default=None, max_length=120)
    next_action: str | None = Field(default=None, max_length=1000)
    required: bool = True
    reason: str = Field(default='', max_length=2000)


class CommunicationCommand(Envelope):
    case_id: str
    language: Literal['en', 'ar'] = 'en'
    channel: Literal['portal', 'sms_simulator', 'email_simulator'] = 'portal'


class Understanding(Envelope):
    outcome: Literal['passed', 'needs_help', 'unknown']


class Preferences(Envelope):
    language: Literal['en', 'ar']
    channel: Literal['portal', 'sms_simulator', 'email_simulator']


class Barrier(Envelope):
    barrier: str = Field(min_length=1, max_length=120)
    detail: str = Field(default='', max_length=2000)


class Experience(Envelope):
    confidence: int = Field(ge=1, le=5, strict=True)
    reassurance: int = Field(ge=1, le=5, strict=True)
    comment: str = Field(default='', max_length=2000)


class ConsultationCommand(Envelope):
    case_id: str
    type: Literal['patient_to_clinician', 'clinician_to_specialist']
    question: str = Field(min_length=1, max_length=4000)
    recipient: str = 'clinician'


class ConsultationReply(Envelope):
    reply: str = Field(min_length=1, max_length=8000)
    agreed_action: str = Field(min_length=1, max_length=2000)
    action_owner: str = Field(min_length=1, max_length=120)


class HandoffCommand(Envelope):
    case_id: str
    receiver: Literal['provider-a', 'provider-b']
    scope: Literal['episode', 'task']
    reason: str = Field(default='', max_length=2000)


class Decision(Envelope):
    reason: str = Field(default='', max_length=2000)


class AppointmentCommand(Envelope):
    provider: Literal['provider-a', 'provider-b']
    scheduled_at: str = Field(min_length=10, max_length=50)
    _scheduled_utc = field_validator('scheduled_at')(utc_time)


class AppointmentEvent(Envelope):
    status: Literal['booked', 'cancelled', 'no_show', 'attended', 'no_slots']
    occurred_at: str | None = None
    source_event_id: str | None = Field(default=None, max_length=160)
    _occurred_utc = field_validator('occurred_at')(utc_time)


class EvidenceCommand(Envelope):
    type: Literal['investigation', 'reviewed_outcome', 'patient_updated', 'treatment_initiated', 'surveillance_plan', 'outreach', 'exception_review']
    reference: str = Field(min_length=1, max_length=1000)
    source: str | None = Field(default=None, max_length=120)
    patient_id: str = Field(min_length=1, max_length=120)
    order_id: str = Field(min_length=1, max_length=120)
    result_version: int = Field(ge=1)
    requires_onward: bool = False
    effective_at: str | None = None
    plan_owner: str | None = None
    recall_date: str | None = None
    document_text: str | None = Field(default=None, min_length=10, max_length=20000)
    _effective_utc = field_validator('effective_at')(utc_time)


class Verification(Envelope):
    verified: bool
    reason: str = Field(min_length=1, max_length=2000)


class UrgentDisposition(Envelope):
    decision: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=2000)


class CaseDisposition(Envelope):
    category: Literal['completed_required_care', 'clinically_resolved', 'informed_decline', 'unable_to_contact', 'accepted_transfer_open', 'other_exception']
    reason: str = Field(min_length=1, max_length=4000)
    residual_need: str = Field(default='', max_length=2000)


class ProviderCallback(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_id: str = Field(min_length=1, max_length=160)
    kind: Literal['handoff_accept', 'handoff_reject', 'appointment_create', 'appointment_event', 'evidence_add']
    case_id: str
    expected_version: int = Field(ge=1)
    data: dict


class CallbackHandoff(Decision):
    handoff_id: str = Field(min_length=1)


class CallbackAppointmentEvent(AppointmentEvent):
    appointment_id: str = Field(min_length=1)
