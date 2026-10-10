"""
HTTP layer. `create_app()` wires one read-only Report into two front doors:

    pages  (web/pages.py)  server-rendered HTML, no client-side JavaScript
    api    (web/api.py)    the same read models as JSON under /api/v1

Nothing in this package calculates; it parses requests and renders results.
"""

import hashlib
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from analysis.report import Report

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_FILE = ROOT / "data" / "aadhaar_auth_attempts.csv"

# Strict by default: only our own files, plus Google Fonts for typography.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    # Bar lengths are server-computed inline widths; no inline <style> or script.
    "style-src-attr 'unsafe-inline'",
    "font-src https://fonts.gstatic.com",
    "img-src 'self' data:",
    "script-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
])


def create_app(data_file=DEFAULT_DATA_FILE, report=None):
    """Build the app. Pass `report` to inject a prebuilt one (tests)."""
    app = Flask(__name__, template_folder=str(ROOT / "templates"),
                static_folder=str(ROOT / "static"))
    app.config.update(DATA_FILE=Path(data_file))
    app.json.sort_keys = False      # keep read-model key order in API output

    # The CSV is loaded once; every request reads the same immutable report.
    app.extensions["report"] = report or Report.from_csv(data_file)

    from web import api, pages
    app.register_blueprint(pages.bp)
    app.register_blueprint(api.bp, url_prefix="/api/v1")

    # Fingerprint the stylesheet so a changed file gets a new URL and no
    # browser keeps showing a stale cached copy.
    stylesheet = ROOT / "static" / "css" / "style.css"
    app.jinja_env.globals["asset_version"] = hashlib.sha256(stylesheet.read_bytes()).hexdigest()[:10]

    register_template_filters(app)
    register_hardening(app)
    register_errors(app)

    @app.get("/healthz")
    def health():
        attempts = app.extensions["report"].attempts
        return {"status": "ok", "attempts": len(attempts)}

    return app


def register_template_filters(app):
    @app.template_filter("pct")
    def format_percent(value, digits=1):
        """A 0-1 rate as a percentage, or a dash if missing."""
        if value is None:
            return "—"
        return f"{value * 100:.{digits}f}%"

    @app.template_filter("thousands")
    def format_thousands(value):
        return f"{value:,}"

    @app.template_filter("ratio")
    def format_ratio(value):
        return "—" if value is None else f"{value:.1f}×"

    @app.template_filter("pvalue")
    def format_p_value(value):
        if value is None:
            return "not testable"
        return "p < 0.001" if value < 0.001 else f"p = {value:.3f}"


def register_hardening(app):
    @app.after_request
    def security_headers(response):
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # Static assets are versioned by content in production; pages are not cached.
        if request.endpoint != "static":
            response.headers.setdefault("Cache-Control", "no-store")
        return response


def register_errors(app):
    def wants_json():
        return request.path.startswith("/api/")

    @app.errorhandler(404)
    def not_found(_error):
        if wants_json():
            return jsonify(error="not_found"), 404
        return render_template("error.html", code=404,
                               message="That page does not exist."), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="method_not_allowed"), 405

    @app.errorhandler(500)
    def server_error(_error):
        if wants_json():
            return jsonify(error="internal_error"), 500
        return render_template("error.html", code=500,
                               message="Something went wrong on our side."), 500
