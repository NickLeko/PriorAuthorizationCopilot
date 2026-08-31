from __future__ import annotations

import json
from typing import Any, Dict, List

from engine.evaluate import (
    compute_overall_status,
    evaluate_requirements,
    summarize_results,
)
from engine.extract import extract_facts
from engine.rules_loader import load_rules


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

        facts, evidence_map = extract_facts(note_text)
        results, _ = evaluate_requirements(reqs, facts, evidence_map=evidence_map)
        result_summary = summarize_results(results)
        overall = compute_overall_status(results)

        expected_status = c.get("expected_overall_status") or (c.get("showcase") or {}).get("expected_overall_status")
        exact_match = bool(expected_status and overall["overall_status"] == expected_status)

        rows.append(
            {
                "id": c.get("id"),
                "payer": payer,
                "procedure": proc,
                "expected": expected_status,
                "overall_status": overall["overall_status"],
                "documentation_coverage_pct": round(
                    100
                    * (result_summary["met_count"] + result_summary["not_met_count"] + result_summary["needs_review_count"])
                    / result_summary["total"],
                    1,
                )
                if result_summary["total"]
                else 0.0,
                "not_documented": result_summary["not_documented_count"],
                "not_met": result_summary["not_met_count"],
                "needs_review": result_summary["needs_review_count"],
                "pass": "✅" if exact_match else "❌",
            }
        )

    return rows


def summarize_safety_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    labeled = [row for row in rows if row.get("expected")]
    expected_not_ready = [row for row in labeled if row["expected"] != "READY"]
    false_ready_count = sum(1 for row in expected_not_ready if row.get("overall_status") == "READY")
    exact_correct_count = sum(1 for row in labeled if row.get("overall_status") == row.get("expected"))
    needs_review_count = sum(1 for row in labeled if row.get("overall_status") == "NEEDS_REVIEW")
    cannot_determine_count = sum(1 for row in labeled if row.get("overall_status") == "CANNOT_DETERMINE")
    abstention_count = needs_review_count + cannot_determine_count

    def rate(count: int, denominator: int) -> float:
        return round(count / denominator * 100, 1) if denominator else 0.0

    return {
        "total_labeled_cases": len(labeled),
        "expected_non_ready_count": len(expected_not_ready),
        "exact_status_correct_count": exact_correct_count,
        "exact_overall_status_accuracy_pct": rate(exact_correct_count, len(labeled)),
        "false_ready_count": false_ready_count,
        "false_ready_rate_pct": rate(false_ready_count, len(expected_not_ready)),
        "needs_review_count": needs_review_count,
        "needs_review_rate_pct": rate(needs_review_count, len(labeled)),
        "cannot_determine_count": cannot_determine_count,
        "cannot_determine_rate_pct": rate(cannot_determine_count, len(labeled)),
        "abstention_count": abstention_count,
        "abstention_rate_pct": rate(abstention_count, len(labeled)),
    }
