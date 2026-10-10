# web/

The HTTP layer. It parses requests, calls `analysis/report.py` and renders the result; it never calculates anything itself.

| File | What it does |
|---|---|
| `__init__.py` | `create_app()`: loads the dataset once, registers the two blueprints, adds security headers, error pages and the `/healthz` check, and fingerprints the stylesheet URL so browsers never show a stale copy |
| `pages.py` | The four HTML screens, the CSV download, and 301 redirects from the first version's nine URLs |
| `api.py` | The JSON API under `/api/v1`, serving the same read models as the pages |

## Routes

| Method | Path | Returns |
|---|---|---|
| GET | `/` | Overview |
| GET | `/exclusion?by=age_group` | Who is excluded (also `occupation`, `area_type`, `service_type`, `state`, `gender`) |
| GET, POST | `/simulator` | Simulator form and result |
| GET | `/method` | Method, ethics lens, assumptions and limits |
| GET | `/data/attempts.csv` | The dataset as a download |
| GET | `/api/v1/meta` | Filter values, dimensions, thresholds |
| GET | `/api/v1/overview` | Overview read model |
| GET | `/api/v1/exclusion?by=…` | Exclusion read model |
| POST | `/api/v1/simulate` | Simulation for a JSON profile, e.g. `{"age": 68, "occupation": "Farmer"}` |
| GET | `/healthz` | `{"status": "ok"}` for a load balancer |

Filters (`state`, `area_type`, `service_type`) work as query parameters on every analysis route; values not in the data are ignored.

## Security headers

Every response carries a strict Content-Security-Policy (only this site's own scripts and styles, plus Google Fonts), `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy` and `frame-ancestors 'none'`.
