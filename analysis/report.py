"""
Read models: one function per screen, returning plain dicts.

The HTML pages and the JSON API both call this module, so a chart and the
API response behind it can never disagree. The dataset is read-only, so the
same filters always produce the same answer: each read model is memoised per
filter combination (at most 7 states x 4 areas x 5 services = 140 entries).

Layering:
    metrics / fairness / model   pure calculations on a DataFrame
    report (this file)           shapes those results for one screen + caches
    web/                         HTTP only: parse request, call report, render
"""

import math
from dataclasses import asdict, dataclass
from functools import lru_cache

from analysis import fairness, metrics, model

# Dimensions a viewer can compare groups by, in the order the tabs appear.
DIMENSIONS = {
    "age_group": "Age",
    "occupation": "Occupation",
    "area_type": "Area",
    "service_type": "Service",
    "state": "State",
    "gender": "Gender",
}
DEFAULT_DIMENSION = "age_group"

# Finding cards on the overview, strongest mechanism first. Gender is the
# control: the generator has no gender effect, so it should show no gap.
FINDING_DIMENSIONS = ["age_group", "occupation", "area_type", "service_type"]

DRIVER_COUNT = 8            # odds ratios shown on the exclusion page
DRIVER_SCALE_MAX = 8.0      # an odds ratio of 8 fills the bar (log scale)
CACHE_SIZE = 256


@dataclass(frozen=True)
class Filters:
    """The global filters. Frozen, so it can key the cache."""

    state: str = ""
    area_type: str = ""
    service_type: str = ""

    def as_dict(self):
        return asdict(self)

    def active(self):
        """Only the filters that are set, e.g. {"state": "Bihar"}."""
        return {key: value for key, value in asdict(self).items() if value}


class Report:
    """Every number the product shows, computed from one loaded dataset."""

    def __init__(self, attempts):
        self.attempts = attempts
        self.options = metrics.filter_options(attempts)
        self.threshold = metrics.match_threshold(attempts)
        # Memoise per instance (not at module level) so tests can build
        # isolated reports and nothing leaks between them.
        self.overview = lru_cache(maxsize=CACHE_SIZE)(self._overview)
        self.exclusion = lru_cache(maxsize=CACHE_SIZE)(self._exclusion)

    @classmethod
    def from_csv(cls, path):
        return cls(metrics.load_attempts(path))

    # -- Request parsing -------------------------------------------------------
    def parse_filters(self, args):
        """Build Filters from query args, dropping any value not in the data.

        WHY: unknown values would otherwise show an empty page and, worse,
        fill the cache with arbitrary keys.
        """
        chosen = {}
        for column in metrics.FILTER_COLUMNS:
            value = args.get(column, "")
            chosen[column] = value if value in self.options[column] else ""
        return Filters(**chosen)

    @staticmethod
    def parse_dimension(value):
        return value if value in DIMENSIONS else DEFAULT_DIMENSION

    def meta(self):
        """What a client needs to build its own filter controls."""
        return {
            "filters": self.options,
            "dimensions": DIMENSIONS,
            "match_threshold": self.threshold,
            "four_fifths_limit": fairness.FOUR_FIFTHS_LIMIT,
            "significance_level": fairness.SIGNIFICANCE_LEVEL,
        }

    # -- Read models -----------------------------------------------------------
    def _rows(self, filters):
        return metrics.apply_filters(self.attempts, filters.as_dict())

    def _overview(self, filters):
        rows = self._rows(filters)
        if rows.empty:
            return None
        tables = {column: fairness.fairness_table(rows, column)
                  for column in FINDING_DIMENSIONS}
        return {
            "kpis": metrics.overview_kpis(rows),
            "headline": biggest_gap(tables["age_group"]),
            "age": with_widths(tables["age_group"]["rows"]),
            "findings": [finding(tables[column]) for column in FINDING_DIMENSIONS],
            "families": metrics.failure_family_shares(rows),
        }

    def _exclusion(self, filters, dimension):
        rows = self._rows(filters)
        if rows.empty:
            return None
        table = fairness.fairness_table(rows, dimension)
        fitted = model.fit_failure_model(rows)
        return {
            "dimension": dimension,
            "label": DIMENSIONS[dimension],
            "groups": with_widths(table["rows"]),
            "gap": biggest_gap(table),
            "p_value": table["p_value"],
            "significant": table["significant"],
            "reference": table["reference"],
            "drivers": drivers(fitted),
            "quality": with_widths(metrics.failure_by_quality_band(rows), "failure_rate"),
            "reasons": with_widths(metrics.failure_reason_breakdown(rows), "share"),
            "families": metrics.failure_family_shares(rows),
            "retries": with_widths(metrics.success_rate_by_attempt_number(rows)),
            "repeat_denied": repeat_denied(rows),
            "infrastructure": metrics.denial_heatmap(rows, "area_type", "device_quality"),
        }


# -----------------------------------------------------------------------------
# Shaping helpers (pure functions, easy to test)
# -----------------------------------------------------------------------------
def with_widths(rows, key="rate"):
    """Copy rows adding `width`: the value as a % of the largest value.

    WHY: bars are drawn in HTML/CSS on the server, so the template only
    needs a ready-made percentage, and no chart library ships to the browser.
    """
    values = [row[key] for row in rows if row.get(key) is not None]
    top = max(values, default=0)
    shaped = []
    for row in rows:
        value = row.get(key)
        width = 0 if not value or not top else value / top * 100
        shaped.append({**row, "width": round(width, 1)})
    return shaped


def biggest_gap(table):
    """The worst trusted group against the reference group, or None."""
    reference = next((row for row in table["rows"] if row["is_reference"]), None)
    rated = [row for row in table["rows"]
             if row["ratio"] is not None and not row["small_sample"]]
    if reference is None or not rated:
        return None
    worst = max(rated, key=lambda row: row["ratio"])
    if worst["group"] == reference["group"]:
        return None
    return {
        "group": worst["group"],
        "rate": worst["rate"],
        "denied": worst["denied"],
        "count": worst["count"],
        "reference": reference["group"],
        "reference_rate": reference["rate"],
        "ratio": worst["ratio"],
        # A reference denied under 1% of the time makes any ratio look huge.
        "rare_reference": reference["rate"] < 0.01,
    }


def finding(table):
    """One overview card: the biggest gap for a dimension and its test."""
    return {
        "dimension": table["column"],
        "label": DIMENSIONS.get(table["column"], table["label"]),
        "gap": biggest_gap(table),
        "significant": table["significant"],
        "p_value": table["p_value"],
        "sentence": table["sentence"],
    }


def drivers(fitted):
    """Top odds ratios above 1, with a log-scaled bar width."""
    if fitted is None:
        return None
    raising = [item for item in fitted["odds_ratios"] if item["odds_ratio"] > 1]
    shaped = []
    for item in raising[:DRIVER_COUNT]:
        width = math.log(item["odds_ratio"]) / math.log(DRIVER_SCALE_MAX) * 100
        shaped.append({**item, "width": round(min(100.0, width), 1)})
    lowering = [item for item in fitted["odds_ratios"] if item["odds_ratio"] < 1]
    return {
        "raising": shaped,
        "lowering": lowering,
        "rows_used": fitted["rows_used"],
    }


def repeat_denied(rows):
    """Beneficiaries denied on two or more visits: exclusion, not bad luck."""
    visits = metrics.genuine_visits(rows)
    if visits.empty:
        return {"people": 0, "share": None}
    denials = visits.groupby("beneficiary_id")["service_denied"].sum()
    people = int((denials >= 2).sum())
    return {"people": people, "share": metrics.safe_rate(people, len(denials))}
