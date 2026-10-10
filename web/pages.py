"""
The four screens, plus redirects so links to the old nine pages keep working.

    /           Overview          the headline finding and four key numbers
    /exclusion  Who is excluded   group gaps, fairness tests, drivers, causes
    /simulator  Simulator         one visit for a chosen profile vs a baseline
    /method     Method & data     assumptions, definitions, limits, the CSV
"""

from urllib.parse import urlencode

from flask import (Blueprint, current_app, redirect, render_template, request,
                   send_file, url_for)

from analysis import fairness, simulator
from analysis.report import DIMENSIONS
from data.generate_aadhaar_auth_dataset import ASSUMPTION_NOTES, ASSUMPTIONS

bp = Blueprint("pages", __name__)

# Old URL -> new screen. The query string (filters) is carried across.
LEGACY_ROUTES = {
    "/bias": "pages.exclusion",
    "/fairness": "pages.exclusion",
    "/quality": "pages.exclusion",
    "/system": "pages.exclusion",
    "/repeated": "pages.exclusion",
    "/methodology": "pages.method",
    "/explorer": "pages.method",
}


def report():
    return current_app.extensions["report"]


def render_screen(template, filters=None, **context):
    """Render with the shared chrome: nav, filter bar, filter-preserving links."""
    active = filters.active() if filters else {}
    return render_template(
        template,
        filters=filters,
        filter_options=report().options,
        filter_query=("?" + urlencode(active)) if active else "",
        **context,
    )


@bp.get("/")
def overview():
    filters = report().parse_filters(request.args)
    return render_screen("overview.html", filters, data=report().overview(filters))


@bp.get("/exclusion")
def exclusion():
    filters = report().parse_filters(request.args)
    dimension = report().parse_dimension(request.args.get("by"))
    return render_screen("exclusion.html", filters,
                         data=report().exclusion(filters, dimension),
                         dimensions=DIMENSIONS,
                         limit=fairness.FOUR_FIFTHS_LIMIT)


@bp.route("/simulator", methods=["GET", "POST"])
def simulate():
    profile = simulator.DEFAULT_PROFILE
    result = None
    if request.method == "POST":
        profile = simulator.read_profile(request.form)
        result = simulator.compare_with_baseline(profile)
    return render_screen("simulator.html", profile=profile, result=result,
                         options=simulator.FORM_OPTIONS,
                         baseline=simulator.COMPARISON_PROFILE)


@bp.get("/method")
def method():
    everything = report().parse_filters({})
    return render_screen("method.html",
                         kpis=report().overview(everything)["kpis"],
                         assumptions=ASSUMPTIONS, notes=ASSUMPTION_NOTES,
                         threshold=report().threshold,
                         limit=fairness.FOUR_FIFTHS_LIMIT)


@bp.get("/data/attempts.csv")
def download_dataset():
    return send_file(current_app.config["DATA_FILE"], mimetype="text/csv",
                     as_attachment=True, download_name="aadhaar_auth_attempts.csv")


def make_legacy_redirect(endpoint):
    def legacy():
        query = request.query_string.decode()
        return redirect(url_for(endpoint) + (f"?{query}" if query else ""), code=301)
    return legacy


for old_path, new_endpoint in LEGACY_ROUTES.items():
    bp.add_url_rule(old_path, f"legacy{old_path.replace('/', '_')}",
                    make_legacy_redirect(new_endpoint))
