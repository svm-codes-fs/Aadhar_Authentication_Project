"""
Every calculation used by the dashboard.

Rules followed throughout (they come from the project brief):
* FRR (False Rejection Rate) is computed on GENUINE users only.
* FAR (False Acceptance Rate) is computed on IMPOSTORS only.
* Biometric failures (mismatch, poor capture) are kept separate from
  system failures (network timeout, device error).
* Visit-level numbers use ONE row per session_id.
* "Denial rate" for bias analysis is measured on genuine visits only:
  blocking an impostor is the system working correctly, not exclusion.

Every function returns plain Python lists/dicts so templates and Chart.js
can use the results directly.
"""

import math

import pandas as pd

# Failure reasons grouped into the two families we compare.
BIOMETRIC_REASONS = ["Biometric mismatch", "Poor quality capture"]
SYSTEM_REASONS = ["Network timeout", "Device error"]

# Quality bands used on the "Biometric Quality vs Failure" page.
QUALITY_BAND_EDGES = [0, 20, 40, 60, 80, 100]
QUALITY_BAND_LABELS = ["0-20", "20-40", "40-60", "60-80", "80-100"]

# Natural display order for categories (instead of alphabetical).
CATEGORY_ORDER = {
    "age_group": ["18-30", "31-45", "46-60", "61-75", "75+"],
    "area_type": ["Urban", "Rural", "Remote"],
    "device_quality": ["High", "Medium", "Low"],
    "network": ["Good", "Poor"],
    "environment": ["Normal", "Hot & dry", "Dusty", "Humid/wet hands"],
    "auth_method": ["Fingerprint", "Iris"],
    "quality_band": QUALITY_BAND_LABELS,
}

# Friendly names for columns, used in chart titles and sentences.
COLUMN_LABELS = {
    "age_group": "Age group",
    "occupation": "Occupation",
    "area_type": "Area type",
    "gender": "Gender",
    "state": "State",
    "service_type": "Service",
    "device_quality": "Device quality",
    "network": "Network",
    "environment": "Environment",
    "auth_method": "Authentication method",
}

# Global filters offered on the analysis pages.
FILTER_COLUMNS = ["state", "area_type", "service_type"]


# -----------------------------------------------------------------------------
# Loading and preparing data
# -----------------------------------------------------------------------------
def load_attempts(csv_path):
    """Load the attempt-level CSV and add helper columns.

    WHY: we load once at start-up and add three columns that make later
    calculations readable: is_failure, failure_family and quality_band.
    """
    attempts = pd.read_csv(csv_path)
    attempts["is_genuine_user"] = attempts["is_genuine_user"].astype(bool)
    attempts["service_denied"] = attempts["service_denied"].astype(bool)
    attempts["is_failure"] = attempts["outcome"] == "Failure"
    attempts["failure_family"] = attempts["failure_reason"].apply(classify_failure_reason)
    attempts["quality_band"] = pd.cut(
        attempts["biometric_quality"],
        bins=QUALITY_BAND_EDGES,
        labels=QUALITY_BAND_LABELS,
        include_lowest=True,
    ).astype(str)
    return attempts


def classify_failure_reason(reason):
    """Map a failure reason to 'Biometric', 'System' or 'None'.

    WHY: a biometric failure blames the person's body; a system failure
    blames the infrastructure. Policy fixes differ for each.
    """
    if reason in BIOMETRIC_REASONS:
        return "Biometric"
    if reason in SYSTEM_REASONS:
        return "System"
    return "None"


def apply_filters(attempts, filters):
    """Return only the rows matching the chosen filters.

    `filters` is a dict like {"state": "Bihar", "area_type": ""}; an empty
    value means "all". WHY: lets the audience zoom in on one state or service.
    """
    filtered = attempts
    for column, value in filters.items():
        if value:
            filtered = filtered[filtered[column] == value]
    return filtered


def filter_options(attempts):
    """List the choices available in each global filter drop-down."""
    options = {}
    for column in FILTER_COLUMNS:
        options[column] = sorted(attempts[column].unique().tolist())
    return options


def genuine_attempts(attempts):
    """Attempts made by the real beneficiary (used for FRR)."""
    return attempts[attempts["is_genuine_user"]]


def impostor_attempts(attempts):
    """Attempts made by someone else (used for FAR)."""
    return attempts[~attempts["is_genuine_user"]]


def to_visits(attempts):
    """Collapse attempts to ONE row per visit (session_id).

    WHY: a person is only denied a ration if every attempt in the visit
    fails. Counting attempts would over-weight people who retried.
    The profile columns are identical on every row of a visit, so we keep
    the first row and add the number of attempts made.
    """
    if attempts.empty:
        return attempts.copy()
    first_rows = attempts.sort_values("attempt_no").drop_duplicates("session_id").copy()
    attempt_counts = attempts.groupby("session_id")["attempt_no"].max()
    first_rows["attempts_used"] = first_rows["session_id"].map(attempt_counts)
    return first_rows


def genuine_visits(attempts):
    """Visits by genuine beneficiaries (the population that can be excluded)."""
    return to_visits(genuine_attempts(attempts))


# -----------------------------------------------------------------------------
# Basic rates
# -----------------------------------------------------------------------------
def safe_rate(numerator, denominator):
    """Divide safely: return None instead of crashing when there is no data."""
    if denominator == 0:
        return None
    return numerator / denominator


def attempt_failure_rate(attempts):
    """Share of ALL attempts that failed (genuine and impostor together)."""
    return safe_rate(int(attempts["is_failure"].sum()), len(attempts))


def false_rejection_rate(attempts):
    """FRR: share of GENUINE users' attempts that were rejected.

    WHY: this is the core harm. A genuine person was told 'you are not you'.
    Impostor rows are removed first, otherwise correct rejections would
    inflate the figure.
    """
    genuine = genuine_attempts(attempts)
    return safe_rate(int(genuine["is_failure"].sum()), len(genuine))


def false_acceptance_rate(attempts):
    """FAR: share of IMPOSTOR attempts that were wrongly accepted.

    WHY: shows the security side of the trade-off. A low FAR with a high
    FRR means the system is strict, and genuine people pay the price.
    """
    impostors = impostor_attempts(attempts)
    successes = int((impostors["outcome"] == "Success").sum())
    return safe_rate(successes, len(impostors))


def visit_denial_rate(visits):
    """Share of visits where every attempt failed (service denied)."""
    return safe_rate(int(visits["service_denied"].sum()), len(visits))


def biometric_failure_rate(attempts):
    """Share of attempts that failed for a biometric reason."""
    biometric = attempts["failure_family"] == "Biometric"
    return safe_rate(int(biometric.sum()), len(attempts))


def system_failure_rate(attempts):
    """Share of attempts that failed for a network or device reason."""
    system = attempts["failure_family"] == "System"
    return safe_rate(int(system.sum()), len(attempts))


def beneficiaries_denied_at_least_once(attempts):
    """Number of genuine beneficiaries denied service on at least one visit."""
    visits = genuine_visits(attempts)
    denied = visits[visits["service_denied"]]
    return int(denied["beneficiary_id"].nunique())


# -----------------------------------------------------------------------------
# Overview page
# -----------------------------------------------------------------------------
def overview_kpis(attempts):
    """All numbers shown on the KPI cards of the Overview page."""
    all_visits = to_visits(attempts)
    real_visits = genuine_visits(attempts)
    return {
        "total_attempts": len(attempts),
        "total_visits": len(all_visits),
        "total_beneficiaries": int(attempts["beneficiary_id"].nunique()),
        "attempt_failure_rate": attempt_failure_rate(attempts),
        "frr": false_rejection_rate(attempts),
        "far": false_acceptance_rate(attempts),
        "visit_denial_rate_all": visit_denial_rate(all_visits),
        "visit_denial_rate_genuine": visit_denial_rate(real_visits),
        "genuine_visits": len(real_visits),
        "impostor_visits": len(all_visits) - len(real_visits),
        "beneficiaries_denied": beneficiaries_denied_at_least_once(attempts),
        "impostor_attempts": len(impostor_attempts(attempts)),
    }


# -----------------------------------------------------------------------------
# Group comparisons (bias dashboard)
# -----------------------------------------------------------------------------
def ordered_groups(column, values):
    """Sort group names in their natural order when one is defined."""
    present = list(values)
    if column in CATEGORY_ORDER:
        preferred = CATEGORY_ORDER[column]
        known = [group for group in preferred if group in present]
        unknown = sorted(group for group in present if group not in preferred)
        return known + unknown
    return sorted(present)


def denial_rate_by_group(attempts, column):
    """Genuine-visit denial rate for every group in `column`.

    Returns a list of {"group", "count", "denied", "rate"} in display order.
    """
    visits = genuine_visits(attempts)
    rows = []
    for group in ordered_groups(column, visits[column].unique()):
        group_visits = visits[visits[column] == group]
        denied = int(group_visits["service_denied"].sum())
        rows.append({
            "group": group,
            "count": len(group_visits),
            "denied": denied,
            "rate": safe_rate(denied, len(group_visits)),
        })
    return rows


def frr_by_group(attempts, column):
    """False Rejection Rate (genuine attempts only) for every group."""
    genuine = genuine_attempts(attempts)
    rows = []
    for group in ordered_groups(column, genuine[column].unique()):
        group_attempts = genuine[genuine[column] == group]
        failures = int(group_attempts["is_failure"].sum())
        rows.append({
            "group": group,
            "count": len(group_attempts),
            "failures": failures,
            "rate": safe_rate(failures, len(group_attempts)),
        })
    return rows


def best_and_worst(rows):
    """Return (best_group, worst_group) by lowest / highest rate.

    WHY: highlighting the extremes makes the gap visible at a glance.
    """
    rated = [row for row in rows if row["rate"] is not None]
    if not rated:
        return None, None
    best = min(rated, key=lambda row: row["rate"])
    worst = max(rated, key=lambda row: row["rate"])
    return best["group"], worst["group"]


def group_chart(rows, column, title, metric_name):
    """Package one group comparison for Chart.js, with best/worst marked."""
    best, worst = best_and_worst(rows)
    rate_of = {row["group"]: row["rate"] for row in rows}
    return {
        "best_rate": rate_of.get(best),
        "worst_rate": rate_of.get(worst),
        "column": column,
        "title": title,
        "metric": metric_name,
        "labels": [row["group"] for row in rows],
        "values": [row["rate"] for row in rows],
        "counts": [row["count"] for row in rows],
        "best": best,
        "worst": worst,
    }


# -----------------------------------------------------------------------------
# Biometric quality page
# -----------------------------------------------------------------------------
def failure_by_quality_band(attempts):
    """Biometric and system failure rates for each quality band (genuine)."""
    genuine = genuine_attempts(attempts)
    rows = []
    for band in QUALITY_BAND_LABELS:
        band_attempts = genuine[genuine["quality_band"] == band]
        rows.append({
            "band": band,
            "count": len(band_attempts),
            "biometric_rate": biometric_failure_rate(band_attempts) if len(band_attempts) else None,
            "system_rate": system_failure_rate(band_attempts) if len(band_attempts) else None,
            "failure_rate": safe_rate(int(band_attempts["is_failure"].sum()), len(band_attempts)),
        })
    return rows


def quality_score_points(attempts):
    """Points for the quality-vs-match-score scatter plot.

    Rows without a match score (network/device failures) are skipped,
    because no comparison happened. Genuine and impostor points are kept
    apart so the audience can see the two clouds either side of 0.60.
    """
    scored = attempts.dropna(subset=["match_score"])
    genuine = scored[scored["is_genuine_user"]]
    impostor = scored[~scored["is_genuine_user"]]
    return {
        "genuine": points_from_frame(genuine),
        "impostor": points_from_frame(impostor),
    }


def points_from_frame(frame):
    """Turn a frame into a list of {x: quality, y: score} dicts for Chart.js."""
    points = []
    for quality, score in zip(frame["biometric_quality"], frame["match_score"]):
        points.append({"x": float(quality), "y": float(score)})
    return points


def match_threshold(attempts):
    """The threshold used in the data (0.60), read rather than hard-coded."""
    if attempts.empty:
        return None
    return float(attempts["threshold"].iloc[0])


def method_comparison(attempts):
    """Fingerprint vs iris: attempts, FRR, mean quality, visit denial rate."""
    visits = genuine_visits(attempts)
    genuine = genuine_attempts(attempts)
    rows = []
    for method in ordered_groups("auth_method", genuine["auth_method"].unique()):
        method_attempts = genuine[genuine["auth_method"] == method]
        method_visits = visits[visits["auth_method"] == method]
        rows.append({
            "method": method,
            "attempts": len(method_attempts),
            "visits": len(method_visits),
            "frr": safe_rate(int(method_attempts["is_failure"].sum()), len(method_attempts)),
            "mean_quality": float(method_attempts["biometric_quality"].mean()),
            "denial_rate": visit_denial_rate(method_visits),
        })
    return rows


# -----------------------------------------------------------------------------
# System & infrastructure page
# -----------------------------------------------------------------------------
def failure_reason_breakdown(attempts):
    """Count of failed attempts by reason, tagged biometric or system."""
    failures = attempts[attempts["is_failure"]]
    total_failures = len(failures)
    rows = []
    for reason in BIOMETRIC_REASONS + SYSTEM_REASONS:
        count = int((failures["failure_reason"] == reason).sum())
        rows.append({
            "reason": reason,
            "family": classify_failure_reason(reason),
            "count": count,
            "share": safe_rate(count, total_failures),
        })
    return rows


def failure_family_shares(attempts):
    """Share of failed attempts that were biometric vs system."""
    failures = attempts[attempts["is_failure"]]
    biometric = int((failures["failure_family"] == "Biometric").sum())
    system = int((failures["failure_family"] == "System").sum())
    return {
        "biometric": safe_rate(biometric, len(failures)),
        "system": safe_rate(system, len(failures)),
    }


def failure_family_by_group(attempts, column):
    """Biometric vs system failure rate for each group (genuine attempts).

    WHY: shows whether a group fails because of their fingerprints or
    because of the device and network they were given.
    """
    genuine = genuine_attempts(attempts)
    rows = []
    for group in ordered_groups(column, genuine[column].unique()):
        group_attempts = genuine[genuine[column] == group]
        rows.append({
            "group": group,
            "count": len(group_attempts),
            "biometric_rate": biometric_failure_rate(group_attempts),
            "system_rate": system_failure_rate(group_attempts),
        })
    return rows


def denial_heatmap(attempts, row_column="area_type", column_column="device_quality"):
    """Genuine-visit denial rate for every row x column combination.

    Returns {"rows": [...], "columns": [...], "cells": [[{rate, count}]]}.
    """
    visits = genuine_visits(attempts)
    row_groups = ordered_groups(row_column, visits[row_column].unique())
    column_groups = ordered_groups(column_column, visits[column_column].unique())
    cells = []
    for row_group in row_groups:
        cell_row = []
        for column_group in column_groups:
            mask = (visits[row_column] == row_group) & (visits[column_column] == column_group)
            cell_visits = visits[mask]
            cell_row.append({
                "rate": visit_denial_rate(cell_visits),
                "count": len(cell_visits),
            })
        cells.append(cell_row)
    return {"rows": row_groups, "columns": column_groups, "cells": cells}


# -----------------------------------------------------------------------------
# Repeated failures page
# -----------------------------------------------------------------------------
def success_rate_by_attempt_number(attempts):
    """Success rate at attempt 1, 2 and 3 for genuine users.

    WHY: if retries rarely help, telling people to 'try again' is not a fix.
    """
    genuine = genuine_attempts(attempts)
    rows = []
    for attempt_no in sorted(genuine["attempt_no"].unique()):
        at_this_try = genuine[genuine["attempt_no"] == attempt_no]
        successes = int((at_this_try["outcome"] == "Success").sum())
        rows.append({
            "attempt_no": int(attempt_no),
            "count": len(at_this_try),
            "rate": safe_rate(successes, len(at_this_try)),
        })
    return rows


def denials_per_beneficiary(attempts):
    """How many beneficiaries were denied 0, 1, 2 or 3 times.

    WHY: separates bad luck (denied once) from systematic exclusion
    (denied on every visit).
    """
    visits = genuine_visits(attempts)
    if visits.empty:
        return []
    denials = visits.groupby("beneficiary_id")["service_denied"].sum()
    most_visits = int(visits.groupby("beneficiary_id").size().max())
    rows = []
    for times in range(0, most_visits + 1):
        people = int((denials == times).sum())
        rows.append({
            "times_denied": times,
            "beneficiaries": people,
            "share": safe_rate(people, len(denials)),
        })
    return rows


def most_affected_beneficiaries(attempts, limit=10):
    """The beneficiaries with the most denied visits, then most failed attempts."""
    genuine = genuine_attempts(attempts)
    if genuine.empty:
        return []
    visits = to_visits(genuine)
    denied_visits = visits.groupby("beneficiary_id")["service_denied"].sum()
    failed_attempts = genuine.groupby("beneficiary_id")["is_failure"].sum()
    profile = visits.drop_duplicates("beneficiary_id").set_index("beneficiary_id")

    summary = profile[["age", "age_group", "occupation", "area_type", "state",
                       "service_type", "gender"]].copy()
    summary["denied_visits"] = denied_visits
    summary["failed_attempts"] = failed_attempts
    summary["visits"] = visits.groupby("beneficiary_id").size()
    summary = summary.sort_values(["denied_visits", "failed_attempts", "age"],
                                  ascending=[False, False, False])
    summary = summary.head(limit).reset_index()
    return summary.to_dict(orient="records")


# -----------------------------------------------------------------------------
# Data explorer
# -----------------------------------------------------------------------------
def paginate(frame, page, page_size):
    """Return one page of rows plus the total number of pages."""
    total_pages = max(1, math.ceil(len(frame) / page_size))
    page = min(max(1, page), total_pages)
    start = (page - 1) * page_size
    return frame.iloc[start:start + page_size], page, total_pages
