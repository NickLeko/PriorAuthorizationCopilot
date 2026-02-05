from __future__ import annotations

import json
from typing import Any, Dict, List

from engine.rules_loader import load_rules
from engine.extract import extract_facts
from engine.evaluate import evaluate_requirements, compute_readiness_score, compute_overall_status


def label_from_score(score: int, not_documented: int, not_met: int) -> str:
    """
    Heuristic labels for synthetic evaluation only.
    Mirrors product guardrails:
      - Missing documentation is a hard blocker.
    """
    if not_documented > 0:
        return "incomplete"

    if score >= 85 and not_met == 0:
        return "complete"

    if score >= 60 and not_met <= 1:
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

        facts, evidence_map = extract_facts(c.get("note_text", ""))
        results, _ = evaluate_requirements(reqs, facts, evidence_map=evidence_map)

        score_info = compute_readiness_score(results)
        overall = compute_overall_status(results)

        pred = label_from_score(
            score_info["readiness_score"],
            score_info["not_documented_count"],
            score_info["not_met_count"],
        )

        expected = c.get("expected_label")

        rows.append(
            {
                "id": c.get("id"),
                "payer": payer,
                "procedure": proc,
                "expected": expected,
                "predicted": pred,
                "overall_status": overall["overall_status"],
                "submission_readiness": bool(overall["submission_readiness"]),
                "score": score_info["readiness_score"],
                "not_documented": score_info["not_documented_count"],
                "not_met": score_info["not_met_count"],
                "pass": "✅" if (expected is not None and pred == expected) else "❌"
                "test_category": c.get("test_category", ""),
,
            }
        )

    return rows
