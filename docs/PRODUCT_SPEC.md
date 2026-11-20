# Suhail Health Product Specification

Version 1.1 | 14 November 2026 | Future Health Population Health Challenge 05

This product contract is packaged with CODEX_BUILD_PROMPT.md. Groq is the default inference provider; the main prompt and benchmark protocol specify its current API and report requirements. This is the implementation reference for Suhail Health. Build an add-on coordination service that carries an actionable screening result through communication, consultation, confirmation when required, accepted referral, appropriate care and documented closure. Existing hospital systems retain their clinical authority. Suhail owns its coordination ledger and links each clinical milestone to its source evidence.

The governing scope is the Challenge 05 statement supplied in this conversation. Its six requirements control product decisions. This document supersedes the earlier CareRelay and Suhail concept plans. The existing interactive interface is a design concept; its simulated button actions are not implemented backend capabilities.

**Recommendation:** proceed. The direction is relevant and potentially competitive if the team demonstrates completed workflows, recovery from failures and credible measurements. A polished interface and model scores alone would leave major challenge requirements unproven. No reliable probability of winning can be assigned from the public rubric or available information about other entrants.

**Fixed first release:** one complete colorectal screening follow-up pathway, five practical user surfaces, six bounded agent functions, a persisted workflow, English and Arabic core messages, two independent simulated provider services, a FHIR test server, file intake and reproducible evaluation. Existing models and RAG come first. Expert assessment is a separate optional evidence workstream.

**Primary success claim:** the prototype makes responsibility, next actions, consultation outcomes and required evidence visible across provider boundaries, and demonstrates the effect of the workflow and AI on named test scenarios. Patient outcome improvement requires later clinical evidence.

**How to use this reference:** implement sections 2 to 10 in the order in section 13; use sections 11 and 12 as verification contracts; prepare the demonstration in section 14; start Codex with section 15. Keep the Markdown and PDF synchronized from the same content. Changes to scope, endpoint or safety rules require a versioned decision before implementation.

**Document status:** specification completed; application implementation, model deployment, benchmark results, hospital integration and external expert validation are pending. Submission is listed for 20 November 2026; confirm the dashboard cutoff and required formats [1].

<!-- page -->
## 1 Challenge requirements and traceability

The challenge asks how innovative, low-friction approaches can ensure every actionable screening result leads to timely communication, rapid patient-to-clinician or clinician-to-clinician consultation, appropriate confirmation and follow-up, clear ownership, completed referral and documented closure across providers and care settings. The objective is conversion of an actionable result into timely appropriate care.

The requirement names below come from the user-supplied Challenge 05 statement. IDs are internal development references, not official organizer IDs.

| Requirement | Required product evidence | Acceptance scenarios |
| --- | --- | --- |
| CH05-1 End-to-end visibility | Source-linked milestones from result issuance through notification, acknowledgement, understanding, consultation, confirmation, referral, appointment, attendance, treatment initiation or surveillance and closure. | AT01, AT03, AT08, AT10, AT18 |
| CH05-2 Ownership and timely progression | One accountable episode owner, task assignees, accepted transfers, backup queue, configured deadlines and visible rejected, unassigned or overdue work. | AT02, AT05, AT06, AT14, AT17 |
| CH05-3 Patient communication and reassurance | Plain-language information, suitable channel and language, separate understanding check, question/help request, barrier capture and reassurance measurements. | AT03, AT04, AT15 |
| CH05-4 Consultation and coordination | Assigned patient callback and clinician consultation with a human response, agreed next action and owner; referral acceptance and returning care evidence. | AT04, AT05, AT08, AT18 |
| CH05-5 Human-governed escalation | Trusted urgent signals reach qualified staff, acknowledgement and disposition are distinct, and evidence or an authorized human decision governs closure. | AT07, AT09, AT10, AT11, AT13 |
| CH05-6 Closure and impact measures | Defined denominators, stage timings, completed care, unresolved need, delay reasons, dispositions, understanding and confidence; results identified by evidence type. | AT12, AT15, AT19, AT20 |

Every backlog item must identify its requirement ID, backend behavior, relevant UI and acceptance test. Infrastructure items may support several requirements. A feature without a clear relationship to the challenge or the published assessment dimensions should be deferred.

The public assessment considers clinical relevance, technical architecture, demonstration, responsible AI and data governance, deployment readiness and commercial viability. Public numerical weights were not stated [1]. Treat the traceability and proposed gates in this plan as team decisions, not an invented organizer scoring formula.

<!-- page -->
## 2 Scope and the care endpoint

**Included:** actionable-result intake; source and identity validation; accountable ownership; result communication and understanding; patient questions; clinician-to-clinician consultation; required confirmation; accepted referrals; appointment and attendance events; treatment-initiation or surveillance evidence where applicable; urgent exceptions; closure review; audit and impact reporting.

**First pathway:** positive fecal immunochemical test screening follow-up. Abnormal stool screening results require further colonoscopy evaluation [2]. The prototype coordinates an already actionable result; it does not interpret an image, diagnose cancer or decide medical eligibility. Local clinical policy and service windows remain configurable. Mark prototype rules as demonstration configurations until appropriately approved for a deployment.

**Episode endpoint:** complete the required diagnostic follow-up, record the clinician's assessment and communicate the next plan. When further care is indicated, retain the episode until the configured treatment-initiation endpoint is evidenced or an authorized surveillance plan is accepted with an owner and recall date. A referral, booked visit or completed procedure is only a milestone when later required evidence is outstanding.

Three demonstration branches make this explicit:

1. Assessment resolves the actionable concern: required investigation/outcome evidence, authorized review, patient communication and documented recall or no-further-action decision support closure.
2. Assessment requires onward care: open a linked owned task for the relevant receiving service. The episode remains unresolved until its declared care endpoint or authorized clinical disposition is documented. A transfer alone does not count as completed care.
3. Patient declines, cannot be contacted or another exception occurs: retain outreach and escalation evidence, an authorized handling decision and a separate exception disposition. Show any remaining care need; do not count the episode as care completed.

**Deferred:** generalized emergency-department triage, autonomous diagnosis or prescribing, new disease prediction, imaging interpretation, a second complete screening pathway, speech-model training, broad patient chat, live national-exchange onboarding and an independent foundation-model training effort. Optional fine-tuning and expert review cannot block completion of the first pathway.

**Reusable design:** pathway configuration defines applicable test mappings, required and conditional milestones, evidence types, role permissions, message templates, service windows and closure conditions. A second configuration can demonstrate extensibility after the first pathway works; it must not be presented as a validated clinical pathway without the corresponding evidence.

<!-- page -->
## 3 Milestones and patient outcomes

Store milestones independently. Consultation, notification, referral and confirmation may overlap. Derive the displayed phase from unfinished required work; do not use one linear status or a next button as the clinical truth.

| Milestone | Evidence required to mark it completed |
| --- | --- |
| Result issued and ingested | Issuance time, result/order reference, source, status and version; separate received time. |
| Identity and actionability established | Deterministic match or authorized reconciliation; configured actionable-result mapping or human decision. |
| Owner established | Accountable team, responsible service, backup queue and next due action. |
| Notification attempted and delivered | Channel, language, template/version and delivery outcome. Delivery is not acknowledgement. |
| Acknowledgement and understanding | Separate patient acknowledgement and teach-back outcome; failed or unknown understanding creates follow-up work. |
| Consultation when required | Patient question or clinician request, assigned clinician, documented human reply, agreed next action and owner. |
| Confirmation when required | Applicable order, completed assessment/result, clinician review and any required additional evidence. |
| Referral accepted | Correct destination and authorized receiving actor's acceptance, linked to the relevant task. |
| Appointment and attendance | Separate booking, cancellation, no-show and attended events from an identified source. |
| Appropriate care reached | Evidence of the pathway's treatment-initiation endpoint or accepted surveillance/recall plan, when required. |
| Patient updated and episode disposition | Documented outcome communication, current evidence check and authorized disposition. |

Milestone states: required, ready, in progress, awaiting external action, completed, blocked, overdue, cancelled or not applicable. Not applicable needs a role-authorized reason under the pathway rules. Required evidence can become invalid after a corrected result; retain the earlier record and reopen affected work.

Episode dispositions: open, completed required care, clinically resolved by authorized decision, accepted transfer with downstream work open, informed decline, unable to contact, or another authorized exception. Record the clinical rationale and residual care need independently from administrative completion.

A closure review must answer: which endpoint applied, which milestones were required, which evidence satisfies them, which exceptions were authorized, what ongoing work remains, who owns it, and whether the patient was informed. Keep closure timestamp, reviewer and policy version. Do not automatically close outstanding care because a patient-facing message was read or a clinician opened a chart.

<!-- page -->
## 4 Ownership escalation and closure invariants

**Episode owner and task assignee are separate fields.** The episode owner remains accountable for the whole case; a consultation or specialist task may have another assignee. Proposing a new episode owner does not release the sending owner. Transfer requires explicit acceptance from an authorized receiving actor. Rejection, timeout and provider disconnection leave the sending owner in place.

At intake, use the facility's configured navigation/intake team and backup queue. An uncertain identity or unsupported pathway creates owned quarantined work. Do not contact an uncertain patient or merge records using an LLM similarity guess. Missing staffing mappings enter the visible backup exception queue rather than dropping the result.

Recovery requires an authorized reconciliation command with source evidence, current case version and audit. A qualified operator can confirm identity or select an existing permitted pathway; a permitted reviewer can verify pending uploaded evidence. Recreate affected tasks after reconciliation. Ordinary task completion cannot release an identity, pathway or evidence gate.

Non-negotiable invariants:

- No actionable event is silently lost; every active or quarantined case has an accountable queue.
- Every open required task has an assignee or accountable exception queue, next action and due condition.
- A model cannot downgrade a trusted urgent flag, authorize clinical decisions or waive required evidence.
- Sending an alert, staff acknowledgement and clinical disposition are distinct events.
- Booking, attendance, completed assessment and clinician-reviewed outcome are distinct events.
- Acknowledgement and demonstrated understanding are distinct events.
- Duplicate, delayed or reordered events cannot duplicate referrals, erase urgency or silently extend deadlines.
- Corrected clinical information invalidates affected evidence and triggers fresh review.
- Decline, lost contact and administrative closure are never counted as completed care.
- Clinical state changes require server-side authorization and a current case version.

**Urgent screening-pathway branch:** trusted incoming critical-result flags invoke the configured staff escalation independently of model or RAG availability. Concerning patient text can create a review proposal; existing hospital urgent procedures remain authoritative. Show the alert recipient, acknowledged time, reviewing clinician and disposition. Escalate unacknowledged tasks to the configured backup. Pause affected routine transitions until the required disposition. This is a safety branch within screening follow-up, not a general ED triage product.

**Closure contract:** a deterministic check returns missing or invalid requirements. A separate authorized disposition command rechecks current evidence, remaining tasks, urgent review, policy version and authorization within a transaction. The closure assistant may locate evidence but cannot approve closure. An exceptional human decision records its rationale and outcome category without rewriting the record to imply care was received.

<!-- page -->
## 5 Canonical records and event rules

Use PostgreSQL as the authoritative coordination store. Preserve clinical source identifiers and record provenance; do not replace the hospital's diagnostic record. Use structured records rather than storing the whole case only in agent conversation history.

| Record | Minimum fields or responsibility |
| --- | --- |
| Case | ID, patient/source references, source organization, result/order/version, pathway/version, episode owner, backup queue, derived phase, disposition, residual care need, row version. |
| Milestone and task | Type, required/conditional rule, prerequisites, status, assignee, due time/condition, evidence requirements and completion record. |
| Handoff | Episode or task scope, sending owner, proposed receiver, request time, accepted/rejected status, authorized actor and decision time. |
| Communication | Channel, consent/preference state, language/template, delivery status, acknowledgement, understanding check and callback need. |
| Consultation | Patient-to-clinician or clinician-to-clinician type, question, recipient, urgency source, response, human author, agreed action and owner. |
| Appointment | Receiving service, source appointment ID, status events and timestamps; linked attendance/encounter evidence. |
| Evidence | Patient/order/case link, evidence type, document/resource reference, source, effective/received times, verification state and superseded version. |
| Access grant | Case/packet scope, sending and receiving organization, authorized participant, purpose/basis, granted-by actor, expiry and revocation. Independent from ownership. |
| Escalation | Trigger/source, priority rule, staff recipient, backup, alert, acknowledgement and disposition records. |
| Disposition | Outcome category, endpoint, reviewer, reason, evidence references, ongoing work and communication evidence. |
| Audit event and outbox | Actor, organization, event type, correlation and idempotency keys, before/after references, delivery attempts and recovery state. |

Each external event carries event ID, source organization, patient and order references, case correlation where known, occurred time, received time, resource version, event type and provenance. Validate against the authenticated connector and a schema before applying it.

Use a unique source/event key for deduplication. Commit state changes, audit events and outbox messages atomically. Workers deliver outbox actions with bounded retries and idempotent destination commands. Persist deadlines and worker leases; restart must not lose overdue tasks. Keep a dead-letter queue with an accountable operator and visible retry/reconcile actions.

For amended results, compare versions rather than assuming arrival order is clinical order. Record both original and correction, identify affected milestones and reopen them. Preserve the human review history. Use synthetic stable identifiers in all public demonstrations and redact secrets from logs.

<!-- page -->
## 6 Application commands and access control

Define narrow commands. The model requests a tool action; application code validates identity, role, organization, patient scope, state version and idempotency before committing it. The following routes are the planned contract; response schemas belong in the API package.

| Route or command | Required behavior |
| --- | --- |
| POST /events/results | Authenticate source, validate event/version, deduplicate, create or reconcile an owned case. |
| GET /cases and /cases/{id} | Return authorized queue/detail, milestones, next actions and evidence references. |
| POST /cases/{id}/tasks | Create or update an allowed task with owner, prerequisites and due condition. |
| POST /cases/{id}/reconciliation | Authorized identity/pathway resolution with source evidence, version check, audit and affected-task reconciliation. |
| POST /handoffs | Propose transfer; retain existing accountability until accepted. |
| POST /handoffs/{id}/accept or /reject | Verify receiving actor and expected version; update acceptance and ownership atomically. |
| POST /communications | Send approved content through a connector; persist delivery separately. |
| POST /communications/{id}/acknowledgement or /understanding | Record patient response against the correct communication; create assistance work if needed. |
| POST /consultations and /consultations/{id}/reply | Assign question; record authorized clinician response, resulting task and owner. |
| POST /appointments/{id}/events | Reconcile booking, cancellation, no-show or attendance with source and time. |
| POST /cases/{id}/evidence | Link validated source evidence; uncertain uploads remain pending verification. |
| POST /evidence/{id}/verification | Authorized reviewer records source/matching checks or rejection; an upload alone cannot clear the evidence gate. |
| POST /escalations/{id}/acknowledge or /disposition | Record separate staff acknowledgement and clinician decision. |
| GET /cases/{id}/closure-check | Return missing, conflicting, stale or unauthorized evidence and active required work. |
| POST /cases/{id}/dispositions | Recheck closure contract transactionally; store clinical completion or explicit exception category. |

Command envelopes include correlation ID, idempotency key and expected case version. Return explicit validation, authorization, conflict and unavailable-connector errors. A success response means a recorded action; externally delivered or clinically completed work needs its own evidence.

Roles: patient sees only their own permitted information and submits preferences/questions; navigator coordinates approved communication and tasks; clinician records clinical responses and dispositions; receiving-service staff accepts authorized handoffs and appointment events; connector identity submits permitted source events; administrator manages configuration and access. An administrator role must not silently impersonate a clinician.

Use organization-scoped access, patient authorization and explicit clinician privileges. A simulated role switcher belongs only in the demo environment. Do not implement a broad agent can do anything endpoint or trust an actor ID supplied in model-generated text.

<!-- page -->
## 7 Architecture and hospital integration

Default implementation: Next.js with TypeScript for the interface; FastAPI with validated schemas for application commands; PostgreSQL for coordination, audit, outbox and deadlines; pgvector or a replaceable retrieval index; LangGraph with a durable PostgreSQL checkpointer for agent execution and approval pauses. Pin dependency versions in the repository. Keep business authorization and closure checks in the application service, independently of agent prompts.

LangGraph supports persisted pauses for human input [3]. Graph checkpointing does not itself make external side effects exactly once. Tool executions and outbox delivery still require idempotency and replay-safe commands.

Deploy separate components for web, API, worker, database, model gateway, FHIR test server and two provider simulators. Start the demonstration with one compose command. The provider simulators must be independently running services, not only browser state changes. Both send authenticated callbacks and support rejection, acceptance and returning downstream evidence.

| Integration | First-release proof | Deployment limitation |
| --- | --- | --- |
| FHIR R4 | Synthetic Patient, Observation/DiagnosticReport, ServiceRequest, Task, Appointment and downstream encounter/procedure evidence. | Resource support and write permission vary by installation. |
| Provider services A and B | Referral request, reject/accept callbacks, appointment status and evidence return across service boundaries. | Simulated provider organizations, clearly identified. |
| File intake | Validated synthetic CSV/JSON and a small controlled document example, with source and matching review. | A file upload alone does not establish clinical evidence authenticity. |
| Existing EHR | Connector interface and documented capability discovery; source chart links. | Real credentials, registration and supported interfaces are prerequisites. |
| UAE exchanges | Integration plan referencing Malaffi, NABIDH and Riayati. | No live national-exchange connection or universal write access is claimed. |

Epic and Oracle document FHIR interfaces [4,5]. Mediclinic has published a TrakCare implementation announcement [6]. UAE authorities describe exchange integration [7]. SMART on FHIR can support embedded EHR launch where installed and authorized [8]. These establish plausible integration routes, not ready access to any hospital.

Maintain a capability matrix marking each operation implemented, simulated, manual or unsupported. Approved writeback is optional and capability-dependent. A failed writeback remains visible and owned. Support standalone coordination first, then connected and embedded deployments as the hospital permits.

A proposed receiver sees only the authorized minimum referral packet through an explicit access grant. Acceptance changes accountability without granting unrestricted source-provider record access. Apply expiry/revocation and patient-sharing permissions or the institution's authorized sharing basis. Test both permitted receiving-team access and unrelated-provider denial.

<!-- page -->
## 8 Agent graph and permitted tools

Use six bounded functions sharing a model endpoint where practical. The graph orchestrates their work; a separate model per function is unnecessary. Preserve structured proposals, tool events and source references, not hidden reasoning as clinical evidence.

| Function | Output and permitted tools | Authority boundary |
| --- | --- | --- |
| Intake | Extract fields/source spans; read permitted records; submit a reconciliation proposal. | Cannot merge uncertain identities or invent missing facts. |
| Pathway router | Suggest supported pathway from configured codes/context; retrieve applicable pack. | Unsupported or uncertain cases go to review; no invented pathway. |
| Safety and escalation | Identify concerning content; prepare staff handoff; request review. | Fixed rules enforce trusted urgent flags; model cannot clear them. |
| Patient navigator | Use approved messages, assess teach-back, record barriers and request callback. | Clinical questions route to clinicians; no autonomous diagnosis or prescribing. |
| Coordination | Prepare consultation/referral packet, inspect acceptance, propose scheduling and recovery tasks. | Actual consultation response and clinical decisions require authorized humans. |
| Closure evidence | Find relevant records, compare evidence requirements, call closure-check. | Cannot waive evidence, claim a procedure occurred or authorize a disposition. |

Graph sequence: validated intake enables pathway selection and required milestone creation. Communication, consultation, confirmation and referral tasks may run concurrently when prerequisites allow. External events resume waiting work. Urgent signals interrupt affected routine progression. Evidence review reaches a human approval pause before the separate application disposition command.

Tools should map to narrow application commands and read-only queries: read_case, retrieve_policy, propose_task, draft_communication, request_callback, prepare_consultation, propose_referral, inspect_available_slots, inspect_handoff and check_closure. Give each function only the tools it needs. Never expose unrestricted SQL, shell, arbitrary network access or arbitrary message sending to clinical agents.

A proposal contains case ID/version, function name, recommended action, source references, policy version, missing fields and review reason. Validate structured output; source excerpts and outside documents are data, not tool instructions. An unsupported recommendation becomes review work, not an automatic fallback action.

Persist approval pauses. Bound steps, retries, context length and tool budgets. Model timeout or invalid output falls back to approved templates and a staffed queue. The workflow, urgent routing, timers and required-evidence checks continue without model inference.

<!-- page -->
## 9 Knowledge and the Groq provider

Use a small versioned disease knowledge pack and the owner-provided Groq key. Read the external dotenv file server-side; preserve its contents and never expose credentials in browser variables, logs, reports or source control. Existing process variables take precedence. Keep required local runtime settings in a separate ignored file.

Default candidates are openai/gpt-oss-120b and openai/gpt-oss-20b, subject to actual account availability [9]. Respect a configured model, probe capabilities with synthetic inputs and record the exact model in each run. A different model starts a different benchmark run. H100s are optional future comparison resources and do not block application completion.

Implement separate schema-output and tool-call modes. Current Groq Structured Outputs documentation excludes combining them with tools or streaming [10]. Use strict extraction/final proposal requests only on a supported model, and a separate bounded local function-calling loop with validated tools/arguments and role checks [11]. Do not assume parallel tool calls for GPT-OSS. Recheck and record compatibility at implementation time.

Enforce timeouts, request/token/step budgets, concurrency, finite retries and retry-after. Provider errors and exhaustion remain explicit. Templates are a deliberate labelled operating mode, never fake live inference. Keep urgent rules, ownership, evidence, timers and clinical authority in application code. Do not enable unrestricted provider browsing, code execution or remote MCP.

RAG retains source authority, jurisdiction, pathway, effective/version dates, language, access scope and exact citation locations. Retrieve only permitted content; filter before keyword/vector retrieval and optional reranking. Distinguish published guidance, demonstration workflow defaults and actually reviewed local policy. Missing/conflicting/expired content or document prompt injection creates review work. It must not silently generate a new clinical rule.

Use permitted public/synthetic records for Groq. Credentialed MIMIC stays outside this default path [12]. MedAgentBench is optional until the specific data/container/scorer release and cloud-processing permissions are established; do not assume its profiles are wholly synthetic. Follow BENCHMARK_PROTOCOL.md for separate software, live-agent and adapted external reports.

Defer training until a functioning end-to-end application and measured error analysis justify a narrow adaptation. Eight H100s are not an application deployment requirement. Benchmark token/request budgets govern the default Groq implementation.

<!-- page -->
## 10 Interface layout and relevance

Preserve the Suhail Health logo and teal/gold identity. Use gold sparingly for navigation emphasis, with text labels for status. Provide accessible contrast, keyboard interactions, mobile reflow and Arabic RTL. The interface should answer four questions immediately: where the case is, what happens next, who is responsible and what evidence is missing.

| Surface | Essential content and actions | Requirement |
| --- | --- | --- |
| Care-team queue | Current owner, next due action, priority source, waiting/rejected/overdue work, barriers and backup queue. Filter by meaningful operational state. | CH05-1,2,5 |
| Case journey | Independent milestones, evidence, consultations, accepted ownership changes and unfinished downstream care. Derive phase from backend state. | CH05-1,4,5 |
| Clinician workspace | Patient question, specialist consultation, source guidance, missing facts, human reply, agreed action and authorized disposition. | CH05-3,4,5 |
| Patient next-step page | Clear result context, next step, stated urgency, responsible team, acknowledgement, understanding check, language preference and help request. | CH05-3,4 |
| Operations and impact | Failed delivery/writeback, retry/dead-letter queue, overdue escalation, disposition categories and defined measurements. | CH05-2,5,6 |

The existing three-perspective concept is relevant but incomplete. Keep its case journey and owner/evidence panels. Add the care-team work queue, a genuine clinician consultation workspace and operational recovery views. Every view reads the same backend state; local clicks alone cannot complete a clinical milestone.

A patient question must produce an assigned callback/consultation task and display its status. A clinician-to-clinician request must show a human response and resulting action. Both require task ownership and a service window. An AI-generated summary is preparation, not a consultation outcome.

Teach-back can ask the patient to identify the next step in their own words or choose a clear option. Persist passed, needs help or unknown separately from acknowledgement. Offer a staff-assisted alternative when literacy, access or language is a barrier. Clinical and Arabic content remain labelled with their actual review status.

When ownership, appointment state, urgency or outcome changes, update the patient view appropriately. Show ongoing care after milestone closure. Do not retain a your appointment is being arranged message after the episode has reached its endpoint.

Keep model selectors, raw execution graphs, prompts and benchmark dashboards in developer/admin areas. The staff activity view should show meaningful actions, sources and pending decisions. The patient sees guidance and responsibility, not implementation machinery.

<!-- page -->
## 11 Evaluation protocol and claims

Separate development cases, model-selection validation cases, known safety regressions and the untouched final holdout. Debug and select models using the first two sets. Freeze model, prompts, tools, retrieval snapshot, metrics and scoring before the final run. Separate model capability, software reliability, simulated workflow outcomes, volunteer usability and any later clinical evidence.

| Resource | Scope of evidence | Release use |
| --- | --- | --- |
| MedAgentBench [13] | Research FHIR-agent tool use and task completion. | Optional after data/cloud rights, container and original scorer are verified. Label subsets or changed tool protocols as adapted; do not assume wholly synthetic data. |
| HealthBench [14] | Physician-rubric conversation quality, uncertainty and emergency-referral responses. | Predeclare the subset, denominator and Groq grader; preserve original rubric aggregation and label the Groq-only result adapted. |
| Synthea [15] | Synthetic FHIR integration data. | Use for fixtures; it is not clinical triage ground truth. |
| Suhail journey suite | Direct tests of owned screening-to-care workflows. | 1,000 held-out trajectories plus at least 500 invalid-closure attempts; publish generator assumptions and independent expected states. |
| MIMIC-IV-ED [16] | Retrospective ED urgency using arrival-time information. | Optional research after credentialed access. It must not block the release or be presented as direct screening validation. |

**Comparisons:** A is reminder/dashboard baseline; B is the full ownership/evidence workflow with fixed templates; C is the same workflow with AI assistance. Compare model swaps inside C under identical tools, retrieval, cases and budgets. Run a no-RAG ablation if time permits. A versus B measures workflow contribution; B versus C measures incremental AI contribution.

Keep patient behavior, capacity, event availability and operational rules identical across simulated arms. Use paired seeds, repeat runs and sensitivity checks. Score state transitions with independent assertions; use external rubrics for their intended domains. Do not rely only on the tested model to judge itself. Hold out patients, template families and scenario variants together.

Run the final holdout after the release candidate is frozen. If its failures lead to implementation changes, disclose the change and use a new untouched evaluation version; do not relabel a repeatedly used set as unseen. Known regression scenarios establish tested invariant behavior separately from generalization performance.

**Challenge measures:** time from issuance and ingestion to notification, understanding, consultation, confirmation and the care endpoint; referral acceptance; appointments attended; required follow-up and treatment initiation; unresolved need; reason for delay; disposition and evidence completeness. Report median and tail times, denominators and follow-up horizon. Separate delivery from acknowledgement and booking from care.

**Patient impact:** if a usability study is completed, measure correct next step, who to contact, urgency understanding, reassurance and navigation confidence. A small consenting volunteer study uses fictional scenarios and remains usability evidence. If not run, label these outcomes unmeasured.

Report all actionable cases, including decline and lost contact, and state how unfinished/censored cases are handled. Publish source/citation correctness, unsupported actions, review rate, language breakdown, task success, latency and cost per success. Safety invariants must pass the tested release suite; performance targets such as reduced staff time are proposed goals until measured. Research datasets do not confer regulatory approval.

<!-- page -->
## 12 Acceptance suite and seeded scenarios

The following tests are release contracts. Implement them against real application commands and persisted state, not only UI mocks. All safety and ownership scenarios must pass before the demonstration freeze.

| ID | Acceptance scenario |
| --- | --- |
| AT01 | A synthetic actionable result creates the correct source-linked case, required tasks, default owner and next action; issuance and ingestion times differ correctly. |
| AT02 | Identity conflict, unsupported pathway or missing staffing mapping creates owned quarantine/exception work. Authorized reconciliation with evidence restores valid progression; unauthorized or unsupported resolution is rejected. |
| AT03 | Delivery, acknowledgement and teach-back have separate states; failed understanding creates an assigned assistance task. |
| AT04 | Patient callback and clinician consultation each reach an authorized human reply, with a documented next action and owner. |
| AT05 | Referral rejection preserves episode accountability; acceptance by the authorized destination changes only the intended ownership scope. |
| AT06 | No-show, cancellation and acceptance timeout create owned follow-up work and visible delay reasons. |
| AT07 | A trusted urgent signal alerts staff with the model/RAG unavailable; unacknowledged work escalates; acknowledgement alone does not close the review. |
| AT08 | Evidence arrives from another service and is matched to patient/order/version; booking, attendance and assessment remain separate. |
| AT09 | Booking-only, wrong-patient, stale, fabricated, unverified or missing evidence cannot close the episode. Authorized verification can resolve valid pending evidence; unauthorized verification is rejected. |
| AT10 | Completed-care closure is blocked until every task defining the declared care endpoint is satisfied. An accepted referral, assessment report or visible open treatment task cannot satisfy a required treatment-initiation endpoint. Exceptions retain their distinct category and residual need. |
| AT11 | An amended result invalidates affected evidence and reopens work with fresh clinical review. |
| AT12 | Decline, unreachable, transfer and clinical-resolution dispositions remain separate from completed care in every metric. |
| AT13 | Authorized receiving staff can access only the granted referral packet; unrelated-provider/cross-patient access, unauthorized acceptance/disposition and tools outside the allowlist are rejected. |
| AT14 | Duplicate/reordered events and a worker restart cause no duplicate referral or lost deadline; failed delivery enters owned recovery. |
| AT15 | English/Arabic and RTL flows remain usable; patient ownership, outcome and next-step text update from backend state. |
| AT16 | Missing/conflicting policy and injected document instructions cause review, not unsupported recommendations or unauthorized actions. |
| AT17 | Overdue, rejected and unassigned work is queryable with owner, due condition, cause and escalation status. |
| AT18 | An entire episode crosses both provider services through consultation, required assessment and the declared care endpoint. |
| AT19 | A fresh install replays fixtures and produces a traceable report with model/configuration, data split and failed as well as successful cases. |
| AT20 | Metric queries reconcile to the full actionable-case denominator and show residual care need and patient-understanding status. |

Seed at least six named cases: uncomplicated completion; rejected handoff/no-show; urgent signal; uncertain identity; amended result; and decline/unreachable exceptions. Include an onward-care branch where closure remains blocked after referral acceptance. Use a demonstration clock with explicitly labelled operational windows; these are not clinical guideline deadlines.

<!-- page -->
## 13 Ordered implementation plan

Build vertical behavior first. Each work package references CH05 requirements and the acceptance scenarios above. Begin with the current repository state and follow this dependency order. The current handoff is 14 November; the published submission date is 20 November [1]. Confirm the cutoff and prioritize the complete first pathway. The stages in BUILD_STAGES.md govern implementation checkpoints.

| Work package | Required deliverable and gate |
| --- | --- |
| WP01 | Freeze endpoint, pathway/demo policy, schema, role model, invariants and fixtures. Create requirement/test mapping. CH05-1,2,5; AT01,02,09,10. |
| WP02 | Backend-driven fixed-template journey, roles, independent milestones, owner and audit. Gate: one complete case persists after restart. CH05-1,2,5; AT01,05,10,13. |
| WP03 | FHIR/file intake, two provider services, callbacks, outbox/retries, source evidence and no-show recovery. CH05-1,2,4; AT05,06,08,14,18. |
| WP04 | Patient acknowledgement/teach-back, callback, clinician consultation, urgent acknowledgement/disposition and graph pauses. CH05-3,4,5; AT03,04,07. |
| WP05 | Integrate model, restricted tools, RAG and baselines. Use development/validation evaluations; seal the independent final holdout. CH05-3,5,6; AT13,16,19. |
| WP06 | Fix regression failures and select model using validation results. Freeze the evaluation candidate before final holdout execution. CH05-1,2,5,6; AT09-14,17,20. |
| WP07 | Finish five surfaces, patient text/RTL, impact queries, operating instructions and optional volunteer usability. CH05-1-6; AT15,17,20. |
| WP08 | Freeze features; run untouched final holdout and fresh-install/replay check. Finish results, architecture, limitations, costs, pilot offer and backup video. AT18,19. |
| WP09 | Submit early; verify runnable links, access instructions, recording and confirmation. |

A small team can split backend/workflow, UI/integration, ML/evaluation and product/clinical scenario review within the competition's team-size rules. A solo builder should keep the same order and reduce optional work. Coding agents may work in isolated modules, but a single owner reviews shared schema and command contracts.

**Cut order if behind:** custom training, voice, extra languages beyond reviewed core templates, a second pathway, broad model sweeps and extra visual effects. Retain patient and clinician consultation, accepted ownership, real backend persistence, urgent review, evidence-based closure and the direct workflow evaluation. Limit the model comparison to one local candidate and one permitted external baseline if needed.

**Readiness gates:** functioning full fixed-template journey before agent integration; integration/recovery and permission tests before scale testing; final metrics only after protocol freeze; no new clinical capabilities after the feature freeze. An inaccessible dataset or unavailable clinical reviewer becomes a declared optional evidence gap rather than a reason to fake completion.

<!-- page -->
## 14 Demonstration commercial path and competitiveness

**Four to five minute demonstration:** begin with an actionable result entering a real adapter. Show the assigned owner and patient next step. Record acknowledgement and understanding; have a clinician role answer the patient's question and obtain a specialist reply. Reject the first referral and show the original owner retained. Accept another handoff, book a visit, inject a no-show and recover it. Inject an urgent signal, record staff acknowledgement and clinician disposition. Attempt closure with booking-only proof, then return valid assessment/outcome evidence. Show any required onward-care task before authorized closure. Replay a correction scenario separately if time allows.

Show a results panel with measured workflow and AI comparisons, denominators, failure categories and source evidence. Distinguish observed software results, simulated care outcomes and any completed usability study. Avoid a staged all-success story that hides inaccessible patients, capacity constraints or failed cases.

**Submission materials:** runnable code and pinned dependencies; synthetic fixtures and replay command; setup/access instructions; architecture/data flow; requirement-to-test mapping; pathway and closure definitions; model/data cards and licenses; evaluation protocol/results; source and limitation register; demonstration video and a practical pilot proposal. Verify dashboard-specific formats and rules [1].

**Pilot proposal:** one screening program/provider network, one laboratory, a primary-care service and a specialist clinic, one pathway and a limited connector scope. Begin with approved observation and then supervised assistance. Measure notification/consultation, accepted handoffs, staff effort and unresolved cases; follow the declared care endpoint long enough to measure it. Quote integration work separately and derive recurring facility/episode pricing from measured costs and buyer feedback. Do not invent a hospital partner or endorsement.

**Competitive assessment:** potentially strong, because the proposed behaviors map to all six requirements and provide a concrete cross-provider failure-recovery demonstration. Existing products already advertise AI outreach and booking [17]. Defend the entry through accepted accountability, actual consultation outcomes, required care evidence and transparent evaluation; do not claim those capabilities are globally unique without broader evidence.

The major risks are overbuilding general triage, spending the remaining days training models, presenting frontend simulation as operational integration, counting appointments as care, or relying on public model benchmarks as the main impact claim. The layout is relevant when it prioritizes owner, next action, evidence and patient guidance. Attractive visuals help demonstration quality, while the complete care workflow supplies the main case for the entry.

External healthcare expert review stays a separate optional track. If performed, record reviewers' specialties, scenarios, rubric, disagreements and resulting changes in a dated report. Product clinician-role controls remain required. Any later clinical pilot needs its applicable institutional approvals and appropriate review; benchmark scores alone do not establish clinical readiness.

<!-- page -->
## 15 Codex handoff and repository contract

Start the implementation session with this instruction:

> Implement Suhail Health from this versioned master plan. Treat CH05-1 through CH05-6, the episode endpoint, ownership/closure invariants and AT01 through AT20 as the acceptance contract. Build WP01 and WP02 first using fixed templates and synthetic records, then continue in package order. Use independent persisted milestones and separate episode ownership from task assignees. Agents submit restricted proposals; backend authorization and deterministic checks govern state changes. Complete the two-provider workflow and evidence return before model optimization. Preserve the supplied logo, create the five specified surfaces, and keep expert review separate. Maintain a requirement-to-implementation-to-test matrix. Label simulated integrations and do not invent benchmark results, clinical approval or hospital partnerships. Report each completed package with its tests, remaining gaps and next package. Escalate a contradiction in the endpoint or safety contract before changing it.

Suggested repository areas:

- docs/master-plan.md contains this reference; docs/decisions.md records changes; docs/requirements.csv maps requirement, module, test and evidence.
- apps/web contains patient, clinical and operational views from the shared API.
- services/api contains schemas, permissions, domain commands and closure checks.
- services/worker contains persisted timers, outbox, retries and recovery.
- services/agents contains graph nodes, allowed tools, model gateway and policy retrieval.
- integrations contains FHIR, file and provider adapter contracts.
- simulators/provider-a and simulators/provider-b implement independent source services.
- pathways/colorectal-demo contains mappings, milestone/evidence rules, demo windows, templates and policy metadata.
- fixtures contains only synthetic cases and source events.
- tests contains domain, authorization, connector, recovery and acceptance scenarios.
- evals contains registry, fixed splits, baselines, runners, independent scorers and result manifests.
- infra contains compose configuration and environment examples without credentials.

Provide planned commands for startup, migrations/seed, acceptance verification, demonstration replay and benchmark execution. A new developer should reproduce the baseline without GPU access using fixed templates; local inference becomes an optional service profile.

For every change, record requirement IDs, behavior, interface/API change, data migration if any, verification and limitation. Do not let multiple coding agents redefine the shared case schema independently. Treat agent output and outside documents as untrusted inputs. Keep model prompts and retrieval snapshots versioned.

The first completed development checkpoint is a working persisted result-to-care case with a failed closure attempt and authorized resolution. A model endpoint, chatbot or visually complete dashboard on its own does not satisfy that checkpoint.

<!-- page -->
## 16 Sources decisions and remaining confirmations

The supplied Challenge 05 statement is the primary product requirement. The public page's static rendering exposes a different selected challenge, so this plan does not substitute that text for the user's complete Challenge 05 statement. External sources support the specific clinical, integration, model, benchmark and competition facts referenced here. Original product-source check: 12 November 2026. Groq and benchmark corrections checked 14 November 2026; see SOURCES.md.

1. Competition and submission requirements: https://hack2skill.com/event/futurehealthchallenge/
2. USPSTF colorectal screening guidance: https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/colorectal-cancer-screening
3. LangGraph persisted human-input pauses: https://docs.langchain.com/oss/python/langgraph/interrupts
4. Epic FHIR interface documentation: https://open.epic.com/Interface/FHIR
5. Oracle Health Millennium FHIR R4: https://docs.oracle.com/en/industries/health/millennium-platform-apis/mfrap/
6. Mediclinic TrakCare announcement: https://www.mediclinic.ae/en/corporate/media-and-news/press-releases-and-news/mediclinic-middle-east-selects-intersystems.html
7. UAE exchange integration: https://mohap.gov.ae/en/w/uae-health-authorities-announce-successful-integration-between-riayati-malaffi-and-nabidh-
8. SMART App Launch authorization: https://hl7.org/fhir/smart-app-launch/app-launch.html
9. Groq supported models: https://console.groq.com/docs/models
10. Groq structured outputs: https://console.groq.com/docs/structured-outputs
11. Groq tool calling: https://console.groq.com/docs/tool-use/overview
12. PhysioNet restricted-data and LLM guidance: https://physionet.org/news/post/llm-responsible-use/
13. MedAgentBench authors' repository: https://github.com/stanfordmlgroup/MedAgentBench
14. HealthBench original release: https://openai.com/index/healthbench/
15. Synthea repository: https://github.com/synthetichealth/synthea
16. MIMIC-IV-ED v2.2 and access conditions: https://physionet.org/content/mimic-iv-ed/2.2/
17. Existing AI outreach/booking capabilities: https://www.lumahealth.io/blog/new-ai-agents-run-patient-outreach-and-book-appointments

**Fixed decisions:** Challenge 05 is the scope; first pathway is colorectal follow-up; Groq-hosted existing models and RAG first; urgency is a screening safety branch; independent milestones; accepted episode-owner transfer; evidence/authorized decisions govern closure; expert review is separate; all public demonstration records are synthetic.

**Confirm during WP01:** registration/dashboard access and exact submission cutoff; team availability; H100 configuration/location and model access; the demonstration pathway's source pack and endpoint rule; available messaging/testing accounts; benchmark version/license/access; which language material has actually been reviewed. Existing organizer rules, data rights and deployment approvals take precedence over assumptions in this plan.

**Change control:** increment the master-plan version for a changed endpoint, permission, clinical rule, milestone, claim or benchmark protocol. Record the reason and affected acceptance tests. Update both human-readable and coding references from the same source. The plan is the agreed development baseline, not certification of a finished medical product.
