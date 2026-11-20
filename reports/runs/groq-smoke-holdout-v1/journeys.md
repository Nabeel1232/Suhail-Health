# Suhail Health · journeys

Run `groq-smoke-holdout-v1` · **PARTIAL** · live_groq_synthetic

Selected 18; attempted 14; evaluated 12; failed 2; skipped 4.

Task passed 12; incorrect 0.



| Measurement | Value | Denominator | Method |

|---|---:|---:|---|

| task_accuracy | 1.0 | 12 | Independent scenario truth; incorrect evaluated answers remain in denominator. |

| evaluated_coverage | 0.6666666666666666 | 18 | All selected cases remain in execution coverage, including failures and skipped cases. |

| selected_case_pass_fraction | 0.6666666666666666 | 18 | Passed primary scored cases / all selected; infrastructure failures and skips are not counted as passed. |

| arm_A_marginal_coverage_required_care_completed | 0.0 | 6 | Marginal observed arm coverage only; different evaluated subsets are not a matched comparison or patient outcome evidence. |

| arm_B_marginal_coverage_required_care_completed | 1.0 | 5 | Marginal observed arm coverage only; different evaluated subsets are not a matched comparison or patient outcome evidence. |

| arm_C_marginal_coverage_required_care_completed | 1.0 | 1 | Marginal observed arm coverage only; different evaluated subsets are not a matched comparison or patient outcome evidence. |

| matched_A_B_required_care_difference | 1.0 | 5 | Same paired IDs, evaluated independent arm stores only; scripted conformance and synthetic assumptions, no clinical or incremental-AI outcome-effect estimate. |

| matched_B_C_required_care_difference | 0.0 | 1 | Same paired IDs, evaluated independent arm stores only; scripted conformance and synthetic assumptions, no clinical or incremental-AI outcome-effect estimate. |



API calls: 11; input tokens: 26000; output tokens: 8916; cost USD: 0.009249599999999998.

Model: openai/gpt-oss-120b; dataset revision: 08dd171414d78a0adc5f51401fdb24c5f09eda6ebd66ed7285f2ebc721d62cdf.



## Limits



- Single frozen configured candidate; no model sweep, optimization or clinical effectiveness claim.

- Live journey proposals are observed drafts with explicit human-simulated approval; backend truth and endpoint checks govern every transition.

- A/B/C comparisons share synthetic behavior, capacity and evidence; no human usability study or reassurance measurement performed.

- Standard/full presets not executed unless explicit budgets are supplied.

- Observed429s consume conservative unknown-usage reservations; all failed calls retained.

- Operational30-second dispatch pacing and round-robin pending-case order added after observing8000TPM; model/prompt/RAG/scoring/inputIDs unchanged.

- Backend security corrections before fulljourneys recorded in backend-source-at-resume; model-only responses use the original frozen agentcode.

- Postresume latency includes explicit local pacing; no pure network-latency claim.

- usage.api_calls is reserved request attempts, including queued cancellations; actual dispatches are reported separately, with conservative unknown usage retained.

- Version1 has disjoint split IDs/seeds but overlapping scripted templates, question wording and scenario families; no unseen-family or clinical generalization claim.

- Actual RAG sections are retained in provider inputs and validated against a transparently late-captured knowledge pack; original retrieval_hash covered pathway files only.

- Scripted authorized domain role actions and known evidence use synthetic behavior and service capacity; no clinical effectiveness or reassurance claim.

- A reminders; B full workflow templates; C same workflow plus observed bounded live proposals. Unexecuted selected arms remain skipped/failed with no outcome estimate.

- The first shared-store pair is invalid for matched comparisons and retained with its failures. Only valid evaluated independent-store pairs enter comparison metrics.

- Authorized scripted actors follow independent scenario truth while AI drafts are observed; no causal effect of model recommendations or real human review/understanding was measured.



## Sanitized errors



- paired-trajectory-holdout-500000-B: execution_error — Execution did not produce a valid evaluated result; see sanitized command events.

- paired-trajectory-holdout-500000-C: execution_error — Execution did not produce a valid evaluated result; see sanitized command events.

- paired-trajectory-holdout-500002-C: budget_insufficient_for_full_journey — Remainingconservativeallowancecannotreserve35000tokensforanothercomplete6-functionjourney; noproviderrequestdispatched.

- paired-trajectory-holdout-500003-C: budget_insufficient_for_full_journey — Remainingconservativeallowancecannotreserve35000tokensforanothercomplete6-functionjourney; noproviderrequestdispatched.

- paired-trajectory-holdout-500004-C: budget_insufficient_for_full_journey — Remainingconservativeallowancecannotreserve35000tokensforanothercomplete6-functionjourney; noproviderrequestdispatched.

- paired-trajectory-holdout-500005-C: budget_insufficient_for_full_journey — Remainingconservativeallowancecannotreserve35000tokensforanothercomplete6-functionjourney; noproviderrequestdispatched.
