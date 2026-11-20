from evals.impact import BASELINE_TARGETS, N, simulate, write_artifacts


def test_impact_outputs_are_byte_identical(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    write_artifacts(first)
    write_artifacts(second)
    for name in ("impact-summary.json", "impact-cohort.csv", "impact-summary.md"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_baseline_calibration():
    summary, _ = simulate()
    baseline = summary["arms"]["usual_care"]
    for day, target in BASELINE_TARGETS.items():
        assert abs(baseline[f"completed_{day}d"] - target) <= 0.005


def test_paired_recovery_preserves_every_baseline_completion():
    summary, rows = simulate()
    assert len(rows) == 2 * N
    gained = 0
    for baseline, suhail in zip(rows[:N], rows[N:]):
        assert baseline["arm"] == "usual_care" and suhail["arm"] == "suhail"
        assert baseline["episode_id"] == suhail["episode_id"]
        if baseline["colonoscopy_day"]:
            assert baseline["colonoscopy_day"] == suhail["colonoscopy_day"]
        elif suhail["colonoscopy_day"]:
            gained += 1
    assert gained == summary["delta"]["additional_completed_per_10000"]
    assert sum(summary["arms"]["suhail"]["drop_off"].values()) == N - 5600 - gained
