from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .schemas import EvidenceSpan, RequirementResult


def _coerce_evidence_snippets(evidence_items: Any) -> List[str]:
    """
    evidence_items may be:
      - None
      - List[str]
      - List[{"start": int, "end": int, "text": str}]
    Return: List[str] (schema-stable for Pydantic).
    """
    if not evidence_items:
        return []

    out: List[str] = []
    if isinstance(evidence_items, list):
        for it in evidence_items:
            if isinstance(it, str):
                s = it.strip()
                if s:
                    out.append(s)
            elif isinstance(it, dict):
                s = str(it.get("text", "")).strip()
                if s:
                    out.append(s)
            else:
                s = str(it).strip()
                if s:
                    out.append(s)

    # Dedup preserve order
    dedup: List[str] = []
    seen = set()
    for s in out:
        if s not in seen:
            seen.add(s)
            dedup.append(s)
    return dedup


def _coerce_evidence_spans(evidence_items: Any) -> List[EvidenceSpan]:
    if not evidence_items:
        return []

    spans: List[EvidenceSpan] = []
    if isinstance(evidence_items, list):
        for item in evidence_items:
            if not isinstance(item, dict):
                continue
            start = item.get("start")
            end = item.get("end")
            text = str(item.get("text", "")).strip()
            if not isinstance(start, int) or not isinstance(end, int) or not text:
                continue
            if end <= start or start < 0:
                continue
            spans.append(EvidenceSpan(start=start, end=end, text=text))
    return spans


def _eval_number(
    key: str,
    label: str,
    facts: Dict[str, Any],
    req: Dict[str, Any],
    evidence_map: Optional[Dict[str, Any]] = None,
) -> RequirementResult:
    val = facts.get(key)
    minv = req.get("min")
    evidence_items = (evidence_map or {}).get(key)
    snippets = _coerce_evidence_snippets(evidence_items)
    spans = _coerce_evidence_spans(evidence_items)

    if val is None:
        return RequirementResult(
            key=key,
            label=label,
            status="NOT_DOCUMENTED",
            reason="Not found in note. Add explicit duration/value.",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
            evidence_spans=spans,
        )

    if minv is not None and val < minv:
        return RequirementResult(
            key=key,
            label=label,
            status="NOT_MET",
            reason=f"Documented value ({val}) below requirement (>= {minv}). Clarify or justify.",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
            evidence_spans=spans,
        )

    return RequirementResult(
        key=key,
        label=label,
        status="MET",
        reason=f"Documented value: {val}.",
        evidence=req.get("evidence"),
        evidence_snippets=snippets,
        evidence_spans=spans,
    )


def _eval_boolean(
    key: str,
    label: str,
    facts: Dict[str, Any],
    req: Dict[str, Any],
    evidence_map: Optional[Dict[str, Any]] = None,
) -> RequirementResult:
    """
    Boolean requirement semantics:

    - If the field is explicitly addressed in the note (either True or False),
      that counts as DOCUMENTED.

    - Whether False should be MET vs NOT_MET depends on the *meaning* of the field.
      For this MVP, boolean fields represent "criterion addressed/present" patterns
      (e.g., 'neuro_red_flags_documented' means addressed, not 'present').

    Therefore:
      - True => MET
      - False => MET (documented denial still satisfies "addressed" requirement)
      - None => NOT_DOCUMENTED
    """
    val = facts.get(key)
    evidence_items = (evidence_map or {}).get(key)
    snippets = _coerce_evidence_snippets(evidence_items)
    spans = _coerce_evidence_spans(evidence_items)

    if val is True:
        return RequirementResult(
            key=key,
            label=label,
            status="MET",
            reason="Explicitly addressed in documentation (present/affirmed).",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
            evidence_spans=spans,
        )

    if val is False:
        return RequirementResult(
            key=key,
            label=label,
            status="MET",
            reason="Explicitly addressed in documentation (denied/absent).",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
            evidence_spans=spans,
        )

    return RequirementResult(
        key=key,
        label=label,
        status="NOT_DOCUMENTED",
        reason="Not found in note. Add explicit statement.",
        evidence=req.get("evidence"),
        evidence_snippets=snippets,
        evidence_spans=spans,
    )


def _eval_enum(
    key: str,
    label: str,
    facts: Dict[str, Any],
    req: Dict[str, Any],
    evidence_map: Optional[Dict[str, Any]] = None,
) -> RequirementResult:
    val = facts.get(key)
    allowed = req.get("allowed", [])
    evidence_items = (evidence_map or {}).get(key)
    snippets = _coerce_evidence_snippets(evidence_items)
    spans = _coerce_evidence_spans(evidence_items)

    if val is None:
        return RequirementResult(
            key=key,
            label=label,
            status="NOT_DOCUMENTED",
            reason="Not found in note. Add explicit result/category.",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
            evidence_spans=spans,
        )

    if val == "unrecognized":
        return RequirementResult(
            key=key,
            label=label,
            status="NEEDS_REVIEW",
            reason="Imaging result is documented but its category is unrecognized; human review is required.",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
            evidence_spans=spans,
        )

    if allowed and val not in allowed:
        return RequirementResult(
            key=key,
            label=label,
            status="NOT_MET",
            reason=f"Value '{val}' not in allowed set {allowed}. Clarify wording/category.",
            evidence=req.get("evidence"),
            evidence_snippets=snippets,
            evidence_spans=spans,
        )

    return RequirementResult(
        key=key,
        label=label,
        status="MET",
        reason=f"Documented: {val}.",
        evidence=req.get("evidence"),
        evidence_snippets=snippets,
        evidence_spans=spans,
    )


def evaluate_requirements(
    requirements: List[Dict[str, Any]],
    facts: Dict[str, Any],
    evidence_map: Optional[Dict[str, Any]] = None,
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

        if out.status in ("NOT_DOCUMENTED", "NOT_MET", "NEEDS_REVIEW"):
            reasons.append(f"{out.label}: {out.status} — {out.reason}")

    return results, reasons


def compute_readiness_score(results: List[RequirementResult]) -> Dict[str, int]:
    """
    Score is informational only.
    MET = 1
    NOT_MET = 0.5 (documented but failing threshold)
    NOT_DOCUMENTED = 0
    NEEDS_REVIEW = 0 (documented but unevaluable; no threshold credit)
    """
    total = len(results) if results else 1
    met = sum(1 for r in results if r.status == "MET")
    not_met = sum(1 for r in results if r.status == "NOT_MET")
    not_doc = sum(1 for r in results if r.status == "NOT_DOCUMENTED")
    needs_review = sum(1 for r in results if r.status == "NEEDS_REVIEW")

    raw = met + 0.5 * not_met
    score = int(round(100 * raw / total))

    return {
        "readiness_score": max(0, min(100, score)),
        "met_count": met,
        "not_met_count": not_met,
        "not_documented_count": not_doc,
        "needs_review_count": needs_review,
        "total": total,
    }


def compute_overall_status(results: List[RequirementResult]) -> Dict[str, Any]:
    """
    Semantics Contract (locked):
      READY: all required MET
      CANNOT_DETERMINE: >=1 NOT_DOCUMENTED
      NEEDS_REVIEW: no missing requirements, but >=1 NEEDS_REVIEW
      NOT_READY: all documented and evaluable, but >=1 NOT_MET
    """
    has_not_doc = any(r.status == "NOT_DOCUMENTED" for r in results)
    has_needs_review = any(r.status == "NEEDS_REVIEW" for r in results)
    has_not_met = any(r.status == "NOT_MET" for r in results)

    if has_not_doc:
        return {"overall_status": "CANNOT_DETERMINE", "submission_readiness": False}
    if has_needs_review:
        return {"overall_status": "NEEDS_REVIEW", "submission_readiness": False}
    if has_not_met:
        return {"overall_status": "NOT_READY", "submission_readiness": False}
    return {"overall_status": "READY", "submission_readiness": True}
