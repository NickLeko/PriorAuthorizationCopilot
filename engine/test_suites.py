from __future__ import annotations

import json
from typing import Any, Dict, List

from engine.rules_loader import load_rules
from engine.extract import extract_facts
from engine.evaluate import (
    evaluate_requirements,
    compute_readiness_score,
    compute_overall_status,
)


def label_from_outputs(overall_status: str, score_info: Dict[str, Any]) -> str:
    """
    Heuristic labels for synthetic evaluation only (NOT a product output).

    Mapping:
      - READY -> complete
      - NOT_READY -> incomplete
      - CANNOT_DETERMINE -> borderline (missing documentation but partially present)
    """
    if overall_status == "READY":
        return "complete"
    if overall_status == "NOT_READY":
        return "incomplete"

    # CANNOT_DETERMINE: differentiate borderline vs incomplete using extracted signal
    # If they documented at least half the requirements (met + not_met), call it borderline.
    total = int(score_info.get("total", 0) or 0)
    met = int(score_info.get("met_count", 0) or 0)
    not_met = int(score_info.get("not_met_count", 0) or 0)

    documented = met + not_met
    if total > 0 and (documented / total) >= 0.5:
        return "borderline"
    return "incomplete"


def run_cases(rules_path: str, cases_path: str) -> List[Dict[str, Any]]:
    rules = load_rules(rules_path)
    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    rows: List[Dict[str, Any]] = []

    for c in cases:
        payer = c["payer"]
        proc = c["procedure_code"]

        proc_obj = rules["payers"][payer]["procedures"][proc]
        reqs = proc_obj.get("required", [])

        note_text = c.get("note_text", "") or ""

        # NEW: extract_facts now returns (facts, evidence_map)
        facts, evidence_map = extract_facts(note_text)

        results, _reasons = evaluate_requirements(reqs, facts, evidence_map=evidence_map)
        score_info = compute_readiness_score(results)
        overall = compute_overall_status(results)

        predicted = label_from_outputs(overall["overall_status"], score_info)
        expected = c.get("expected_label")

        rows.append(
            {
                "id": c.get("id"),
                "payer": payer,
                "procedure": proc,
                "expected": expected,
                "predicted": predicted,
                "overall_status": overall["overall_status"],
                "submission_readiness": str(bool(overall["submission_readiness"])).upper(),
                "score": score_info["readiness_score"],
                "not_documented": score_info["not_documented_count"],
                "not_met": score_info["not_met_count"],
                "pass": "✅" if predicted == expected else "❌",
            }
        )

    return rows

