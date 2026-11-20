// Generated from the authoritative persisted Python record types. Do not put credentials here.

export type CommandEnvelope = { expected_version: number; idempotency_key: string; correlation_id?: string };

export type Role = 'patient'|'navigator'|'clinician'|'specialist'|'receiver_a'|'receiver_b'|'connector'|'admin';

export interface CaseRecord {
  id: string;
  dataset: string;
  patient_id: string;
  patient_name: string;
  source_organization: string;
  order_id: string;
  result_version: number;
  test_code: string;
  pathway: string;
  policy_version: string;
  owner: string;
  backup_queue: string;
  disposition: string;
  residual_need: string;
  version: number;
  quarantine_reason: string | null;
  identity_verified: boolean;
  urgent: boolean;
  requires_onward: boolean;
  language: string;
  channel: string;
  issued_at: string;
  created_at: string;
  closed_at: string | null;
  delay_reasons: string[];
}

export interface TaskRecord {
  id: string;
  case_id: string;
  type: string;
  status: string;
  assignee: string;
  next_action: string;
  due_at: string;
  required: boolean;
  reason: string;
  created_at: string;
  completed_at: string | null;
}

export interface MilestoneRecord {
  id: string;
  case_id: string;
  type: string;
  status: string;
  required: boolean;
  evidence_ids: string[];
}

export interface CommunicationRecord {
  id: string;
  case_id: string;
  language: string;
  channel: string;
  body: string;
  template_version: string;
  delivery_status: string;
  acknowledged_at: string | null;
  understanding: string;
  created_at: string;
  delivered_at: string | null;
}

export interface ConsultationRecord {
  id: string;
  case_id: string;
  type: string;
  question: string;
  recipient: string;
  status: string;
  reply: string | null;
  agreed_action: string | null;
  action_owner: string | null;
  human_author: string | null;
  requester: string;
  due_at: string;
  created_at: string;
  replied_at: string | null;
}

export interface HandoffRecord {
  id: string;
  case_id: string;
  scope: string;
  sender: string;
  receiver: string;
  status: string;
  reason: string;
  requested_at: string;
  due_at: string;
  decided_at: string | null;
  decision_actor: string | null;
}

export interface AccessGrantRecord {
  id: string;
  case_id: string;
  handoff_id: string;
  organization: string;
  scope: string;
  purpose: string;
  granted_by: string;
  expires_at: string;
  revoked: boolean;
}

export interface AppointmentRecord {
  id: string;
  case_id: string;
  provider: string;
  scheduled_at: string;
  status: string;
  events: Array<Record<string, unknown>>;
}

export interface EvidenceRecord {
  id: string;
  case_id: string;
  type: string;
  reference: string;
  source: string;
  patient_id: string;
  order_id: string;
  result_version: number;
  verification: string;
  status: string;
  effective_at: string;
  received_at: string;
  verified_by: string | null;
  verification_reason: string | null;
  requires_onward: boolean;
  plan_owner: string | null;
  recall_date: string | null;
}

export interface SourceArtifactRecord {
  reference: string;
  case_id: string;
  source: string;
  authority: string;
  content_hash: string;
  content: Record<string, unknown>;
  received_at: string;
}

export interface EscalationRecord {
  id: string;
  case_id: string;
  trigger: string;
  recipient: string;
  backup: string;
  created_at: string;
  due_at: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  disposition: string | null;
  disposition_by: string | null;
  disposition_reason: string | null;
  escalated_at: string | null;
}

export interface DispositionRecord {
  id: string;
  case_id: string;
  category: string;
  reason: string;
  residual_need: string;
  reviewer: string;
  endpoint: string;
  policy_version: string;
  evidence_ids: string[];
  created_at: string;
}

export interface AuditEventRecord {
  id: string;
  case_id: string | null;
  actor_id: string;
  organization: string;
  event_type: string;
  correlation_id: string;
  before_version: number | null;
  after_version: number | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface OutboxRecord {
  id: string;
  case_id: string;
  kind: string;
  destination: string;
  payload: Record<string, unknown>;
  status: string;
  attempts: number;
  owner: string;
  next_attempt_at: string;
  lease_until: string | null;
  error_code: string | null;
  created_at: string;
}

export interface SourceEventRecord {
  key: string;
  case_id: string;
  source_organization: string;
  event_id: string;
  result_version: number;
  occurred_at: string;
  received_at: string;
  provenance: Record<string, unknown>;
}

export interface PatientExperienceRecord {
  id: string;
  case_id: string;
  patient_id: string;
  confidence: number;
  reassurance: number;
  comment: string;
  captured_at: string;
}

export interface StaffCaseDetail extends CaseRecord {
  phase: string;
  next_action: string;
  due_at: string | null;
  tasks: TaskRecord[];
  milestones: MilestoneRecord[];
  communications: CommunicationRecord[];
  consultations: ConsultationRecord[];
  handoffs: HandoffRecord[];
  appointments: AppointmentRecord[];
  evidence: EvidenceRecord[];
  escalations: EscalationRecord[];
  dispositions: DispositionRecord[];
  audit: AuditEventRecord[];
  experience: PatientExperienceRecord[];
  access_grants: AccessGrantRecord[];
}

export interface ClosureCheck { allowed: boolean; missing: string[]; endpoint: string; policy_version: string; evidence_ids: string[]; case_id: string; version: number }
