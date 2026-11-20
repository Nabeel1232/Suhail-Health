# Suhail Health · journeys

Run `software-delivery-final` · **COMPLETE** · deterministic_software

Selected 1000; attempted 1000; evaluated 1000; failed 0; skipped 0.

Task passed 1000; incorrect 0.



| Measurement | Value | Denominator | Method |

|---|---:|---:|---|

| task_accuracy | 1.0 | 1000 | Independent scenario truth; incorrect evaluated answers remain in denominator. |

| evaluated_coverage | 1.0 | 1000 | All selected cases remain in execution coverage, including failures and skipped cases. |

| selected_case_pass_fraction | 1.0 | 1000 | Passed primary scored cases / all selected; infrastructure failures and skips are not counted as passed. |

| arm_B_marginal_coverage_required_care_completed | 0.05 | 1000 | Marginal observed arm coverage only; different evaluated subsets are not a matched comparison or patient outcome evidence. |

| matched_A_B_required_care_difference | Not measured | Not measured | Same paired IDs, evaluated independent arm stores only; scripted conformance and synthetic assumptions, no clinical or incremental-AI outcome-effect estimate. |

| matched_B_C_required_care_difference | Not measured | Not measured | Same paired IDs, evaluated independent arm stores only; scripted conformance and synthetic assumptions, no clinical or incremental-AI outcome-effect estimate. |



API calls: 0; input tokens: 0; output tokens: 0; cost USD: 0.

Model: Not run; dataset revision: 47cae95630030e6a5d121cd9b840cb380480f157b88aae2462d0cf451e95ac3a.



## Limits



- Deterministic persisted domain commands, no live model inference in this layer.

- SQLite isolated test store; production PostgreSQL API/browser integration verified separately.

- Provider requests/events here execute domain authorization with synthetic actors; independent provider HTTP-contract checks are a separate test layer.

- Operational deadlines and behavior are demonstration settings, not clinical validation.

- usage.api_calls is reserved request attempts, including queued cancellations; actual dispatches are reported separately, with conservative unknown usage retained.

- Scripted authorized domain role actions and known evidence use synthetic behavior and service capacity; no clinical effectiveness or reassurance claim.

- A reminders; B full workflow templates; C same workflow plus observed bounded live proposals. Unexecuted selected arms remain skipped/failed with no outcome estimate.

- The first shared-store pair is invalid for matched comparisons and retained with its failures. Only valid evaluated independent-store pairs enter comparison metrics.

- Authorized scripted actors follow independent scenario truth while AI drafts are observed; no causal effect of model recommendations or real human review/understanding was measured.
