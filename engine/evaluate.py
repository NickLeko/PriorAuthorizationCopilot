from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
from .schemas import RequirementResult


def _eval_number(
    key: str,
    label: str,
    facts: Dict[str, Any],
    req: Dict[str, Any],
    evidence_map: Optional[Dict[str, List[str]]] = None,
) -> RequirementResult:
    val = facts.get(key)
    minv = req.get("min")
    snippets = (evidence_map or {}).get(key, [])

    if val is None:
        return RequirementResult(
            key=key,
            label=label,
            status="NOT_DOCUMENTED",
            reason="Not found in note. Add explicit duration/value.",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
        )

    if minv is not None and val < minv:
        return RequirementResult(
            key=key,
            label=label,
            status="NOT_MET",
            reason=f"Documented value ({val}) below requirement (>= {minv}). Clarify or justify.",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
        )

    return RequirementResult(
        key=key,
        label=label,
        status="MET",
        reason=f"Documented value: {val}.",
        evidence=req.get("evidence"),
        evidence_snippets=snippets,
    )


def _eval_boolean(
    key: str,
    label: str,
    facts: Dict[str, Any],
    req: Dict[str, Any],
    evidence_map: Optional[Dict[str, List[str]]] = None,
) -> RequirementResult:
    val = facts.get(key)
    snippets = (evidence_map or {}).get(key, [])

    if val is None:
        return RequirementResult(
            key=key,
            label=label,
            status="NOT_DOCUMENTED",
            reason="Not found in note. Add explicit statement.",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
        )

    if val is True:
        return RequirementResult(
            key=key,
            label=label,
            status="MET",
            reason="Present in documentation.",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
        )

    # val is False
    return RequirementResult(
        key=key,
        label=label,
        status="NOT_MET",
        reason="Documented as absent/denied. If applicable, add supporting details; otherwise criteria may not be met.",
        evidence=req.get("evidence"),
        evidence_snippets=snippets,
    )


def _eval_enum(
    key: str,
    label: str,
    facts: Dict[str, Any],
    req: Dict[str, Any],
    evidence_map: Optional[Dict[str, List[str]]] = None,
) -> RequirementResult:
    val = facts.get(key)
    allowed = req.get("allowed", [])
    snippets = (evidence_map or {}).get(key, [])

    if val is None:
        return RequirementResult(
            key=key,
            label=label,
            status="NOT_DOCUMENTED",
            reason="Not found in note. Add explicit result/category.",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
        )

    if allowed and val not in allowed:
        return RequirementResult(
            key=key,
            label=label,
            status="NOT_MET",
            reason=f"Value '{val}' not in allowed set {allowed}. Clarify wording/category.",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
        )

    return RequirementResult(
        key=key,
        label=label,
        status="MET",
        reason=f"Documented: {val}.",
        evidence=req.get("evidence"),
        evidence_snippets=snippets,
    )


def evaluate_requirements(
    requirements: List[Dict[str, Any]],
    facts: Dict[str, Any],
    evidence_map: Optional[Dict[str, List[str]]] = None,
) -> Tuple[List[RequirementResult], List[str]]:
    results: List[RequirementResult] = []
    reasons: List[str] = []

    for req in requirements:
        key = req["key"]
        label = req.get("label", key)
        rtype = req.get("type", "boolean")

        if rtype == "number":
            out = _eval_number(key, label, facts, req, evidence_map=evidence_map)
        elif rtype == "enum":
            out = _eval_enum(key, label, facts, req, evidence_map=evidence_map)
        else:
            out = _eval_boolean(key, label, facts, req, evidence_map=evidence_map)

        results.append(out)

        if out.status in ("NOT_DOCUMENTED", "NOT_MET"):
            reasons.append(f"{out.label}: {out.status} — {out.reason}")

    return results, reasons


def compute_readiness_score(results: List[RequirementResult]) -> Dict[str, Any]:
    """
    Simple deterministic scoring for demo:
      MET=1, NOT_MET=0, NOT_DOCUMENTED=0
    """
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
    """
    Guardrail-aligned overall status:
      - Any NOT_DOCUMENTED => CANNOT_DETERMINE
      - Else any NOT_MET => NOT_READY
      - Else READY
    """
    any_not_doc = any(r.status == "NOT_DOCUMENTED" for r in results)
    if any_not_doc:
        return {"overall_status": "CANNOT_DETERMINE", "submission_readiness": False}

    any_not_met = any(r.status == "NOT_MET" for r in results)
    if any_not_met:
        return {"overall_status": "NOT_READY", "submission_readiness": False}

    return {"overall_status": "READY", "submission_readiness": True}
