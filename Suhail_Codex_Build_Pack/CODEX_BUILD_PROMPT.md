# Codex instruction for the complete Suhail Health application

## Inputs from the owner

```text
PROJECT_ROOT=<absolute path to the application repository>
BUILD_PACK_PATH=<absolute path to the extracted Suhail_Codex_Build_Pack>
ENV_FILE_PATH=<absolute path to the owner's private .env file>
LOGO_FILE_PATH=<absolute path to the owner's supplied logo>
DEPLOY_TARGET=<optional destination explicitly supplied by the owner; otherwise local deployment>
```

The owner will provide `GROQ_API_KEY` through the private environment file. Do not ask them to paste a key into chat. If the logo path is absent, use the bundled `brand/logo-original.png`. If a required path is missing, finish independent implementation and identify exactly which input is needed for the remaining operation.

## Your assignment

Act as the implementation owner. Build, run, test and finish a complete, coherent Suhail Health web application for Future Health Population Health Challenge 05, Closing the Screening-to-Care Loop. Execute the work rather than returning another plan. Complete each stage, repair failures and continue to the next stage. Keep a persistent progress record so a new Codex session can resume accurately.

Read this prompt, `docs/PRODUCT_SPEC.md`, `docs/CUSTOMER_EXPERIENCE.md`, `docs/BENCHMARK_PROTOCOL.md`, `docs/BUILD_STAGES.md` and `brand/BRAND_GUIDE.md` from the package before implementing their respective areas. Copy the controlling references into the project `docs/` directory. The product specification governs clinical-workflow scope; this prompt governs Groq integration and implementation delivery. If a safety/endpoint contradiction is found, preserve the stricter documented requirement and record the decision. Make routine technical decisions independently.

Inspect the repository and existing `AGENTS.md` instructions first. Preserve unrelated work. Reuse working project conventions. In a new repository use Next.js and TypeScript, FastAPI and validated Python schemas, PostgreSQL, a durable worker/outbox and LangGraph with persistent checkpoints. Use pgvector for retrieval if appropriate. Provide Docker Compose and lockfiles. Use currently supported dependency versions and record them. Avoid adding infrastructure that does not help the required journeys.

Use subagents for independent UI, backend or evaluation work when available, with one owner of shared contracts. Integrate and verify their output. Do not let parallel agents redefine the case schema independently.

## Governing challenge

The application must satisfy all six requirements:

1. **CH05-1 End-to-end visibility:** track result issuance, notification, acknowledgement, understanding, consultation, required confirmation, referral acceptance, appointment, attendance, appropriate treatment initiation or surveillance and documented closure.
2. **CH05-2 Ownership and timely progression:** every active episode and task has an accountable owner or exception queue, next action, configured deadline and backup escalation. Rejected, overdue and unassigned work is visible.
3. **CH05-3 Patient-centered communication:** plain-language explanations, preferred language/channel, acknowledgement separate from understanding, accessible help and barrier reporting, and measures of understanding/reassurance.
4. **CH05-4 Consultation and coordination:** actual patient-to-clinician questions and human replies; clinician-to-specialist consultations and human replies; accepted cross-provider referrals and returning evidence.
5. **CH05-5 Human-governed escalation:** trusted urgent flags route to qualified staff without waiting for an LLM; staff acknowledgement and clinical disposition are separate; evidence and authorized human decisions govern closure.
6. **CH05-6 Closure and patient impact:** measure timings, accepted/completed referrals, attendance, care endpoints, unresolved need, delay reasons, dispositions and patient understanding using explicit denominators.

Build one complete colorectal screening follow-up pathway with configurable milestone/evidence rules. This coordinates an already actionable result. It does not autonomously diagnose, prescribe or become a general emergency-department triage product. Keep expert assessment a separate optional workstream, labelled with its actual completion status.

## Complete application behavior

Implement a real persisted backend. Do not use local browser state or a fixed happy-path animation as the final application.

- Store independent milestones, since communication, consultation, confirmation and referral can overlap. Derive the displayed phase. Separate overall episode accountability from task assignees.
- Preserve the sending owner until an authorized destination explicitly accepts the intended episode/task handoff. A proposed receiver sees only an authorized minimum referral packet; acceptance does not grant arbitrary source-record access.
- Create owned quarantine work for uncertain identity or an unsupported pathway. Implement authorized reconciliation and evidence-verification recovery commands. An uploaded document or ordinary task completion cannot clear those gates.
- Keep delivery, acknowledgement and understanding separate. Teach-back failure or uncertainty creates assigned help work.
- Keep booking, attendance, completed investigation and reviewed outcome separate.
- Implement both consultation journeys end to end: assigned question, authorized clinician reply, agreed next action, owner and service window. An AI summary is not a human consultation.
- Handle rejection, cancellation, no-show, unavailable slots, lost contact, informed decline and overdue work. Preserve delay reasons and keep these cases in the actionable-case denominator.
- A trusted urgent signal creates a staff review and backup route independently of inference availability. Routine progression pauses where required until the clinician's disposition. A model cannot downgrade the flag.
- Implement deterministic closure checking and a separate role-protected disposition command. Completed-care closure stays blocked while any task defining the declared care endpoint is unfinished. Referral acceptance plus an open treatment-initiation task is not completed care. Explicit exceptions retain their category and residual need.
- Corrected results reopen affected work and require fresh review. Duplicate/reordered events, retries and restarts cannot duplicate referrals or lose timers.
- Persist audit events, access decisions, evidence provenance, command versions and an outbox. Implement server-side role and patient/organization authorization.

Use the canonical records and narrow application commands in `docs/PRODUCT_SPEC.md`. Create typed API contracts and a requirement-to-module-to-test matrix. Extend them when necessary without weakening the invariants.

## Entire customer experience

Implement the following complete, linked surfaces from the shared backend:

1. A useful public introduction/sign-in page and a clearly labelled synthetic demonstration entry. No fake partner, certification or clinical-approval badges.
2. Navigator work queue with meaningful filters, owner, due action, urgency source, barriers, overdue/rejected/quarantined work and recovery actions.
3. Case journey with independent milestone states, source evidence, ownership history, consultation outcomes and open downstream care.
4. Clinician and specialist workspace with patient questions, e-consults, review evidence, replies, agreed actions and authorized dispositions.
5. Receiving-provider workspace for limited referral packets, accept/reject, appointment/attendance events and returning evidence.
6. Secure patient next-step view with plain-language information, Arabic/English, RTL, acknowledgement, teach-back, questions, barriers, appointment updates and care-team contact.
7. Operations/impact workspace with retries, failed integrations, pending staff acknowledgements, residual need, defined metrics and actual downloadable reports.
8. A restricted evaluation/developer view, separate from clinical and patient flows, displaying real run status and benchmark reports. Do not fabricate a leaderboard.

All visible controls must work or have a truthful disabled state and explanation. Include loading, empty, validation, failure, waiting, blocked and completed states; responsive mobile layouts; accessible labels, focus and keyboard flows. Do not use agent graphs or model selectors as patient-facing workflow chrome. Demo-only role switching must be explicit and disabled in normal deployment.

Apply the supplied logo unchanged and the bundled Suhail visual system. Use teal/deep ink, a restrained gold navigation accent, clear typography and meaningful semantic states. Add the supplied app icon, favicon, share card, journey motif and report styles. Make the experience calm, professional and specific to care coordination.

## Environment and secrets

Load `ENV_FILE_PATH` server-side using a dotenv parser. Treat it as data, not executable shell code. Do not print, paste, log, commit, copy into frontend files or include its contents in screenshots, traces, reports, archives or error messages. Preserve process-environment precedence and the owner's original file. Read required keys only. Never use `NEXT_PUBLIC_` for secrets.

Generate missing local application/session/demo credentials into a separate ignored runtime file, without modifying the owner's environment file. Provide a secret-free `.env.example`. Use real password hashing, role authorization and secure session configuration. Use synthetic records only. Default notification delivery to a visible local outbox/provider simulator; do not contact real patients or clinicians.

## Groq implementation

Use Groq, not xAI Grok. Default candidates are `openai/gpt-oss-120b` and `openai/gpt-oss-20b`, subject to current account availability. Prefer a configured `GROQ_MODEL`. Probe current model access and make tiny synthetic capability checks. Record the exact selected model and parameters. Never silently change a benchmark model.

Use the official Groq SDK or its compatible endpoint `https://api.groq.com/openai/v1` from the backend. Implement two separate request modes because current Groq docs do not support JSON-schema Structured Outputs with tools or streaming:

- **Structured extraction/final proposal mode:** schema-constrained output on a supported model, with no tools or streaming; validate again server-side.
- **Tool mode:** a bounded local function-calling loop; validate tool names, argument schemas, authorization and case version before execution. Do not assume parallel tool calls for GPT-OSS models.

Recheck current official compatibility while implementing and record any change. Only Suhail's allowlisted local application tools are permitted. Do not enable provider built-in browsing, arbitrary code execution or remote MCP for clinical agents.

Implement timeout, exponential backoff with jitter, `retry-after`, finite retries, step/token budgets, cancellation, request concurrency and redacted observability. Authentication failures, rate limits, provider errors and exhausted budgets produce visible states. An intentional fixed-template fallback remains labelled fallback; it must never be counted as a successful live model response.

Implement six bounded agent functions: intake, pathway router, safety/escalation assistant, patient navigator, coordination assistant and closure-evidence assistant. They may share one model endpoint. Persist graph pauses and source-linked proposals. Keep urgency enforcement, ownership, deadlines, access, evidence validation and closure outside model prompts.

## RAG

Build a real retrieval path over a small versioned knowledge pack for the first pathway. Index only permitted source content. Retain authority, jurisdiction, pathway, effective/version dates, language, access scope and exact section citations. Label local operational defaults as demonstration policies unless actually reviewed. Filter before retrieval; use keyword/vector retrieval and optional reranking. A missing, conflicting, expired or injected document creates review work rather than invented guidance. Do not infer clinical deadlines or diagnoses from memory.

## Integrations and demonstration data

Provide a FHIR R4 test server and two independent provider services with authenticated request/accept/reject/status/evidence callbacks. Also provide validated file intake. Respect source versions and idempotency. Publish the connector capability matrix as implemented, simulated, manual or unavailable. Do not claim a live EHR, Malaffi, NABIDH or Riayati connection.

Seed all specified success and failure journeys. Provide a resettable, deterministic demo clock whose service windows are explicitly demonstration settings. Include an onward-care branch that cannot close at referral acceptance. A demo reset may affect only an identified synthetic demo dataset, never unrelated records.

## Verification and actual benchmarking

Implement and execute AT01 through AT20 in the product specification, plus customer-journey browser tests, provider-contract tests, permissions, restart/replay and rate-limit/failure tests. Use real application commands and persisted state. Run the application and inspect the actual pages at desktop and mobile widths. Fix critical failures before release.

Build actual benchmark runners and report generators using `docs/BENCHMARK_PROTOCOL.md` and `evals/dataset-registry.yaml`. Cover all six functions, including their deterministic safety/application boundaries. Default data for live Groq runs is project-generated synthetic data plus the permitted public HealthBench subset. Preserve data/code licenses and exact upstream revisions.

Fetch HealthBench from `openai/healthbench` on Hugging Face, inspecting the pinned files and schema. Reference `openai/simple-evals/healthbench_eval.py` for rubric aggregation. A Groq grader or changed subset is an **adapted HealthBench evaluation**, not the official overall score. Preserve negative rubric weights. Grader results are an estimate and must be distinguished from independent state assertions.

MedAgentBench is optional until data/cloud-processing rights, its FHIR container and original scoring dependency are available. Do not assume all records are synthetic or that the code license grants unrestricted data processing. Credentialed MIMIC stays outside the default Groq data path. An optional blocked dataset must not block the application or permitted tests.

Separate three evidence layers: deterministic software/reliability tests, actual live Groq agent runs, and adapted external conversation evaluation. Never count mocked model responses as live inference. Never claim 1,000 live AI trajectories because 1,000 deterministic cases ran.

Generate genuine reports from executed records for each agent, full journeys, dataset provenance, tests and limitations. Include timestamps, code/model/data/prompt/RAG versions, attempted/completed/failed counts, exact selected cases, scoring, tokens, latency, actual or explicitly unknown cost and sanitized error examples. Implement an integrity validator linking every live-scored case to actual candidate response records and, for adapted external rubric scores, actual grader responses and model provenance. Reconcile denominators, case IDs and usage; a single capability probe cannot substantiate unexecuted tasks. Missing measurements stay null. Support not-run, blocked, partial and completed statuses. Do not prefill invented percentages.

Use development/validation data for debugging and selection, then freeze the candidate before final holdout execution. Bound optimization rounds. Execute the smoke preset automatically when the supplied key works, within configured limits. Execute the standard preset only within its explicit budgets; otherwise report the completed subset accurately. Do not run an unbounded full public suite. Export Markdown, JSON, CSV and a readable HTML report from the same run records; charts must use measured data.

## Execution and completion

Follow the stages in `docs/BUILD_STAGES.md`; continue through them autonomously for reversible implementation and fixes. Maintain `docs/IMPLEMENTATION_STATUS.md`, `docs/DECISIONS.md`, `docs/REQUIREMENTS_MATRIX.csv` and exact executed commands. Preserve work across context resets. Do not stop after scaffolding, a design, a model endpoint or a happy-path screenshot.

Provide tested commands for setup, configuration validation, migrations, seed, application startup, fresh-install checks, acceptance tests, demo replay, dataset fetch, deterministic evaluation, live smoke/standard evaluation and report generation. Provide container deployment instructions, health checks, persistent volumes and hosting prerequisites. Publish externally only to a destination and action explicitly authorized by the owner; otherwise leave it ready to deploy locally with an honest access URL.

Expose a consistent command interface such as `make doctor ENV_FILE=/private/path/.env`, `make setup`, `make up`, `make seed`, `make test`, `make test-e2e`, `make demo-replay`, `make eval-fetch DATASET=healthbench_adapted`, `make eval-offline`, `make eval-live PRESET=smoke` and `make reports RUN_ID=<id>`. Implement and verify the commands rather than documenting nonexistent targets. Startup must explain service URLs and failures without printing secrets. Use the same environment-file mechanism for the app, worker and evaluation runner.

Completion requires a working branded application, all core patient/staff journeys, server-side Groq integration, persisted ownership/evidence workflow, executable verification, reports from actual runs and an honest list of remaining blocked optional items. Give the owner application URLs, access instructions, report locations, verified commands and the exact next step for anything that could not execute. Do not claim finished production medical validation or a public deployment that did not happen.

Begin now with repository inspection, configuration validation without revealing secrets, and the first complete persisted fixed-template case. Then finish the application, integrate Groq, run the tests and permitted evaluations, and deliver the full result.
