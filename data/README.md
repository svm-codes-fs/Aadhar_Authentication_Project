# data/

The synthetic dataset and the generator that defines it. **No real Aadhaar numbers, biometrics or UIDAI data are used anywhere.**

| File | What it is |
|---|---|
| `aadhaar_auth_attempts.csv` | The dataset the app analyses: 7,858 authentication attempts from 6,000 visits by 2,000 invented beneficiaries |
| `generate_aadhaar_auth_dataset.py` | Seeded generator (seed 42). Its `ASSUMPTIONS` block holds every number that creates a disparity, with a plain-English note for each |

## How an attempt is simulated

1. Capture quality (0–100) = 82 + occupation effect + device effect + environment effect − 0.85 per year of age above 55 + noise.
2. Network timeout? (1.0% on a good network, 10.7% on a poor one) → fail with no match score.
3. Device error? (0.7% High, 1.5% Medium, 3.8% Low device) → fail with no match score.
4. Match score = 0.30 + 0.0074 × quality + noise for genuine users; low for impostors.
5. Quality below 40 → *Poor quality capture*; score below 0.60 → *Biometric mismatch*; otherwise *Success*.

Up to three attempts per visit; if all fail, the visit is **service denied**. Gender is assigned but has **no effect** (a deliberate control).

## Regenerating

```bash
python data/generate_aadhaar_auth_dataset.py --output data/my_run.csv --seed 7
```

The default output name keeps the original CSV safe. The script is a **reconstruction** calibrated to the supplied CSV, so a re-run gives a statistically similar dataset, not an identical one.

## Columns (23)

`attempt_id`, `session_id` (one visit), `beneficiary_id`, `timestamp`, `state`, `area_type`, `age`, `age_group`, `gender`, `occupation`, `service_type`, `auth_method`, `device_quality`, `network`, `environment`, `biometric_quality`, `match_score` (empty when the network or device failed first), `threshold`, `attempt_no`, `is_genuine_user`, `outcome`, `failure_reason`, `service_denied`.
