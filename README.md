# Aadhaar Biometric Authentication Failures
### A Case of Algorithmic & System Bias in National Infrastructure

An academic **simulation and bias-analysis platform**. It studies who is excluded when welfare services
(PDS rations, old-age pensions, MGNREGA wages, AePS banking) depend on fingerprint or iris authentication.

> **Simulated data for academic analysis. Not real UIDAI data.**
> The platform never collects, stores or asks for real Aadhaar numbers or biometrics. Every beneficiary is invented.
> No official UIDAI/Aadhaar logo or branding is used.

---

## 1. Project summary

The synthetic log holds **7,858 authentication attempts** made during **6,000 visits** by **2,000 beneficiaries**.
Each visit allows up to 3 attempts. If all of them fail, the service is denied for that visit.

The dashboard measures:

* how often genuine people are wrongly rejected (FRR) compared with how often impostors are wrongly accepted (FAR);
* which groups (age, occupation, area, state, service, gender) are denied most often;
* whether failures are **biometric** (worn fingerprints, poor capture) or **system** (network, device);
* whether the gaps pass standard fairness tests (disparity ratio, four-fifths rule, chi-square);
* which factors drive failure once all the others are held constant (logistic regression odds ratios).

All bias findings come from **documented mechanisms built into the simulation** (see the generator's `ASSUMPTIONS`
block). They are not measurements of the real system.

## 2. Setup

Requires Python 3.10 or newer (tested on Python 3.12).

```bash
pip install -r requirements.txt
```

```bash
python app.py
```

Then open **http://127.0.0.1:5000**.

Run the tests:

```bash
python -m pytest -q
```

## 3. Folder structure

```
Adhar_Auth_Project/
├── app.py                     Entry point: builds the app with web.create_app().
├── requirements.txt           Pinned package versions.
├── analysis/                  Pure calculations. No Flask, no HTML.
│   ├── metrics.py             FRR, FAR, denial rates, group rates, failure causes.
│   ├── fairness.py            Disparity ratio, adapted four-fifths rule, chi-square test.
│   ├── model.py               Logistic regression: failure drivers as odds ratios.
│   ├── simulator.py           One visit for a chosen profile vs a baseline (reuses the generator).
│   └── report.py              Read models: one per screen, cached per filter combination.
├── web/                       HTTP only: parse the request, call report, render.
│   ├── __init__.py            create_app(): config, security headers, errors, /healthz.
│   ├── pages.py               The four HTML screens, CSV download, redirects from old URLs.
│   └── api.py                 JSON API (/api/v1) serving the same read models.
├── data/
│   ├── aadhaar_auth_attempts.csv        The synthetic dataset.
│   └── generate_aadhaar_auth_dataset.py Seeded generator; ASSUMPTIONS defines every disparity.
├── templates/                 base, _filters, overview, exclusion, simulator, method, error.
├── static/css/style.css       The whole design system: palette tokens, layout, print.
├── tests/                     test_metrics.py (numbers), test_web.py (read models, pages, API).
└── presentation/              15-slide animated deck for the UCS421 presentation.
```

Each folder has its own `README.md` with more detail.

### Architecture

```
            ┌──────────── web/ ────────────┐
 browser ──►│ pages.py  (HTML, no JS)      │
 client  ──►│ api.py    (JSON, /api/v1)    │──► analysis/report.py ──► metrics · fairness · model
            └──────────────────────────────┘     (read models, cached)        (pure functions)
                                                          ▲
                                     data/aadhaar_auth_attempts.csv, loaded once at start-up
```

* **One source of truth.** Every chart and every API response comes from the same read-model function, so the page
  and the API cannot disagree.
* **Cached, read-only.** The CSV never changes while running, so each screen is computed once per filter combination
  (at most 140) and reused. Filter values not present in the data are discarded before they reach the cache.
* **No client-side JavaScript.** Bars, columns and the heatmap are HTML/CSS with server-computed sizes. Every view,
  including filters and the chosen comparison, is a plain shareable URL.
* **Hardened by default.** Strict Content-Security-Policy, `nosniff`, no framing, JSON errors under `/api`, and a
  `/healthz` endpoint for a load balancer.

### Running in production

```bash
pip install waitress
```

```bash
waitress-serve --port=8000 --call web:create_app
```

**Note on the generator:** the original generator script was not supplied with the dataset. The file in `data/` is a
**reconstruction** whose assumptions were calibrated (by regression and cross-tabulation) to reproduce the patterns in
the supplied CSV. The dashboard always analyses the original CSV unchanged. The reconstructed generator drives the
Simulator and the Methodology page. Re-running it with the default seed gives a statistically similar dataset
(about 7,860 attempts, FRR about 24%), not an identical one.

## 4. Screens

| Screen | URL | What it shows |
|------|-----|---------------|
| Overview | `/` | The headline gap, four key numbers, denial by age, the FRR/FAR trade-off, four tested findings |
| Who is excluded | `/exclusion?by=age_group` | Denial rate per group with the four-fifths verdict and chi-square test (age, occupation, area, service, state, gender), odds-ratio drivers, failure by capture quality, biometric vs system causes, retries, area × device heatmap |
| Simulator | `/simulator` | One visit for a chosen profile, side by side with a young office worker, plus the denial probability over 1,000 runs |
| Method & data | `/method` | How the data was generated, live assumptions, definitions, limitations, recommendations, CSV download, API |

Overview and Who is excluded share a filter bar (state, area, service); filters follow you between them. The nine
pages of the first version redirect to these four, so old links keep working.

### JSON API

| Method | Path | Returns |
|---|---|---|
| GET | `/api/v1/meta` | Filter values, dimensions, thresholds |
| GET | `/api/v1/overview?state=Bihar` | The overview read model |
| GET | `/api/v1/exclusion?by=occupation&area_type=Remote` | The exclusion read model |
| POST | `/api/v1/simulate` with `{"age": 68, "occupation": "Farmer"}` | Subject vs baseline simulation |

## 5. Metric definitions

| Metric | Formula | Population |
|---|---|---|
| **FRR** (False Rejection Rate) | rejected attempts ÷ attempts | **genuine users only** |
| **FAR** (False Acceptance Rate) | accepted attempts ÷ attempts | **impostors only** |
| Attempt failure rate | failed attempts ÷ attempts | everyone |
| **Denial rate** | visits where all attempts failed ÷ visits | one row per `session_id`; bias pages use **genuine visits** because blocking an impostor is not exclusion |
| Biometric failure | `Biometric mismatch` + `Poor quality capture` | kept separate from system failures |
| System failure | `Network timeout` + `Device error` | no match score is produced |
| **Disparity ratio** | group denial rate ÷ best group's denial rate | best group needs at least 30 visits |
| **Four-fifths rule (adapted)** | FAIL if disparity ratio > 1.25 (= 1 ÷ 0.8) | the classic rule flipped for failure rates |
| Chi-square p-value | test of independence on group × (denied, not denied) | p < 0.05 = significant |
| Odds ratio | exp(coefficient) from a logistic regression of first-attempt failure | genuine first attempts; > 1 raises the odds vs the reference group |

## 6. Screenshot list (for the report)

Use the browser's print preview (the stylesheet hides navigation and filters when printing) or a screenshot tool.

1. **Overview**: headline, key numbers and the four findings.
2. **Who is excluded, Age**: the 75+ bar in orange and the FAIL verdicts.
3. **Who is excluded, Gender**: the control check with no significant gap.
4. **Who is excluded, drivers**: the odds-ratio chart.
5. **Who is excluded, causes**: failure by capture quality, and the area × device heatmap.
6. **Simulator**: an elderly manual labourer next to the baseline.
7. **Method & data**: the assumptions table.
8. **Filtered view**: e.g. Who is excluded with *Area = Remote*.
9. **Phone layout**: any screen at phone width.

## 7. How to regenerate data with different assumptions

1. Open `data/generate_aadhaar_auth_dataset.py` and edit values in the `ASSUMPTIONS` dictionary. Examples:
   * Remove the age effect: set `"age_decline_per_year": 0.0`.
   * Give every area good devices: set each entry of `"device_mix_by_area"` to `{"High": 1.0, "Medium": 0.0, "Low": 0.0}`.
   * Make the system stricter: raise `"match_threshold"` to `0.70`.
2. Generate a new file. By default it is written next to the original, so the original is never overwritten:
   ```bash
   python data/generate_aadhaar_auth_dataset.py --output data/aadhaar_auth_attempts_regenerated.csv --seed 42
   ```
3. To analyse the new file in the dashboard, back up the original CSV and then copy the new file over
   `data/aadhaar_auth_attempts.csv`. Alternatively, change `DATA_FILE` in `app.py`. Restart `python app.py`.
4. Note: `tests/test_metrics.py` checks the original dataset's exact size (7,858 rows), so that test will fail on a
   regenerated file. This is expected.

Because the Simulator imports the same `ASSUMPTIONS`, any edit also changes the Simulator's behaviour after a restart.
