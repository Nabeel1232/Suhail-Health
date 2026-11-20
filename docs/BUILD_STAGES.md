# Staged implementation and recovery prompts

The main prompt authorizes continuation through these stages. They are checkpoints, not repeated requests for permission. Use the stage prompts individually only if a new session or focused repair is needed. Read the product invariants before each relevant change.

## Stage 0 Inspect and establish contracts

```text
Read CODEX_BUILD_PROMPT.md and the product/experience references. Inspect the repository and its instructions. Validate the provided environment-file and logo paths without exposing secrets. Establish the typed case, milestone, ownership, evidence, access-grant and command contracts. Copy the supplied branding and controlling references into the repository. Create the requirement-to-test matrix and a persistent implementation status. Record framework versions and run instructions. Start implementing immediately; continue to Stage 1 without waiting for approval.
```

Gate: repo instructions honored, synthetic-only default, secret handling established, schemas and acceptance scenarios mapped. A missing Groq key blocks live inference only, not backend/UI work.

## Stage 1 Complete a persisted care workflow

```text
Implement database migrations, authenticated roles, independent milestones, episode ownership, narrow commands, evidence, closure checks, urgent review and audit/outbox. Use fixed templates initially. Complete one persisted result-to-care case, including a premature closure rejection. Add owned identity/pathway quarantine and authorized recovery, separate patient acknowledgement/understanding, two consultation types and conditional onward-care tasks. Execute domain and permission tests against the real API/database; fix failures before adding model complexity.
```

Gate: AT01-AT05, AT09-AT13 exercised; app restarts preserve the case and owner. No required clinical milestone can be advanced by a browser-only next button.

## Stage 2 Cross-provider integrations and recovery

```text
Add the FHIR test server, validated file intake and two independently running provider simulators. Demonstrate rejection, explicit acceptance, limited referral access, appointment/no-show events and returning evidence. Implement idempotency, persistent deadlines, worker leases, retries/dead letters and amended-result reopening. Run connector, cross-organization access and restart/reordered-event tests. Update the capability matrix honestly. Continue to the UI stage after these work.
```

Gate: AT05-AT08, AT11, AT13-AT14 and AT17-AT18; external-event failures stay visible and owned.

## Stage 3 Full branded patient and staff experience

```text
Implement every surface in CUSTOMER_EXPERIENCE.md from shared backend state. Apply the preserved logo and brand assets. Finish real patient questions/clinician replies, clinician-specialist consultations, handoff decisions, teach-back, barriers, appointment updates, evidence review, exception dispositions and operational recovery. Add empty, loading, blocked and error states. Verify English/Arabic, RTL, keyboard, mobile and outcome-dependent text. Use a test browser to complete the journeys. No dead buttons or fabricated impact cards.
```

Gate: a patient, navigator, clinician, specialist, receiving service and operator can complete their roles with consistent persistence and access. AT15 passes. Clinical graphs/model selectors remain in admin/developer areas.

## Stage 4 Groq and versioned RAG

```text
Load the configured private dotenv file server-side and verify Groq access with tiny synthetic checks. Implement separate schema-output and local-tool request modes, bounded sequential calls, validation, rate-limit recovery and clear unavailable/fallback states. Integrate the six restricted agent functions with persisted pauses. Add source-filtered versioned retrieval and source links. Test missing/conflicting policy, prompt injection, unauthorized tools, invalid output, timeout and 429 behavior. Record the actual model and configuration. Do not silently replace a failed live response with a success fixture.
```

Gate: actual permitted Groq requests work or a precise provider block is reported; app remains operable through explicitly labelled templates. AT07, AT13 and AT16 pass independently of model availability.

## Stage 5 Benchmarks and measured reports

```text
Implement BENCHMARK_PROTOCOL.md and the dataset registry. Fetch permitted public data with source/revision/license/checksum manifests. Generate independent development, validation and final synthetic sets. Run the deterministic 1,000-trajectory/500-invalid-closure suite, then the budgeted live Groq smoke evaluation for all six functions and the declared adapted HealthBench subset. Compare rules/templates and the identical AI-enabled workflow on the same live-evaluated cases. Produce per-agent and full-system Markdown/JSON/CSV/HTML reports from actual records. Preserve failed/skipped/budget-limited counts and null metrics for unexecuted runs. Optional dataset access errors must not block the rest.
```

Gate: reports reproduce from immutable run records, fixtures are not counted as live AI, final holdout was not used for model selection, and cost/token budgets are enforced. Critical application invariants remain passing even when model benchmark scores are low.

## Stage 6 Finish and hand over

```text
Run a fresh-install check, full role-based browser journeys, acceptance/security/recovery tests, the permitted live checks and report rebuild. Fix material failures. Provide Docker deployment, health checks, persistent-volume/backup guidance, environment validation and a demo replay script. Prepare a four-to-five-minute recorded-demo script and screenshots of the actual app. Do not publish externally without an explicitly supplied authorized target. Deliver URLs, access instructions, exact run commands, actual report paths and a precise implemented/blocked/optional checklist. Update all progress references and preserve the product source of truth.
```

## Resume after context reset

```text
Resume Suhail Health. Read CODEX_BUILD_PROMPT.md, docs/PRODUCT_SPEC.md, docs/IMPLEMENTATION_STATUS.md, docs/DECISIONS.md and the requirement/test matrix. Inspect actual repository state and recent test/benchmark manifests. Continue from the first incomplete gate without rebuilding completed work or inventing prior results. Keep the configured external dotenv file private. Finish the remaining application, verification and reports.
```

## Repair a Groq or dataset block

```text
Diagnose the exact failed request or data-fetch step using redacted logs and current official documentation. Distinguish missing key, invalid authorization, model access, unsupported parameter combinations, rate limit, budget exhaustion and dataset rights/access. Fix reversible implementation errors. Do not change model, grader, dataset, mode or completed-run status silently. Keep the application and permitted evaluations moving; record optional blocked items with the exact next action needed.
```

## Final adversarial product audit

```text
Audit the running application against CH05-1 through CH05-6 and AT01 through AT20. Attempt early closure, unauthorized/cross-patient access, rejection/timeouts, identity conflict, evidence mismatch, amended results, unavailable inference and worker restart. Complete both human consultation journeys. Check Arabic/mobile and all visible controls. Verify benchmark scores against raw executed records and check no credentials or restricted records entered reports. Repair material gaps and rerun affected checks. Report observed evidence, not intentions.
```
