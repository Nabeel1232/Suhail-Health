# Suhail Health execution report

Run `20261120T123924Z-offline` · **COMPLETE**

1500 selected; 1500 attempted; 1500 evaluated; 0 failed; 0 skipped.

Software execution, live inference and adapted conversation rubric estimates are separate evidence layers.

| Component | Evidence | Status | Attempted / selected | Evaluated | Incorrect |

|---|---|---|---:|---:|---:|

| intake | deterministic_software | NOT_RUN | 0 / 0 | 0 | Not measured |

| pathway_router | deterministic_software | NOT_RUN | 0 / 0 | 0 | Not measured |

| safety_escalation | deterministic_software | NOT_RUN | 0 / 0 | 0 | Not measured |

| patient_navigator | deterministic_software | NOT_RUN | 0 / 0 | 0 | Not measured |

| coordination | deterministic_software | NOT_RUN | 0 / 0 | 0 | Not measured |

| closure_evidence | deterministic_software | NOT_RUN | 0 / 0 | 0 | Not measured |

| journeys | deterministic_software | COMPLETE | 1000 / 1000 | 1000 | 0 |

| software_suite | deterministic_software | COMPLETE | 500 / 500 | 500 | 0 |

| external_suite | adapted_external | NOT_RUN | 0 / 0 | 0 | Not measured |



Actual request usage: `{"api_calls":0,"budget_reason":null,"cost_usd":0,"input_tokens":0,"latency_ms_p50":null,"latency_ms_p95":null,"output_tokens":0,"price_map_version":null}`.

Optional expert review was not performed. MedAgentBench/MIMIC are blocked or excluded; no restricted records were sent.

Public data and model benchmarks do not establish medical validation. Synthetic workflow outcomes do not establish patient impact.

Reserved request attempts: 0; confirmed actual dispatches: 0; queued pre-dispatch cancellations: 0. Unknown usage remains conservatively charged; paid inference call count and total cost are unknown.

Matched A/B pairs: 0; matched B/C pairs: 0. Marginal arm rates use different subsets and are coverage only. Invalid first pair remains in failure counts.

No secondary response scoring audit.



## Reproduce



`python -m evals.runner reports --run-id 20261120T123924Z-offline`

`python -m evals.runner validate --run-id 20261120T123924Z-offline`
