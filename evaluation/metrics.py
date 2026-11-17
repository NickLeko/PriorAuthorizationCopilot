"""Pure requirement-level metrics. No extraction, no I/O.

Every rate is returned as ``{"numerator", "denominator", "value"}``. ``value`` is
``None`` when the denominator is zero: an empty denominator is "not measured",
never a perfect or a zero score.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .schema import STATES

ABSTAIN_STATES = ("NOT_DOCUMENTED", "NEEDS_REVIEW")
DECIDED_STATES = ("MET", "NOT_MET")
# Predicted states for which the service is expected to cite the note.
CITED_STATES = ("MET", "NOT_MET", "NEEDS_REVIEW")
CONTROLS = ("ALWAYS_NOT_DOCUMENTED", "ALWAYS_NEEDS_REVIEW", "ALWAYS_MET")


@dataclass(frozen=True)
class ScoredItem:
    """One scored (case, requirement) pair. Only verified/provisional labels become items."""

    dataset_id: str
    case_id: str
    requirement_key: str
    tier: str
    expected: str
    acceptable: tuple[str, ...]
    predicted: str
    has_evidence: bool = False
    # None when not applicable (no expected quote, or nothing was cited).
    evidence_overlaps_expected: Optional[bool] = None


def ratio(numerator: int, denominator: int) -> Dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": round(numerator / denominator, 4) if denominator else None,
    }


def error_class(item: ScoredItem) -> Optional[str]:
    """Classify a prediction outside the acceptable set; None when acceptable."""
    if item.predicted in item.acceptable:
        return None
    if item.predicted == "MET":
        return "FALSE_MET"
    if item.expected == "MET":
        return "MISSED_MET"
    if item.predicted == "NOT_MET":
        return "FALSE_NOT_MET"
    if item.expected == "NOT_MET":
        return "MISSED_NOT_MET"
    return "WRONG_ABSTENTION_TYPE"


def confusion_matrix(items: Iterable[ScoredItem]) -> Dict[str, Dict[str, int]]:
    matrix = {expected: {predicted: 0 for predicted in STATES} for expected in STATES}
    for item in items:
        matrix[item.expected][item.predicted] += 1
    return matrix


def summarize(items: Sequence[ScoredItem]) -> Dict[str, Any]:
    """Aggregate metrics over scored items. Denominators are explicit in every entry."""
    items = list(items)
    total = len(items)
    predicted_met = [item for item in items if item.predicted == "MET"]
    met_is_wrong = [item for item in items if "MET" not in item.acceptable]
    expected_met = [item for item in items if item.expected == "MET"]
    expected_decided = [item for item in items if item.expected in DECIDED_STATES]
    predicted_abstain = [item for item in items if item.predicted in ABSTAIN_STATES]
    cited = [item for item in items if item.predicted in CITED_STATES]
    overlap_eligible = [item for item in items if item.evidence_overlaps_expected is not None and item.predicted == item.expected]

    true_met = sum(1 for item in predicted_met if "MET" in item.acceptable)
    false_met = len(predicted_met) - true_met
    recalled_met = sum(1 for item in expected_met if item.predicted == "MET")

    per_state = {}
    for state in STATES:
        predicted_state = [item for item in items if item.predicted == state]
        expected_state = [item for item in items if item.expected == state]
        per_state[state] = {
            "precision": ratio(sum(1 for item in predicted_state if state in item.acceptable), len(predicted_state)),
            "recall": ratio(sum(1 for item in expected_state if item.predicted == state), len(expected_state)),
        }

    errors: Dict[str, int] = {}
    for item in items:
        kind = error_class(item)
        if kind:
            errors[kind] = errors.get(kind, 0) + 1

    summary = {
        "scored_labels": total,
        "exact_agreement": ratio(sum(1 for item in items if item.predicted == item.expected), total),
        "acceptable_agreement": ratio(sum(1 for item in items if item.predicted in item.acceptable), total),
        # Safety: asserting a fact the label says is not supported.
        "false_met": {
            **ratio(false_met, len(met_is_wrong)),
            "denominator_meaning": "scored labels where MET is not an acceptable state",
        },
        "met_precision": {**ratio(true_met, len(predicted_met)), "denominator_meaning": "scored labels predicted MET"},
        # Usefulness: failing to recognise a fact the label says is supported.
        "missed_met": {
            **ratio(len(expected_met) - recalled_met, len(expected_met)),
            "denominator_meaning": "scored labels whose expected state is MET",
        },
        "met_recall": {**ratio(recalled_met, len(expected_met)), "denominator_meaning": "scored labels whose expected state is MET"},
        "decided_coverage": {
            **ratio(sum(1 for item in items if item.predicted in DECIDED_STATES), total),
            "denominator_meaning": "all scored labels; predicted MET or NOT_MET",
        },
        "abstention_rate": {
            **ratio(len(predicted_abstain), total),
            "denominator_meaning": "all scored labels; predicted NOT_DOCUMENTED or NEEDS_REVIEW",
        },
        "review_rate": {
            **ratio(sum(1 for item in items if item.predicted == "NEEDS_REVIEW"), total),
            "denominator_meaning": "all scored labels; predicted NEEDS_REVIEW",
        },
        "over_abstention": {
            **ratio(
                sum(1 for item in expected_decided if item.predicted in ABSTAIN_STATES and item.predicted not in item.acceptable),
                len(expected_decided),
            ),
            "denominator_meaning": "scored labels whose expected state is MET or NOT_MET",
        },
        "evidence_coverage": {
            **ratio(sum(1 for item in cited if item.has_evidence), len(cited)),
            "denominator_meaning": "scored labels predicted MET, NOT_MET or NEEDS_REVIEW; at least one cited span",
        },
        "evidence_overlap": {
            **ratio(sum(1 for item in overlap_eligible if item.evidence_overlaps_expected), len(overlap_eligible)),
            "denominator_meaning": "exact-agreement labels with an expected quote and a cited span; cited span overlaps the quote",
        },
        "per_state": per_state,
        "error_classes": dict(sorted(errors.items())),
        "confusion_matrix": confusion_matrix(items),
    }
    summary["utility_flags"] = utility_flags(summary)
    summary["meets_minimum_utility"] = not summary["utility_flags"]
    return summary


def utility_flags(summary: Dict[str, Any]) -> List[str]:
    """Reasons a result must not be read as good, however low its false-MET count.

    A system that never asserts anything has zero false MET. These flags make that
    visible next to the safety number instead of leaving it to the reader.
    """
    flags: List[str] = []
    if summary["scored_labels"] == 0:
        return ["NO_SCORED_LABELS"]
    if summary["met_recall"]["denominator"] == 0:
        flags.append("MET_RECALL_NOT_MEASURED")
    elif summary["met_recall"]["numerator"] == 0:
        flags.append("ZERO_MET_RECALL")
    if summary["decided_coverage"]["numerator"] == 0:
        flags.append("NEVER_DECIDES")
    if summary["false_met"]["denominator"] == 0:
        flags.append("FALSE_MET_NOT_MEASURED")
    elif summary["false_met"]["numerator"] == summary["false_met"]["denominator"]:
        flags.append("ASSERTS_EVERY_UNSUPPORTED_FACT")
    return flags


def apply_control(items: Sequence[ScoredItem], control: str) -> List[ScoredItem]:
    """Replace every prediction with a constant. Controls bound what the metrics can hide."""
    if control not in CONTROLS:
        raise ValueError(f"Unknown control: {control}")
    state = control.removeprefix("ALWAYS_")
    return [replace(item, predicted=state, has_evidence=False, evidence_overlaps_expected=None) for item in items]


def by_requirement(items: Sequence[ScoredItem]) -> Dict[str, Dict[str, Any]]:
    keys = sorted({item.requirement_key for item in items})
    return {key: summarize([item for item in items if item.requirement_key == key]) for key in keys}
