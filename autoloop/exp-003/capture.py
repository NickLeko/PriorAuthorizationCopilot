"""Read-only scoring gates; write evidence only under this experiment directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DIRECTORY = ROOT / "autoloop/exp-003"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("baseline", "final"))
    args = parser.parse_args()
    if args.phase == "baseline":
        # Replay both changed modules from main in memory. Never replace files
        # or switch branches; all other existing engine files stay fixed.
        import subprocess
        import types

        for name in ("note_context", "extract"):
            source = subprocess.check_output(["git", "show", f"3413381:engine/{name}.py"], cwd=ROOT, text=True)
            module = types.ModuleType(f"engine.{name}")
            module.__file__ = str(ROOT / f"engine/{name}.py")
            sys.modules[f"engine.{name}"] = module
            exec(compile(source, module.__file__, "exec"), module.__dict__)

    from autoloop.score import metrics, score
    from engine.acceptance import normalize_drift_payload
    from engine.schemas import PARequest
    from engine.service import ReadinessService

    cases = [case for path in sorted((DIRECTORY / "cases").glob("iteration-*.json")) for case in json.loads(path.read_text())]
    old_cases = [case for path in sorted((ROOT / "autoloop/exp-002/cases").glob("*.json")) for case in json.loads(path.read_text())]
    historical_path = DIRECTORY / "evidence/exp002-cases.json"
    historical_path.write_text(json.dumps(old_cases, indent=2) + "\n")
    assert len({case["id"] for case in cases}) == len(cases)
    corpus = score(ROOT / "inputs/synthetic_cases.json")
    all_cases_path = DIRECTORY / "evidence/all-cases.json"
    all_cases_path.write_text(json.dumps(cases, indent=2) + "\n")
    paired = score(all_cases_path)
    historical = score(historical_path)
    by_role = {}
    for role in ("positive", "negative"):
        rows = [row for case, row in zip(cases, paired["case_results"]) if case["pair_role"] == role]
        by_role[role] = metrics([row["expected"] for row in rows], [row["actual"] for row in rows])
    service = ReadinessService()
    governance = {
        "bundle_digest": service._bundle_digest(),
        "governance_paths": [path for path, _ in service._bundle_snapshot()],
        "drift": normalize_drift_payload(service.get_drift_status().model_dump(mode="json")),
        "rulebook": service.get_rulebook_status().model_dump(mode="json"),
    }
    # Compare complete extraction proposals and fingerprints on the frozen
    # corpus, including literal citations, rather than only status labels.
    corpus_proposals = []
    for case in json.loads((ROOT / "inputs/synthetic_cases.json").read_text()):
        request = PARequest.model_validate(
            {key: case[key] for key in ("payer", "procedure_code", "note_text", "dx_codes", "site_of_care", "specialty") if key in case}
        )
        result = service.evaluate(request)
        corpus_proposals.append(
            {
                "id": case["id"],
                "input_fingerprint": result.input_fingerprint,
                "fact_set_fingerprint": result.fact_set_fingerprint,
                "facts": result.facts,
                "evidence": {key: [span.model_dump(mode="json") for span in spans] for key, spans in result.evidence_map.items()},
                "verification_fingerprints": {item.key: item.verification_fingerprint for item in result.results},
            }
        )
    output = {
        "phase": args.phase,
        "corpus": corpus,
        "corpus_proposals": corpus_proposals,
        "paired": paired,
        "by_role": by_role,
        "exp002": historical,
        "governance": governance,
    }
    (DIRECTORY / f"evidence/{args.phase}-audit.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    assert corpus == json.loads((DIRECTORY / "evidence/baseline-corpus.json").read_text())
    assert governance == json.loads((DIRECTORY / "evidence/baseline-governance.json").read_text())
    for report in (corpus, historical):
        assert report["system"]["false_pending_verification"] == 0, "False pending: revert candidate."
        assert report["system"]["automated_ready"] == 0
    assert historical["system"]["exact_status_correct"] == 64  # Preserve the five documented exp-002 misses.
    if args.phase == "final":
        assert paired["system"]["false_pending_verification"] == 0, "False pending: revert candidate."
        assert paired["system"]["automated_ready"] == 0
        baseline = json.loads((DIRECTORY / "evidence/baseline-audit.json").read_text())
        assert corpus_proposals == baseline["corpus_proposals"], "Corpus proposals/fingerprints changed."
        assert historical == baseline["exp002"], "Historical authored results changed."
        assert paired["system"]["exact_status_correct"] == len(cases), paired["mismatches"]
    else:
        assert by_role["positive"]["missed_passes"] == by_role["positive"]["cases"]
    print(json.dumps({"phase": args.phase, "paired": paired["system"], "by_role": by_role, "governance_unchanged": True}, indent=2))


if __name__ == "__main__":
    main()
