"""Fixed automated evaluator. Run from any working directory; inputs stay in repo."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.schemas import PARequest  # noqa: E402
from engine.service import ReadinessService  # noqa: E402

STATUSES = ("READY", "PENDING_VERIFICATION", "NOT_READY", "CANNOT_DETERMINE", "NEEDS_REVIEW", "UNKNOWN")
ABSTENTIONS = {"CANNOT_DETERMINE", "NEEDS_REVIEW"}
PASSING = {"READY", "PENDING_VERIFICATION"}


def metrics(expected: list[str], actual: list[str]) -> dict:
    if not expected or len(expected) != len(actual):
        raise ValueError("Scoring requires equally sized, nonempty status lists.")
    if any(status not in STATUSES for status in expected + actual):
        raise ValueError("Unknown status label.")
    matrix = Counter(zip(expected, actual))
    count = len(expected)
    exact = sum(e == a for e, a in zip(expected, actual))
    return {
        "cases": count,
        "exact_status_correct": exact,
        "exact_status_accuracy": exact / count,
        "false_pending_verification": sum(e not in PASSING and a == "PENDING_VERIFICATION" for e, a in zip(expected, actual)),
        "false_ready": sum(e not in PASSING and a == "READY" for e, a in zip(expected, actual)),
        "automated_ready": actual.count("READY"),
        "missed_passes": sum(e == "PENDING_VERIFICATION" and a != "PENDING_VERIFICATION" for e, a in zip(expected, actual)),
        "abstention_rate": sum(a in ABSTENTIONS for a in actual) / count,
        "expected_abstention_rate": sum(e in ABSTENTIONS for e in expected) / count,
        "confusion_matrix_expected_rows_actual_columns": {e: {a: matrix[e, a] for a in STATUSES} for e in STATUSES},
    }


def score(path: Path) -> dict:
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Case file must be inside this repository for this experiment.")
    raw = path.read_bytes()
    payload = json.loads(raw)
    cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(cases, list) or not cases:
        raise ValueError("Expected a nonempty list or an object with a nonempty cases list.")
    service = ReadinessService()
    rows = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"Case {index} must be an object.")
        for key in ("payer", "procedure_code", "note_text", "expected_overall_status"):
            if key not in case:
                raise ValueError(f"Case {index} is missing {key}.")
        if case.get("fact_verifications") or case.get("corrections"):
            raise ValueError("Automated scoring forbids human attestations and corrections.")
        expected = case["expected_overall_status"]
        if expected not in STATUSES:
            raise ValueError(f"Case {index} has invalid expected status: {expected!r}")
        request = PARequest.model_validate(
            {key: case[key] for key in ("payer", "procedure_code", "note_text", "dx_codes", "site_of_care", "specialty") if key in case}
        )
        result = service.evaluate(request)
        rows.append({"index": index, "id": case.get("id"), "expected": expected, "actual": result.overall_status})
    expected = [row["expected"] for row in rows]
    return {
        "case_file": str(path.relative_to(ROOT)),
        "case_file_sha256": hashlib.sha256(raw).hexdigest(),
        "system": metrics(expected, [row["actual"] for row in rows]),
        "always_cannot_determine_canary": metrics(expected, ["CANNOT_DETERMINE"] * len(rows)),
        "mismatches": [row for row in rows if row["expected"] != row["actual"]],
        "case_results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "inputs/synthetic_cases.json")
    args = parser.parse_args()
    try:
        report = score(args.cases)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
