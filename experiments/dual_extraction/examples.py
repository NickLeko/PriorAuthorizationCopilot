"""Check immutable Phase 2 examples and reproduce the current Phase 3 example."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from engine.corrections import note_hash
from engine.fact_contracts import FACT_CONTRACTS
from engine.schemas import REVIEW_REQUIRED_FACT

from .proposals import extract_regex_proposal, proposal_from_legacy
from .reconcile import reconcile
from .recorded import adapt_recorded_response

DIRECTORY = Path(__file__).parent
NOTICE = "Hand-authored synthetic recorded response; no model was called. Structural comparison only, not clinical verification."
CURRENT_EXAMPLE = "phase3/structural-v2-reconciliation-example.json"
HISTORICAL_HASHES = {
    "phase2-recorded-proposal-example.json": "83ca3cdba476f99759a597c51ac29006170f7478f89dbaa0c118865c5ced47c0",
    "phase2-reconciliation-example.json": "e96f873a00b5d2316a63d1171977be51e32da13f220818b63fffe40c48dd4479",
}


def _proposal_view(proposal):
    return dict(
        source=proposal.source, note_text=proposal.note_text, diagnostics=list(proposal.diagnostics), snapshot=proposal.snapshot.content
    )


def _review_required_examples():
    """Two hand-authored source-role reproductions, not live regex/model captures."""
    note = "NSAIDs for 8 weeks with no improvement. Gabapentin for 3 weeks with no improvement."
    key = "cpb_0236_conservative_therapy_weeks"
    spans = [
        dict(start=note.index(quote), end=note.index(quote) + len(quote), text=quote)
        for quote in ("NSAIDs for 8 weeks with no improvement", "Gabapentin for 3 weeks with no improvement")
    ]
    output = {}
    for review_role in ("regex", "llm"):
        left = {name: None for name in FACT_CONTRACTS} | {key: REVIEW_REQUIRED_FACT if review_role == "regex" else 8}
        regex = proposal_from_legacy(note, (left, {key: [spans[0]]}), source="synthetic-regex-proposal")
        payload = dict(
            recording=dict(
                source="recorded-llm:synthetic",
                model_id="synthetic-no-model",
                prompt_version="synthetic-schema-v1",
                response_id=f"synthetic-review-{review_role}",
                origin="hand_authored_synthetic",
            ),
            note_sha256=note_hash(note),
            facts={name: dict(state="MISSING", value=None, evidence=[]) for name in FACT_CONTRACTS},
            evidence_counts={},
        )
        payload["facts"][key] = dict(
            state="NEEDS_REVIEW" if review_role == "llm" else "CAPTURED", value=None if review_role == "llm" else 3, evidence=[spans[1]]
        )
        record = reconcile(regex, adapt_recorded_response(note, payload))
        output[f"phase3/review-required-{review_role}-example.json"] = dict(
            notice="Hand-authored synthetic source-role reproduction; neither source was called.",
            **record.model_dump(mode="json"),
        )
    return output


def build_examples() -> dict[str, dict]:
    fixture = json.loads((DIRECTORY / "fixtures/recorded/duration-disagreement.json").read_text())
    # Capture each source exactly once, then preserve these same inputs in the record.
    recorded = adapt_recorded_response(fixture["note_text"], fixture["recorded_response"])
    regex = extract_regex_proposal(fixture["note_text"])
    record = reconcile(regex, recorded)
    recorded_view = dict(
        notice=NOTICE,
        recording=recorded.recording.model_dump(mode="json"),
        recording_sha256=recorded.recording_sha256,
        proposal=_proposal_view(recorded.proposal),
    )
    return _review_required_examples() | {
        CURRENT_EXAMPLE: dict(
            notice=NOTICE,
            reconciliation_version=record.reconciliation_version,
            clinical_verification=record.clinical_verification,
            regex=_proposal_view(record.regex),
            recorded_llm=recorded_view,
            dual=_proposal_view(record.dual),
            comparisons=[item.model_dump(mode="json") for item in record.comparisons],
            jointly_captured_therapy_citation_source=record.jointly_captured_therapy_citation_source,
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DIRECTORY / "artifacts")
    args = parser.parse_args(argv)
    for name, digest in HISTORICAL_HASHES.items():
        path = DIRECTORY / "artifacts" / name
        if not path.exists() or sha256(path.read_bytes()).hexdigest() != digest:
            print("Historical Phase 2 examples differ.")
            return 1
    for name, example in build_examples().items():
        path = args.output_dir / name
        encoded = json.dumps(example, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encoded)
        elif not path.exists() or path.read_text() != encoded:
            print("Synthetic Phase 3 example differs.")
            return 1
    print("Historical Phase 2 examples match. " + ("Phase 3 example written." if args.write else "Phase 3 example matches."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
