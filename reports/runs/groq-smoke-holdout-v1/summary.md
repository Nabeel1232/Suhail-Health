# Suhail Health execution report

Run `groq-smoke-holdout-v1` · **PARTIAL**

66 selected; 52 attempted; 44 evaluated; 8 failed; 14 skipped.

Software execution, live inference and adapted conversation rubric estimates are separate evidence layers.

| Component | Evidence | Status | Attempted / selected | Evaluated | Incorrect |

|---|---|---|---:|---:|---:|

| intake | live_groq_synthetic | PARTIAL | 6 / 6 | 5 | 0 |

| pathway_router | live_groq_synthetic | PARTIAL | 6 / 6 | 5 | 0 |

| safety_escalation | live_groq_synthetic | PARTIAL | 6 / 6 | 5 | 0 |

| patient_navigator | live_groq_synthetic | PARTIAL | 6 / 6 | 5 | 0 |

| coordination | live_groq_synthetic | PARTIAL | 6 / 6 | 5 | 0 |

| closure_evidence | live_groq_synthetic | PARTIAL | 6 / 6 | 5 | 0 |

| journeys | live_groq_synthetic | PARTIAL | 14 / 18 | 12 | 0 |

| software_suite | deterministic_software | NOT_RUN | 0 / 0 | 0 | Not measured |

| external_suite | adapted_external | PARTIAL | 2 / 12 | 2 | Not measured |



Actual request usage: `{"api_calls":69,"budget_reason":null,"cost_usd":null,"input_tokens":null,"latency_ms_p50":28706.83143287897,"latency_ms_p95":30635.62273606658,"output_tokens":null,"price_map_version":"groq-models-2026-11-15"}`.

Optional expert review was not performed. MedAgentBench/MIMIC are blocked or excluded; no restricted records were sent.

Public data and model benchmarks do not establish medical validation. Synthetic workflow outcomes do not establish patient impact.

Reserved request attempts: 69; confirmed actual dispatches: 67; queued pre-dispatch cancellations: 2. Unknown usage remains conservatively charged; paid inference call count and total cost are unknown.

Matched A/B pairs: 5; matched B/C pairs: 1. Marginal arm rates use different subsets and are coverage only. Invalid first pair remains in failure counts.

Six Arabic scoring failures are preserved in primary counts. A separate score-only audit reuses six actual responses with zero API calls (five passed, one incorrect); it does not rewrite primary outcomes.



## Reproduce



`python -m evals.runner reports --run-id groq-smoke-holdout-v1`

`python -m evals.runner validate --run-id groq-smoke-holdout-v1`
