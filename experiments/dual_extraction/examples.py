"""Reproduce two fixed synthetic review artifacts; not a comparison runner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .proposals import extract_regex_proposal
from .reconcile import reconcile
from .recorded import adapt_recorded_response

DIRECTORY = Path(__file__).parent
NOTICE = "Hand-authored synthetic recorded response; no model was called. Structural comparison only, not clinical verification."


def _proposal_view(proposal):
    return dict(
        source=proposal.source, note_text=proposal.note_text, diagnostics=list(proposal.diagnostics), snapshot=proposal.snapshot.content
    )


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
    return {
        "phase2-recorded-proposal-example.json": recorded_view,
        "phase2-reconciliation-example.json": dict(
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
    for name, example in build_examples().items():
        path = args.output_dir / name
        encoded = json.dumps(example, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encoded)
        elif not path.exists() or path.read_text() != encoded:
            print("Synthetic Phase 2 examples differ.")
            return 1
    print("Synthetic Phase 2 examples written." if args.write else "Synthetic Phase 2 examples match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
