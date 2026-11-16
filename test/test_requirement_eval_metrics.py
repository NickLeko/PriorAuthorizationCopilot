"""Metric arithmetic for the requirement-level evaluation. No extractor is involved."""

from evaluation.metrics import ScoredItem, apply_control, by_requirement, confusion_matrix, error_class, ratio, summarize


def item(expected, predicted, acceptable=None, key="k", evidence=False, overlap=None):
    return ScoredItem("d", "c", key, "provisional", expected, tuple(acceptable or [expected]), predicted, evidence, overlap)


def test_zero_denominator_is_not_measured_rather_than_perfect_or_zero():
    assert ratio(0, 0) == {"numerator": 0, "denominator": 0, "value": None}
    assert ratio(1, 4)["value"] == 0.25


def test_false_met_and_missed_met_use_separate_explicit_denominators():
    items = [
        item("MET", "MET"),
        item("MET", "NOT_DOCUMENTED"),
        item("MET", "NEEDS_REVIEW"),
        item("NOT_DOCUMENTED", "MET"),
        item("NOT_DOCUMENTED", "NOT_DOCUMENTED"),
        item("NOT_MET", "NOT_MET"),
    ]
    summary = summarize(items)
    assert (summary["false_met"]["numerator"], summary["false_met"]["denominator"]) == (1, 3)
    assert (summary["missed_met"]["numerator"], summary["missed_met"]["denominator"]) == (2, 3)
    assert (summary["met_precision"]["numerator"], summary["met_precision"]["denominator"]) == (1, 2)
    assert (summary["met_recall"]["numerator"], summary["met_recall"]["denominator"]) == (1, 3)
    assert (summary["over_abstention"]["numerator"], summary["over_abstention"]["denominator"]) == (2, 4)
    assert (summary["abstention_rate"]["numerator"], summary["abstention_rate"]["denominator"]) == (3, 6)
    assert (summary["review_rate"]["numerator"], summary["decided_coverage"]["numerator"]) == (1, 3)
    assert summary["error_classes"] == {"FALSE_MET": 1, "MISSED_MET": 2}
    assert all("denominator_meaning" in summary[name] for name in ("false_met", "missed_met", "met_precision", "met_recall"))


def test_acceptable_states_never_excuse_an_unsupported_met():
    conservative = item("NOT_DOCUMENTED", "NEEDS_REVIEW", ["NOT_DOCUMENTED", "NEEDS_REVIEW"])
    asserted = item("NEEDS_REVIEW", "MET", ["NEEDS_REVIEW", "NOT_DOCUMENTED"])
    defensible_met = item("NEEDS_REVIEW", "MET", ["NEEDS_REVIEW", "MET"])
    assert error_class(conservative) is None
    assert error_class(asserted) == "FALSE_MET"
    assert error_class(defensible_met) is None
    summary = summarize([conservative, asserted, defensible_met])
    assert (summary["false_met"]["numerator"], summary["false_met"]["denominator"]) == (1, 2)
    assert summary["exact_agreement"]["numerator"] == 0
    assert summary["acceptable_agreement"]["numerator"] == 2


def test_error_classes_cover_every_wrong_direction():
    assert error_class(item("NOT_MET", "MET")) == "FALSE_MET"
    assert error_class(item("MET", "NOT_MET")) == "MISSED_MET"
    assert error_class(item("NOT_DOCUMENTED", "NOT_MET")) == "FALSE_NOT_MET"
    assert error_class(item("NOT_MET", "NOT_DOCUMENTED")) == "MISSED_NOT_MET"
    assert error_class(item("NEEDS_REVIEW", "NOT_DOCUMENTED")) == "WRONG_ABSTENTION_TYPE"


def test_confusion_matrix_counts_every_item_once():
    items = [item("MET", "MET"), item("MET", "NOT_DOCUMENTED"), item("NEEDS_REVIEW", "MET")]
    matrix = confusion_matrix(items)
    assert matrix["MET"] == {"MET": 1, "NOT_MET": 0, "NOT_DOCUMENTED": 1, "NEEDS_REVIEW": 0}
    assert sum(sum(row.values()) for row in matrix.values()) == len(items)


def test_always_abstaining_predictor_has_no_false_met_and_is_still_flagged():
    items = [item("MET", "MET"), item("MET", "MET"), item("NOT_DOCUMENTED", "MET"), item("NOT_MET", "NOT_MET")]
    for control in ("ALWAYS_NOT_DOCUMENTED", "ALWAYS_NEEDS_REVIEW"):
        summary = summarize(apply_control(items, control))
        assert summary["false_met"]["numerator"] == 0
        assert summary["met_recall"] == {**ratio(0, 2), "denominator_meaning": summary["met_recall"]["denominator_meaning"]}
        assert summary["decided_coverage"]["numerator"] == 0
        assert summary["abstention_rate"]["value"] == 1.0
        assert {"ZERO_MET_RECALL", "NEVER_DECIDES"} <= set(summary["utility_flags"])
        assert summary["meets_minimum_utility"] is False


def test_always_met_predictor_has_full_recall_and_is_still_flagged():
    items = [item("MET", "NOT_DOCUMENTED"), item("NOT_DOCUMENTED", "NOT_DOCUMENTED"), item("NEEDS_REVIEW", "NEEDS_REVIEW")]
    summary = summarize(apply_control(items, "ALWAYS_MET"))
    assert summary["met_recall"]["value"] == 1.0
    assert (summary["false_met"]["numerator"], summary["false_met"]["denominator"]) == (2, 2)
    assert summary["utility_flags"] == ["ASSERTS_EVERY_UNSUPPORTED_FACT"]
    assert summary["meets_minimum_utility"] is False


def test_unmeasured_quantities_are_flagged_instead_of_scored():
    only_negatives = summarize([item("NOT_DOCUMENTED", "NOT_DOCUMENTED")])
    assert only_negatives["met_recall"]["value"] is None
    assert "MET_RECALL_NOT_MEASURED" in only_negatives["utility_flags"]
    only_positives = summarize([item("MET", "MET")])
    assert only_positives["false_met"]["value"] is None
    assert "FALSE_MET_NOT_MEASURED" in only_positives["utility_flags"]
    empty = summarize([])
    assert empty["utility_flags"] == ["NO_SCORED_LABELS"]
    assert empty["meets_minimum_utility"] is False
    assert empty["exact_agreement"]["value"] is None


def test_evidence_metrics_count_only_eligible_predictions():
    items = [
        item("MET", "MET", evidence=True, overlap=True),
        item("MET", "MET", evidence=True, overlap=False),
        item("NOT_MET", "MET", evidence=False),
        item("NOT_DOCUMENTED", "NOT_DOCUMENTED"),
    ]
    summary = summarize(items)
    assert (summary["evidence_coverage"]["numerator"], summary["evidence_coverage"]["denominator"]) == (2, 3)
    assert (summary["evidence_overlap"]["numerator"], summary["evidence_overlap"]["denominator"]) == (1, 2)


def test_per_requirement_breakdown_partitions_the_items():
    items = [item("MET", "MET", key="a"), item("MET", "NOT_DOCUMENTED", key="a"), item("NOT_DOCUMENTED", "MET", key="b")]
    breakdown = by_requirement(items)
    assert set(breakdown) == {"a", "b"}
    assert sum(entry["scored_labels"] for entry in breakdown.values()) == len(items)
    assert breakdown["a"]["missed_met"]["numerator"] == 1
    assert breakdown["b"]["false_met"]["numerator"] == 1
