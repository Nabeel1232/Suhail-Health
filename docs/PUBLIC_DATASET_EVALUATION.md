# Public dataset assessment and executed pilot

Updated 16 November 2026, Asia/Dubai. This document separates public benchmark inputs, project-generated software fixtures, and actual model execution.

Public datasets are available for relevant parts of Suhail. **HealthBench was selected for a small patient-navigation pilot**, because its public conversations can test how a bounded assistant handles a patient's question. Public availability does not imply real-patient provenance: HealthBench describes simulated interactions produced through synthetic generation and adversarial authoring. Its original task is to answer a conversation against physician-written criteria. Suhail's navigation function instead prepares a source-linked coordination proposal and routes clinical questions to a human. These are different tasks. [Official dataset description](https://openai.com/index/healthbench/), [dataset card](https://huggingface.co/datasets/openai/healthbench).

## What was actually executed

| Evidence layer | Actual result | Meaning |
|---|---|---|
| Persisted software/reliability checks | 1,500/1,500 passed; zero model calls | Deterministic application behavior on project-generated cases |
| Existing six bounded functions | 35/36 known synthetic conformance results, only when joining the separately labelled saved-response audit | Small known-family checks; original six primary scoring errors remain preserved |
| Earlier adapted public HealthBench conversations | 2 of 12 selected conversations evaluated; 20.1040% adapted rubric estimate | General-model conversation responses, **not application-agent accuracy** |
| New public-input patient-navigation pilot | 2 selected, 2 attempted, 0 evaluated, 2 provider request rejections | **No new accuracy measured**; both requests returned HTTP400 before a scorable response |

The new pilot ran on 16 November 2026 at approximately 00:47–00:48 Dubai time. It used the actual `services.agents.engine.propose('patient_navigator', ...)` entry point and the configured `openai/gpt-oss-120b` model through Groq. The provider gateway retained status and error type, but no response body or request ID; the exact rejection cause is unknown. No retry, model substitution, rubric change, or outcome-based reselection followed the failures.

Open the executed pilot report (archived at `../reports/runs/public-navigation-healthbench-v3/summary.html`), JSON (archived at `../reports/runs/public-navigation-healthbench-v3/summary.json`), CSV (archived at `../reports/runs/public-navigation-healthbench-v3/metrics.csv`), or passed integrity reconciliation (archived at `../reports/runs/public-navigation-healthbench-v3/integrity.json`). Model-quality success was not inferred from the integrity check.

## Frozen data and method

The exact upstream is `openai/healthbench`, revision `40ee1968852fc57f625934251ac22be47077a8fb`, MIT dataset card. The selected standard file is `2025-05-07-06-14-12_oss_eval.jsonl`, containing 5,000 rows with SHA-256 `e99dd3c6372c10d6fcc5e385c5fae69d0dd40392dae56836ef9493ae324ecd2f`. The original reference evaluator is pinned separately at `openai/simple-evals` commit `652c89d0ca9df547706735883097e9537d40dc47`; its MIT notice is retained. The pinned dataset card and fetch manifest are in `reports/public-dataset-v3/research-sources/`.

Selection was fixed before inference: match the declared colorectal/FIT/colonoscopy user-text terms; retain complete conversations no larger than 768 UTF-8 bytes; exclude all 12 previously selected public IDs; sort by original ID; take the first two of ten eligible records. The two original IDs are `096e9eae-ff12-48db-ac65-e62ce040c25e` and `1bbfec86-e327-416a-9845-de86ecb84199`. Neither conversation was truncated. No outcome was known when the questions, rubric, source snapshots and request parameters were frozen.

The public questions remained unchanged. Case identity/version, owner, language and next action were explicitly synthetic workflow fixtures. Benchmark text was treated as untrusted patient input rather than a verified clinical record. The declared operational rubric checked scope, human referral, source support, evidence boundaries, grounded facts, a patient-facing message, the actual next step and consistent responsibility, with penalties for invented clinical instructions or completed care. Upstream medical rubrics were preserved for provenance but withheld from candidates and not substituted for this operational task. Since neither request returned a proposal, no automatic or semantic case scoring occurred.

The frozen plan is freeze.json (archived at `../reports/public-dataset-v3/freeze.json`), digest `867623a612b969ffddb06a63bed1b11c530086f4b4a69f859c62cc8fbda221bf`. Requests used temperature 0, a declared 704-token output cap, sequential dispatch with at least 31 seconds spacing, no tools and zero automatic retries. The smaller output cap is a different bounded configuration from the earlier 1,500-token run; no performance comparison is claimed.

## Public dataset fit

| Source | Useful Suhail use case | Decision and limit |
|---|---|---|
| [HealthBench](https://huggingface.co/datasets/openai/healthbench) | Patient communication, uncertainty and referral boundaries | Selected above. Original medical-answer grading and adapted application checks remain separate. |
| [Synthea](https://github.com/synthetichealth/synthea) | Publicly reproducible FHIR/CSV intake and integration fixtures | Apache-2.0 synthetic record generator; useful integration data, not real-patient clinical ground truth. No new Synthea run is claimed. |
| [MedAgentBench](https://github.com/stanfordmlgroup/MedAgentBench) | Agent actions in an EHR environment | Not run. Its original FHIR server and reference solution are required; code licensing alone does not resolve downstream data/cloud-processing rights. |
| [MIMIC-IV-ED](https://physionet.org/content/mimic-iv-ed/2.2/) | Optional retrospective emergency-care research | Excluded from remote processing. Access requires credentials, training and a data-use agreement; it is also outside this application's screening-follow-up focus. |

The source assessment and retained licence references are indexed in research-sources/manifest.json (archived at `../reports/public-dataset-v3/research-sources/manifest.json`). No private or credentialed patient dataset was sent to a model.

## Spending and immutable lineage

The original 300-reservation / 300,000-conservative-token allowance was not increased or reset. The two new attempts reserved 9,346 and 9,647 tokens, respectively: 18,993 additional conservatively charged tokens. With usage missing, those reservations remain charged. The forked cumulative ledger contains **71 reservations and 299,042 conservatively charged tokens**, leaving 958 tokens. Known actual tokens remain 146,772, with 16 unknown-usage attempts. Complete actual token usage and cost remain unknown. No additional model call was issued after these attempts.

The continuation copied the original accounting database and provider-chain prefix into a new run; it did not reopen the original run for writing. All five frozen original artifacts—budget database, provider ledger, case ledger, manifest and summary—still match their pre-run hashes. The new case and provider hash chains, request hashes, source snapshots, dataset bytes, selected IDs, exact reservations, and count equations passed 30 saved-artifact integrity checks.

The earlier external report's `usage.api_calls=6` is a reservation count: **four completed candidate/grader responses plus two queued pre-dispatch cancellations**. Those four completed responses carry 11,398 known tokens. The separately frozen audit's `existing_provider_requests=4` names the completed responses; it should not be read as six paid generations. The explicit reconciliation (archived at `../reports/public-dataset-v3/call-accounting-reconciliation.json`) retains both definitions without rewriting the original records.

The earlier general-model rubric score preserves signed weights: raw scores were -2/33 and 31/67, followed by the declared aggregate clipping rule. It used the same candidate/grader model family on a small thematic subset. No independent physician adjudication, official full HealthBench score, clinical validation or patient-outcome improvement is established.

## Rebuilding and checking the saved report

These commands create no provider client and perform no inference:

```bash
TMPDIR="$PWD/.runtime/showcase-tmp" .venv/bin/python -m evals.public_dataset_v3 verify
TMPDIR="$PWD/.runtime/showcase-tmp" .venv/bin/python -m evals.public_dataset_v3 reports
TMPDIR="$PWD/.runtime/showcase-tmp" .venv/bin/python reports/public-dataset-v3/finalize_reports.py
TMPDIR="$PWD/.runtime/showcase-tmp" .venv/bin/python reports/public-dataset-v3/verify_integrity.py
```

The presentation pass clarifies missing total token measurements as null and distinguishes known-token subtotals. Earlier generated report snapshots remain under `reports/public-dataset-v3/pre-finalization/`; executed ledgers and the frozen candidate adapter remain unchanged. `finalize_reports.py` does not change the benchmark score, cases or spending database. The freeze artifact intentionally retains its pre-execution `PREPARED_NO_INFERENCE` label; actual execution status is in the separate run report.

For presentation, the application can emphasize its six bounded capabilities and demonstrated workflow. The supporting reports retain every evidence layer. A small selected sample should not be described as blanket 100% medical or agent accuracy, and changing models requires a new measured comparison before claiming better accuracy.
