"""
JSON API, version 1. Same read models as the HTML screens.

    GET  /api/v1/meta                      filter values, dimensions, constants
    GET  /api/v1/overview?state=…          headline numbers
    GET  /api/v1/exclusion?by=age_group&…  group gaps, drivers, failure causes
    POST /api/v1/simulate                  {"age": 68, "occupation": …}
"""

from flask import Blueprint, current_app, jsonify, request

from analysis import simulator

bp = Blueprint("api", __name__)


def report():
    return current_app.extensions["report"]


def respond(payload, filters=None):
    if payload is None:
        return jsonify(error="no_data", filters=filters.active() if filters else {}), 404
    body = {"data": payload}
    if filters is not None:
        body["filters"] = filters.active()
    return jsonify(body)


@bp.get("/meta")
def meta():
    return respond(report().meta())


@bp.get("/overview")
def overview():
    filters = report().parse_filters(request.args)
    return respond(report().overview(filters), filters)


@bp.get("/exclusion")
def exclusion():
    filters = report().parse_filters(request.args)
    dimension = report().parse_dimension(request.args.get("by"))
    return respond(report().exclusion(filters, dimension), filters)


@bp.post("/simulate")
def simulate():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify(error="expected_json_object"), 400
    profile = simulator.read_profile(body)
    return respond(simulator.compare_with_baseline(profile))
