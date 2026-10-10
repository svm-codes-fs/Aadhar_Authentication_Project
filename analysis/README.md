# analysis/

All the calculations, as pure Python functions. Nothing here knows about Flask or HTML, so every number can be tested on its own.

| File | What it does |
|---|---|
| `metrics.py` | Loads the CSV once and computes FRR, FAR, attempt failure rate, visit denial rate, denial by group, failure by capture quality, biometric vs system failures, the area × device heatmap and success by attempt number |
| `fairness.py` | Fairness tests per attribute: reference group (lowest denial, at least 30 visits), disparity ratio, adapted four-fifths rule (fail above 1.25×) and chi-square test; writes a plain-English summary sentence |
| `model.py` | Logistic regression (scikit-learn) on genuine first attempts; returns odds ratios for each factor against its reference group |
| `simulator.py` | Simulates one visit for a chosen profile using the generator's own rules, plus a 1,000-run denial estimate and a comparison with a baseline person |
| `report.py` | Read models: one function per screen that shapes the results above into plain dictionaries, cached per filter combination; used by both the HTML pages and the JSON API |

## Rules the code follows

- FRR uses **genuine users only**; FAR uses **impostors only**.
- Denial is measured **per visit** (one row per `session_id`), on **genuine visits only**: blocking an impostor is not exclusion.
- Biometric failures (mismatch, poor capture) are kept separate from system failures (network timeout, device error).

## Example

```python
from analysis.report import Report, Filters

report = Report.from_csv("data/aadhaar_auth_attempts.csv")
print(report.overview(Filters())["kpis"]["frr"])                      # 0.243
print(report.exclusion(Filters(state="Bihar"), "age_group")["gap"])
```
