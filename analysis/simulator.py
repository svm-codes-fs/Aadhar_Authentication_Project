"""
Simulate an authentication visit for a profile typed in by the user.

The simulator does NOT invent new rules: it calls `simulate_visit` from the
data generator, so the animated result follows exactly the same assumptions
that produced the dataset.

No real Aadhaar number or biometric is ever asked for. The user only picks
a profile (age, occupation, device...).
"""

import numpy as np

from data.generate_aadhaar_auth_dataset import ASSUMPTIONS, simulate_visit

DEFAULT_RUNS = 1000
MIN_AGE = 18
MAX_AGE = 100

# Options for each drop-down, read from the generator so they always match.
FORM_OPTIONS = {
    "occupation": list(ASSUMPTIONS["occupation_quality_effect"].keys()),
    "area_type": list(ASSUMPTIONS["device_mix_by_area"].keys()),
    "device_quality": list(ASSUMPTIONS["device_quality_effect"].keys()),
    "network": list(ASSUMPTIONS["network_timeout_probability"].keys()),
    "environment": list(ASSUMPTIONS["environment_quality_effect"].keys()),
    "auth_method": ["Fingerprint", "Iris"],
}

DEFAULT_PROFILE = {
    "age": 68,
    "occupation": "Manual labourer",
    "area_type": "Remote",
    "device_quality": "Low",
    "network": "Poor",
    "environment": "Dusty",
    "auth_method": "Fingerprint",
}

# The "Compare with" person: young office worker, best conditions.
COMPARISON_PROFILE = {
    "age": 25,
    "occupation": "Office/Skilled",
    "area_type": "Urban",
    "device_quality": "High",
    "network": "Good",
    "environment": "Normal",
    "auth_method": "Fingerprint",
}


def read_profile(form):
    """Turn submitted form values into a safe profile dict.

    Any missing or unexpected value falls back to the default, so a
    tampered form can never crash the page.
    """
    profile = dict(DEFAULT_PROFILE)
    try:
        age = int(form.get("age", DEFAULT_PROFILE["age"]))
        profile["age"] = min(MAX_AGE, max(MIN_AGE, age))
    except (TypeError, ValueError):
        profile["age"] = DEFAULT_PROFILE["age"]

    for field, allowed in FORM_OPTIONS.items():
        value = form.get(field)
        if value in allowed:
            profile[field] = value
    return profile


def run_one_visit(profile, rng):
    """Simulate one visit (up to 3 attempts) for a random person with this profile.

    A fresh person-level offset is drawn so that two people with the same
    profile can still have slightly different fingerprints.
    """
    person_offset = rng.normal(0, ASSUMPTIONS["person_noise_sd"])
    return simulate_visit(rng, profile, True, person_offset, ASSUMPTIONS)


def visit_was_denied(attempts):
    """A visit is denied when no attempt succeeded."""
    for attempt in attempts:
        if attempt["outcome"] == "Success":
            return False
    return True


def estimate_denial_probability(profile, runs=DEFAULT_RUNS, seed=2026):
    """Run many visits and return the share that ended in denial.

    WHY: one animated run can be lucky or unlucky. 1,000 runs give a stable
    estimate of how often this kind of person is turned away.
    """
    rng = np.random.default_rng(seed)
    denied = 0
    for _ in range(runs):
        if visit_was_denied(run_one_visit(profile, rng)):
            denied += 1
    return denied / runs


def simulate_profile(profile, seed=None):
    """Everything the simulator page shows for one profile."""
    rng = np.random.default_rng(seed)
    attempts = run_one_visit(profile, rng)
    denied = visit_was_denied(attempts)
    return {
        "profile": profile,
        "attempts": attempts,
        "denied": denied,
        "final_message": "Service denied" if denied else "Ration received",
        "denial_probability": estimate_denial_probability(profile),
        "threshold": ASSUMPTIONS["match_threshold"],
        "min_capture_quality": ASSUMPTIONS["min_capture_quality"],
    }
