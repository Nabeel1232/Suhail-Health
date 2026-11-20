# Suhail Health

**Guiding every result to care.** Suhail Health is a working prototype for Future Health Challenge 05, Closing the Screening-to-Care Loop.

- A shared worklist assigns each actionable colorectal screening result an owner, deadline and next action.
- A dated case journey connects notification, teach-back, referral decisions, attendance and evidence.
- Arabic and English patient views show the next step and keep receipt separate from understanding.
- A trusted urgent flag goes directly to clinical staff. Verified evidence and clinician authorization govern closure.
- The frozen release passed 1,500 deterministic checks, including 500 refused premature closures.
- A simulated cohort projects 56% to 69% follow-up completion under declared assumptions. The pilot would measure the effect locally.

[Submission brief](SUBMISSION.md) · [Deck](docs/Suhail_Health_Deck.pdf) · [Three-minute demo](reports/video-final/Suhail_Health_Final_Demo.mp4) · [Impact model](docs/IMPACT_MODEL.md) · [Pilot plan](docs/PILOT_PLAN.md) · [Upload files and form copy](SUBMISSION_TODO_FOR_HUMAN.md)

## Intro and walkthrough

Watch the **[Suhail Health intro and walkthrough on YouTube](https://www.youtube.com/watch?v=hb6RlSThlnE)**.

[![Watch the Suhail Health intro and walkthrough](https://img.youtube.com/vi/hb6RlSThlnE/hqdefault.jpg)](https://www.youtube.com/watch?v=hb6RlSThlnE)

## Submission videos and verification

- [Three-minute prototype demo](reports/video-final/Suhail_Health_Final_Demo.mp4) · 2:55.18 · [Captions](reports/video-final/Suhail_Health_Final_Demo.vtt) · [Verification](reports/video-final/verification.json). Shows the frozen worklist, dated journey, Arabic patient view, urgent review, closure and operations.
- [Extended showcase](reports/video-final/Suhail_Health_5_Minute_Showcase.mp4) · 4:58.42 · [Captions](reports/video-final/Suhail_Health_5_Minute_Showcase.vtt) · [Verification](reports/video-final/five-minute-verification.json). Reuses verified footage from the earlier application showcase.

The final release passed 16 browser tests and 1,500 deterministic checks, including 500 correctly refused premature closures. [Submission verification](reports/verification/summary.md) · [Final offline results](reports/runs/20261120T135507Z-offline/summary.html)

## Open the local application

```bash
make doctor ENV_FILE=/absolute/private/path/.env
make up
```

- Application: <http://127.0.0.1:3000>
- API/OpenAPI: <http://127.0.0.1:18000/docs>
- Synthetic provider A/B: local ports 8101/8102; authenticated service endpoints
- FHIR R4 test server: <http://127.0.0.1:8103/fhir/metadata>

Select **Enter synthetic demo** on the sign-in page, or use a generated email/password from `.runtime/demo-credentials.json`. The role chooser is available only with `DEMO_MODE=true`. Passwords are hashed; cookies are HTTP-only, scoped and expiring. Generated credentials and connector tokens remain in ignored runtime files. Do not publish these local credentials.

**Ask Suhail** is available throughout the signed-in workspace, including mobile. Open the launcher or press **Ctrl/Cmd + J**. Ask “How many requests do I have?” or ask about an authorized case, then follow its record links. Counts come from current permitted records. Patients see their own linked episodes, providers see granted referral packets, and specialists see assigned consultations. Conversation history is private to the account and is rechecked against current access.

The assistant reads records and versioned guidance. Optional GPT-OSS120B question interpretation uses a separate, persistent application ledger capped at 20 calls and 40,000 tokens, with no automatic retries; common questions need no model call. It does not submit clinical decisions. Configure `CHAT_LLM_ENABLED` and the `CHAT_MAX_*` settings server-side; no provider key is sent to the browser. This application allowance does not reset or extend the original benchmark budget.

The host already had an unrelated application on port 8000; Suhail uses **18000 locally**. The default Compose configuration binds API port 8000 to loopback; the verified isolated override uses **18001** and web **13000** so it can run alongside this host's services.

## Fresh setup

Prerequisites: Linux, Python 3.13, Node.js 22+, npm, Docker Engine/Compose, about 3 GB of free disk and outbound access to the package registries. No GPU is required. `make setup` installs Node 22 locally when necessary, a Python virtual environment, locked application dependencies and test Chromium. All assets/fonts used by the web application are served locally.

```bash
make setup
make build
make up
make doctor
make status
make migrate
make seed
```

`ENV_FILE` sets `ENV_FILE_PATH` for the API, worker and evaluation runner. The owner file is parsed with python-dotenv, never executed or rewritten. Process environment takes precedence, followed by nonempty owner settings and generated runtime settings. A Groq-format legacy `grok-api` entry is supported server-side when `GROQ_API_KEY` is absent. See the secret-free `.env.example`. Database/session/demo credentials are generated separately in `.runtime/`.

Notifications are delivered to a visible local simulator. There is no real SMS/email delivery, live EHR, national exchange, hospital affiliation or clinical approval.

## Verification and replay

Start the application before HTTP/browser integration tests.

```bash
make test
RUN_POSTGRES_TESTS=1 make test
make test-e2e
make demo-replay
make fresh-check
```

The ordinary acceptance suite uses isolated persisted databases. PostgreSQL concurrency checks create and remove isolated schemas. HTTP integration tests call the independently running providers and FHIR server. Chromium tests exercise the actual shared patient/staff state, mobile/Arabic RTL, consultation replies, quarantine, urgent decisions and closure blocks. The demo replay uses a separately identified synthetic case dataset and produces a persistent execution record.

The built-in reset affects only `demo-v1` synthetic cases, preserving unrelated datasets and accounts. The demonstration clock supports a frozen base plus persisted advances. Its service windows are demonstration settings, not clinical deadlines. `make down` stops only processes recorded by this application and retains PostgreSQL data.

## Evaluation

```bash
make eval-fetch DATASET=healthbench_adapted
make eval-offline
make eval-live PRESET=smoke
make reports RUN_ID=<existing-run-id>
.venv/bin/python -m evals.runner validate --run-id <existing-run-id>
```

The offline preset runs 1,000 synthetic trajectories and 500 invalid closure attempts without model calls. Live smoke selects six cases for each of six functions, six paired full journeys and twelve public HealthBench conversations. The aggregate cap is 300 API calls and 300,000 tokens, including probes, retries and grading. Unknown usage keeps its conservative budget reservation; missing costs stay null. Account rate limits can leave a run partial. A scored incorrect answer stays in its task denominator.

Standard runs require explicit call/token budgets. Full public-suite runs are not enabled by default. The runner preserves prior cases and provider records, freezes model/prompts/RAG/scorers, and resumes only pending work. Read the actual manifest for completed counts rather than inferring them from the preset name. Avoid running multiple live evaluations on the same rate-limited account.

Reports live in `reports/runs/<run-id>/`: source/case/provider lineage, a manifest, six agent reports, journey comparisons, dataset provenance, integrity validation and Markdown/JSON/CSV/HTML summaries. The operations administrator can download reports in the restricted evaluation workspace. The public HealthBench subset uses the real signed rubrics and an explicitly named Groq grader; it is an **adapted exploratory evaluation**, with same-family grader bias, not the official HealthBench overall score. See `docs/BENCHMARK_PROTOCOL.md` and `docs/EVAL_STATUS.md`.

MedAgentBench is blocked pending separate data/cloud-processing rights, the original FHIR container and scorer. Credentialed MIMIC is disabled. Synthea was not run; integration fixtures are project-generated synthetic FHIR. External expert review and clinical/volunteer studies are not performed.

## Container deployment

```bash
.venv/bin/python scripts/runtime_config.py
.venv/bin/python scripts/prepare_reports.py --required
bash scripts/compose.sh --env-file .runtime/app.env config --quiet
bash scripts/compose.sh --env-file .runtime/app.env up --build -d
```

Set `ENV_FILE_PATH` to the owner's absolute private dotenv path if it is not `.env`; Compose mounts it read-only into backend services. It is excluded from image build context. Compose creates separate API, worker, PostgreSQL, two provider simulators, FHIR test and web services, with health checks and persistent volumes. The only exposed application ports bind to loopback.

`prepare_reports.py` grants only the container application UID read access to downloadable report artifacts through POSIX ACLs. Existing effective access for other users is preserved; private databases and credentials stay excluded. Run it again after generating new artifacts. `make reports` and `make compose-up` include this preparation.

Before institutional hosting, supply HTTPS and a reverse proxy, real identity/account provisioning, organization-specific connector credentials and approved access/sharing policy; set `DEMO_MODE=false` and `SESSION_SECURE=true`. Review pathways, translations and service windows with qualified local reviewers. Configure backup retention and monitoring. External publication is not performed by this build.

Back up PostgreSQL with `pg_dump` and back up runtime connector/session configuration, provider/FHIR stores and reports as access-controlled data. Restore into a separate environment and verify source versions, ownership, outbox leases and timers before resuming workers. Database migration v1 is additive and recorded in the `settings` schema-version record; future changes require explicit versioned migrations and backup rehearsal.

## Source map and limits

| Area | Location |
|---|---|
| Next.js patient/staff/operations surfaces | `apps/web/` |
| Canonical records, commands, authorization, audit | `services/api/` |
| Durable worker/outbox/timers | `services/api/worker.py` |
| Groq, six functions, retrieval, PostgreSQL graph pauses | `services/agents/` |
| Independent provider/FHIR services and import adapter | `integrations/` |
| Configurable first pathway | `pathways/colorectal-demo/` |
| Actual evaluations and report integrity | `evals/` |
| Staged status, decisions, matrix and delivery evidence | `docs/` |

This is a locally verified software prototype with fictional participants. Synthetic workflow performance and model rubric estimates do not establish patient outcome improvement, regulatory approval or medical production readiness. The controlling source specifications are copied into `docs/`.

See [the local handover](docs/HANDOFF.md), [executed verification](reports/verification/summary.html), [actual Groq results](reports/runs/groq-smoke-holdout-v1/summary.html) and [deployment/recovery instructions](docs/DEPLOYMENT.md).
