# templates/

Jinja2 templates for the four screens. Charts are plain HTML elements whose widths and heights come from the server, so no JavaScript is needed in the browser.

| File | Screen |
|---|---|
| `base.html` | Shared layout: navy header, navigation, "Simulated data" tag, footer |
| `_filters.html` | State / area / service filter bar (a plain GET form, so every view is a shareable URL) |
| `overview.html` | Overview: headline gap, four key numbers, denial by age, the FRR/FAR trade-off, four tested findings |
| `exclusion.html` | Who is excluded: group tabs, four-fifths verdicts, odds-ratio drivers, capture quality, failure causes, retries, area × device heatmap |
| `simulator.html` | Simulator: profile form and two animated visits (your profile and the baseline) |
| `method.html` | Method & data: generation process, ethics and risk lens, assumptions, definitions, limitations, recommendations, CSV and API |
| `error.html` | 404 and 500 pages |
