# Evaluation delivery status

Updated 2026-11-15 (Asia/Dubai). No more live inference is running.

| Evidence | Executed status | Actual counts |
|---|---|---|
| Deterministic persisted software | COMPLETE | 1,000 trajectories + 500 invalid closures; 1,500 evaluated/passed; zero model calls |
| Original bounded Groq smoke | PARTIAL | 66 selected, 52 attempted, 44 evaluated, 8 failed, 14 skipped |
| Standalone six functions | PARTIAL | 36 actual candidate responses; 30 primary scored/passed, six primary scoring errors retained |
| Secondary Arabic scoring audit | COMPLETE, score-only | Six existing real responses audited; five correct, one incorrect; zero new API calls |
| Full paired journeys | PARTIAL | One complete independent-store A/B/C triple, including all six actual C function responses; other arms and failures retained |
| Adapted public HealthBench | PARTIAL | Two candidate/grader pairs scored of twelve selected; ten skipped for remaining allowance |
| V2 generator and future CLI | Software verified; live NOT_RUN | 28 evaluation/scheduler/generator tests pass; validation manifest prepared with zero provider requests |

## Primary evidence paths

- Final release proof: `reports/runs/software-delivery-final/summary.html` and `.json`, `.md`, `metrics.csv`; 1,500/1,500 passed, zero model requests, actual command/audit records and execution.sqlite3 retained. Earlier `software-holdout-v1` remains preserved as the prior implementation-version run.
- `reports/runs/groq-smoke-holdout-v1/summary.html` and `.json`, `.md`, `metrics.csv`.
- All six `agents/<function>.json`, `.md`, `.csv`, `.html`; journey/external reports in all four formats.
- `secondary-scoring-audit/`: separately versioned replay of six existing Arabic responses. Original primary failures remain unchanged.
- `journey-databases/A.sqlite3`, `B.sqlite3`, `C.sqlite3`, their hash manifest, plus the original invalid shared-store database and raw event lineage.
- `rag-provenance/`: full actual-source archive, transparent late-capture erratum, and per-provider-call retrieved-section hashes.
- `actual-backend-first-import.json` and `actual-backend-source/`: exact API bytes before journey imports. Later application security corrections are a separate app version, not retroactively claimed as benchmark code.
- `candidate-selection-history/`: all four development/validation provider ledgers, including failures.
- `dispatch-accounting.json`, `comparison-validity.json`, `split-provenance-erratum.json`, `journey-harness-isolation-erratum.json`.

## Spending and request accounting

The final run retained its original 300-request-attempt / 300,000-token allowance throughout. There were 69 reserved request attempts, 67 confirmed actual network/SDK dispatches, 55 completed provider responses (54 generation responses plus model-list access), twelve observed HTTP 429 responses, and two queued pre-dispatch cancellations. Do not label all reservations as paid inference.

Conservatively charged tokens: **280,049**. Known actual response tokens: **146,772**. Fourteen attempts have unknown usage and retain their conservative reservations. Total actual tokens and complete cost remain unknown. Remaining allowance could not safely reserve another full six-function journey or mandatory candidate+rubric grading; no cap was increased or reset.

Candidate and grader: configured `openai/gpt-oss-120b`. Output cap 1,500. A 30-second SDK dispatch scheduler was added after observed 8,000 TPM limits; post-resume gateway latency includes that queue delay. No model, prompt, RAG document, or task-truth change was used to improve the final results.

## Integrity and limitations

Immutable case/provider-call chains, selected IDs, count equations, schemas, exact candidate inputs/outputs, candidate/grader lineage, signed rubric aggregation, reservation usage, all 59 policy-bearing call contexts, archived API source hashes, and actual independent-arm database endpoint states validate.

The original v1 scorer used English FTS terms for Arabic context and threw a scoring exception on six real responses. Those primary scoring failures remain. The secondary audit corrects only source-context validation; it found a real incorrect intake proposal instead of inventing a perfect score.

The first A/B/C fixture shared one database and was deduplicated by the application's correct patient/order identity rule. Its B/C failures and five C responses remain recorded; that pair is excluded from matched comparisons. Remaining arms use separate actual stores with shared scenario truth. Matched A/B comparisons use five valid pairs; B/C uses one valid pair with difference zero. Marginal rates are coverage only. Scripted actors follow known truth while AI drafts are observed; no clinical, causal incremental-AI, or human-understanding effect was measured.

V1 has disjoint split IDs/seeds but overlapping scripted templates, question wording and scenario families. It supports known-family conformance claims, not unseen-family generalization. Future v2 now separates actual source formats, request wording and observable support-condition combinations, with 17 tests, while explicitly sharing core care rules. V2 has not been live evaluated.

HealthBench source revision `40ee1968852fc57f625934251ac22be47077a8fb`, 5,000-row standard file SHA256 `e99dd3c6372c10d6fcc5e385c5fae69d0dd40392dae56836ef9493ae324ecd2f`; MIT card retained. Reference simple-evals commit `652c89d0ca9df547706735883097e9537d40dc47`, MIT notice retained. Original IDs/tags/signed weights preserved, rubrics never given to candidates. Groq batched grading and a thematic subset are adapted evaluation, not an official overall HealthBench score.

Expert clinical/Arabic review and real patient understanding/reassurance studies: NOT_RUN. Synthea generator: NOT_RUN, project-generated FHIR identified. MedAgentBench: BLOCKED pending data/cloud rights, original container and scorer. Credentialed MIMIC excluded from remote path. Standard/full live suites: NOT_RUN; no unbounded public suite or additional model budget used.

## Verified commands

```sh
.venv/bin/python -m pytest tests/test_evaluation.py tests/test_eval_scheduling.py tests/test_synthetic_v2.py -q --junitxml=runtime/evaluation-final-tests.xml
.venv/bin/python -m evals.runner offline --run-id software-holdout-v1 --trajectories 1000 --invalid-closures 500 --split holdout
.venv/bin/python -m evals.runner live --run-id groq-smoke-holdout-v1 --preset smoke --max-calls 300 --max-tokens 300000
.venv/bin/python -m evals.runner reports --run-id groq-smoke-holdout-v1
.venv/bin/python -m evals.runner validate --run-id groq-smoke-holdout-v1
.venv/bin/python -m evals.runner live --run-id synthetic-v2-validation-preparation --preset smoke --split validation --cases 1 --journeys 0 --external 0 --max-calls 10 --max-tokens 30000 --prepare-only
```

The historical smoke resumed through preserved scheduler scripts under its run directory; exact commands, operational source revisions and unchanged spending ledger remain available. Future new-run CLI now reads canonical `BENCHMARK_*` owner settings with legacy aliases, uses 30-second actual SDK pacing, round-robin function coverage, independent A/B/C stores, primary language-correct scoring and full source/knowledge snapshots. It cleanly handles interruption. `--prepare-only` builds a truthful NOT_RUN manifest/reports without initializing a provider client. A new live v2 run requires a new explicitly allocated budget; none was consumed after the original run terminated.

## Final packaging verification

The existing `software-delivery-final` run completed at 2026-11-14T22:08:51.857720+00:00: 1,500 selected/attempted/evaluated/passed, zero failed/skipped/model requests. It was not duplicated. Final report generation and integrity validation passed for this release run and `groq-smoke-holdout-v1`. The secondary audit was re-rendered with `scripts/render_secondary_audit.py`: six saved responses, five correct, one incorrect, zero new inference. Primary live counts remain 44 evaluated, eight failed, fourteen skipped of 66 selected. Exact packaging commands, exit codes and output paths are recorded in `runtime/evaluation-packaging-commands.jsonl`. No application/model source changed and no inference ran during packaging.


## Public-input continuation — 16 November 2026

The [public dataset assessment](PUBLIC_DATASET_EVALUATION.md) is complete. Two frozen HealthBench conversations were attempted through the actual patient-navigation entry point with synthetic workflow facts. Both requests returnedHTTP 400 before a scorable response:2 selected/2 attempted/0 evaluated/2 failed/0 skipped, no accuracy measured. No retry, input selection change, model substitution or rubric tuning followed. The original two public conversations remain a separate bare-model adapted rubric estimate of20.104%, not application-agent accuracy.

The new run is `reports/runs/public-navigation-healthbench-v3/`, with actual ledgers, a pinned/frozen method and30/30passed saved-artifact integrity checks. Original parent artifacts remain unchanged. The continuation did not raise or reset the300 request/300,000 token allowance: cumulative 71reservations,299,042 conservatively charged tokens,146,772 known actual tokens and16 unknown-usage attempts, leaving958 tokens. Complete actual tokens and cost remain unknown. The report preserves unknown total usage as null and known subtotals separately. No additional inference is authorized by rebuilding these reports.
