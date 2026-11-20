# Suhail Health · external suite

Run `software-delivery-final` · **NOT_RUN** · adapted_external

Selected 0; attempted 0; evaluated 0; failed 0; skipped 0.

Task passed Not measured; incorrect Not measured.



| Measurement | Value | Denominator | Method |

|---|---:|---:|---|

| adapted_healthbench_rubric_score | Not measured | Not measured | Signed weights / total positive weights per example; clip aggregate mean to [0,1]. Groq batched rubric-grader estimate; not official HealthBench. |



API calls: 0; input tokens: 0; output tokens: 0; cost USD: 0.

Model: Not run; dataset revision: 47cae95630030e6a5d121cd9b840cb380480f157b88aae2462d0cf451e95ac3a.



## Limits



- Deterministic persisted domain commands, no live model inference in this layer.

- SQLite isolated test store; production PostgreSQL API/browser integration verified separately.

- Provider requests/events here execute domain authorization with synthetic actors; independent provider HTTP-contract checks are a separate test layer.

- Operational deadlines and behavior are demonstration settings, not clinical validation.

- usage.api_calls is reserved request attempts, including queued cancellations; actual dispatches are reported separately, with conservative unknown usage retained.

- Public deterministic thematic subset, not representative overall HealthBench.

- Candidate and grader may share model/family; no independent human review performed.

- Batched rubric grading differs from the reference one-criterion-per-request protocol.
