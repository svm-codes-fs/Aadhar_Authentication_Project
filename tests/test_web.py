"""
Checks for the read models (analysis/report.py) and the HTTP layer (web/).

Run with:  python -m pytest -q
"""

import pytest

from analysis.report import Filters, Report, with_widths
from web import DEFAULT_DATA_FILE, create_app


@pytest.fixture(scope="module")
def report():
    return Report.from_csv(DEFAULT_DATA_FILE)


@pytest.fixture(scope="module")
def client(report):
    return create_app(report=report).test_client()


# --- Read models --------------------------------------------------------------
def test_unknown_filter_values_are_dropped(report):
    filters = report.parse_filters({"state": "Atlantis", "area_type": "Rural"})
    assert filters == Filters(area_type="Rural")


def test_unknown_dimension_falls_back_to_age(report):
    assert report.parse_dimension("shoe_size") == "age_group"


def test_overview_headline_is_the_age_gap(report):
    headline = report.overview(Filters())["headline"]
    assert headline["group"] == "75+"
    assert headline["reference"] == "18-30"
    assert headline["ratio"] > 10


def test_read_models_are_cached(report):
    assert report.overview(Filters()) is report.overview(Filters())


def test_exclusion_for_every_dimension(report):
    for dimension in ["age_group", "occupation", "area_type", "service_type", "state", "gender"]:
        data = report.exclusion(Filters(), dimension)
        assert data["groups"]
        assert max(row["width"] for row in data["groups"]) == 100


def test_with_widths_handles_missing_and_zero():
    rows = with_widths([{"rate": 0.2}, {"rate": None}, {"rate": 0.1}])
    assert [row["width"] for row in rows] == [100.0, 0, 50.0]
    assert with_widths([{"rate": 0}])[0]["width"] == 0


# --- Pages --------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/", "/exclusion", "/exclusion?by=gender&area_type=Remote",
                                  "/simulator", "/method", "/healthz"])
def test_pages_render(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert "Content-Security-Policy" in response.headers


def test_empty_filter_shows_empty_state(client):
    # A valid state + service combination with no rows still renders.
    response = client.get("/?state=Delhi&area_type=Remote")
    assert response.status_code == 200


def test_simulator_post(client):
    response = client.post("/simulator", data={"age": "80", "occupation": "Farmer"})
    assert response.status_code == 200
    assert b"Baseline" in response.data


def test_old_urls_redirect_with_filters(client):
    response = client.get("/fairness?state=Bihar")
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/exclusion?state=Bihar")


def test_dataset_download(client):
    response = client.get("/data/attempts.csv")
    assert response.status_code == 200
    assert response.data.startswith(b"attempt_id,")


def test_unknown_page_is_404(client):
    assert client.get("/nope").status_code == 404


# --- API ----------------------------------------------------------------------
def test_api_overview_matches_page_numbers(client, report):
    body = client.get("/api/v1/overview").get_json()
    assert body["data"]["kpis"]["total_attempts"] == 7858
    assert body["data"]["kpis"] == report.overview(Filters())["kpis"]


def test_api_exclusion_echoes_filters(client):
    body = client.get("/api/v1/exclusion?by=area_type&state=Bihar").get_json()
    assert body["filters"] == {"state": "Bihar"}
    assert body["data"]["dimension"] == "area_type"


def test_api_simulate(client):
    body = client.post("/api/v1/simulate", json={"age": 30}).get_json()
    assert 0 <= body["data"]["subject"]["denial_probability"] <= 1


def test_api_rejects_non_object_json(client):
    assert client.post("/api/v1/simulate", json=[1, 2]).status_code == 400


def test_api_unknown_route_is_json_404(client):
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found"}
