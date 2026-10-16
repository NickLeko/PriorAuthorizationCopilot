"""Record public-score evidence and enforce exp-002's paired safety checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from autoloop.score import metrics, score  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iteration", type=int)
    parser.add_argument("phase", choices=("before", "after", "reverted"))
    args = parser.parse_args()
    directory = ROOT / "autoloop/exp-002"
    cases = []
    current = []
    for path in sorted((directory / "cases").glob("iteration-*.json")):
        batch = json.loads(path.read_text())
        cases.extend(batch)
        if path.name == f"iteration-{args.iteration}.json":
            current = batch
    assert current and sum(c["pair_role"] == "positive" for c in current) >= 3
    assert sum(c["pair_role"] == "negative" for c in current) >= 3
    prefix = directory / "evidence" / f"iteration-{args.iteration}-{args.phase}"
    case_path = prefix.with_name(prefix.name + "-cases.json")
    case_path.write_text(json.dumps(cases, indent=2) + "\n")
    report = score(case_path)
    corpus = score(ROOT / "inputs/synthetic_cases.json")
    baseline = json.loads((directory / "evidence/baseline-corpus.json").read_text())
    summary = {}
    for role in ("positive", "negative"):
        rows = [row for case, row in zip(cases, report["case_results"]) if case["pair_role"] == role]
        summary[role] = metrics([r["expected"] for r in rows], [r["actual"] for r in rows])
    output = {"corpus": corpus, "paired": report, "by_role": summary}
    prefix.with_name(prefix.name + "-score.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    assert corpus == baseline, "Corpus changed from frozen baseline."
    assert summary["negative"]["false_pending_verification"] == 0, "UNSAFE: false pending on negatives; revert candidate."
    assert report["system"]["automated_ready"] == 0
    if args.phase == "before":
        current_ids = {c["id"] for c in current if c["pair_role"] == "positive"}
        assert all(r["actual"] != "PENDING_VERIFICATION" for r in report["case_results"] if r["id"] in current_ids)
    if args.phase == "after":
        assert report["system"]["exact_status_correct"] == len(cases), report["mismatches"]
    print(
        json.dumps(
            {
                role: {
                    k: result[k]
                    for k in (
                        "cases",
                        "exact_status_correct",
                        "false_pending_verification",
                        "missed_passes",
                        "abstention_rate",
                        "expected_abstention_rate",
                    )
                }
                for role, result in summary.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
