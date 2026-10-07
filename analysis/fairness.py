"""
Fairness checks: disparity ratio, adapted four-fifths rule, chi-square test.

The classic four-fifths (80%) rule says a group is treated unfairly if its
SUCCESS rate is below 80% of the best group's success rate. We study
FAILURE (denial) rates instead, so the rule is flipped: a group is flagged
if its denial rate is more than 1 / 0.8 = 1.25 times the best group's rate.
"""

from scipy.stats import chi2_contingency

from analysis.metrics import COLUMN_LABELS, denial_rate_by_group, genuine_visits

FOUR_FIFTHS_LIMIT = 1.25        # 1 / 0.8, the four-fifths rule for failure rates
SIGNIFICANCE_LEVEL = 0.05       # usual cut-off for "statistically significant"
MIN_GROUP_SIZE = 30             # smaller groups cannot be the "best" reference

# Attributes analysed on the Fairness page.
FAIRNESS_ATTRIBUTES = ["age_group", "occupation", "area_type", "gender",
                       "state", "service_type"]


def disparity_ratio(group_rate, best_rate):
    """How many times more often this group is denied than the best group.

    Returns None when the best group has a zero rate, because dividing by
    zero would give a meaningless 'infinite' ratio.
    """
    if group_rate is None or best_rate is None or best_rate == 0:
        return None
    return group_rate / best_rate


def passes_four_fifths_rule(ratio, group_rate):
    """True if the group is within 1.25x of the best group's denial rate.

    WHY: this is the standard first screen for disparate impact used in
    fairness auditing. When the ratio cannot be computed (best rate is 0)
    the group passes only if it was never denied either.
    """
    if ratio is None:
        return group_rate == 0
    return ratio <= FOUR_FIFTHS_LIMIT


def chi_square_p_value(visits, column):
    """Chi-square test: is denial independent of this attribute?

    Builds a table of (group x denied / not denied) and returns the p-value.
    A small p-value (< 0.05) means the differences between groups are
    unlikely to be due to chance alone. Returns None when the test cannot run
    (fewer than two groups, or nobody / everybody denied).
    """
    if visits.empty:
        return None
    table = []
    for group in visits[column].unique():
        group_visits = visits[visits[column] == group]
        denied = int(group_visits["service_denied"].sum())
        table.append([denied, len(group_visits) - denied])

    total_denied = sum(row[0] for row in table)
    total_not_denied = sum(row[1] for row in table)
    if len(table) < 2 or total_denied == 0 or total_not_denied == 0:
        return None
    _statistic, p_value, _dof, _expected = chi2_contingency(table)
    return float(p_value)


def pick_reference_group(rows):
    """The group with the lowest denial rate among groups big enough to trust."""
    large_groups = [row for row in rows
                    if row["count"] >= MIN_GROUP_SIZE and row["rate"] is not None]
    if not large_groups:
        return None
    return min(large_groups, key=lambda row: row["rate"])


def fairness_table(attempts, column):
    """Build the full fairness table for one attribute.

    Each row: group, visits, denial rate, disparity ratio vs best group,
    and whether it passes the adapted four-fifths rule.
    """
    rows = denial_rate_by_group(attempts, column)
    reference = pick_reference_group(rows)
    best_rate = reference["rate"] if reference else None

    table_rows = []
    for row in rows:
        ratio = disparity_ratio(row["rate"], best_rate)
        table_rows.append({
            "group": row["group"],
            "count": row["count"],
            "denied": row["denied"],
            "rate": row["rate"],
            "ratio": ratio,
            "passes": passes_four_fifths_rule(ratio, row["rate"]),
            "is_reference": reference is not None and row["group"] == reference["group"],
            "small_sample": row["count"] < MIN_GROUP_SIZE,
        })

    p_value = chi_square_p_value(genuine_visits(attempts), column)
    return {
        "column": column,
        "label": COLUMN_LABELS.get(column, column),
        "rows": table_rows,
        "reference": reference["group"] if reference else None,
        "p_value": p_value,
        "significant": p_value is not None and p_value < SIGNIFICANCE_LEVEL,
        "sentence": plain_english_sentence(column, table_rows, reference, p_value),
    }


def describe_group(column, group):
    """Phrase a group name naturally for a sentence."""
    if column == "age_group":
        return f"people aged {group}"
    if column == "area_type":
        return f"people in {group.lower()} areas"
    if column == "state":
        return f"people in {group}"
    if column == "gender":
        return f"{group.lower()} beneficiaries"
    if column == "service_type":
        return f"people collecting {group}"
    return f"people in the '{group}' group"


def plain_english_sentence(column, table_rows, reference, p_value):
    """One sentence summarising the biggest gap for a non-technical audience."""
    if reference is None:
        return "No data for this filter."
    if reference["rate"] == 0:
        return zero_reference_sentence(column, table_rows, reference)
    rated = [row for row in table_rows
             if row["ratio"] is not None and not row["small_sample"]]
    if not rated:
        return "Not enough data to compare groups for this filter."
    worst = max(rated, key=lambda row: row["ratio"])
    if worst["group"] == reference["group"]:
        return "All groups have the same denial rate under this filter."

    subject = describe_group(column, worst["group"])
    sentence = (f"{subject[0].upper()}{subject[1:]} are {worst['ratio']:.1f} times more "
                f"likely to be denied than {describe_group(column, reference['group'])} "
                f"({worst['rate'] * 100:.1f}% vs {reference['rate'] * 100:.1f}% of visits).")
    if p_value is None or p_value >= SIGNIFICANCE_LEVEL:
        sentence += " This gap is NOT statistically significant, so it may be chance."
    if reference["rate"] < 0.01:
        sentence += " (The best group is denied very rarely, which makes ratios large.)"
    return sentence


def zero_reference_sentence(column, table_rows, reference):
    """Sentence for when the best group was never denied (ratio undefined)."""
    trusted = [row for row in table_rows if not row["small_sample"]]
    worst = max(trusted, key=lambda row: row["rate"])
    if worst["rate"] == 0:
        return "No group was denied under this filter."
    subject = describe_group(column, worst["group"])
    return (f"{subject[0].upper()}{subject[1:]} were denied on {worst['rate'] * 100:.1f}% "
            f"of visits, while {describe_group(column, reference['group'])} were never denied "
            f"(so a ratio cannot be calculated).")


def all_fairness_tables(attempts):
    """Fairness tables for every attribute on the Fairness page."""
    tables = []
    for column in FAIRNESS_ATTRIBUTES:
        tables.append(fairness_table(attempts, column))
    return tables
