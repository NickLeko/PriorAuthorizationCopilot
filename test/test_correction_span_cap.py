from pathlib import Path

import pytest
from pydantic import ValidationError
from test_corrections import NOTE, THERAPY_KEY, event, request

from engine.corrections import validate_note_evidence
from engine.decision_store import DecisionStore
from engine.schemas import CorrectionSpan
from engine.service import ReadinessService


@pytest.mark.parametrize("length", [300, 301])
def test_set_value_span_character_boundary(length, tmp_path):
    # Offsets and character counts use Python Unicode code points, not UTF-8 bytes.
    quote = "😀" * length
    note = NOTE + " " + quote
    span = {"start": len(NOTE) + 1, "end": len(note), "text": quote}
    patch = event(note, evidence_spans=[span])
    if length == 301:
        with pytest.raises(ValidationError, match="at most 300 characters each"):
            request(note, events=[patch])
        return
    service = ReadinessService()
    result = service.evaluate(request(note, events=[patch]))
    assert result.request.corrections[0].evidence_spans[0].text == quote
    text, metadata = service.generate_letter(result)
    assert not metadata["draft_blocked"]
    assert f'"{quote}"' in text  # Full quotation, never a truncated prefix.
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        store.record(result, "boundary")
        assert store.get_decision("boundary") == result


def test_overlength_whole_note_span_rejected():
    note = NOTE + " " + "x" * 300
    with pytest.raises(ValidationError, match="at most 300 characters each"):
        request(note, events=[event(note)])


def test_multiple_short_spans_accepted_even_when_total_exceeds_300(tmp_path):
    first, second = "a" * 200, "b" * 200
    note = NOTE + " " + first + " " + second
    spans = [{"start": note.index(quote), "end": note.index(quote) + len(quote), "text": quote} for quote in (first, second)]
    result = ReadinessService().evaluate(request(note, events=[event(note, evidence_spans=spans)]))
    assert [span.text for span in result.evidence_map[THERAPY_KEY]] == [first, second]
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        store.record(result, "multiple")
        assert store.get_decision("multiple") == result


def test_archive_writer_rejects_oversized_span_on_bypassed_models(tmp_path):
    note = NOTE + " " + "x" * 301
    start = len(NOTE) + 1
    short = {"start": start, "end": start + 300, "text": "x" * 300}
    result = ReadinessService().evaluate(request(note, events=[event(note, evidence_spans=[short])]))
    # model_copy bypasses frozen-model validators, as an adversarial caller can.
    oversized = CorrectionSpan(start=start, end=len(note), text="x" * 301)
    forged_event = result.request.corrections[0].model_copy(update={"evidence_spans": (oversized,)})
    with pytest.raises(ValueError, match="at most 300 characters each"):
        validate_note_evidence(forged_event, note)
    forged = result.model_copy(deep=True)
    forged.request = forged.request.model_copy(update={"corrections": [forged_event]})
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        with pytest.raises(ValidationError, match="at most 300 characters each"):
            store.record(forged, "forged")
        assert store.decision_ids() == []
        assert store.list_policies() == []


def test_canonical_correction_limits_and_single_links_are_retained():
    canonical = Path("docs/safety_and_scope.md").read_text().split("## Correction Limits\n", 1)[1].split("## Product Boundary", 1)[0]
    for limitation in (
        "source-located",
        "location integrity, not semantic support",
        "misreading of negation or borrowed qualifiers",
        "self-reported timestamp ordering",
        "not action separation, distinct reviewers, or proof of review",
        "correction at T and attestation at T+1s",
        "without backdating",
        "viewable, not replayable",
        "RESTORE_ORIGINAL",
        "not checked for recency or ordering",
        "300 Python Unicode characters",
        "Multiple spans are allowed",
        "rejected, never truncated",
        "audit comments do not enter letter reasoning",
        "no ontology, LLM or RAG",
    ):
        assert limitation in canonical
    for path in (
        "README.md",
        "EXTRACTION_CONTRACT.md",
        "LETTER_DRAFTING_CONTRACT.md",
        "docs/reviewer_guide.md",
        "FAILURE_MODES.md",
        "LIMITATIONS.md",
        "docs/policy_replay.md",
        "docs/api.md",
    ):
        assert Path(path).read_text().count("safety_and_scope.md#correction-limits") == 1
