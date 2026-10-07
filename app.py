"""
Flask web app: routes only. All calculations live in the analysis/ package.

Run:  python app.py   then open http://127.0.0.1:5000
"""

import io
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, Response, render_template, request

from analysis import fairness, metrics, model, simulator
from data.generate_aadhaar_auth_dataset import ASSUMPTION_NOTES, ASSUMPTIONS

DATA_FILE = Path(__file__).resolve().parent / "data" / "aadhaar_auth_attempts.csv"
EXPLORER_PAGE_SIZE = 25
EXPLORER_FILTERS = ["state", "area_type", "age_group", "occupation", "service_type",
                    "auth_method", "outcome", "failure_reason"]
EXPLORER_COLUMNS = ["attempt_id", "session_id", "beneficiary_id", "timestamp", "state",
                    "area_type", "age", "age_group", "gender", "occupation",
                    "service_type", "auth_method", "device_quality", "network",
                    "environment", "biometric_quality", "match_score", "threshold",
                    "attempt_no", "is_genuine_user", "outcome", "failure_reason",
                    "service_denied"]
BIAS_ATTRIBUTES = ["age_group", "occupation", "area_type", "gender", "state", "service_type"]

app = Flask(__name__)

# Load the CSV ONCE when the app starts; every page reuses it.
ATTEMPTS = metrics.load_attempts(DATA_FILE)
FILTER_OPTIONS = metrics.filter_options(ATTEMPTS)


def read_global_filters():
    """Read the state / area / service filters from the URL query string."""
    filters = {}
    for column in metrics.FILTER_COLUMNS:
        filters[column] = request.args.get(column, "")
    return filters


def filtered_attempts():
    """Return (filtered rows, chosen filters) for the analysis pages."""
    filters = read_global_filters()
    return metrics.apply_filters(ATTEMPTS, filters), filters


def render_page(template, filters=None, **context):
    """Render a template with the shared filter bar information.

    `filter_query` (e.g. "state=Bihar") is added to navigation links so the
    chosen filters follow the user from one analysis page to the next.
    """
    active_filters = {}
    if filters:
        active_filters = {column: value for column, value in filters.items() if value}
    return render_template(template, filters=filters, filter_options=FILTER_OPTIONS,
                           column_labels=metrics.COLUMN_LABELS,
                           filter_query=urlencode(active_filters), **context)


@app.route("/")
def overview():
    rows, filters = filtered_attempts()
    kpis = metrics.overview_kpis(rows) if not rows.empty else None
    return render_page("overview.html", filters, kpis=kpis)


@app.route("/bias")
def bias():
    rows, filters = filtered_attempts()
    charts = []
    if not rows.empty:
        for column in BIAS_ATTRIBUTES:
            label = metrics.COLUMN_LABELS[column]
            charts.append({
                "column": column,
                "label": label,
                "denial": metrics.group_chart(metrics.denial_rate_by_group(rows, column), column,
                                              f"Denial rate by {label.lower()}", "Visits denied"),
                "frr": metrics.group_chart(metrics.frr_by_group(rows, column), column,
                                           f"False Rejection Rate by {label.lower()}", "FRR"),
            })
    return render_page("bias.html", filters, charts=charts)


@app.route("/quality")
def quality():
    rows, filters = filtered_attempts()
    data = None
    if not rows.empty:
        data = {
            "bands": metrics.failure_by_quality_band(rows),
            "scatter": metrics.quality_score_points(rows),
            "threshold": metrics.match_threshold(rows),
            "methods": metrics.method_comparison(rows),
        }
    return render_page("quality.html", filters, data=data)


@app.route("/system")
def system():
    rows, filters = filtered_attempts()
    data = None
    if not rows.empty:
        data = {
            "reasons": metrics.failure_reason_breakdown(rows),
            "family_shares": metrics.failure_family_shares(rows),
            "device": metrics.failure_family_by_group(rows, "device_quality"),
            "network": metrics.failure_family_by_group(rows, "network"),
            "environment": metrics.failure_family_by_group(rows, "environment"),
            "heatmap": metrics.denial_heatmap(rows, "area_type", "device_quality"),
        }
    return render_page("system.html", filters, data=data)


@app.route("/repeated")
def repeated():
    rows, filters = filtered_attempts()
    data = None
    if not rows.empty:
        data = {
            "by_attempt": metrics.success_rate_by_attempt_number(rows),
            "denial_counts": metrics.denials_per_beneficiary(rows),
            "most_affected": metrics.most_affected_beneficiaries(rows),
        }
    return render_page("repeated.html", filters, data=data)


@app.route("/fairness")
def fairness_page():
    rows, filters = filtered_attempts()
    tables = fairness.all_fairness_tables(rows) if not rows.empty else []
    model_result = model.fit_failure_model(rows) if not rows.empty else None
    return render_page("fairness.html", filters, tables=tables, model_result=model_result,
                       limit=fairness.FOUR_FIFTHS_LIMIT,
                       alpha=fairness.SIGNIFICANCE_LEVEL,
                       min_group=fairness.MIN_GROUP_SIZE)


@app.route("/simulator", methods=["GET", "POST"])
def simulator_page():
    profile = simulator.DEFAULT_PROFILE
    result = None
    comparison = None
    if request.method == "POST":
        profile = simulator.read_profile(request.form)
        result = simulator.simulate_profile(profile)
        if request.form.get("compare") == "yes":
            comparison = simulator.simulate_profile(simulator.COMPARISON_PROFILE)
    return render_page("simulator.html", profile=profile, options=simulator.FORM_OPTIONS,
                       result=result, comparison=comparison,
                       runs=simulator.DEFAULT_RUNS,
                       comparison_profile=simulator.COMPARISON_PROFILE)


@app.route("/methodology")
def methodology():
    kpis = metrics.overview_kpis(ATTEMPTS)
    return render_page("methodology.html", assumptions=ASSUMPTIONS, notes=ASSUMPTION_NOTES,
                       kpis=kpis, limit=fairness.FOUR_FIFTHS_LIMIT,
                       threshold=metrics.match_threshold(ATTEMPTS))


def explorer_rows():
    """Apply the Data Explorer's own (wider) set of filters."""
    chosen = {}
    for column in EXPLORER_FILTERS:
        chosen[column] = request.args.get(column, "")
    return metrics.apply_filters(ATTEMPTS, chosen), chosen


@app.route("/explorer")
def explorer():
    rows, chosen = explorer_rows()
    try:
        page_number = int(request.args.get("page", 1))
    except ValueError:
        page_number = 1
    page_rows, page_number, total_pages = metrics.paginate(rows, page_number, EXPLORER_PAGE_SIZE)
    options = {column: sorted(ATTEMPTS[column].unique().tolist()) for column in EXPLORER_FILTERS}
    # Empty match scores (network/device failures) become None so the table shows a dash.
    visible = page_rows[EXPLORER_COLUMNS].astype(object)
    visible = visible.where(visible.notna(), None)
    return render_page("explorer.html", rows=visible.to_dict(orient="records"),
                       columns=EXPLORER_COLUMNS, chosen=chosen, options=options,
                       page=page_number, total_pages=total_pages, total_rows=len(rows))


@app.route("/explorer/download")
def explorer_download():
    rows, _chosen = explorer_rows()
    buffer = io.StringIO()
    rows[EXPLORER_COLUMNS].to_csv(buffer, index=False)
    return Response(buffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=filtered_attempts.csv"})


@app.template_filter("pct")
def format_percent(value):
    """Show a 0-1 rate as a percentage with 1 decimal, or a dash if missing."""
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


@app.template_filter("thousands")
def format_thousands(value):
    """Show a whole number with thousands separators (7858 -> 7,858)."""
    return f"{value:,}"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
