# Modelled impact after a positive FIT result

The model follows 10,000 synthetic actionable screening results for 360 days. Projected completion rises from **56% under usual care to 69% with Suhail-supported navigation**, with a scenario range of **62.5–75.4%**. That is **1,300 additional completions per 10,000 results**, with a range of **650–1,940**. These are simulated outcomes. Use the JSON for exact values and the CSV to audit each paired episode. [Impact summary](../reports/impact/impact-summary.json) · [Paired cohort](../reports/impact/impact-cohort.csv)

## Evidence used

- Mohl et al. studied 32,769 people with positive stool-based screening results across US organizations in 2017–2020. Colonoscopy completion was 43.3% by 90 days, 51.4% by 180 days and 56.1% by 360 days. The model calibrates to the rounded rates of 43%, 51% and 56%. [Mohl et al., JAMA Network Open, 2023](https://doi.org/10.1001/jamanetworkopen.2022.51384)
- The PRECISE trial analysed 967 participants in a Washington State health center network of 32 clinics. Adjusted 12-month completion was 55.1% with human navigation and 42.1% with usual care. The difference was 13.0 percentage points, with a 95% confidence interval of 6.5 to 19.4. The model uses this effect to set the recovery scenarios. [Coronado et al., Annals of Internal Medicine, 2025](https://doi.org/10.7326/ANNALS-24-01885)
- In a cohort of 70,124 people with positive FIT results, follow-up at 10 to 12 months was associated with higher odds of colorectal cancer (1.48) and advanced-stage disease (1.97) than follow-up at 8 to 30 days. The study does not establish causality. This evidence explains why the report shows unresolved follow-up at day 300. It does not enter the completion calibration. [Corley et al., JAMA, 2017](https://doi.org/10.1001/jama.2017.3634)

## Method

1. **Usual care.** The cumulative completion curve is `p∞ × Φ((log(t) − μ) / σ)`. Bisection finds the eventual completion probability `p∞` that satisfies the three calibration targets. The first two targets determine `μ` and `σ` for each candidate. The fitted values are `p∞ = 0.60035`, `μ = 3.64310` and `σ = 1.49846`. The simulation uses seed `20261120` to shuffle cohort mid-quantiles before drawing times. It records results beyond day 360 as incomplete at the horizon.
2. **Paired recovery.** Both arms share the same 10,000 episode IDs. Every usual-care completion within the horizon keeps its original date in the Suhail arm. Each usual-care noncompletion receives one modelled failure point and is eligible for recovery. The failure, recovery and recovery-delay draws use independently shuffled mid-quantiles within this eligible group. The low, central and high recovery probabilities are the respective PRECISE differences divided by the 44% baseline incomplete share.
3. **Recovery timing.** Each modelled failure is detected by its corresponding workflow check and gives rise to owned follow-up. A successful recovery completes after a lognormal delay from day 30, with a median delay of 45 days and a log-scale standard deviation of 0.50. These timing parameters are assumptions. They simplify differences in contact, referral and appointment timing.
4. **Ownership and closure.** The simulation assigns an owned ledger entry to every Suhail episode. It represents the 3,100 central-scenario noncompletions as documented exceptions with residual need. In a deployment, a clinician must authorize an exception and record that need. Unresolved episodes can stay open under a named owner. The model assigns 0% to unknown tracking or outcome in the Suhail arm by design. In usual care, the tracking status of the 44% without completion is unknown because the source studies measure colonoscopy completion rather than ownership.

The final software evaluation passed 1,000 synthetic journey checks and refused 500 of 500 premature closures. This supports the software mechanisms, including explicit ownership and evidence gates. Clinical recovery probabilities and documentation rates require pilot data. [Final software evaluation](../reports/runs/20261120T135507Z-offline/summary.html)

## Failure points and recovery mechanisms

| Modelled failure point | Share of usual-care noncompletions | Suhail workflow | Tested scenarios |
| --- | ---: | --- | --- |
| Unreached or unclear next step | 30% | Delivery tracking, teach-back, and an owned help or consultation task | `failed_understanding`, `unanswered_consultation` |
| Referral not placed, rejected or lost | 25% | Explicit rejection or expiry preserves ownership and generates recovery work | `rejected_handoff`, `expired_handoff` |
| Appointment never booked | 20% | Capacity or access barriers open navigator follow-up | `no_slots`, `access_barrier` |
| Missed or cancelled visit stays unbooked | 25% | The cancelled or missed attendance creates recovery work | `cancelled_visit`, `no_show` |

The shares are declared assumptions. Scenario names map to end-to-end synthetic checks. [Scenario harness](../evals/domain_harness.py)

## Sensitivity

The table holds each recovery probability fixed and changes the assumed usual-care baseline. Projected completion is the baseline plus the remaining incomplete share multiplied by the recovery probability.

| Assumed usual-care completion | Low recovery (14.8%) | Central recovery (29.5%) | High recovery (44.1%) |
| --- | ---: | ---: | ---: |
| 42% | 50.6% | 59.1% | 67.6% |
| 56% | 62.5% | 69.0% | 75.4% |
| 80% | 83.0% | 85.9% | 88.8% |

## Limitations and pilot

The anchors come from US health systems. UAE baseline completion and service capacity require local measurement. PRECISE measured human navigation. Its results may differ in a Suhail-supported service with different staffing, access, patient needs or capacity. The scenario range transfers only the trial's uncertainty in effect size. It excludes uncertainty in adoption, baseline rates, timing, staffing and case mix. The model uses synthetic episodes and estimates completion and tracking. It provides no estimate of cancer outcomes, cost savings or effectiveness in practice.

A pilot should establish local baseline completion at fixed time points, track unknown dispositions and residual needs separately, and compare follow-up and documented closure with the same denominator. It should measure what happens to cases that remain open, including delays attributable to capacity and access.

## Reproduce

`make impact` regenerates the JSON, Markdown summary and paired CSV with Python's standard library. The report uses a fixed revision date to allow byte-for-byte reproduction. The CSV contains one row per episode and arm, with an empty colonoscopy day for noncompletion within the horizon. Usual-care ownership is blank because ownership was unobserved in the source. The CSV records day 30 only for Suhail episodes eligible for recovery. Run `.venv/bin/python -m pytest tests/test_impact.py -q` to verify determinism, baseline calibration and paired completion.
