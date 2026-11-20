import {human} from './api';

const labels: Record<string, string> = {
  'verified_current_evidence:investigation': 'Verified investigation result is missing',
  'verified_current_evidence:reviewed_outcome': 'Clinician-reviewed outcome is missing',
  'verified_current_evidence:patient_updated': 'Record that the patient was told the outcome is missing',
  declared_onward_care_endpoint: 'Onward care needs treatment started or an owned surveillance plan',
  urgent_clinician_disposition: 'Urgent flag awaits a clinician decision',
  policy_version_review: 'Current pathway policy needs review',
  'navigation-team': 'Navigation team',
  'screening-exceptions': 'Screening exceptions desk',
  clinician: 'Clinician',
  'on-call-clinician': 'On-call clinician',
  'provider-a': 'Provider A',
  'provider-b': 'Provider B',
  'integration-operations': 'Integration operations',
  diagnostic_followup_review_and_patient_plan: 'Diagnostic follow-up, clinician review and patient plan',
  treatment_initiation_or_authorized_surveillance: 'Treatment started or authorized surveillance',
  result_ingested: 'Result received',
  identity: 'Identity confirmed',
  notification: 'Patient notified',
  acknowledgement: 'Patient acknowledged',
  understanding: 'Understanding confirmed',
  referral: 'Referral accepted',
  appointment: 'Appointment booked',
  attendance: 'Appointment attended',
  investigation: 'Investigation completed',
  reviewed_outcome: 'Outcome reviewed by clinician',
  patient_updated: 'Patient told the outcome',
  handoff_rejected: 'Referral rejected by provider',
  handoff_timeout: 'Referral expired without a response',
  no_show: 'Appointment missed',
  cancelled: 'Appointment cancelled',
  no_slots: 'No appointments available',
};

const arabic: Record<string, string> = {
  'navigation-team': 'فريق تنسيق الرعاية',
  'screening-exceptions': 'مكتب الحالات الخاصة',
  clinician: 'الطبيب',
  'on-call-clinician': 'الطبيب المناوب',
  'provider-a': 'المزوّد أ',
  'provider-b': 'المزوّد ب',
  'integration-operations': 'عمليات التكامل',
};

const steps: Record<string, string> = {
  notification: 'Notification',
  acknowledgement: 'Patient acknowledgement',
  understanding: 'Understanding check',
  referral: 'Referral acceptance',
  appointment: 'Appointment booking',
  attendance: 'Attendance',
  investigation: 'Investigation',
  reviewed_outcome: 'Outcome review',
  patient_updated: 'Patient update',
  treatment_initiated: 'Treatment started',
  understanding_help: 'Help with understanding the result',
  referral_recovery: 'Referral recovery',
  appointment_recovery: 'Appointment recovery',
  urgent_review: 'Urgent clinician review',
  quarantine: 'Identity or pathway reconciliation',
};

const capitalized = (value: unknown) => human(value).replace(/^./, first => first.toUpperCase());

export function label(code: unknown, lang: 'en' | 'ar' = 'en'): string {
  const key = String(code ?? '');
  if (lang === 'ar' && Object.hasOwn(arabic, key)) return arabic[key];
  if (Object.hasOwn(labels, key)) return labels[key];
  const [prefix, kind] = key.split(':', 2);
  if (kind) {
    const step = Object.hasOwn(steps, kind) ? steps[kind] : capitalized(kind);
    if (prefix === 'quarantine') return 'Identity or pathway must be reconciled first';
    if (prefix === 'open_required_task') return step + ' not yet completed';
    if (prefix === 'overdue') return step + ' overdue';
    if (prefix === 'barrier') return capitalized(kind) + ' barrier';
    if (prefix === 'verified_current_evidence' || prefix === 'verified_current_onward_evidence') {
      return 'Verified ' + human(kind) + ' evidence is missing';
    }
  }
  return capitalized(code);
}
