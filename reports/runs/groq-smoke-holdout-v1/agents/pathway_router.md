# Suhail Health · pathway router

Run `groq-smoke-holdout-v1` · **PARTIAL** · live_groq_synthetic

Selected 6; attempted 6; evaluated 5; failed 1; skipped 0.

Task passed 5; incorrect 0.



| Measurement | Value | Denominator | Method |

|---|---:|---:|---|

| task_accuracy | 1.0 | 5 | Independent scenario truth; incorrect evaluated answers remain in denominator. |

| evaluated_coverage | 0.8333333333333334 | 6 | All selected cases remain in execution coverage, including failures and skipped cases. |

| selected_case_pass_fraction | 0.8333333333333334 | 6 | Passed primary scored cases / all selected; infrastructure failures and skips are not counted as passed. |

| action_correct | 1.0 | 5 | Independent known synthetic truth; no grader model. |

| review_or_abstention | 0.6 | 5 | Independent known synthetic truth; no grader model. |

| secondary_existing_response_audit_pass_fraction | 1.0 | 1 | Post-hoc source-language scoring audit of existing actual responses; zero new inference. Primary scoring-error/failure counts remain unchanged. |



API calls: 14; input tokens: Unknown; output tokens: Unknown; cost USD: Unknown.

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

- One Arabic case had a primary scoring exception; its existing response is evaluated only in the separately versioned secondary audit, preserving the primary failure denominator.



## Sanitized errors



- pathway_router-holdout-002: execution_error — Execution did not produce a valid evaluated result; see sanitized command events.
