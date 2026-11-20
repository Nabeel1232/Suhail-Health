# Local handover

The current dynamic UI is complete and runs at the same URL. Watch the final 6:25 showcase (archived at `../reports/video-v3/index.html`) or download the MP4 (archived at `../reports/video-v3/Suhail_Health_Final_Showcase.mp4`). The exact production release passed 16 browser checks; media verification passed 17/17 checks. Current UI evidence (archived at `../reports/ui-redesign-v3/verification.json`) covers list/board views, real filters, milestone inspection, English/Arabic scroll navigation and the full care journey. Current model configuration is one GPT-OSS120B model through Groq serving six focused functions; the video describes a future model-integration/evaluation path without promising an accuracy gain. [Public dataset testing](PUBLIC_DATASET_EVALUATION.md) remains separately and completely reported. Original evidence below is preserved.

Open **http://127.0.0.1:3000** on the execution host and select **Enter synthetic demo**. Choose Patient, Care navigator, Clinician, Specialist, Provider A, Provider B or Operations administrator. Credentials for ordinary password sign-in are generated in ignored `.runtime/demo-credentials.json`; no password is printed here.

If connecting remotely, forward local port 3000 to port 3000 on the workspace host. This build was not published externally. The API is **http://127.0.0.1:18000/docs**; an unrelated host application already owned port 8000 and was preserved. Synthetic providers use8101/8102, FHIR uses8103 and the local PostgreSQL database uses55432.

SC-001 is the completed visible patient-to-care journey with accepted Provider B episode accountability and an approved source plan. The worklist also retains actual synthetic verification datasets so negative/recovery evidence remains inspectable; search `SC-` to focus on the eight named demo episodes. Operations can reset only the identified `demo-v1` records for another demonstration. Evaluation records and other datasets survive that reset.

## Evidence to review

- `reports/verification/summary.html`: application, browser, clean-install, container and restart verification consolidated from actual artifacts.
- `reports/runs/software-delivery-final/summary.html`: 1,000 persisted trajectories plus500invalid closure attempts, all 1500passed, zero model calls. This run uses the final application source. Earlier regression versions remain preserved and do not represent additional unseen case families.
- `reports/runs/groq-smoke-holdout-v1/summary.html`: actual partial Groq run, with allsix standalone functions, a full valid six-function live journey and two adapted HealthBench candidate/grader pairs. Primary execution failures and skips remain visible. Follow its linked provenance/scorer audits for explicitly corrected secondary scoring, not new inference.
- `runtime/browser-fullcare-journey.json`: actual state snapshots for rejection, accepted ownership, no slots without booking, no-show recovery, attendance, returned source evidence, clinician verification and authorized closure.
- `reports/screenshots/INDEX.md`: packaged actual desktop/mobile/Arabic and completed-care captures, with source paths and checksums.
- `docs/REQUIREMENTS_MATRIX.csv`, `docs/IMPLEMENTATION_STATUS.md`, `docs/DECISIONS.md`: traceability, staged progress and versioned decisions.

Final verification: **98/98** application/security/provider/PostgreSQL tests, **10/10** browser journeys, and **65/65** acceptance/boundary tests using the final source in the isolated clean dependency installation. The clean web production build passed. These checks are separate from model-quality measurements.

Exact service commands are recorded in `runtime/commands.jsonl`; final test/build output is in `runtime/final-test-console.log`, `runtime/browser-final-console.log`, `runtime/fresh-install/manifest.json`, `runtime/container-build-final.log` and `runtime/container-startup-final.log`. Each evaluation run has `commands.txt`; report-rebuild/validation commands are in `runtime/evaluation-packaging-commands.jsonl`. The secret scan passed across source, reports and production frontend output (`runtime/final-secret-scan.json`).

## Verified command interface

```bash
make doctor ENV_FILE=/absolute/private/path/.env
make up
make status
make migrate
make seed
RUN_POSTGRES_TESTS=1 make test
make test-e2e
make demo-replay
make fresh-check
make eval-fetch DATASET=healthbench_adapted
make eval-offline
make reports RUN_ID=groq-smoke-holdout-v1
.venv/bin/python -m evals.runner validate --run-id groq-smoke-holdout-v1
```

`make setup` installs locked dependencies and the supported local runtime; `make build` creates the web production build. `make eval-live PRESET=smoke` performs new inference and spending, rather than replaying existing measurements. The supplied smoke run already executed; its300call/300000token allowance was not reset. Standard/full evaluation was not run automatically. Review the future runner's dry/prepared configuration and provide a separate explicit budget before a broader run. Reports rebuild without model calls.

Native startup, app/worker/evaluation configuration all parse the owner dotenv server-side. The owner file is never sourced, overwritten or copied into frontend assets. Generated runtime settings, sessions, connector credentials and private backup dumps are ignored. The read-only deployment report mount exposes only actual sanitized reports to the authorized administrator.

## Remaining external/optional work

Institutional deployment needs an authorized host/HTTPS, account provisioning, institution-specific clinical/sharing policies, reviewed translations/service windows and real connector registration/credentials. There is no live EHR or UAE exchange connection. MedAgentBench needs separate data/cloud-processing rights, original FHIR container and original scorer; MIMIC remains disabled. Optional Synthea needs supportedJava17+ and a pinned permitted release (the host hasJava11); project-generated FHIR was used. Expert/volunteer/clinical validation was not performed.

V1 model results are known-family conformance evidence. The future v2 generator prepares stronger source/context family separation but has no new live score in this delivery. The public rubric evaluation is adapted and uses a same-model Groq grader. Software correctness, synthetic behavior, model quality and real patient outcomes remain different evidence layers.
