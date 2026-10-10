# tests/

46 automated checks with pytest. Run them from the project root:

```bash
python -m pytest -q
```

| File | What it checks |
|---|---|
| `test_metrics.py` | Dataset size (7,858 attempts, 2,000 people, 6,000 visits); FRR uses genuine users only and FAR impostors only; every rate is between 0 and 1; group counts add up; network and device failures have no match score; the four-fifths rule and disparity ratio on known inputs; age is significant and gender (the control) is not; the model finds age and device effects; the simulator denies a disadvantaged profile more than the baseline; bad form input falls back safely; an empty filter never crashes |
| `test_web.py` | Unknown filter values and dimensions are handled; read models are cached; every page returns 200 with a security header; the simulator form works; old URLs redirect with filters kept; the CSV downloads; unknown pages give 404; the API returns the same numbers as the pages; bad API input gives 400 |
| `conftest.py` | Makes the project root importable |
