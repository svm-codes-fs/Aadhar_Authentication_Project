"""
Seeded generator for the SYNTHETIC Aadhaar authentication log.

IMPORTANT
---------
* This is a simulation. No real Aadhaar numbers, biometrics or UIDAI data are
  used or produced. Every person in the output is invented.
* This file is a RECONSTRUCTION. The original generator script was not
  available, so the ASSUMPTIONS below were calibrated (by regression and
  cross-tabulation) to reproduce the patterns found in
  data/aadhaar_auth_attempts.csv. Re-running it gives a statistically similar
  dataset, not a row-for-row copy of the original CSV.
* Every disparity in the data comes from a number in the ASSUMPTIONS block.
  If a group is excluded more often, you can point to the line that causes it.

Usage
-----
    python data/generate_aadhaar_auth_dataset.py
    python data/generate_aadhaar_auth_dataset.py --output data/my_run.csv --seed 7
"""

import argparse
import datetime

import numpy as np
import pandas as pd


# =============================================================================
# ASSUMPTIONS  (edit these to explore "what if" scenarios)
# =============================================================================
ASSUMPTIONS = {
    # --- Size of the simulation ---------------------------------------------
    "seed": 42,
    "n_beneficiaries": 2000,
    "visits_per_beneficiary": 3,
    "max_attempts_per_visit": 3,

    # --- Matching rules -----------------------------------------------------
    "match_threshold": 0.60,          # score needed to accept a fingerprint/iris
    "min_capture_quality": 40,        # below this the capture is "poor quality"

    # --- Fingerprint quality model (0-100) ----------------------------------
    # quality = base + occupation + device + environment - age decline + noise
    "fingerprint_base_quality": 82.0,
    "occupation_quality_effect": {
        "Office/Skilled": 0.0,
        "Student": 1.0,
        "Retired/Not working": -2.5,
        "Domestic worker": -12.0,
        "Farmer": -15.0,
        "Manual labourer": -17.0,
        "Construction worker": -19.5,
    },
    "device_quality_effect": {"High": 0.0, "Medium": -5.7, "Low": -13.5},
    "environment_quality_effect": {
        "Normal": 0.0,
        "Hot & dry": -5.8,
        "Dusty": -6.9,
        "Humid/wet hands": -8.2,
    },
    "age_decline_starts_at": 55,       # fingerprints wear out after this age
    "age_decline_per_year": 0.85,      # quality points lost per year after 55
    "person_noise_sd": 4.0,            # stable person-to-person differences
    "visit_noise_sd": 4.0,             # differs from one visit to the next
    "attempt_noise_sd": 6.0,           # differs between retries in one visit
    "retry_quality_gain": 4.0,         # re-placing / wiping the finger helps a little

    # --- Iris quality model (not affected by work, age or dust) --------------
    "iris_quality_mean": 85.0,
    "iris_quality_sd": 6.0,
    "iris_share_on_high_device": 0.066,  # iris scanners exist only on High devices

    # --- Match score model ---------------------------------------------------
    # genuine match score = intercept + slope * quality + noise
    "match_intercept": 0.30,
    "match_slope_per_quality_point": 0.0074,
    "match_noise_sd": 0.078,
    "impostor_visit_share": 0.02,
    "impostor_quality_mean": 60.0,
    "impostor_quality_sd": 16.0,
    "impostor_match_mean": 0.36,
    "impostor_match_sd": 0.08,

    # --- Infrastructure failures (checked before the biometric match) -------
    "network_timeout_probability": {"Good": 0.010, "Poor": 0.107},
    "device_error_probability": {"High": 0.007, "Medium": 0.015, "Low": 0.038},

    # --- Who has which infrastructure --------------------------------------
    "device_mix_by_area": {
        "Urban": {"High": 0.45, "Medium": 0.43, "Low": 0.12},
        "Rural": {"High": 0.22, "Medium": 0.43, "Low": 0.35},
        "Remote": {"High": 0.09, "Medium": 0.34, "Low": 0.57},
    },
    "poor_network_share_by_area": {"Urban": 0.11, "Rural": 0.37, "Remote": 0.67},
    "environment_mix": {
        "Normal": 0.54, "Hot & dry": 0.20, "Dusty": 0.15, "Humid/wet hands": 0.11,
    },

    # --- Population mix -----------------------------------------------------
    "area_mix_by_state": {
        "Andhra Pradesh": {"Urban": 0.34, "Rural": 0.48, "Remote": 0.18},
        "Bihar": {"Urban": 0.16, "Rural": 0.66, "Remote": 0.18},
        "Delhi": {"Urban": 0.95, "Rural": 0.04, "Remote": 0.01},
        "Jharkhand": {"Urban": 0.19, "Rural": 0.62, "Remote": 0.19},
        "Maharashtra": {"Urban": 0.52, "Rural": 0.38, "Remote": 0.10},
        "Rajasthan": {"Urban": 0.24, "Rural": 0.57, "Remote": 0.19},
    },
    "age_group_mix": {
        "18-30": 0.251, "31-45": 0.289, "46-60": 0.289, "61-75": 0.134, "75+": 0.037,
    },
    "age_group_range": {
        "18-30": (18, 30), "31-45": (31, 45), "46-60": (46, 60),
        "61-75": (61, 75), "75+": (76, 90),
    },
    "occupation_mix_by_age_group": {
        "18-30": {"Student": 0.28, "Farmer": 0.18, "Manual labourer": 0.17,
                  "Office/Skilled": 0.14, "Domestic worker": 0.12,
                  "Construction worker": 0.11},
        "31-45": {"Manual labourer": 0.28, "Farmer": 0.23, "Office/Skilled": 0.17,
                  "Construction worker": 0.18, "Domestic worker": 0.14},
        "46-60": {"Manual labourer": 0.26, "Office/Skilled": 0.24, "Farmer": 0.19,
                  "Domestic worker": 0.17, "Construction worker": 0.14},
        "61-75": {"Retired/Not working": 0.37, "Farmer": 0.27,
                  "Manual labourer": 0.22, "Office/Skilled": 0.05,
                  "Construction worker": 0.05, "Domestic worker": 0.04},
        "75+": {"Retired/Not working": 0.49, "Farmer": 0.32, "Manual labourer": 0.19},
    },
    "service_mix_by_age_group": {
        "18-30": {"PDS ration": 0.46, "MGNREGA wages": 0.31, "AePS banking": 0.23},
        "31-45": {"PDS ration": 0.46, "MGNREGA wages": 0.29, "AePS banking": 0.25},
        "46-60": {"PDS ration": 0.45, "MGNREGA wages": 0.31, "AePS banking": 0.22,
                  "Old-age pension": 0.02},
        "61-75": {"Old-age pension": 0.58, "PDS ration": 0.21, "MGNREGA wages": 0.11,
                  "AePS banking": 0.10},
        "75+": {"Old-age pension": 0.70, "PDS ration": 0.13, "AePS banking": 0.11,
                "MGNREGA wages": 0.06},
    },
    "female_share": 0.49,              # gender has NO effect on quality (control)
}

# Plain-English notes shown on the Methodology page next to each assumption.
ASSUMPTION_NOTES = {
    "match_threshold": "Minimum match score needed to authenticate.",
    "min_capture_quality": "Captures below this quality are rejected as 'Poor quality capture'.",
    "fingerprint_base_quality": "Average fingerprint quality for a young office worker on a High device in normal conditions.",
    "occupation_quality_effect": "Manual work wears down fingerprint ridges, lowering quality.",
    "device_quality_effect": "Cheaper or older scanners capture worse images.",
    "environment_quality_effect": "Dust, heat and wet hands degrade the capture.",
    "age_decline_starts_at": "Age after which fingerprint quality starts to fall.",
    "age_decline_per_year": "Quality points lost for every year above that age.",
    "iris_quality_mean": "Iris scans are not affected by manual work, dust or age in this model.",
    "iris_share_on_high_device": "Share of visits on High-quality devices that use iris instead of fingerprint.",
    "match_slope_per_quality_point": "Higher capture quality gives a higher match score for genuine users.",
    "retry_quality_gain": "Each retry gains a little quality because the person wipes or re-places the finger.",
    "impostor_visit_share": "Share of visits made by someone pretending to be the beneficiary.",
    "network_timeout_probability": "Chance that an attempt times out, by network quality.",
    "device_error_probability": "Chance that the scanner itself fails, by device quality.",
    "device_mix_by_area": "Remote and rural areas get lower-quality devices more often.",
    "poor_network_share_by_area": "Remote and rural areas have poor connectivity more often.",
    "female_share": "Gender is assigned but has NO effect on any outcome (a control group).",
}

# =============================================================================
# Helper functions
# =============================================================================
def pick_from_mix(rng, mix):
    """Pick one key from a {option: probability} dictionary.

    WHY: the population and infrastructure are described as probability
    tables in ASSUMPTIONS; this turns a table into one random choice.
    """
    options = list(mix.keys())
    probabilities = np.array(list(mix.values()), dtype=float)
    probabilities = probabilities / probabilities.sum()   # tolerate rounding
    return options[rng.choice(len(options), p=probabilities)]


def expected_fingerprint_quality(age, occupation, device_quality, environment,
                                 assumptions=ASSUMPTIONS):
    """Return the average fingerprint quality for a profile (before noise).

    WHY: this single formula is where age, occupation, device and environment
    bias enters the system. It is the heart of the simulation.
    """
    quality = assumptions["fingerprint_base_quality"]
    quality += assumptions["occupation_quality_effect"][occupation]
    quality += assumptions["device_quality_effect"][device_quality]
    quality += assumptions["environment_quality_effect"][environment]
    years_of_decline = max(0, age - assumptions["age_decline_starts_at"])
    quality -= years_of_decline * assumptions["age_decline_per_year"]
    return quality


def clip_quality(value):
    """Keep a quality value inside the valid 0-100 range."""
    return float(min(100.0, max(0.0, value)))


def simulate_attempt(rng, profile, visit_quality_offset, is_genuine,
                     attempt_no=1, assumptions=ASSUMPTIONS):
    """Simulate ONE authentication attempt and return its result as a dict.

    The order of checks mirrors a real point-of-sale device:
      1. Does the network time out?
      2. Does the scanner fail?
      3. Is the captured image good enough?
      4. Does the match score clear the threshold?

    WHY: keeping infrastructure failures (1, 2) separate from biometric
    failures (3, 4) lets the analysis show which kind of failure hurts whom.
    """
    # Step 0: capture quality for this attempt.
    if not is_genuine:
        quality = rng.normal(assumptions["impostor_quality_mean"],
                             assumptions["impostor_quality_sd"])
        quality = max(20.0, quality)
    elif profile["auth_method"] == "Iris":
        quality = rng.normal(assumptions["iris_quality_mean"],
                             assumptions["iris_quality_sd"])
    else:
        quality = expected_fingerprint_quality(
            profile["age"], profile["occupation"],
            profile["device_quality"], profile["environment"], assumptions)
        quality += visit_quality_offset
        quality += assumptions["retry_quality_gain"] * (attempt_no - 1)
        quality += rng.normal(0, assumptions["attempt_noise_sd"])
    quality = round(clip_quality(quality), 1)

    threshold = assumptions["match_threshold"]
    result = {"biometric_quality": quality, "match_score": None,
              "threshold": threshold}

    # Step 1 and 2: infrastructure failures (no match score is produced).
    timeout_chance = assumptions["network_timeout_probability"][profile["network"]]
    if rng.random() < timeout_chance:
        result.update(outcome="Failure", failure_reason="Network timeout")
        return result
    device_chance = assumptions["device_error_probability"][profile["device_quality"]]
    if rng.random() < device_chance:
        result.update(outcome="Failure", failure_reason="Device error")
        return result

    # Step 3 and 4: biometric comparison.
    if is_genuine:
        score = (assumptions["match_intercept"]
                 + assumptions["match_slope_per_quality_point"] * quality
                 + rng.normal(0, assumptions["match_noise_sd"]))
    else:
        score = rng.normal(assumptions["impostor_match_mean"],
                           assumptions["impostor_match_sd"])
    score = round(float(min(1.0, max(0.0, score))), 3)
    result["match_score"] = score

    if quality < assumptions["min_capture_quality"]:
        result.update(outcome="Failure", failure_reason="Poor quality capture")
    elif score < threshold:
        result.update(outcome="Failure", failure_reason="Biometric mismatch")
    else:
        result.update(outcome="Success", failure_reason="No failure")
    return result


def simulate_visit(rng, profile, is_genuine=True, person_quality_offset=0.0,
                   assumptions=ASSUMPTIONS):
    """Simulate one visit: up to max_attempts tries, stopping at first success.

    Returns a list of attempt dicts. The visit is 'service denied' when every
    attempt failed.

    WHY: a person is excluded only when ALL retries fail, so denial must be
    measured per visit, not per attempt.
    """
    visit_offset = person_quality_offset + rng.normal(0, assumptions["visit_noise_sd"])
    attempts = []
    for attempt_no in range(1, assumptions["max_attempts_per_visit"] + 1):
        attempt = simulate_attempt(rng, profile, visit_offset, is_genuine,
                                   attempt_no, assumptions)
        attempt["attempt_no"] = attempt_no
        attempts.append(attempt)
        if attempt["outcome"] == "Success":
            break
    return attempts


def make_beneficiary(rng, number, assumptions=ASSUMPTIONS):
    """Create one invented beneficiary with fixed demographic attributes."""
    state = pick_from_mix(rng, {s: 1 for s in assumptions["area_mix_by_state"]})
    area_type = pick_from_mix(rng, assumptions["area_mix_by_state"][state])
    age_group = pick_from_mix(rng, assumptions["age_group_mix"])
    low_age, high_age = assumptions["age_group_range"][age_group]
    female = rng.random() < assumptions["female_share"]
    return {
        "beneficiary_id": f"B{number:05d}",
        "state": state,
        "area_type": area_type,
        "age": int(rng.integers(low_age, high_age + 1)),
        "age_group": age_group,
        "gender": "Female" if female else "Male",
        "occupation": pick_from_mix(rng, assumptions["occupation_mix_by_age_group"][age_group]),
        "service_type": pick_from_mix(rng, assumptions["service_mix_by_age_group"][age_group]),
        "person_quality_offset": rng.normal(0, assumptions["person_noise_sd"]),
    }


def make_visit_conditions(rng, area_type, assumptions=ASSUMPTIONS):
    """Draw the device, network, environment and method for one visit."""
    device = pick_from_mix(rng, assumptions["device_mix_by_area"][area_type])
    poor_share = assumptions["poor_network_share_by_area"][area_type]
    network = "Poor" if rng.random() < poor_share else "Good"
    environment = pick_from_mix(rng, assumptions["environment_mix"])
    method = "Fingerprint"
    if device == "High" and rng.random() < assumptions["iris_share_on_high_device"]:
        method = "Iris"
    return {"device_quality": device, "network": network,
            "environment": environment, "auth_method": method}


def random_visit_time(rng):
    """Random working-hours timestamp between 1 Jan and 31 Mar 2026."""
    start = datetime.datetime(2026, 1, 1, 9, 0)
    day = int(rng.integers(0, 89))
    minute = int(rng.integers(0, 9 * 60))
    return start + datetime.timedelta(days=day, minutes=minute)


def generate_dataset(assumptions=ASSUMPTIONS):
    """Build the full attempt-level log as a pandas DataFrame."""
    rng = np.random.default_rng(assumptions["seed"])
    rows = []
    attempt_counter = 0
    for number in range(1, assumptions["n_beneficiaries"] + 1):
        person = make_beneficiary(rng, number, assumptions)
        for visit_no in range(1, assumptions["visits_per_beneficiary"] + 1):
            conditions = make_visit_conditions(rng, person["area_type"], assumptions)
            profile = {**person, **conditions}
            is_genuine = rng.random() >= assumptions["impostor_visit_share"]
            attempts = simulate_visit(rng, profile, is_genuine,
                                      person["person_quality_offset"], assumptions)
            denied = all(a["outcome"] == "Failure" for a in attempts)
            visit_time = random_visit_time(rng)
            for attempt in attempts:
                attempt_counter += 1
                timestamp = visit_time + datetime.timedelta(minutes=attempt["attempt_no"] - 1)
                rows.append({
                    "attempt_id": f"A{attempt_counter:06d}",
                    "session_id": f"S{number:05d}-{visit_no}",
                    "beneficiary_id": person["beneficiary_id"],
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "state": person["state"],
                    "area_type": person["area_type"],
                    "age": person["age"],
                    "age_group": person["age_group"],
                    "gender": person["gender"],
                    "occupation": person["occupation"],
                    "service_type": person["service_type"],
                    "auth_method": profile["auth_method"],
                    "device_quality": profile["device_quality"],
                    "network": profile["network"],
                    "environment": profile["environment"],
                    "biometric_quality": attempt["biometric_quality"],
                    "match_score": attempt["match_score"],
                    "threshold": attempt["threshold"],
                    "attempt_no": attempt["attempt_no"],
                    "is_genuine_user": is_genuine,
                    "outcome": attempt["outcome"],
                    "failure_reason": attempt["failure_reason"],
                    "service_denied": denied,
                })
    return pd.DataFrame(rows)


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Generate the synthetic Aadhaar auth log.")
    parser.add_argument("--output", default="data/aadhaar_auth_attempts_regenerated.csv",
                        help="Where to write the CSV (default keeps the original file safe).")
    parser.add_argument("--seed", type=int, default=ASSUMPTIONS["seed"])
    args = parser.parse_args()

    settings = dict(ASSUMPTIONS)
    settings["seed"] = args.seed
    dataset = generate_dataset(settings)
    dataset.to_csv(args.output, index=False)
    print(f"Wrote {len(dataset):,} attempts for "
          f"{dataset['beneficiary_id'].nunique():,} beneficiaries to {args.output}")


if __name__ == "__main__":
    main()
