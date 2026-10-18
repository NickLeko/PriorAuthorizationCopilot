from copy import deepcopy

import pytest
from dual_extraction_helpers import synthetic_regex, synthetic_response

from engine.corrections import capture_original
from experiments.dual_extraction.proposals import proposal_to_legacy
from experiments.dual_extraction.reconcile import reconcile
from experiments.dual_extraction.recorded import adapt_recorded_response

KEY = "cpb_0236_conservative_therapy_weeks"


def passages(note, *quotes):
    return [{"start": note.index(quote), "end": note.index(quote) + len(quote), "text": quote} for quote in quotes]


def item(record):
    return next(value for value in record.comparisons if value.key == KEY)


def test_exact_nsaid_gabapentin_disagreement_retains_both_passages():
    note = "NSAIDs for 8 weeks with no improvement. Gabapentin for 3 weeks with no improvement."
    left = synthetic_response(note, {KEY: 8}, evidence={KEY: passages(note, "NSAIDs for 8 weeks with no improvement")})
    right = synthetic_response(note, {KEY: 3}, evidence={KEY: passages(note, "Gabapentin for 3 weeks with no improvement")})
    regex, recorded = synthetic_regex(note, left), adapt_recorded_response(note, right)
    before = regex.model_dump_json(), recorded.model_dump_json()
    record = reconcile(regex, recorded)
    assert item(record).reason == "VALUE_DISAGREEMENT"
    assert item(record).disposition == "NEEDS_REVIEW"
    assert record.dual.snapshot.content["evidence"][KEY] == left["facts"][KEY]["evidence"] + right["facts"][KEY]["evidence"]
    assert item(record).evidence_source == "both"
    assert item(record).dual_citation_sources == (("regex",), ("llm",))
    assert item(record).dual_complete_citation_count == 2
    assert "COMPETING_CITATIONS_NOT_A_SHARED_INTERPRETATION" in record.dual.diagnostics
    assert record.regex == regex and record.recorded_llm == recorded
    assert before == (regex.model_dump_json(), recorded.model_dump_json())


def test_state_disagreement_combines_existing_missing_state_evidence():
    note = "NSAIDs for 8 weeks. Treatment duration not documented elsewhere."
    left = synthetic_response(note, {KEY: 8}, evidence={KEY: passages(note, "NSAIDs for 8 weeks")})
    right = synthetic_response(note, evidence={KEY: passages(note, "Treatment duration not documented elsewhere")})
    record = reconcile(synthetic_regex(note, left), adapt_recorded_response(note, right))
    assert item(record).reason == "STATE_DISAGREEMENT"
    assert item(record).evidence_source == "both"
    assert len(record.dual.snapshot.content["evidence"][KEY]) == 2


def test_disagreement_order_deduplication_and_shared_span_provenance():
    note = "NSAIDs for 8 weeks. Gabapentin for 3 weeks."
    spans = passages(note, "NSAIDs for 8 weeks", "Gabapentin for 3 weeks")
    left = synthetic_response(note, {KEY: 8}, evidence={KEY: [spans[1], spans[0]]})
    right = synthetic_response(note, {KEY: 3}, evidence={KEY: [spans[0], spans[1]]})
    record = reconcile(synthetic_regex(note, left), adapt_recorded_response(note, right))
    assert record.dual.snapshot.content["evidence"][KEY] == [spans[1], spans[0]]
    assert item(record).dual_citation_sources == (("regex", "llm"), ("regex", "llm"))
    assert record == reconcile(synthetic_regex(note, left), adapt_recorded_response(note, right))


@pytest.mark.parametrize("source_truncated", [False, True])
def test_combined_evidence_cap_and_truthful_complete_count(source_truncated):
    note = " ".join(f"Course {number} weeks." for number in range(20))
    spans = passages(note, *(f"Course {number} weeks" for number in range(20)))
    left = synthetic_response(note, {KEY: 8}, evidence={KEY: spans[:10]})
    right = synthetic_response(note, {KEY: 3}, evidence={KEY: spans[10:]})
    if source_truncated:
        left["evidence_counts"] = {KEY: 15}
    recorded_left = adapt_recorded_response(note, left)
    record = reconcile(recorded_left.proposal, adapt_recorded_response(note, right))
    facts, evidence = proposal_to_legacy(record.dual)
    assert len(evidence[KEY]) == 10
    assert evidence[KEY][:4] == [spans[0], spans[10], spans[1], spans[11]]
    assert item(record).dual_evidence_capped is True
    if source_truncated:
        assert item(record).dual_complete_citation_count is None
        assert evidence.total_counts == {}
        assert "COMBINED_CITATION_TOTAL_UNKNOWN" in record.dual.diagnostics
    else:
        assert item(record).dual_complete_citation_count == 20
        assert evidence.total_counts == {KEY: 20}
    # Existing canonical count constraints still accept the compatible projection.
    assert capture_original(facts, evidence) == record.dual.snapshot
    assert item(record).evidence_source == "both"  # Counts/provenance include both observed inputs even when the cap excludes one.


def test_agreed_capture_is_not_changed_or_unionized():
    note = "NSAIDs for 8 weeks. Gabapentin for 8 weeks."
    left = synthetic_response(note, {KEY: 8}, evidence={KEY: passages(note, "NSAIDs for 8 weeks")})
    right = deepcopy(left)
    right["facts"][KEY]["evidence"] = passages(note, "Gabapentin for 8 weeks")
    record = reconcile(synthetic_regex(note, left), adapt_recorded_response(note, right))
    assert record.dual.snapshot.content["evidence"][KEY] == left["facts"][KEY]["evidence"]
    assert item(record).evidence_source == "regex"
    assert record.jointly_captured_therapy_citation_source is None
