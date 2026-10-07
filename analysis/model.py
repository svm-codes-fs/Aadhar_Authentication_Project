"""
One simple logistic regression that explains WHAT drives a failed attempt.

We model: P(first attempt fails | profile) for genuine users only.
* Genuine users only, because rejecting an impostor is not a failure.
* First attempt only, so each visit is counted once and retries (which are
  only made by people who already failed) do not skew the result.

Each factor is turned into yes/no (dummy) columns compared with a
reference group, e.g. "Age 75+ vs Age 18-30". The model's coefficients are
converted to ODDS RATIOS: an odds ratio of 3 means the odds of failing are
three times higher than for the reference group, all else being equal.
"""

import math

import pandas as pd
from sklearn.linear_model import LogisticRegression

from analysis.metrics import COLUMN_LABELS, genuine_attempts

# Factor -> reference group (the "baseline" everyone is compared with).
MODEL_FACTORS = {
    "age_group": "18-30",
    "occupation": "Office/Skilled",
    "area_type": "Urban",
    "gender": "Male",
    "device_quality": "High",
    "network": "Good",
    "environment": "Normal",
    "auth_method": "Fingerprint",
}

MIN_ROWS_TO_FIT = 200   # too few rows give unstable, misleading estimates


def build_design_matrix(rows):
    """Create 0/1 columns for every non-reference group of every factor.

    WHY: logistic regression needs numbers. Leaving out the reference group
    means each coefficient reads as 'compared with the reference group'.
    """
    columns = {}
    for factor, reference in MODEL_FACTORS.items():
        for group in sorted(rows[factor].unique()):
            if group == reference:
                continue
            column_name = f"{factor}={group}"
            columns[column_name] = (rows[factor] == group).astype(int)
    return pd.DataFrame(columns, index=rows.index)


def fit_failure_model(attempts):
    """Fit the model and return a list of odds ratios, largest first.

    Returns None if there is not enough data (e.g. after heavy filtering).
    """
    first_tries = genuine_attempts(attempts)
    first_tries = first_tries[first_tries["attempt_no"] == 1]
    if len(first_tries) < MIN_ROWS_TO_FIT:
        return None

    features = build_design_matrix(first_tries)
    target = first_tries["is_failure"].astype(int)
    if target.nunique() < 2 or features.shape[1] == 0:
        return None

    # A very large C means (almost) no regularisation, so the coefficients
    # are the plain maximum-likelihood estimates we can explain in a viva.
    model = LogisticRegression(C=1e6, max_iter=5000)
    model.fit(features, target)

    results = []
    for column_name, coefficient in zip(features.columns, model.coef_[0]):
        factor, group = column_name.split("=", 1)
        results.append({
            "factor": COLUMN_LABELS.get(factor, factor),
            "group": group,
            "reference": MODEL_FACTORS[factor],
            "label": f"{group} (vs {MODEL_FACTORS[factor]})",
            "odds_ratio": math.exp(coefficient),
            "rows_in_group": int(features[column_name].sum()),
        })
    results.sort(key=lambda item: item["odds_ratio"], reverse=True)
    return {
        "odds_ratios": results,
        "rows_used": len(first_tries),
        "failure_rate": float(target.mean()),
    }
