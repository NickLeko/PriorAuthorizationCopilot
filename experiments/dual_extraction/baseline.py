"""Explicit capture/check of observed v2.7.0 synthetic behavior, not clinical truth."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from engine import __version__
from engine.acceptance import ACCEPTANCE_GOVERNANCE_NOW
from engine.config import load_app_config
from engine.corrections import capture_original, note_hash
from engine.demo_cases import demo_case_to_request, load_demo_cases
from engine.extract import extract_facts
from engine.policies import canonical_json
from engine.schemas import REVIEW_REQUIRED_FACT, PARequest
from engine.service import ReadinessService

RELEASE_COMMIT = "5d7a03f646eccd70e69bfc32f3281057b3bf6b54"
DEFAULT_OUTPUT = Path(__file__).parent / "artifacts" / "regex-v2.7.0.jsonl"
INPUT_SOURCES = (
    "inputs/synthetic_cases.json",
    "EXTRACTION_CONTRACT.md",
    "test/fixtures/v210_independent.json",
    "inputs/replay/cases.json",
)


def case_inputs(root: Path) -> list[dict]:
    """Keep source order, identifiers, notes and annotations; do not interpret labels."""
    cases = []

    def append(source, identifier, note, request, known_failure=None):
        cases.append(dict(case_id=f"{source}#{identifier}", source=source, note=note, request=request, known_failure=known_failure))

    for case in load_demo_cases(root / INPUT_SOURCES[0]):
        append(INPUT_SOURCES[0], case.id, case.note_text, demo_case_to_request(case))
    examples = re.search(r"```json\n(.*?)\n```", (root / INPUT_SOURCES[1]).read_text(), re.S)
    if examples is None:
        raise ValueError("Extraction contract JSON examples were not found.")
    for case in json.loads(examples[1]):
        request = PARequest(payer="Aetna", procedure_code=case["procedure"], note_text=case["note"]) if "procedure" in case else None
        append(INPUT_SOURCES[1], case["id"], case["note"], request, case.get("known_failure"))
    for case in json.loads((root / INPUT_SOURCES[2]).read_text()):
        request = PARequest(payer="Aetna", procedure_code=case["procedure"], note_text=case["note"])
        append(INPUT_SOURCES[2], case["id"], case["note"], request)
    for case in json.loads((root / INPUT_SOURCES[3]).read_text()):
        request = PARequest.model_validate(case["request"])
        append(INPUT_SOURCES[3], case["id"], request.note_text, request)
    return cases


def normalize_evaluation(payload: dict) -> dict:
    """Only run identity and wall-clock audit timestamps are volatile here."""
    normalized = deepcopy(payload)
    for audit in (normalized["audit_trail"], normalized["report"]["audit_trail"]):
        audit["run_id"] = "__RUN_ID__"
        audit["timestamp_utc"] = "__TIMESTAMP_UTC__"
    return normalized


def build_baseline(repo_root: Path) -> list[dict]:
    root = repo_root.resolve()
    cases = case_inputs(root)
    service = ReadinessService(load_app_config(root), utc_now_provider=lambda: ACCEPTANCE_GOVERNANCE_NOW)
    records = []
    for case in cases:
        request = case["request"]
        if request is not None:
            # Reuse the service's captured extraction instead of extracting twice.
            result = service.evaluate(request)
            snapshot = result.original_snapshot.content
            evaluation = normalize_evaluation(result.model_dump(mode="json"))
        else:
            snapshot = capture_original(*extract_facts(case["note"])).content
            evaluation = None  # The source example declares no evaluation scope.
        facts = {
            key: REVIEW_REQUIRED_FACT if snapshot["states"][key] == "NEEDS_REVIEW" else value for key, value in snapshot["facts"].items()
        }
        records.append(
            dict(
                case_id=case["case_id"],
                source=case["source"],
                note_text=case["note"],
                note_sha256=note_hash(case["note"]),
                request_metadata=request.model_dump(mode="json", exclude={"note_text"}) if request is not None else None,
                facts=facts,
                fact_types={key: type(value).__name__ for key, value in facts.items()},
                states=snapshot["states"],
                evidence=snapshot["evidence"],
                evidence_counts=snapshot.get("evidence_counts", {}),
                known_failure=case["known_failure"],
                evaluation=evaluation,
            )
        )
    manifest = dict(
        baseline_schema_version=1,
        reference_release_commit=RELEASE_COMMIT,
        engine_version=__version__,
        extraction_source=f"regex:{__version__}",
        governance_clock=ACCEPTANCE_GOVERNANCE_NOW.isoformat(),
        purpose="Observed synthetic regression behavior; no clinical gold labels or accuracy claim.",
        case_count=len(records),
        evaluation_count=sum(record["evaluation"] is not None for record in records),
        source_counts=dict(Counter(case["source"] for case in cases)),
        input_sha256={source: sha256((root / source).read_bytes()).hexdigest() for source in INPUT_SOURCES},
    )
    return [manifest, *records]


def encode_baseline(records: list[dict]) -> str:
    """One canonical JSON record per line; citation list order remains significant."""
    return "".join(canonical_json(record) + "\n" for record in records)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="Explicitly regenerate the separate experimental baseline.")
    action.add_argument("--check", action="store_true", help="Compare without writing any artifacts.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    encoded = encode_baseline(build_baseline(args.repo_root))
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
        print(f"Wrote experimental baseline: {args.output}")
        return 0
    if not args.output.exists() or args.output.read_text() != encoded:
        print(f"Experimental baseline differs: {args.output}")
        return 1
    print(f"Experimental baseline matches: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
