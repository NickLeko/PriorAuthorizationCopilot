"""Retrospective common-input comparison against main, with sources loaded in memory."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
BASE = "89a1500e1f3a0888e977ab0dde7cbfd21a26e8c7"
DIRECTORY = ROOT / "autoloop/exp-004"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("baseline", "current"))
    args = parser.parse_args()
    source_hashes = {}
    for name in ("note_context", "extract"):
        path = ROOT / f"engine/{name}.py"
        source = subprocess.check_output(["git", "show", f"{BASE}:engine/{name}.py"], cwd=ROOT, text=True)
        if args.mode == "baseline":
            module = types.ModuleType(f"engine.{name}")
            module.__file__ = str(path)
            sys.modules[f"engine.{name}"] = module
            exec(compile(source, module.__file__, "exec"), module.__dict__)
        else:
            source = path.read_text()
        source_hashes[name] = hashlib.sha256(source.encode()).hexdigest()

    from autoloop.score import score
    from engine.schemas import PARequest
    from engine.service import ReadinessService

    cases = [case for path in sorted((DIRECTORY / "cases").glob("*.json")) for case in json.loads(path.read_text())]
    path = DIRECTORY / "evidence/own-cases.json"
    assert json.loads(path.read_text()) == cases
    own = score(path)
    dev = score(DIRECTORY / "dev.json")
    corpus = score(ROOT / "inputs/synthetic_cases.json")
    service = ReadinessService()
    proposals = []
    for case in json.loads((ROOT / "inputs/synthetic_cases.json").read_text()):
        result = service.evaluate(
            PARequest.model_validate(
                {key: case[key] for key in ("payer", "procedure_code", "note_text", "dx_codes", "site_of_care", "specialty") if key in case}
            )
        )
        proposals.append(
            {
                "id": case["id"],
                "facts": result.facts,
                "states": result.captured_fact_states,
                "evidence": {key: [span.model_dump(mode="json") for span in spans] for key, spans in result.evidence_map.items()},
                "input_fingerprint": result.input_fingerprint,
                "fact_set_fingerprint": result.fact_set_fingerprint,
                "verification_fingerprints": {item.key: item.verification_fingerprint for item in result.results},
            }
        )
    output = {"mode": args.mode, "source_hashes": source_hashes, "own": own, "dev": dev, "corpus": corpus, "corpus_proposals": proposals}
    (DIRECTORY / f"evidence/final-{args.mode}-audit.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    for report in (own, dev, corpus):
        assert report["system"]["false_pending_verification"] == 0
        assert report["system"]["automated_ready"] == 0
    if args.mode == "current":
        baseline = json.loads((DIRECTORY / "evidence/final-baseline-audit.json").read_text())
        assert proposals == baseline["corpus_proposals"], "Corpus proposals/fingerprints changed."
        assert own["system"]["exact_status_correct"] == len(cases)
        assert dev["system"]["exact_status_correct"] == 27
    print(json.dumps({"mode": args.mode, "own": own["system"], "dev": dev["system"], "corpus_proposals_checked": len(proposals)}, indent=2))


if __name__ == "__main__":
    main()
