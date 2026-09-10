"""Counterfactual evaluation of archived evidence using the unchanged rule engine."""

from __future__ import annotations

from collections import Counter

from .decision_store import DecisionStore
from .evaluate import compute_overall_status, evaluate_requirements
from .policies import facts_for_policy
from .schemas import REVIEW_REQUIRED_FACT, EvaluationResult, FactVerification, PolicyVersion

CATEGORIES = (
    "BECAME_UNDETERMINABLE",
    "BECAME_REVIEW_REQUIRED",
    "REFUSAL_RESOLVED",
    "OUTCOME_CHANGED",
    "REASONING_CHANGED",
    "UNCHANGED",
)
REFUSALS = {"CANNOT_DETERMINE", "NEEDS_REVIEW"}


def comparison_status(results) -> str:
    # Compare criterion outcomes independently of a policy-bound human attestation.
    unverified = [item.model_copy(update={"verification": FactVerification()}) for item in results]
    status = compute_overall_status(unverified)["overall_status"]
    return "CRITERIA_MET" if status == "PENDING_VERIFICATION" else status


def replay_decision(original: EvaluationResult, target: PolicyVersion) -> dict:
    target = PolicyVersion.model_validate_json(target.model_dump_json())
    source = original.policy_version
    if (source.policy_id, source.payer, source.procedure_code) != (target.policy_id, target.payer, target.procedure_code):
        raise ValueError("Replay requires the same policy family and request scope.")
    if original.request.site_of_care not in target.supported_sites:
        raise ValueError("Historical site of care is outside target policy scope.")
    facts = {}
    for key, state in original.captured_fact_states.items():
        if state == "NEEDS_REVIEW":
            facts[key] = REVIEW_REQUIRED_FACT
        elif state == "CAPTURED":
            facts[key] = original.facts.get(key)
        else:
            facts[key] = None
    evidence = {key: [span.model_dump() for span in spans] for key, spans in original.evidence_map.items()}
    facts, incompatible = facts_for_policy(facts, target)
    results, reasons = evaluate_requirements(target.requirements, facts, evidence_map=evidence)
    # Fresh unverified results even on same-version replay. No attestations are copied.
    overall = compute_overall_status(results)
    before_status = comparison_status(original.results)
    after_status = comparison_status(results)
    before_rules = {item["key"]: item for item in source.requirements}
    after_rules = {item["key"]: item for item in target.requirements}
    before_results = {item.key: item for item in original.results}
    after_results = {item.key: item for item in results}
    differences = []
    for key in sorted(before_rules.keys() | after_rules.keys()):
        before = before_results.get(key)
        after = after_results.get(key)
        if (before_rules.get(key), before.status if before else None) == (after_rules.get(key), after.status if after else None):
            continue
        differences.append(
            {
                "criterion": key,
                "change": "ADDED" if before is None else "REMOVED" if after is None else "MODIFIED",
                "before": {"definition": before_rules.get(key), "status": before.status, "reason": before.reason} if before else None,
                "after": {"definition": after_rules.get(key), "status": after.status, "reason": after.reason} if after else None,
            }
        )
    if after_status == "CANNOT_DETERMINE" and before_status != after_status:
        category = "BECAME_UNDETERMINABLE"
    elif after_status == "NEEDS_REVIEW" and before_status != after_status:
        category = "BECAME_REVIEW_REQUIRED"
    elif before_status in REFUSALS and after_status not in REFUSALS:
        category = "REFUSAL_RESOLVED"
    elif before_status != after_status:
        category = "OUTCOME_CHANGED"
    else:
        category = "REASONING_CHANGED" if differences else "UNCHANGED"
    missing = [item.key for item in results if item.status == "NOT_DOCUMENTED"]
    newly_required_missing = [key for key in missing if key not in before_rules]
    blocker_status = {"CANNOT_DETERMINE": "NOT_DOCUMENTED", "NEEDS_REVIEW": "NEEDS_REVIEW", "NOT_READY": "NOT_MET"}
    driving_criteria = []
    if before_status != after_status:
        for change in differences:
            old = (change["before"] or {}).get("status")
            new = (change["after"] or {}).get("status")
            if old != new and (
                (old is not None and old == blocker_status.get(before_status))
                or (new is not None and new == blocker_status.get(after_status))
            ):
                driving_criteria.append(change["criterion"])
    return {
        "source_policy": source.model_dump(mode="json"),
        "original_overall_status": original.overall_status,
        "original_criteria_outcome": before_status,
        "target_criteria_outcome": after_status,
        "category": category,
        "overall_status": overall["overall_status"],
        "submission_readiness": False,
        "human_review_required": True,
        "verification_disposition": "Fresh human verification required; historical attestations are not transferable.",
        "criterion_differences": differences,
        "outcome_driving_criteria": driving_criteria,
        "missing_evidence": missing,
        "incompatible_captured_evidence": incompatible,
        "newly_required_missing_evidence": newly_required_missing,
        "refusal_preserved": before_status in REFUSALS and after_status in REFUSALS,
        "results": [item.model_dump(mode="json") for item in results],
        "rule_reasons": reasons,
    }


def replay(store: DecisionStore, decision_ids: list[str], target: PolicyVersion) -> dict:
    if len(set(decision_ids)) != len(decision_ids):
        raise ValueError("Duplicate historical decision IDs would distort denominators.")
    rows = [{"decision_id": key, **replay_decision(store.get_decision(key), target)} for key in sorted(decision_ids)]
    counts = Counter(row["category"] for row in rows)
    denominator = len(rows)
    return {
        "target_policy": target.model_dump(mode="json"),
        "comparison_basis": "Criterion outcomes, independent of verification; CRITERIA_MET does not mean READY.",
        "total_decisions": denominator,
        "categories": {category: {"count": counts[category], "denominator": denominator} for category in CATEGORIES},
        "target_outcomes": dict(sorted(Counter(row["target_criteria_outcome"] for row in rows).items())),
        "newly_required_evidence_missing": {
            "count": sum(bool(row["newly_required_missing_evidence"]) for row in rows),
            "denominator": denominator,
        },
        "refusals_preserved": {
            "count": sum(row["refusal_preserved"] for row in rows),
            "denominator": sum(row["original_criteria_outcome"] in REFUSALS for row in rows),
        },
        "decisions": rows,
    }
