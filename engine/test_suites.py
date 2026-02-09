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


def label_from_outputs(overall_status: str) -> str:
    """
    Heuristic labels for synthetic evaluation only (NOT a product output).

    Current project semantics:
      - READY => complete
      - NOT_READY or CANNOT_DETERMINE => incomplete
    """
    return "complete" if overall_status == "READY" else "incomplete"


def run_cases(rules_path: str, cases_path: str) -> List[Dict[str, Any]]:
    """
    Run deterministic extraction + evaluation over synthetic cases.

    Returns rows shaped for UI display + export.
    This is NOT a pytest module.
    """
    rules = load_rules(rules_path)

    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if not isinstance(cases, list):
        raise ValueError("synthetic_cases.json must contain a top-level list of cases")

    rows: List[Dict[str, Any]] = []

    for c in cases:
        payer = c.get("payer")
        proc = c.get("procedure_code")
        expected = c.get("expected_label")
        note_text = c.get("note_text", "") or ""

        if not payer or not proc:
            rows.append(
                {
                    "id": c.get("id"),
                    "payer": payer,
                    "procedure": proc,
                    "expected": expected,
                    "predicted": "error",
                    "overall_status": "ERROR",
                    "submission_readiness": "FALSE",
                    "score": 0,
                    "not_documented": 0,
                    "not_met": 0,
                    "pass": "❌",
                    "error": "Missing payer or procedure_code in case",
                }
            )
            continue

        try:
            proc_obj = rules["payers"][payer]["procedures"][proc]
            reqs = proc_obj.get("required", [])

            facts, evidence_map = extract_facts(note_text)
            results, _ = evaluate_requirements(reqs, facts, evidence_map=evidence_map)
            score_info = compute_readiness_score(results)
            overall = compute_overall_status(results)

            predicted = label_from_outputs(overall["overall_status"])

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
        except Exception as e:
            rows.append(
                {
                    "id": c.get("id"),
                    "payer": payer,
                    "procedure": proc,
                    "expected": expected,
                    "predicted": "error",
                    "overall_status": "ERROR",
                    "submission_readiness": "FALSE",
                    "score": 0,
                    "not_documented": 0,
                    "not_met": 0,
                    "pass": "❌",
                    "error": f"{type(e).__name__}: {e}",
                }
            )

    return rows
