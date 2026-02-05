from __future__ import annotations
from typing import Any, Dict, List, Tuple
from .schemas import RequirementResult


def _eval_number(key: str, label: str, facts: Dict[str, Any], req: Dict[str, Any]) -> RequirementResult:
    val = facts.get(key)
    minv = req.get("min")
    if val is None:
        return RequirementResult(key=key, label=label, status="missing",
                                 reason="Not found in note. Add explicit duration/value.",
                                 evidence=req.get("evidence"))
    if minv is not None and val < minv:
        return RequirementResult(key=key, label=label, status="weak",
                                 reason=f"Documented value ({val}) below requirement (>= {minv}). Clarify or justify.",
                                 evidence=req.get("evidence"))
    return RequirementResult(key=key, label=label, status="met",
                             reason=f"Documented value: {val}.",
                             evidence=req.get("evidence"))


def _eval_boolean(key: str, label: str, facts: Dict[str, Any], req: Dict[str, Any]) -> RequirementResult:
    val = facts.get(key)

    if val is True:
        return RequirementResult(
            key=key, label=label, status="MET",
            reason="Present in documentation.",
            evidence=req.get("evidence")
        )

    if val is False:
        return RequirementResult(
            key=key, label=label, status="NOT_MET",
            reason="Explicitly documented as not present / not satisfied.",
            evidence=req.get("evidence")
        )

    return RequirementResult(
        key=key, label=label, status="NOT_DOCUMENTED",
        reason="Not found in note. Add explicit statement.",
        evidence=req.get("evidence")
    )

    if val is True:
        return RequirementResult(
            key=key, label=label, status="MET",
            reason="Present in documentation.",
            evidence=req.get("evidence")
        )

    if val is False:
        return RequirementResult(
            key=key, label=label, status="NOT_MET",
            reason="Explicitly documented as not present / not satisfied.",
            evidence=req.get("evidence")
        )

    return RequirementResult(
        key=key, label=label, status="NOT_DOCUMENTED",
        reason="Not found in note. Add explicit statement.",
        evidence=req.get("evidence")
    )


def _eval_enum(key: str, label: str, facts: Dict[str, Any], req: Dict[str, Any]) -> RequirementResult:
    val = facts.get(key)
    allowed = req.get("allowed", [])
    if val is None:
        return RequirementResult(key=key, label=label, status="missing",
                                 reason="Not found in note. Add explicit result/category.",
                                 evidence=req.get("evidence"))
    if allowed and val not in allowed:
        return RequirementResult(key=key, label=label, status="weak",
                                 reason=f"Value '{val}' not in allowed set {allowed}. Clarify wording/category.",
                                 evidence=req.get("evidence"))
    return RequirementResult(key=key, label=label, status="met",
                             reason=f"Documented: {val}.",
                             evidence=req.get("evidence"))


def evaluate_requirements(requirements: List[Dict[str, Any]], facts: Dict[str, Any]) -> Tuple[List[RequirementResult], List[str]]:
    results: List[RequirementResult] = []
    reasons: List[str] = []

    for req in requirements:
        key = req["key"]
        label = req.get("label", key)
        rtype = req.get("type", "boolean")

        if rtype == "number":
            out = _eval_number(key, label, facts, req)
        elif rtype == "enum":
            out = _eval_enum(key, label, facts, req)
        else:
            out = _eval_boolean(key, label, facts, req)

        results.append(out)

        if out.status in ("missing", "weak"):
            reasons.append(f"{out.label}: {out.status.upper()} — {out.reason}")

    return results, reasons


def compute_readiness_score(results: List[RequirementResult]) -> Dict[str, int]:
    total = len(results) if results else 1
    met = sum(1 for r in results if r.status == "MET")
    not_met = sum(1 for r in results if r.status == "NOT_MET")
    not_doc = sum(1 for r in results if r.status == "NOT_DOCUMENTED")

    score = int(round(100 * met / total))

    return {
        "readiness_score": max(0, min(100, score)),
        "met_count": met,
        "not_met_count": not_met,
        "not_documented_count": not_doc,
        "total": total,
    }


def compute_overall_status(results: List[RequirementResult]) -> Dict[str, Any]:
    any_not_documented = any(r.status == "NOT_DOCUMENTED" for r in results)
    any_not_met = any(r.status == "NOT_MET" for r in results)

    if any_not_documented:
        return {"overall_status": "CANNOT_DETERMINE", "submission_readiness": False}
    if any_not_met:
        return {"overall_status": "NOT_READY", "submission_readiness": False}
    return {"overall_status": "READY", "submission_readiness": True}

