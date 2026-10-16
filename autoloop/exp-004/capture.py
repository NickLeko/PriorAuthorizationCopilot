"""Score fixed corpus, immutable owner dev check, prior pairs and new paraphrases."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from autoloop.score import score  # noqa: E402
from engine.acceptance import normalize_drift_payload  # noqa: E402
from engine.schemas import PARequest  # noqa: E402
from engine.service import ReadinessService  # noqa: E402

DIRECTORY = ROOT / "autoloop/exp-004"
DEV_HASH = "4832267bc1ff0ac8f57aac1dd36961ef62ea4d3f15d9286662866a0981685389"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    parser.add_argument("--after", action="store_true")
    args = parser.parse_args()
    assert hashlib.sha256((DIRECTORY / "dev.json").read_bytes()).hexdigest() == DEV_HASH
    datasets = {"corpus": ROOT / "inputs/synthetic_cases.json", "dev": DIRECTORY / "dev.json"}
    for experiment in ("exp-002", "exp-003"):
        cases = [case for path in sorted((ROOT / f"autoloop/{experiment}/cases").glob("*.json")) for case in json.loads(path.read_text())]
        path = DIRECTORY / f"evidence/{experiment}-cases.json"
        path.write_text(json.dumps(cases, indent=2) + "\n")
        datasets[experiment] = path
    own = [case for path in sorted((DIRECTORY / "cases").glob("*.json")) for case in json.loads(path.read_text())]
    if own:
        path = DIRECTORY / "evidence/own-cases.json"
        path.write_text(json.dumps(own, indent=2) + "\n")
        datasets["own"] = path
    reports = {name: score(path) for name, path in datasets.items()}
    service = ReadinessService()
    dev_cases = json.loads((DIRECTORY / "dev.json").read_text())["cases"]
    requirement_misses = []
    for case in dev_cases:
        request = PARequest.model_validate(
            {k: case[k] for k in ("payer", "procedure_code", "note_text", "dx_codes", "site_of_care", "specialty")}
        )
        result = service.evaluate(request)
        actual = {item.key: item.status for item in result.results}
        if actual != case["expected_requirements"]:
            requirement_misses.append({"id": case["id"], "expected": case["expected_requirements"], "actual": actual})
    by_iteration = {}
    for path in sorted((DIRECTORY / "cases").glob("*.json")):
        cases = json.loads(path.read_text())
        report = score(path)
        by_iteration[path.stem] = report
        assert sum(case["pair_role"] == "positive" for case in cases) >= 4
        assert sum(case["pair_role"] == "negative" for case in cases) >= 4
    governance = {
        "bundle_digest": service._bundle_digest(),
        "drift": normalize_drift_payload(service.get_drift_status().model_dump(mode="json")),
        "rulebook": service.get_rulebook_status().model_dump(mode="json"),
    }
    report = {
        "label": args.label,
        "datasets": reports,
        "own_by_iteration": by_iteration,
        "dev_requirement_misses": requirement_misses,
        "governance": governance,
    }
    (DIRECTORY / f"evidence/{args.label}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for name, result in reports.items():
        assert result["system"]["false_pending_verification"] == 0, f"UNSAFE {name}: revert iteration"
        assert result["system"]["automated_ready"] == 0
    assert reports["corpus"]["system"]["exact_status_correct"] == 52
    if args.label != "baseline":
        baseline = json.loads((DIRECTORY / "evidence/baseline.json").read_text())
        assert governance == baseline["governance"]
        for name in ("corpus", "exp-002", "exp-003"):
            assert reports[name] == baseline["datasets"][name], f"Frozen report changed: {name}"
    if args.after and own:
        assert reports["own"]["system"]["exact_status_correct"] == len(own), reports["own"]["mismatches"]
    print(
        json.dumps(
            {name: {k: value for k, value in report["system"].items() if not isinstance(value, dict)} for name, report in reports.items()},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
