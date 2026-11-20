"""Deterministic paired simulation of follow-up after a positive screening result."""
import argparse
from bisect import bisect_right
from collections import Counter
import csv
import json
import math
from pathlib import Path
from random import Random
from statistics import NormalDist, median
from tempfile import NamedTemporaryFile


N = 10_000
SEED = 20261120
HORIZON = 360
BASELINE_TARGETS = {90: 0.43, 180: 0.51, 360: 0.56}
NAVIGATION_EFFECTS = {"low": 0.065, "central": 0.130, "high": 0.194}
RECOVERY_START = 30
RECOVERY_MEDIAN = 45
RECOVERY_LOG_SD = 0.5
FAILURE_POINTS = ("not_reached", "referral_lost", "never_scheduled", "no_show_not_rebooked")
FAILURE_CUTOFFS = (0.30, 0.55, 0.75)
NORMAL = NormalDist()
SOFTWARE_REPORT = "reports/runs/20261120T135507Z-offline/summary.json"
LABEL = "Simulated cohort under declared assumptions. Clinical outcomes were not measured."

ANCHORS = [
    {"id": "mohl2023", "text": "Mohl et al., JAMA Network Open (2023). Among 32,769 US patients with a positive stool-based screening test, 43.3% completed colonoscopy by 90 days, 51.4% by 180 days, and 56.1% by 360 days.", "doi": "10.1001/jamanetworkopen.2022.51384"},
    {"id": "coronado2025", "text": "Coronado et al., Annals of Internal Medicine (2025). PRECISE analysed 967 patients across a 32-clinic network. Twelve-month completion was 55.1% with navigation and 42.1% with usual care, a 13.0-point difference (95% CI 6.5 to 19.4).", "doi": "10.7326/ANNALS-24-01885"},
    {"id": "corley2017", "text": "Corley et al., JAMA (2017). In the 70,124-patient positive FIT cohort, colonoscopy at 10 to 12 months was associated with higher odds of colorectal cancer (1.48) and advanced-stage disease (1.97) than colonoscopy at 8 to 30 days. The study does not establish causality.", "doi": "10.1001/jama.2017.3634"},
]

MECHANISMS = [
    {"failure_point": "not_reached", "suhail_feature": "Delivery tracking, teach-back and an owned help or consultation task.", "verified_by": "failed_understanding, unanswered_consultation"},
    {"failure_point": "referral_lost", "suhail_feature": "Reject or expire the referral while retaining ownership and opening recovery work.", "verified_by": "rejected_handoff, expired_handoff"},
    {"failure_point": "never_scheduled", "suhail_feature": "Capacity and access barriers open navigator follow-up without fabricating a booking.", "verified_by": "no_slots, access_barrier"},
    {"failure_point": "no_show_not_rebooked", "suhail_feature": "Cancellation or nonattendance opens appointment recovery work.", "verified_by": "cancelled_visit, no_show"},
]

ASSUMPTIONS = [
    "A synthetic cohort of 10,000 positive FIT episodes uses a 360-day horizon. Usual care uses rounded study targets of 43%, 51%, and 56% at days 90, 180, and 360.",
    "Usual-care cases without completion by day 360 are assigned one primary failure point with shares of 30% unreached or unclear, 25% referral failure, 20% never scheduled, and 25% attendance failure.",
    "The paired arms retain the same observed baseline completion times. Only cases without usual-care completion within the horizon are eligible for recovery.",
    "Recovery probability is the PRECISE risk difference divided by the baseline incomplete share. For a recovered case, follow-up occurs after a lognormal delay from day 30 with median 45 days and log-scale standard deviation 0.50.",
    "For this simulation, all Suhail episodes have an owned ledger entry, and remaining noncompletions are represented by documented exceptions with residual need. A pilot must distinguish unresolved open work from clinician-authorized exceptions.",
]

LIMITATIONS = [
    "The studies are from US health systems. The figures are neither UAE baselines nor measured outcomes for Suhail.",
    "The navigation trial tested human navigation. Applying its effect to a software-supported workflow assumes comparable staffing, access and capacity. The model range transfers the trial interval and omits other sources of uncertainty.",
    "Failure shares and recovery timing are assumptions. The model does not estimate effects on cancer stage, mortality, service capacity or cost.",
    "Published usual-care completion studies do not measure missing ownership. In this model, usual-care noncompletion is a proxy for cases whose tracking or documented disposition is unknown.",
    "Software checks establish workflow behavior on synthetic trajectories. They do not establish recovery probability, universal documentation or clinical effectiveness.",
]


def fit_usual_care():
    """Fit p(eventual completion), log-time location and scale to three CDF points."""
    low, high = max(BASELINE_TARGETS.values()) + 1e-9, 1.0
    log90, log180, log360 = map(math.log, BASELINE_TARGETS)
    target90, target180, target360 = BASELINE_TARGETS.values()
    for _ in range(70):
        eventual = (low + high) / 2
        z90 = NORMAL.inv_cdf(target90 / eventual)
        z180 = NORMAL.inv_cdf(target180 / eventual)
        scale = (log180 - log90) / (z180 - z90)
        location = log90 - scale * z90
        predicted = eventual * NORMAL.cdf((log360 - location) / scale)
        if predicted < target360:
            low = eventual
        else:
            high = eventual
    return eventual, location, scale


def mid_quantiles(size, rng):
    draws = [(rank + 0.5) / size for rank in range(size)]
    rng.shuffle(draws)
    return draws


def simulate(seed=SEED):
    rng = Random(seed)
    eventual, location, scale = fit_usual_care()
    baseline = []
    for draw in mid_quantiles(N, rng):
        day = math.exp(location + scale * NORMAL.inv_cdf(draw / eventual)) if draw < eventual else None
        baseline.append(day if day is not None and day <= HORIZON else None)
    incomplete = [index for index, day in enumerate(baseline) if day is None]
    recovery_probability = {name: effect / (1 - BASELINE_TARGETS[HORIZON])
                            for name, effect in NAVIGATION_EFFECTS.items()}
    failure_draws, recovery_draws, delay_draws = (mid_quantiles(len(incomplete), rng) for _ in range(3))
    failures, recovered = {}, {}
    additional = dict.fromkeys(recovery_probability, 0)
    for index, failure_draw, recovery_draw, delay_draw in zip(incomplete, failure_draws, recovery_draws, delay_draws):
        failures[index] = FAILURE_POINTS[bisect_right(FAILURE_CUTOFFS, failure_draw)]
        recovery_day = RECOVERY_START + RECOVERY_MEDIAN * math.exp(RECOVERY_LOG_SD * NORMAL.inv_cdf(delay_draw))
        if recovery_day > HORIZON:
            continue
        for name, probability in recovery_probability.items():
            if recovery_draw < probability:
                additional[name] += 1
        if recovery_draw < recovery_probability["central"]:
            recovered[index] = recovery_day
    suhail = [recovered.get(index, day) for index, day in enumerate(baseline)]
    arms = {}
    rows = []
    for arm, days in (("usual_care", baseline), ("suhail", suhail)):
        remaining = Counter()
        for index, day in enumerate(days):
            if day is None:
                remaining[failures[index]] += 1
            rows.append({"episode_id": f"synthetic-{index + 1:05}", "arm": arm,
                         "colonoscopy_day": f"{day:.6f}" if day is not None else "",
                         "baseline_failure_point": failures.get(index, ""),
                         "owned_in_model": True if arm == "suhail" else "",
                         "recovery_review_day": RECOVERY_START if arm == "suhail" and index in failures else "",
                         "disposition_360d": "completed" if day is not None else
                         "documented_exception" if arm == "suhail" else "tracking_unknown",
                         "simulated": True})
        arms[arm] = {f"completed_{horizon}d": sum(day is not None and day <= horizon for day in days) / N
                     for horizon in BASELINE_TARGETS}
        arms[arm].update({
            "median_days": round(median(day for day in days if day is not None), 2),
            "no_followup_by_300d": sum(day is None or day > 300 for day in days) / N,
            "untracked_or_undocumented_360d": len(incomplete) / N if arm == "usual_care" else 0.0,
            "drop_off": {point: remaining[point] for point in FAILURE_POINTS},
        })
    documented_exceptions = N - sum(day is not None for day in suhail)
    arms["suhail"]["documented_exception_360d"] = documented_exceptions / N
    delta = {
        "completed_360d_pp": additional["central"] * 100 / N,
        "low_pp": additional["low"] * 100 / N,
        "high_pp": additional["high"] * 100 / N,
        "additional_completed_per_10000": additional["central"],
        "low_per_10000": additional["low"],
        "high_per_10000": additional["high"],
        "documented_exceptions_per_10000": documented_exceptions,
    }
    sensitivity = [
        {"baseline_completion": baseline_rate, "scenario": scenario, "r": round(probability, 8),
         "suhail_completion": round(baseline_rate + (1 - baseline_rate) * probability, 8)}
        for baseline_rate in (0.42, 0.56, 0.80)
        for scenario, probability in recovery_probability.items()
    ]
    return {
        "schema": "suhail-impact-v1",
        "generated_at": "2026-11-20T00:00:00Z",
        "label": LABEL,
        "cohort": {"n": N, "seed": seed, "horizon_days": HORIZON, "pathway": "colorectal-fit"},
        "arms": arms,
        "delta": delta,
        "calibration": {"eventual_completion": eventual, "log_location": location, "log_scale": scale,
                        "recovery_probability": recovery_probability},
        "sensitivity": sensitivity,
        "mechanisms": MECHANISMS,
        "anchors": ANCHORS,
        "assumptions": ASSUMPTIONS,
        "limitations": LIMITATIONS,
        "software_evidence": {"report": SOFTWARE_REPORT, "journey_checks_passed": 1000, "premature_closures_refused": 500},
    }, rows


def report_markdown(data):
    arms, delta = data["arms"], data["delta"]
    baseline = arms["usual_care"]["completed_360d"]
    central = arms["suhail"]["completed_360d"]
    low, high = (baseline + delta[key] / 100 for key in ("low_pp", "high_pp"))
    text = [
        "# Simulated follow-up after a positive screening result",
        "",
        data["label"],
        "",
        f"In the simulated cohort, completion by day 360 rose from **{baseline:.0%} to {central:.0%}** "
        f"(scenario range {low:.1%}–{high:.1%}). That corresponds to "
        f"**{delta['additional_completed_per_10000']:,} additional completions per 10,000 actionable results** "
        f"(scenario range {delta['low_per_10000']:,}–{delta['high_per_10000']:,}).",
        "",
        "| Simulated measure | Usual care | Suhail-supported navigation |",
        "| --- | ---: | ---: |",
    ]
    usual, suhail = arms["usual_care"], arms["suhail"]
    for key, label in (
        ("completed_90d", "Colonoscopy by day 90"), ("completed_180d", "Colonoscopy by day 180"),
        ("completed_360d", "Colonoscopy by day 360"), ("no_followup_by_300d", "No colonoscopy by day 300"),
        ("untracked_or_undocumented_360d", "Unknown tracking or outcome at day 360 (proxy)"),
    ):
        text.append(f"| {label} | {usual[key]:.1%} | {suhail[key]:.1%} |")
    text.extend([
        f"| Median days among completers by day 360 | {usual['median_days']} | {suhail['median_days']} |",
        f"| Modelled documented exceptions at day 360 | Not modelled | {suhail['documented_exception_360d']:.1%} |",
        "",
        "The two medians summarize different groups of completers. Every paired case that completed in usual care retains its original completion date.",
        "",
        "## Remaining noncompletions at day 360",
        "",
        "| Modelled failure point | Usual care | Suhail-supported navigation |",
        "| --- | ---: | ---: |",
    ])
    for point in FAILURE_POINTS:
        text.append(f"| {point.replace('_', ' ').capitalize()} | {usual['drop_off'][point]:,} | {suhail['drop_off'][point]:,} |")
    text.extend([
        "",
        "## Sensitivity",
        "",
        "| Assumed baseline | Low projected completion | Central | High |",
        "| --- | ---: | ---: | ---: |",
    ])
    for baseline_rate in (0.42, 0.56, 0.80):
        values = [f"{item['suhail_completion']:.1%}" for item in data["sensitivity"] if item["baseline_completion"] == baseline_rate]
        text.append("| " + " | ".join([f"{baseline_rate:.0%}", *values]) + " |")
    text.extend(["", "See the [model method](../../docs/IMPACT_MODEL.md) for calibration, assumptions and cited studies.", ""])
    return "\n".join(text)


def write_artifacts(out, seed=SEED):
    data, rows = simulate(seed)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "impact-cohort.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (out / "impact-summary.md").write_text(report_markdown(data), encoding="utf-8")
    # Write the dashboard input atomically so readers never see an incomplete JSON document.
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=out, delete=False) as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    Path(stream.name).replace(out / "impact-summary.json")
    (out / "impact-summary.json").chmod(0o644)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("reports/impact"))
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    data = write_artifacts(args.out, args.seed)
    print(json.dumps({"cohort": data["cohort"], "delta": data["delta"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
