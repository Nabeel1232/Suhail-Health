# Persisted coordination backend

Implemented 2026-11-15 (Asia/Dubai).

- Canonical SQLAlchemy records for cases, independent milestones/tasks, communications, consultations, handoffs, access grants, appointments, evidence/source artifacts, escalations/dispositions, audit, outbox, source events, sessions and command receipts.
- PostgreSQL is the default authoritative store; isolated SQLite files are explicitly selected by deterministic acceptance/evaluation tests.
- Narrow API commands validate role, organization/patient/packet scope, current case version and replay identity. Case updates serialize under PostgreSQL row locks; intake also uses a per-source/order transaction advisory lock.
- Authenticated receiving services see minimum referral packets only. Episode accountability transfers only after an authorized explicit episode-scope acceptance.
- Trusted urgent flags create staffed review/backup work without model inference. Acknowledgement and clinician disposition are independent.
- Source artifacts retain actual uploaded document bodies or authenticated connector provenance. A claimed evidence URI is insufficient. Separate clinician verification checks patient, order, version and source content before evidence clears clinical work.
- Closure recomputes current evidence, quarantine/urgency and every required open task; downstream treatment initiation remains required after onward referral acceptance. Exception categories preserve residual need.
- Durable leased outbox has finite exponential retries/dead letters. Deadlines, no-show/cancellation, handoff expiry and urgent backup timers persist through restart.
- Seed has eight named synthetic cases, including a genuinely completed episode built with the same application commands and an early closure rejection.

## Commands executed

See `runtime/backend-commands.log` (no credentials). `python -m services.api.seed` has completed against the local PostgreSQL server. The first restricted attempt could not connect to localhost; the authorized host execution succeeded. The owner dotenv was parsed only and preserved. Empty optional values fall back to ignored runtime configuration.

## Executed verification

`tests/test_backend.py` exercises AT01–AT14, AT17 and AT20 with independent state/security assertions and an authenticated TestClient journey. The full backend suite passed 32/32; combined backend/evaluation unit checks passed 38/38 in 22.96 seconds. Additional final source-event collision guards have targeted tests. The opt-in `tests/test_postgres.py` passed 2/2 against temporary real PostgreSQL schemas, proving concurrent duplicate intake and same-version command exclusion; both schemas were removed after execution.

Root integration/browser tests cover separate provider processes, actual PostgreSQL restart, interfaces, Arabic and broader AT15–AT20 behavior. Evaluation harness executes the same domain commands on an isolated persistent store. Root's final full-suite result supersedes these intermediate counts.

Organization-bound connector credentials are generated under a filesystem lock. Source and two provider tokens are distinct; the API derives organization from the credential and rejects conflicting headers. Provider outbox/callback identities reject changed payloads. Explicit packet access revocation is independent of care ownership, cancels undelivered packets and creates owned recovery work. Normal deployments default to demo switching disabled and Secure cookies enabled.

The optional patient experience command persists authenticated 1–5 confidence/reassurance responses separately from understanding. Metric means and denominators come from actual responses, with null when absent; no gain or volunteer-study claim is made.

## Boundaries

Demonstration role switching requires DEMO_MODE. Clinical source verification is an authorized human attestation over retained synthetic source records; it is not clinical validation. Service windows and Arabic content remain demonstration policy. No real notification service or hospital exchange is connected.

## Final adversarial audit

The deterministic audit suite passed **59/59** in 32.28 seconds; actual JUnit evidence is `runtime/backend-audit-results.xml`. No live model calls were made by this audit. A final focused regression separately covers trusted-urgent reopening after completed care.

Critical findings repaired: cancelled required work cannot waive the endpoint; generic specialist-service consultations require the configured specialist organization; normal deployment ignores persisted demonstration-clock settings; accepted surveillance requires a real ISO recall date and nonblank owner; new required work and fresh trusted urgent flags reopen completed-care categories; blank assignees fall back to an accountable queue and blank human agreed-action owners are rejected.

`services/api/policy.py` now validates and applies the actual versioned pathway configuration for test mappings, required/conditional evidence, milestones, ownership and service windows. Built-in FIT aliases normalize to the configured canonical mapping. The loader preserves minimum investigation/outcome/patient-update requirements and clinician-only disposition. It never edits the frozen RAG policy file. A changed policy version blocks closure, creates owned clinician review through the worker, and requires source-backed clinician reconciliation; existing deadlines are preserved while missing stricter evidence tasks are created.

The receiver's narrow `/cases/{id}/capacity` command records unavailable slots before booking, creates owned recovery and a delay reason, and does not fabricate an appointment. The final requirement matrix maps all six challenge requirements and AT01–AT20 to actual modules, tests and available execution evidence; final root evidence is98/98 application/security/provider/PostgreSQL checks,10/10 browser journeys and65/65 clean-install acceptance/boundary checks. The bounded live report remains explicitly PARTIAL.

Reviewed worker lock ordering: case locks precede task/escalation mutations; outbox leases commit before delivery; provider destinations deduplicate receipt identifiers. Source-event fingerprints and immutable source-artifact bodies prevent a replay identity from silently changing its payload. Typed command inputs and server-side scopes remain independent of model proposals. OpenAPI response-body typing remains a documentation improvement; clinical state does not depend on frontend contracts.

## Patient outcome display verification

The patient plan now displays retained plain-language source text from a current, verified clinician-reviewed outcome or a documented patient plan update. Source/matching verification reasons remain staff attestations and never substitute for care advice. Technical JSON resources without an approved readable plan do not generate invented patient text. Completed required care shows the documented-plan next step with no remaining due date when all required work is complete. Focused persisted-state regressions are recorded in `runtime/patient-plan-regression.xml`.

## Final amendment consistency correction

After the original live benchmark became terminal, a focused application-only check reproduced two amendment defects: factual referral/booking/attendance milestones were reset while their tasks remained completed, and the corrected source's test code was not stored. The actual before-repair counterexamples are retained in `runtime/amendment-before-repair.xml`.

The final application preserves factual accepted-referral, booking and attendance history while reopening communication and current clinical evidence requirements. Every prior clinical evidence record is still superseded. A higher source version stores its current test code and identity-verification state; unsupported mappings enter an unresolved pathway with owned quarantine, and uncertain identity blocks patient access until authorized source reconciliation. New source assertions cannot silently clear an existing human reconciliation gate.

Four focused regressions passed in 5.70 seconds (`runtime/amendment-consistency.xml`), including fresh amended-result review to consistent authorized closure without duplicating service history. These final application changes do not rewrite terminal model-run inputs, outputs, source snapshots or scores. The separately implemented future synthetic v2 generator also makes no claim to have been live-evaluated.

## Human source-document review endpoint

The final post-benchmark application adds the read-only `GET /evidence/{id}/source` review endpoint. A clinician or specialist must already have authorized case scope. Patient, receiving-team, navigator and administrator roles cannot read retained source documents through this route. The response contains the actual retained content, authority, immutable content hash and matching metadata; source reference/case/organization must match the evidence link exactly. Missing artifacts return 404, scope mismatches return 403, and explicit patient/order mismatches return 409 without a document body. Same-patient/order historical evidence can be inspected with an explicit superseded/version-mismatch status. Source hashes are rechecked, and source reads are audited.

Document bodies remain outside ordinary case serialization and agent `read_case` payloads. This endpoint does not change evidence verification, clinical transitions, model prompts, retrieval or benchmark records. Three focused API authorization/provenance tests passed in 8.02 seconds; see `runtime/source-review-tests.xml`. The corresponding clinician UI review control is integrated separately by the frontend owner.

## Final delivery verification

The exact final application passed98/98 root tests, including58 backend tests,7 agent-boundary tests,28 evaluation tests,3 real HTTP integration checks and2 real PostgreSQL concurrency checks (`runtime/test-results.xml`). The isolated clean dependency installation passed65/65 backend/agent checks; the full browser sequence passed10/10. Required source documents were actually read before verification in the browser journey. Final handover and aggregate evidence are in `docs/HANDOFF.md` and `reports/verification/summary.html`.
