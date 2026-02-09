# engine/test_suites.py
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
    Synthetic evaluation label (NOT a product output).

    We deliberately collapse:
      - READY => "complete"
      - NOT_READY or CANNOT_DETERMINE => "incomplete"

    This matches the project stance: anything other than READY is not submission-ready.
    """
    return "complete" if overall_status == "READY" else "incomplete"


def run_cases(rules_path: str, cases_path: str) -> List[Dict[str, Any]]:
    """
    Deterministic synthetic test runner used by:
      - Streamlit "System Health" panel
      - Manual test suite execution in UI

    Inputs:
      - rules YAML path
      - synthetic cases JSON path

    Output:
      - list of rows with pass/fail flags and key counters

    NOTE:
      - This is NOT a clinical eval.
      - This is a behavioral contract check for deterministic rules.
    """
    rules = load_rules(rules_path)

    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if not isinstance(cases, list):
        raise ValueError("synthetic_cases.json must be a list of case objects")

    rows: List[Dict[str, Any]] = []

    for c in cases:
        payer = c["payer"]
        proc = c["procedure_code"]

        proc_obj = rules["payers"][payer]["procedures"][proc]
        reqs = proc_obj.get("required", [])

        note_text = c.get("note_text", "") or ""

        facts, evidence_map = extract_facts(note_text)
        results, _ = evaluate_requirements(reqs, facts, evidence_map=evidence_map)

        score_info = compute_readiness_score(results)
        overall = compute_overall_status(results)

        predicted = label_from_outputs(overall["overall_status"])
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
