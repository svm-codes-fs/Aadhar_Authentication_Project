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
├── app.py                     Flask routes only (thin). Loads the CSV once at start-up.
├── requirements.txt           Pinned package versions.
├── analysis/
│   ├── metrics.py             Every calculation: FRR, FAR, denial rates, group rates, heatmap, etc.
│   ├── fairness.py            Disparity ratio, adapted four-fifths rule, chi-square test, plain-English sentences.
│   ├── simulator.py           Simulates one visit for a user-entered profile (reuses the generator's logic).
│   └── model.py               One logistic regression explaining failure drivers as odds ratios.
├── data/
│   ├── aadhaar_auth_attempts.csv        The synthetic dataset analysed by the dashboard.
│   └── generate_aadhaar_auth_dataset.py Seeded generator; the ASSUMPTIONS block defines every disparity.
├── templates/
│   ├── base.html              Layout, navigation bar, "simulated data" banner.
│   ├── _filters.html          Global filter bar (state, area type, service).
│   └── overview / bias / quality / system / repeated / fairness / simulator / methodology / explorer .html
├── static/
│   ├── css/style.css          Plain CSS: palette, cards, responsive and print styles.
│   └── js/charts.js           Reusable Chart.js helpers (Chart.js is loaded from a CDN).
├── tests/
│   └── test_metrics.py        pytest checks of the key numbers.
├── README.md
└── PRESENTATION_GUIDE.md      Demo script, key findings, viva questions.
```

**Note on the generator:** the original generator script was not supplied with the dataset. The file in `data/` is a
**reconstruction** whose assumptions were calibrated (by regression and cross-tabulation) to reproduce the patterns in
the supplied CSV. The dashboard always analyses the original CSV unchanged. The reconstructed generator drives the
Simulator and the Methodology page. Re-running it with the default seed gives a statistically similar dataset
(about 7,860 attempts, FRR about 24%), not an identical one.

## 4. Pages

| # | Page | What it shows |
|---|------|---------------|
| 1 | Overview | Plain-language problem statement and KPI cards (attempts, failure rate, FRR, FAR, visits denied, people denied at least once) |
| 2 | Who Gets Excluded? | Denial rate and FRR by age group, occupation, area type, gender (control group), state and service, with best and worst groups highlighted |
| 3 | Biometric Quality | Failure rate by quality band, quality-vs-score scatter with the 0.60 threshold, fingerprint vs iris |
| 4 | System Failures | Failure reasons (biometric vs system), failures by device, network and environment, area × device heatmap |
| 5 | Repeated Failures | Success rate by attempt number, denials per beneficiary, 10 most-affected profiles |
| 6 | Fairness Metrics | Disparity ratio, four-fifths flag and chi-square p-value per attribute, plain-English sentences, odds-ratio chart |
| 7 | Simulator | Enter a profile, watch up to 3 animated attempts, see the outcome and the denial probability from 1,000 runs, and compare with a young office worker |
| 8 | Methodology | Generation process, live assumptions table, metric definitions, limitations, recommendations |
| 9 | Data Explorer | Filterable, paginated raw table with a "Download filtered CSV" button |

Pages 1 to 6 share a global filter bar (state, area type, service). Chosen filters follow you between those pages.

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

Use the browser's print preview (the stylesheet has a print mode that hides navigation and filters) or a screenshot tool.

1. **Overview**: banner and KPI cards.
2. **Who Gets Excluded? (Age group)**: denial-rate and FRR charts showing the 75+ group in orange.
3. **Who Gets Excluded? (Gender)**: the control-group note with near-identical bars.
4. **Biometric Quality**: failure rate by quality band.
5. **Biometric Quality**: quality vs match-score scatter with the threshold line.
6. **System Failures**: failure-reason chart and the area × device heatmap.
7. **Repeated Failures**: success rate by attempt number and the most-affected table.
8. **Fairness Metrics**: age-group table (FAIL flags) and the odds-ratio chart.
9. **Simulator**: compare view (elderly manual labourer vs young office worker).
10. **Methodology**: assumptions table.
11. **Filtered view**: e.g. Fairness Metrics with *Area type = Remote*, to show the filters working.
12. **Phone layout**: any page at phone width, to show the responsive design.

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
