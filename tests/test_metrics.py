"""
pytest checks for the key numbers.

Run with:  python -m pytest -q
"""

from pathlib import Path

import pandas as pd
import pytest

from analysis import fairness, metrics, model, simulator

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "aadhaar_auth_attempts.csv"


@pytest.fixture(scope="module")
def attempts():
    """Load the dataset once for all tests."""
    return metrics.load_attempts(DATA_FILE)


# --- Dataset shape -----------------------------------------------------------
def test_dataset_has_expected_size(attempts):
    assert len(attempts) == 7858
    assert attempts["beneficiary_id"].nunique() == 2000


def test_visit_level_has_6000_rows(attempts):
    visits = metrics.to_visits(attempts)
    assert len(visits) == 6000
    assert visits["session_id"].is_unique


def test_genuine_plus_impostor_visits_equal_all_visits(attempts):
    kpis = metrics.overview_kpis(attempts)
    assert kpis["genuine_visits"] + kpis["impostor_visits"] == kpis["total_visits"] == 6000


# --- FRR and FAR use the right population -------------------------------------
def test_frr_uses_genuine_users_only(attempts):
    genuine = attempts[attempts["is_genuine_user"]]
    expected = (genuine["outcome"] == "Failure").mean()
    assert metrics.false_rejection_rate(attempts) == pytest.approx(expected)


def test_frr_ignores_impostor_rows(attempts):
    """Adding or removing impostor rows must not change FRR."""
    genuine_only = attempts[attempts["is_genuine_user"]]
    assert metrics.false_rejection_rate(attempts) == pytest.approx(
        metrics.false_rejection_rate(genuine_only))


def test_far_uses_impostors_only(attempts):
    impostors = attempts[~attempts["is_genuine_user"]]
    expected = (impostors["outcome"] == "Success").mean()
    assert metrics.false_acceptance_rate(attempts) == pytest.approx(expected)


def test_far_ignores_genuine_rows(attempts):
    impostors_only = attempts[~attempts["is_genuine_user"]]
    assert metrics.false_acceptance_rate(attempts) == pytest.approx(
        metrics.false_acceptance_rate(impostors_only))


# --- All rates are proper proportions ----------------------------------------
def test_overview_rates_between_zero_and_one(attempts):
    kpis = metrics.overview_kpis(attempts)
    for key in ["attempt_failure_rate", "frr", "far",
                "visit_denial_rate_all", "visit_denial_rate_genuine"]:
        assert 0 <= kpis[key] <= 1, key


@pytest.mark.parametrize("column", ["age_group", "occupation", "area_type",
                                    "gender", "state", "service_type"])
def test_group_rates_between_zero_and_one(attempts, column):
    for row in metrics.denial_rate_by_group(attempts, column):
        assert 0 <= row["rate"] <= 1
    for row in metrics.frr_by_group(attempts, column):
        assert 0 <= row["rate"] <= 1


def test_group_visit_counts_add_up(attempts):
    rows = metrics.denial_rate_by_group(attempts, "age_group")
    total = sum(row["count"] for row in rows)
    assert total == len(metrics.genuine_visits(attempts))


# --- Biometric vs system failures are kept apart -----------------------------
def test_failure_families_are_separate(attempts):
    failures = attempts[attempts["is_failure"]]
    assert set(failures["failure_family"]) == {"Biometric", "System"}
    system_rows = attempts[attempts["failure_family"] == "System"]
    assert system_rows["match_score"].isna().all()


def test_denial_distribution_covers_every_beneficiary(attempts):
    rows = metrics.denials_per_beneficiary(attempts)
    assert sum(row["beneficiaries"] for row in rows) == \
        metrics.genuine_visits(attempts)["beneficiary_id"].nunique()


# --- Fairness -----------------------------------------------------------------
def test_disparity_ratio_and_four_fifths_rule():
    assert fairness.disparity_ratio(0.10, 0.05) == pytest.approx(2.0)
    assert fairness.disparity_ratio(0.10, 0) is None
    assert fairness.passes_four_fifths_rule(1.20, 0.06) is True
    assert fairness.passes_four_fifths_rule(1.30, 0.065) is False


def test_age_shows_significant_disparity(attempts):
    table = fairness.fairness_table(attempts, "age_group")
    assert table["significant"]
    assert table["reference"] == "18-30"


def test_gender_control_has_no_significant_gap(attempts):
    """The generator has no gender effect, so gender should not be significant."""
    table = fairness.fairness_table(attempts, "gender")
    assert table["p_value"] > fairness.SIGNIFICANCE_LEVEL


# --- Empty filters never crash -----------------------------------------------
def test_empty_filter_is_handled(attempts):
    empty = metrics.apply_filters(attempts, {"state": "Nowhere"})
    assert empty.empty
    assert metrics.false_rejection_rate(empty) is None
    assert metrics.visit_denial_rate(metrics.to_visits(empty)) is None
    assert metrics.denials_per_beneficiary(empty) == []
    assert model.fit_failure_model(empty) is None
    table = fairness.fairness_table(empty, "age_group")
    assert table["rows"] == [] and table["p_value"] is None


# --- Model and simulator -----------------------------------------------------
def test_model_finds_age_and_device_effects(attempts):
    result = model.fit_failure_model(attempts)
    odds = {item["label"]: item["odds_ratio"] for item in result["odds_ratios"]}
    assert odds["75+ (vs 18-30)"] > 1
    assert odds["Low (vs High)"] > 1


def test_simulator_disadvantaged_profile_is_denied_more():
    hard = simulator.estimate_denial_probability(simulator.DEFAULT_PROFILE, runs=500)
    easy = simulator.estimate_denial_probability(simulator.COMPARISON_PROFILE, runs=500)
    assert 0 <= easy < hard <= 1


def test_simulator_rejects_bad_form_values():
    profile = simulator.read_profile({"age": "abc", "occupation": "Hacker"})
    assert profile == simulator.DEFAULT_PROFILE
