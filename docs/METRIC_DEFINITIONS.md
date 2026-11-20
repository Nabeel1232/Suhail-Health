# Implemented metric definitions

`GET /metrics` is authorized to the source organization's navigator, clinician and administrator. Its episode denominator is every stored actionable episode in that organization, including open cases, quarantined cases, decline, inability to contact, clinical resolution and accepted transfer with open care. Test/demo/replay datasets in that organization are included. These are synthetic software observations, not patient outcome evidence.

## Persisted episode and event measures

| Field | Numerator / observation | Denominator and interpretation |
|---|---|---|
| denominator / actionable_cases | All authorized episode IDs | Full stored actionable-episode population |
| notified | Distinct cases with at least one delivered communication | Full actionable denominator; cumulative delivery, not acknowledgement |
| acknowledged | Distinct cases with at least one patient acknowledgement | Full actionable denominator; separate from understanding |
| understood | Distinct cases with at least one recorded passed teach-back | Full actionable denominator; cumulative recorded response, not a study of understanding improvement |
| consultation_replied | Distinct cases with at least one human-authored reply | Full actionable denominator; the case view separately shows every unanswered required question |
| referral_accepted | Distinct cases with an accepted handoff | Full actionable denominator; not an attendance or care-completion measure |
| attended | Distinct cases with an appointment whose reconciled status is attended | Full actionable denominator; not a completed investigation |
| care_completed | Cases currently disposed completed_required_care | Full actionable denominator; deterministic current evidence and required endpoint tasks govern this category |
| dispositions | Count of each current disposition | Full actionable denominator; exceptions do not enter care_completed |
| residual_need | Cases with a nonempty documented residual need | Full actionable denominator; retained independently from exception handling |
| understanding | Counts by outcome across stored communication records | Communication-record denominator; multiple messages can belong to one episode |
| stage_timings | Seconds from episode ingestion to the first recorded notification, consultation reply or handoff decision in each episode | Mean across distinct episodes with a timestamp for each event. The response includes `measured_episodes` for each mean and returns null for an empty sample. |
| experience.responses / responding_episodes | Actual patient-role survey submissions / distinct submitting episodes | Response and episode denominators are separate; rating means use submitted 1–5 responses |
| confidence / reassurance | Mean captured self-report, or null before responses | Synthetic self-report only; no baseline, gain, clinical reassurance benefit or volunteer study is claimed |

Communication/referral counts are cumulative event achievements. Corrected results reopen current milestones and evidence gates; previous responses remain historical. Use the case's current independent milestones/closure check for present readiness, rather than interpreting a cumulative aggregate as permission to close. Reports distinguish event counts, episode counts, current care completion and model benchmark cases.

## Outcomes dashboard

The `outcomes` response uses the application clock for `as_of`. Funnel stage totals use the full episode denominator. Its conversion rates carry separate numerator and denominator counts so each rate can be interpreted on its own.

| Measure | Numerator or sample | Denominator and interpretation |
|---|---|---|
| `notified` | Distinct episodes with a delivered update | All actionable episodes |
| `acknowledged_of_notified` | Delivered episodes with a recorded acknowledgement | Episodes with a delivered update |
| `understood_of_acknowledged` | Acknowledged episodes with a passed understanding check | Episodes with a recorded acknowledgement |
| `referral_accepted_of_requested` | Distinct episodes with at least one accepted handoff | Episodes with any handoff record |
| `appointment_attended_of_booked` | Distinct episodes with at least one attended appointment | Episodes with any appointment record |
| `care_completed` | Episodes whose current disposition is `completed_required_care` | All actionable episodes |
| `documented_closure` | Episodes with a disposition other than `open` | All actionable episodes. Includes documented exceptions and accepted transfers whose downstream care remains open. |
| `time_to` | Elapsed hours from source issuance to each episode's latest completed task of that step. Completed-care closure uses `closed_at`. | Reports sample count `n`, median and nearest-rank 90th percentile for episodes with a valid issuance and completion timestamp. Empty samples return null times. |
| `within_target` | Sampled completions on or before the recorded task deadline | The step timing sample. The displayed target is the configured operational service window. Closure timing has no separate configured target. |
| `unresolved` | Episodes with disposition `open` or `accepted_transfer_open`, counted by age. Overdue work counts distinct episodes with overdue tasks. | Age uses the source issuance time and falls back to ingestion where issuance is missing or unreadable. |
| `sla` and `by_owner` | Tasks still open, split by recorded deadline status, 24-hour window and owner | Task-level counts. Completed and cancelled tasks are excluded. |
| `drop_off` | Distinct episodes with each recorded barrier, delay reason or request for help with understanding | One episode can count in several categories. The category totals can exceed the number of episodes. |

## Simulated impact and software evaluation

The Projected Impact panel reads the paired synthetic cohort in `GET /impact`. Its baseline, recovery scenarios, completion gains and documentation results use declared assumptions and a fixed cohort. The observed dashboard uses persisted workflow records. A local pilot would compare both arms using the same actionable-result denominator and account for open work and unknown dispositions. [Impact method](IMPACT_MODEL.md) · [Simulated cohort report](../reports/impact/impact-summary.json)

Benchmark task denominators are separate from application impact denominators. Each benchmark report reconciles selected = attempted + skipped and attempted = evaluated + execution-failed. An evaluated incorrect response remains in the task denominator. Model request counts include recorded probes/retries/grading; they are not the number of patient trajectories. Missing provider usage or cost stays unknown, with conservative token reservations retained against the cap.
