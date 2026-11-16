"""Run labeled datasets through the production service and score each requirement.

The harness supplies no human verifications, so READY is structurally
unreachable here. It measures extraction proposals, not authorization readiness.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from engine.schemas import PARequest
from engine.service import ReadinessService

from .metrics import CONTROLS, ScoredItem, apply_control, by_requirement, error_class, summarize
from .schema import SCORED_TIERS, Dataset, LabeledCase

Predictor = Callable[[LabeledCase], Dict[str, Any]]


def service_predictor(service: Optional[ReadinessService] = None) -> Predictor:
    """Production path: ReadinessService.evaluate with no verifications or corrections."""
    service = service or ReadinessService()

    def predict(case: LabeledCase) -> Dict[str, Any]:
        result = service.evaluate(PARequest(payer=case.payer, procedure_code=case.procedure_code, note_text=case.note_text or ""))
        return {
            "overall_status": result.overall_status,
            "requirements": {
                item.key: {
                    "status": item.status,
                    "fact_value": item.fact_value,
                    "evidence_spans": [span.model_dump() for span in item.evidence_spans],
                }
                for item in result.results
            },
        }

    return predict


def _overlaps(note: str, quote: Optional[str], spans: List[Dict[str, Any]]) -> Optional[bool]:
    if not quote or not spans:
        return None
    starts = []
    cursor = note.find(quote)
    while cursor >= 0:
        starts.append(cursor)
        cursor = note.find(quote, cursor + 1)
    return any(span["start"] < start + len(quote) and start < span["end"] for start in starts for span in spans)


def evaluate_dataset(dataset: Dataset, predict: Predictor) -> Dict[str, Any]:
    items: List[ScoredItem] = []
    observations: List[Dict[str, Any]] = []
    unlabeled: List[Dict[str, str]] = []
    unscored: List[Dict[str, Any]] = []
    orphan_labels: List[Dict[str, str]] = []
    case_rows: List[Dict[str, Any]] = []

    for case in dataset.cases:
        prediction = predict(case)
        predicted = prediction["requirements"]
        labels = {label.requirement_key: label for label in case.labels}
        orphan_labels += [{"case_id": case.case_id, "requirement_key": key} for key in labels if key not in predicted]
        case_items: List[ScoredItem] = []
        fully_scored = True
        for key, observed in predicted.items():
            label = labels.get(key)
            if label is None:
                unlabeled.append({"case_id": case.case_id, "requirement_key": key})
                fully_scored = False
                continue
            if label.review_status not in SCORED_TIERS:
                unscored.append(
                    {
                        "case_id": case.case_id,
                        "requirement_key": key,
                        "proposed_state": label.expected_state,
                        "observed_state": observed["status"],
                        "question_for_reviewer": label.uncertainty_note,
                    }
                )
                fully_scored = False
                continue
            item = ScoredItem(
                dataset_id=dataset.dataset_id,
                case_id=case.case_id,
                requirement_key=key,
                tier=label.review_status,
                expected=label.expected_state,
                acceptable=tuple(label.acceptable_states),
                predicted=observed["status"],
                has_evidence=bool(observed["evidence_spans"]),
                evidence_overlaps_expected=_overlaps(case.note_text or "", label.evidence_quote, observed["evidence_spans"]),
            )
            case_items.append(item)
            kind = error_class(item)
            if kind:
                observations.append(
                    {
                        "case_id": case.case_id,
                        "requirement_key": key,
                        "error_class": kind,
                        "label_tier": item.tier,
                        "expected_state": item.expected,
                        "acceptable_states": list(item.acceptable),
                        "observed_state": item.predicted,
                        "observed_fact_value": observed["fact_value"],
                        "observed_evidence": [span["text"] for span in observed["evidence_spans"]],
                        "phenomena": case.phenomena,
                        "label_uncertainty": label.uncertainty,
                        "overall_status": prediction["overall_status"],
                        "note_text": case.note_text,
                    }
                )
        items += case_items
        false_met_keys = [item.requirement_key for item in case_items if error_class(item) == "FALSE_MET"]
        case_rows.append(
            {
                "case_id": case.case_id,
                "overall_status": prediction["overall_status"],
                "fully_scored": fully_scored,
                "all_expected_met": fully_scored and all(item.expected == "MET" for item in case_items),
                "all_met_acceptable": fully_scored and all("MET" in item.acceptable for item in case_items),
                "false_met_keys": false_met_keys,
            }
        )

    tiers = {}
    for tier in SCORED_TIERS:
        tier_items = [item for item in items if item.tier == tier]
        tiers[tier] = {
            "aggregate": summarize(tier_items),
            "by_requirement": by_requirement(tier_items),
            "controls": {control: summarize(apply_control(tier_items, control)) for control in CONTROLS},
        }

    label_counts = {status: 0 for status in ("verified", "provisional", "needs_review")}
    for case in dataset.cases:
        for label in case.labels:
            label_counts[label.review_status] += 1

    fully = [row for row in case_rows if row["fully_scored"]]
    pending = [row for row in fully if row["overall_status"] == "PENDING_VERIFICATION"]
    should_not_pass = [row for row in fully if not row["all_met_acceptable"]]
    should_pass = [row for row in fully if row["all_expected_met"]]
    with_false_met = [row for row in case_rows if row["false_met_keys"]]
    ready = [row for row in case_rows if row["overall_status"] == "READY"]

    return {
        "dataset_id": dataset.dataset_id,
        "dataset_version": dataset.dataset_version,
        "split": dataset.split,
        "description": dataset.description,
        "note_authorship": dataset.note_authorship,
        "selection": dataset.selection,
        "independent_clinical_ground_truth": dataset.independent_clinical_ground_truth,
        "cases": len(dataset.cases),
        "cases_with_output_seen_before_labeling": sum(1 for case in dataset.cases if case.extractor_output_seen_before_labeling),
        "requirement_slots": len(items) + len(unscored) + len(unlabeled),
        "label_counts": label_counts,
        "unlabeled_requirements": unlabeled,
        "unscored_needs_review": unscored,
        "labels_without_matching_requirement": orphan_labels,
        "tiers": tiers,
        "case_level": {
            "note": "Derived from requirement labels. A case counts only if every requirement has a scored label.",
            "fully_scored_cases": len(fully),
            "false_all_met": {
                "numerator": sum(1 for row in should_not_pass if row["overall_status"] == "PENDING_VERIFICATION"),
                "denominator": len(should_not_pass),
                "denominator_meaning": "fully scored cases where at least one requirement must not be MET",
                "case_ids": [row["case_id"] for row in should_not_pass if row["overall_status"] == "PENDING_VERIFICATION"],
            },
            "missed_all_met": {
                "numerator": sum(1 for row in should_pass if row["overall_status"] != "PENDING_VERIFICATION"),
                "denominator": len(should_pass),
                "denominator_meaning": "fully scored cases where every requirement is expected MET",
                "case_ids": [row["case_id"] for row in should_pass if row["overall_status"] != "PENDING_VERIFICATION"],
            },
            "predicted_all_met": len(pending),
            "false_met_hidden_by_another_blocker": {
                "numerator": sum(1 for row in with_false_met if row["overall_status"] != "PENDING_VERIFICATION"),
                "denominator": len(with_false_met),
                "denominator_meaning": "cases with at least one false MET; overall status was not PENDING_VERIFICATION",
                "case_ids": [row["case_id"] for row in with_false_met if row["overall_status"] != "PENDING_VERIFICATION"],
            },
            "ready": {
                "reachable": False,
                "observed": len(ready),
                "reason": "No human verifications are supplied, so READY cannot occur. No false-READY rate is reported.",
            },
        },
        "observed_failures": observations,
    }
