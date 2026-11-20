# Frontend implementation and verification

## Current dynamic UI release — 16 November 2026

The worklist now has animated list/board switching over the same persisted authorized cases, clickable summary filters, and independent milestone inspection with recorded evidence and assigned work. Patient section navigation follows the visible plan section while preserving vertical scroll in English and RTL. Landing preview motion, keyboard stage selection and reduced-motion behavior were refined. Clinical commands, permissions and endpoint rules remain unchanged.

The exact production release passed **16/16 browser checks** in 111.75 seconds, including the full two-provider care journey and three new dynamic behavior checks. Production compilation and TypeScript passed. Actual evidence: `reports/ui-redesign-v3/verification.json`, `runtime/ui-v3/journey-artifacts`, and `runtime/ui-v3/dynamic-browser-record.json`. Original runtime proof paths were restored byte-for-byte. Focused viewport captures are packaged in `reports/ui-redesign-v3/screenshots/`.

The final 6:25 showcase (archived at `../reports/video-v3/index.html`) is complete, with four authored animation sections, nine actual UI chapters and 96 English captions. All 17 media checks passed. The main application remains on port 3000; SC-001 stays completed with Provider B at version 30. A new Docker UI image was not attempted while the host root disk remains full; the latest native release is verified. The [public dataset assessment](PUBLIC_DATASET_EVALUATION.md) separately records two attempted requests and no scored new response.

The earlier release history follows.

## Previous premium UI release — 15 November2026

The Next.js16.4.6/React19.3.1 application now uses a persistent App Router workspace layout, role-scoped content refresh, keyboard quick navigation, restored modal focus, and reduced-motion-aware transitions. Landing/sign-in, worklist/case/source review, clinical/specialist, receiving, patient English/Arabic/mobile, operations and restricted evaluation surfaces were redesigned from their actual backend state. Manrope, DM Sans and Noto Sans Arabic are self-hosted with OFL provenance. Lucide1.73.0 and Motion14.14.0 are pinned.

The functional release passed **13/13 production browser checks** (`runtime/ui-v2/browser-results.xml`), including the full two-provider care journey, provider-role packet refresh, keyboard focus, persistent navigation and mobile/RTL. Production compilation and TypeScript passed; independent visual review found no layout blocker. The observed secondary-text contrast issue was corrected and rechecked on actual rendered screens. Report access for the unprivileged container API is prepared through a narrow named-user ACL helper; other effective permissions and private database files remain unchanged.

Current evidence and source hashes: `reports/ui-redesign/verification.json`, with screenshots and the joined benchmark definition alongside it. The 13-check run and completed11-step journey are archived under `runtime/ui-v2/journey-artifacts`. The initial failures and their fixes remain recorded separately. No new Groq inference or clinical outcome validation was performed. The new 6:30 showcase (archived at `../reports/video-v2/index.html`) is complete: 1080p, 11 chapters, 98 captions and English ElevenLabs narration. All 17 final media checks passed; the original 12:16 video remains unchanged. Final CSS-only retained-source trigger and mobile provenance refinements passed a separate focused browser check (`runtime/ui-v2/source-label-check.json`). The latest native production build passed. The final Docker rebuild hit host-root ENOSPC; the earlier redesigned container image/proxy checks remain recorded without claiming final CSS parity.

The sections below describe the initial application and its earlier verification history. The current release evidence above supersedes earlier UI counts and typography descriptions.

## Implemented

Next.js 16.4.6, React 19.3.1, TypeScript 5.9.3, Node 22.22.0. Versions checked against the npm registry during this build; npm lockfile is `apps/web/package-lock.json`.

- Public introduction, credential sign-in, and explicitly synthetic demo entry. Production role switching follows server-side `demo_mode`.
- Role-filtered shell and server-authorized API calls. Runtime `/api/[...path]` proxy forwards session cookies, never owner credentials. Local API defaults to port 18000; set `API_INTERNAL_URL` at server startup for containers.
- Care queue with search, operational filters, exact authorized episode totals, ownership, due actions, barriers, urgency, quarantine and synthetic file intake.
- Case detail with independent milestones; current evidence and verification; source reconciliation; clinical gates; owned tasks; handoffs; appointments; communication; audit; urgent acknowledgement and disposition; closure-check and separate authorized disposition.
- Qualified clinicians and assigned specialists can read the actual retained source on demand through a protected endpoint. The evidence card shows verification alongside current/superseded status; source review displays readable document content or structured facts, provenance/hash and matching checks, with loading/error/retry handling. Source bodies stay out of agent case payloads.
- Human patient and specialist consultation threads, replies, agreed actions and action ownership.
- Receiving-service workspace reads only `/referrals` minimal packets. Scope-specific accept/reject, booking/attendance events and pending source evidence return are real commands.
- Unavailable capacity is recorded before any booking through the accepted referral's dedicated capacity action; it creates owned recovery without fabricating an appointment.
- Authenticated patient view with English/Arabic core content, RTL, separate acknowledgement and understanding, human questions/replies, barriers, requested preferred times, confirmed appointment status, communication preferences, team help, approved care-plan display, and an optional persisted confidence/reassurance survey (1–5; no clinical improvement claim).
- Operations reads persisted outbox, retries, overdue work, urgent review, capability states, full-denominator metrics, and demo controls. Evaluation is restricted to administrators and reads actual report manifests/downloads.
- Optional staff AI draft panel invokes all six bounded functions on demand, distinguishes real/fallback outputs, displays sources and the persistent human-review pause, and exposes a separate qualified-review action. It never advances clinical milestones.
- Loading, empty, validation, failure, waiting, blocked and completed states. Responsive mobile layout, keyboard focus, semantic forms, accessible names, skip link and reduced-motion support. Fonts use local system fallbacks with no external request.
- Pending urgent review derives from active escalation records, independently of the preserved historical trusted flag. Authorized exceptions show their own handling decision and residual care need. Completed care shows the approved current source plan, historical result communication and read-only recorded understanding; help and clinician questions remain available.
- Original logo preserved byte-for-byte (SHA-256 `e2f1bc561f1ddb8003096b93814553d68d5749e6882a2e684d43270a5e84344b`), displayed at original proportions. Bundled icon, favicon, social card and journey motif included.

## Executed verification

`PATH="$PWD/.runtime/node/bin:$PATH" npm --prefix apps/web run typecheck` passed multiple times after meaningful API integration edits.

`NEXT_TELEMETRY_DISABLED=1 npm --prefix apps/web run build` passed on approved host execution, generating `/`, `/worklist`, `/cases/[id]`, `/clinical`, `/receiving`, `/patient`, `/operations`, `/evaluation`, and runtime `/api/[...path]`.

Sandbox execution returns empty stdout from Node child processes; this caused the initial Next build's TypeScript configuration parse failure. Direct TypeScript passed; host execution resolved the environment restriction. The final source is verified again by the root release checks.

## Final actual browser verification

The final `make test-e2e` run passed **10/10 tests**, with **0 failures, 0 errors and 0 skipped tests**, after the final backend and frontend fixes. The JUnit source is `runtime/browser-results.xml`; this count was read back from the executed XML, not inferred from an earlier run.

The tests execute public sign-in and keyboard focus; patient acknowledgement, understanding, questions and a human clinician reply across browser sessions; Arabic RTL/mobile and reload persistence; human specialist consultation; authorized identity recovery; trusted urgent acknowledgement and separate clinical disposition; invalid-evidence and onward-endpoint closure rejection; amended-result reopening; informed-decline category and permission denial; and operational/evaluation pages.

The full visible SC-001 care journey completes through Provider A rejection, Provider B episode acceptance, no-slot capacity reporting with no appointment record, confirmed booking, no-show, rebooking, attendance, actual returned source evidence, clinician source verification, reviewed outcome/patient-plan documents, completed owned human coordination work, and authorized completed-care disposition. The patient page then displays the actual approved document plan and historical communication with no current understanding form. Optional experience ratings are synthetic test feedback, not a patient study or evidence of improvement.

`runtime/browser-fullcare-journey.json` contains **11 actual persisted state snapshots**, ending in `completed_required_care`, with `provider-b` accountable and no remaining required task or residual care need.

Final screenshots were captured from the actual final browser run and visually inspected:

- `runtime/screenshots/fullcare-closed-patient-mobile.png`
- `runtime/screenshots/fullcare-closed-clinical.png`
- `runtime/screenshots/fullcare-receiving-b.png`
- `runtime/screenshots/fullcare-source-review-before-verification.png`
- `runtime/screenshots/patient-arabic-mobile.png`
- `runtime/screenshots/worklist-desktop.png`
- `runtime/screenshots/evaluation-desktop.png`

An additional read-only Chromium smoke record, `runtime/frontend-browser-smoke.json`, recorded no JavaScript page errors and no horizontal page overflow at desktop width 1440 or mobile width 390. Earlier browser-discovered accessible-name, language-preference and completed-state text defects were fixed and covered by the final passing run. No clinical or Arabic expert review is claimed.

The subsequent operations-only mapping correction displays the persisted outbox `kind`, scoped case link and available `error_code`. TypeScript and the production build passed; after reloading only the web process, the targeted operations/evaluation browser check passed **1/1** (`runtime/browser-operations-final.xml`), asserting the actual outbox title and case URL. An initial test response-adapter error was corrected; its XML is retained as `runtime/browser-operations-initial.xml`. Clinical and patient logic and SC-001 state were unchanged by this correction/check.

After the required retained-source review interface was added, TypeScript and the production build passed again, and the latest full `make test-e2e` run passed **10/10 in 29.91s** (`runtime/browser-results.xml`, zero failures/errors). The browser opened the actual Provider B investigation body and its provenance before verification, then read both approved plan documents before verification. `runtime/browser-fullcare-journey.json` retains three actual protected-source response records with content hashes and matching metadata, all with verification still `pending` at read time. The source-review screenshot was visually inspected; final closed-care screenshots were regenerated by that same successful run.

Final packaging copied the five requested latest runtime captures unchanged to `reports/screenshots/`: source review before verification, closed clinical case, closed patient mobile, receiving Provider B and Arabic patient mobile. The artifact index (archived at `../reports/screenshots/INDEX.md`) records their original paths, observed states and capture times; `SHA256SUMS` verifies exact copies. Packaging changed no application code and ran no additional browser suite.
