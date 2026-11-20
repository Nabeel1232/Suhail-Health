# Executable agent and application evaluation

Implement this protocol as code. This package specifies the runs; it does not contain measured application or model results. A report is a rendering of immutable executed records, never hand-authored success numbers.

## Evidence layers

1. **Software and reliability:** test actual backend commands, persistence, access, outbox/timers and deterministic policy/closure checks. Run at least 1,000 synthetic trajectories and 500 invalid-closure attempts with known expected states. No model call is required for this layer. Label injected agent outputs and templates as such.
2. **Live Groq agents:** execute the real six functions on held-out permitted synthetic inputs and real allowlisted tool adapters. Include successes, unsupported inputs, abstentions, invalid proposals, provider failures and denied tool actions. All live metrics require actual response records.
3. **Adapted external conversation benchmark:** generate responses to a declared public HealthBench subset, then apply its physician-authored rubric with an explicitly named grader. A Groq grader, changed prompt or subset changes the protocol; call the result adapted/exploratory HealthBench, never the official full-suite score.
4. **Full customer journey:** run paired scenarios through the application's roles/services. A/B/C comparisons must use identical capacity, patient behavior, available evidence and cases. Distinguish automated journey simulation from a volunteer study and future clinical evidence.

Public data are not equivalent to medical/regulatory approval. Keep reviewer and expert validation status separate.

## Per-function evaluation

| Function | Data and independent scoring | Report separately |
| --- | --- | --- |
| Intake | Known synthetic FHIR/document facts; field precision/recall, missingness, patient/order matching, source-span correctness, amendment handling. | Model extraction versus deterministic identity verification; no inference-based identity merge. |
| Pathway router | Held-out configured test-code/text examples, unsupported pathways, conflicts and unknowns; label accuracy, unsupported detection and review/abstention rate. | Routing a supported pathway versus deciding a clinical diagnosis. |
| Safety/escalation | Synthetic trusted flags, missing/ambiguous context, unavailable inference and missed staff acknowledgement; urgent-path recall and escalation timing. Add the declared relevant HealthBench themes for response quality. | Deterministic urgent routing versus the LLM's text recommendations; under/over-escalation and review workload. |
| Patient navigator | Known next action/owner/urgency from synthetic cases plus declared HealthBench conversation tasks; factual support, appropriate referral to a human, rubric score, next-step clarity and language failures. | Automated rubric estimates versus measured patient understanding. Do not invent reassurance gains without a study. |
| Coordination | Known handoff, consultation, appointment, rejection and no-show trajectories; expected tool/action/state, ownership continuity and completion. Optional MedAgentBench only when access and processing permissions are established. | Agent proposals versus authorized application outcomes; no write outside the tool scope. |
| Closure evidence | Matched/mismatched/old/missing evidence with known IDs and prerequisites; evidence-ID precision/recall and false claims of completion. Run the 500 invalid backend closure attempts separately. | Assistant's recommendation error rate versus backend closure-blocking behavior; one cannot substitute for the other. |

Every function receives a report even if its status is NOT_RUN or BLOCKED. For PARTIAL reports show exactly which cases completed. Schema-valid output alone is not task correctness.

## Data sources and acquisition

### Suhail synthetic datasets

Implement deterministic generators from independent scenario truth objects, not just LLM-generated answers. Create FHIR records/documents/events plus gold state/action/evidence labels. Text paraphrases may be generated only for a development set, then checked against truth. Keep final holdout generation seeds and scenario/template families separate. Mark facts that are operational demonstration settings rather than clinical guidance.

Required scenario groups: normal completion, unsupported pathway, identity conflict, corrected result, bad/old/wrong evidence, unanswered consultation, failed notification/understanding, access barrier, rejected/expired handoff, no slots, cancelled/no-show visit, urgent staff acknowledgement timeout, provider/model outage, duplicate/reordered events, unauthorized access, missing onward-care endpoint, decline and lost contact. Include both languages where appropriate.

### HealthBench public data

Source: `https://huggingface.co/datasets/openai/healthbench`; the dataset card is labelled MIT. Reference evaluator: `https://github.com/openai/simple-evals/blob/main/healthbench_eval.py`.

Use Hugging Face repository metadata/listing to discover files and pin the exact upstream revision. Download only needed files into ignored cache, save checksums and license notices, and inspect the schema. Do not depend on a working dataset viewer or assume that a guessed `load_dataset` configuration will cast every optional field correctly. If necessary, read pinned JSONL/Parquet directly and normalize the required conversation/rubric fields with validation.

Keep original example IDs, conversation messages, rubric criteria, signed weights and category metadata. Choose a deterministic declared subset for emergency-referral, uncertainty and patient-communication behavior using actual available metadata. If metadata is absent, create and version a documented selection manifest instead of inventing fields or labels.

Use the original conversation as the candidate input; never leak rubric answers to the candidate. Give rubric criteria only to the evaluator. Inspect and reuse the reference scoring/aggregation logic, including negative criteria and clipping behavior; write scoring unit checks from small known examples. The reference uses an OpenAI grader configuration. With only a Groq key, use a configured Groq grader as an adapted evaluation and disclose same-model/family bias. Do not silently call an unprovided API service. Human review of a sample is optional and must be reported only if performed.

### Synthea

Source: `https://github.com/synthetichealth/synthea`; software is Apache 2.0. Pin the release/commit and preserve notices. Generate a small synthetic FHIR population where Java/runtime access permits; otherwise use clearly identified project-generated FHIR fixtures and report that Synthea was not run. Neither counts as clinical triage ground truth.

### Optional MedAgentBench

Source: `https://github.com/stanfordmlgroup/MedAgentBench`. Verify the data/container release terms separately from its software license before cloud inference. Do not assume the records are wholly synthetic. The published work describes real-record-derived deidentified/jittered profiles. Use the original FHIR image and scoring dependency `refsol.py` only when actually available, with pinned commits/digests. If rights, scorer or access cannot be established, record BLOCKED and continue permitted evaluations. Do not manufacture an equivalent scorer and call it the official benchmark.

### Optional MIMIC-IV-ED

Source: `https://physionet.org/content/mimic-iv-ed/2.2/`. Credentialing, training and data-use conditions apply. It is disabled in the default Groq prototype. Do not upload restricted records or derivatives merely because they are deidentified. If later evaluated locally with established rights, use only arrival-time inputs for retrospective urgency and report the distribution/setting limitations. It is not a replacement for the screening workflow evaluation.

## Fair comparisons and holdouts

Use development cases for engineering and a separate validation set for model selection. Freeze code/model/prompts, tools, retrieval snapshot, cases, scoring and budgets before the final holdout. Keep known safety regressions separate from unseen-generalization claims. If holdout failures lead to changes, disclose the change and use a new untouched evaluation version.

Compare A reminder/dashboard, B complete workflow with fixed templates and C the same workflow with AI. A versus B estimates workflow effects; B versus C estimates incremental AI effects. An offline 1,000-case suite is not a 1,000-case live C run. Use the same live-evaluated subset for paired B/C comparisons. Report raw denominators, effect differences and uncertainty where meaningful. Synthetic behavior/capacity assumptions are explicit and sensitivity-tested; they cannot establish clinical outcome gains.

Benchmark model candidates under identical tool budgets and retrieval. Record context length, sampling, quantization if applicable and actual model IDs. A model change creates a new run. Never tune until a desired score appears and then omit earlier runs.

## Presets and spending controls

Defaults are bounded because the owner's account limits are unknown:

- **Offline:** 1,000 synthetic trajectories, 500 invalid closures and all deterministic/permission tests; zero model requests.
- **Smoke live:** six cases for each of six functions, six full journeys and twelve external conversations. Up to 300 total API calls and 300,000 aggregate tokens, including retries, grader requests and capability probes. Lower the sample count if needed and mark PARTIAL.
- **Standard live:** up to 50 cases/function, 50 paired full journeys and 50 external conversations. Execute only within explicitly configured budgets; default caps remain in force until changed. Do not silently increase them.
- **Full:** owner-configured, explicit opt-in; not the default completion requirement.

Run with concurrency at most two initially, honor provider response limits and retry-after, and use finite backoff. Reserve enough remaining budget for scoring before generating another candidate batch. Persist checkpoints and resume only incomplete case IDs with replay-safe behavior. Stopping on budget is a real result, not a reason to fill missing values.

Record input/output token usage from actual responses. Compute currency cost only with a dated verified price map; otherwise mark unknown. If a USD cap is configured and pricing is unknown, stop that run as budget_configuration_blocked rather than guessing. Count every paid retry and grader request; do not add call counts from unrelated runs.

Reserve request and worst-case token budget atomically before dispatch, including concurrent requests and scoring work, so two workers cannot spend the same remaining allowance. Release unused reservation only when actual usage is known. If a timeout/error omits usage, keep the conservative reservation charged to the remaining allowance and report actual usage unknown; never refund it as zero. A context-size or capability error is an observed failure, not permission to silently drop evidence or change parameters mid-comparison.

## Reports and reproducibility

Implement `reports/runs/<run_id>/` containing:

- `manifest.json`: run ID/times, status, code commit and dirty hash, provider/model, parameters, dataset revision/checksum/license, selected case IDs, prompt/RAG/policy/scorer hashes, budgets and exact commands.
- `cases.jsonl`: immutable sanitized per-case inputs or safe references, proposals, tool events, outputs, errors, scores and usage. Never store keys or restricted records.
- `agents/<function>.json` and `.md`: all six function results with attempted/completed/failed/skipped counts, task metrics, review/abstention, latency, usage and error examples.
- `journeys.json`, `.csv` and `.md`: accepted handoffs, consultation, notification/understanding, attendance, endpoint, delays, residual need and explicit A/B/C denominators.
- `summary.json`, `summary.md`, `summary.html` and metrics CSV: readable branded report, optional measured-data charts, limits and evidence categories.
- `dataset-manifest.json`, test results and a reproducibility README.

Statuses: NOT_RUN, BLOCKED, PARTIAL, COMPLETE. Separate reason codes include missing_credentials, model_unavailable, provider_error, rate_limited, budget_exhausted, dataset_access, scorer_unavailable and rights_unverified. Measurements remain null when unobserved; zero is an observed value. An infrastructure-blocked report may have real attempted-call counts while task scores remain unmeasured.

Use unambiguous terminal counts: selected = attempted + skipped; attempted = completed + failed. Completed means a response was evaluated, including incorrect responses; failed means no valid scored result due to an execution/scoring error. Record task-passed/task-incorrect separately. A wrong evaluated answer must not disappear as an infrastructure failure or be excluded from the task denominator. Keep request retries and provider errors as additional counters.

Reports must rebuild deterministically from executed records and satisfy both the schema and an imperative integrity validator. The validator reconciles selected case IDs, count equations, metric denominators, score aggregation and usage to immutable case/provider-call ledgers. Every live-scored case links to its actual candidate response record; adapted external cases also link to actual grader response records and explicit candidate/grader model IDs. A capability probe cannot justify a live task score. Verify hashes and case/output/call lineage before marking a report complete. A report rebuild preserves its original run/call history rather than presenting cached responses as newly executed inference.

The dashboard reads these records, not hard-coded percentages. Preserve failures in denominators and show all unsuccessful attempts. Report model-only and whole-system safety separately. No report may label a dataset, application or model medically approved based on research benchmark performance.
