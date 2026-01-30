from __future__ import annotations
import json
from typing import Any, Dict, List, Tuple

from engine.rules_loader import load_rules
from engine.extract import extract_facts
from engine.evaluate import evaluate_requirements, compute_readiness_score


def label_from_score(score: int, missing: int, weak: int) -> str:
    # Simple, explicit heuristic for MVP evaluation
    if score >= 85 and missing == 0:
        return "complete"
    if score >= 60 and missing <= 2:
        return "borderline"
    return "incomplete"


def run_cases(rules_path: str, cases_path: str) -> List[Dict[str, Any]]:
    rules = load_rules(rules_path)
    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    rows = []
    for c in cases:
        payer = c["payer"]
        proc = c["procedure_code"]
        proc_obj = rules["payers"][payer]["procedures"][proc]
        reqs = proc_obj.get("required", [])

        facts = extract_facts(c.get("note_text", ""))
        results, reasons = evaluate_requirements(reqs, facts)
        score_info = compute_readiness_score(results)
        pred = label_from_score(score_info["readiness_score"], score_info["missing_count"], score_info["weak_count"])

        rows.append({
            "id": c["id"],
            "payer": payer,
            "procedure": proc,
            "expected": c.get("expected_label"),
            "predicted": pred,
            "score": score_info["readiness_score"],
            "missing": score_info["missing_count"],
            "weak": score_info["weak_count"],
            "pass": "✅" if pred == c.get("expected_label") else "❌",
        })

    return rows
