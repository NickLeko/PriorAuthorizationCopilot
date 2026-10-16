"""Compare every exp-002 input against the original engine and current engine.

Baseline mode loads only the original extractor from git into this process;
both modes then use the unchanged public-service scorer. No checkout or file
replacement is involved. All other engine files must be baseline-identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "67f1f3ccaf1ccdbd74b8c4b3a58620ae3c08209a"
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("baseline", "current"))
    args = parser.parse_args()
    changed = subprocess.check_output(["git", "diff", "--name-only", BASE, "--", "engine"], cwd=ROOT, text=True).splitlines()
    assert changed == ["engine/extract.py"], changed
    if args.mode == "baseline":
        source = subprocess.check_output(["git", "show", f"{BASE}:engine/extract.py"], cwd=ROOT, text=True)
        module = types.ModuleType("engine.extract")
        module.__file__ = str(ROOT / "engine/extract.py")
        sys.modules["engine.extract"] = module
        exec(compile(source, module.__file__, "exec"), module.__dict__)
    else:
        source = (ROOT / "engine/extract.py").read_text()

    from autoloop.score import metrics, score

    directory = ROOT / "autoloop/exp-002"
    cases = [case for path in sorted((directory / "cases").glob("*.json")) for case in json.loads(path.read_text())]
    assert len({c["id"] for c in cases}) == len(cases)
    case_path = directory / "evidence/final-all-cases.json"
    case_path.write_text(json.dumps(cases, indent=2) + "\n")
    report = score(case_path)
    by_role = {}
    for role in ("positive", "negative"):
        rows = [r for c, r in zip(cases, report["case_results"]) if c["pair_role"] == role]
        by_role[role] = metrics([r["expected"] for r in rows], [r["actual"] for r in rows])
    corpus = score(ROOT / "inputs/synthetic_cases.json")
    assert corpus == json.loads((directory / "evidence/baseline-corpus.json").read_text())
    assert report["system"]["false_pending_verification"] == 0
    assert report["system"]["automated_ready"] == 0
    legacy = score(ROOT / "autoloop/resume-all-authored-cases.json")
    assert legacy == json.loads((ROOT / "autoloop/evidence/iteration-7-expanded.json").read_text())
    output = {
        "mode": args.mode,
        "baseline_commit": BASE,
        "extractor_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "all_authored": report,
        "by_role": by_role,
        "corpus": corpus,
        "exp001_legacy": legacy,
    }
    (directory / f"evidence/final-{args.mode}-audit.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {"mode": args.mode, "system": report["system"], "canary": report["always_cannot_determine_canary"], "by_role": by_role},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
