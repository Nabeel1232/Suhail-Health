# Suhail Health · software suite

Run `20261120T135507Z-offline` · **COMPLETE** · deterministic_software

Selected 500; attempted 500; evaluated 500; failed 0; skipped 0.

Task passed 500; incorrect 0.



| Measurement | Value | Denominator | Method |

|---|---:|---:|---|

| task_accuracy | 1.0 | 500 | Independent scenario truth; incorrect evaluated answers remain in denominator. |

| evaluated_coverage | 1.0 | 500 | All selected cases remain in execution coverage, including failures and skipped cases. |

| selected_case_pass_fraction | 1.0 | 500 | Passed primary scored cases / all selected; infrastructure failures and skips are not counted as passed. |



API calls: 0; input tokens: 0; output tokens: 0; cost USD: 0.

Model: Not run; dataset revision: 74a98b22034a5616ff526d0f1753eaf4f15aa85f54c45c914bcfe6cf56d45ecd.



## Limits



- Deterministic persisted domain commands, no live model inference in this layer.

- SQLite isolated test store; production PostgreSQL API/browser integration verified separately.

- Provider requests/events here execute domain authorization with synthetic actors; independent provider HTTP-contract checks are a separate test layer.

- Operational deadlines and behavior are demonstration settings, not clinical validation.

- usage.api_calls is reserved request attempts, including queued cancellations; actual dispatches are reported separately, with conservative unknown usage retained.
