# Suhail Health pilot plan

## Ask

Partner with one provider network for a **12-week pilot** on one colorectal screening pathway. The host provides a screening programme lead, a navigator team, a clinical reviewer and an integration owner. Start with the programme's authorized result source and a receiving service that can confirm referrals, attendance and outcomes.

| Weeks | Work | Exit condition |
|---|---|---|
| 1–2 | Agree the data flow, eligible result definition, current baseline, and safety and privacy approvals. Connect a single authorized FHIR or HL7 result feed in a controlled environment. | Reconciled episode denominator and confirmed ownership for every ingested result. |
| 3–4 | Configure routing, due dates, escalation, evidence and closure. Clinicians and Arabic reviewers approve the message templates. Rehearse reconciliation, downtime and recovery. | Clinical and operational sign-off on a synthetic end-to-end rehearsal. |
| 5–10 | Run navigator-led follow-up for eligible patients. Review overdue work, handoffs, unresolved need and safety events with the host. | Complete episode tracking and adjudicated exceptions. |
| 11–12 | Compare the pilot with the agreed baseline. Review missing outcomes, workload and subgroup counts. Decide with the host whether to extend observation or widen the pathway. | Signed evaluation and a decision on further rollout. |

## What we will measure

Use all eligible actionable results as the cohort denominator. Measure time to notification, acknowledgement, confirmed understanding, referral acceptance, appointment, attendance and the documented care endpoint. Report counts, denominators and follow-up intervals. Keep completed care, clinician-authorized exceptions and unresolved episodes visible. Record patient understanding and confidence with a scored check and optional feedback. Report non-response and relevant language or access differences where counts are sufficient. The pilot can observe short-term workflow measures and define a longer follow-up window for completion.

## Data and safeguards

The host approves access, legal basis, data minimization, retention and deletion under its governance process. Begin with synthetic rehearsals, then an approved minimum result feed and one provider handoff. Keep identity mapping within the host's authorized environment. Require organization-scoped accounts, HTTPS, role checks, evidence provenance, audit logs, incident response and a nominated escalation owner. The urgent route remains clinician-led. Review any optional inference separately before using it with pilot data.

For national or regional exchange access, first agree the host's supported interface and registration. Malaffi, NABIDH and Riayati are potential integration paths subject to separate authorization, supported APIs and conformance testing.

## Commercial hypothesis

A subscription per tracked result may fit screening programmes and provider networks. The pilot should measure navigator time, integration and support cost, and how much work remains after a missed visit or rejected referral. Programme owners and payers can compare follow-up completion and workload. Regulators can inspect the episode denominator, ownership, unresolved need and evidence of authorized closure. The pilot should test whether those benefits justify the deployment cost.
