from copy import deepcopy
from pathlib import Path

import pytest

from engine.corrections import capture_original
from engine.extract import extract_facts
from engine.fact_contracts import FACT_CONTRACTS
from engine.note_context import MAX_EVIDENCE_SPANS, EvidenceMap
from engine.schemas import REVIEW_REQUIRED_FACT
from experiments.dual_extraction import proposals
from experiments.dual_extraction.baseline import case_inputs

CASES = case_inputs(Path.cwd())


def assert_legacy_equal(left, right):
    # Existing canonical snapshots sort mapping keys. Citation list order, exact
    # scalar types and pre-cap counts are the observable extraction contract.
    assert left == right
    assert {key: type(value) for key, value in left[0].items()} == {key: type(value) for key, value in right[0].items()}
    assert left[1].total_counts == right[1].total_counts
    assert capture_original(*left) == capture_original(*right)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["case_id"])
def test_every_frozen_input_survives_lossless_regex_round_trip(case):
    legacy = extract_facts(case["note"])
    proposal = proposals.proposal_from_legacy(case["note"], legacy, source="regex:2.7.0")
    restored = proposals.proposal_to_legacy(proposal)
    assert_legacy_equal(legacy, restored)
    assert set(proposal.snapshot.content["facts"]) == set(FACT_CONTRACTS)
    assert proposals.extract_regex_proposal(case["note"]) == proposal
    # JSON transport must preserve exact scalar types and citation list order too.
    decoded = proposals.ExtractionProposal.model_validate_json(proposal.model_dump_json())
    assert_legacy_equal(legacy, proposals.proposal_to_legacy(decoded))


def test_false_missing_and_review_remain_separate():
    note = "Low back pain without radiculopathy. PT for 6 weeks. PT for 8 weeks."
    proposal = proposals.extract_regex_proposal(note)
    snapshot = proposal.snapshot.content
    assert snapshot["facts"]["back_pain_with_radiculopathy"] is False
    assert snapshot["states"]["back_pain_with_radiculopathy"] == "CAPTURED"
    assert snapshot["states"]["ahi_documented"] == "MISSING"
    assert snapshot["states"]["conservative_therapy_weeks"] == "NEEDS_REVIEW"
    restored, _ = proposals.proposal_to_legacy(proposal)
    assert restored["ahi_documented"] is None
    assert restored["conservative_therapy_weeks"] == REVIEW_REQUIRED_FACT


@pytest.mark.parametrize(
    "key,value",
    [
        ("back_pain_with_radiculopathy", 1),
        ("back_pain_with_radiculopathy", "true"),
        ("conservative_therapy_weeks", True),
        ("conservative_therapy_weeks", 6.0),
        ("conservative_therapy_weeks", "6"),
        ("conservative_therapy_weeks", -1),
        ("prior_imaging_result", "new-category"),
        ("osa_diagnosis", False),  # Reviewer vocabulary must not leak into extraction.
        ("sleep_study_date", "2026-03-09"),
        ("ahi_documented", 22),
        ("neuro_red_flags_documented", False),
    ],
)
def test_invalid_fact_representations_are_rejected(key, value):
    facts, evidence = extract_facts("")
    facts[key] = value
    with pytest.raises(ValueError):
        proposals.proposal_from_legacy("", (facts, evidence), source="recorded:test")


@pytest.mark.parametrize("key", list(FACT_CONTRACTS))
def test_missing_keys_are_rejected(key):
    facts, evidence = extract_facts("")
    facts.pop(key)
    with pytest.raises(ValueError, match="fact keys"):
        proposals.proposal_from_legacy("", (facts, evidence), source="test")


def test_unknown_keys_are_rejected():
    facts, evidence = extract_facts("")
    facts["metadata"] = "must stay separate"
    with pytest.raises(ValueError, match="fact keys"):
        proposals.proposal_from_legacy("", (facts, evidence), source="test")


@pytest.mark.parametrize(
    "span",
    [
        {"start": -1, "end": 3, "text": "OSA"},
        {"start": 0, "end": 4, "text": "OSA"},
        {"start": 0, "end": 3, "text": "osa"},
        {"start": True, "end": 3, "text": "SA"},
        {"start": "0", "end": 3, "text": "OSA"},
        {"start": 0.0, "end": 3, "text": "OSA"},
        {"start": 2, "end": 1, "text": "S"},
        {"start": 0, "end": 0, "text": ""},
        {"start": 0, "end": 3, "text": "OSA", "extra": "unsupported"},
    ],
)
def test_invalid_citation_representations_are_rejected(span):
    facts, _ = extract_facts("OSA")
    with pytest.raises(ValueError):
        proposals.proposal_from_legacy("OSA", (facts, {"osa_diagnosis": [span]}), source="test")


def test_citation_order_is_preserved_even_when_not_sorted_by_offset():
    note = "OSA. OSA."
    facts, evidence = extract_facts(note)
    evidence["osa_diagnosis"] = [{"start": 5, "end": 8, "text": "OSA"}, {"start": 0, "end": 3, "text": "OSA"}]
    proposal = proposals.proposal_from_legacy(note, (facts, evidence), source="test")
    assert_legacy_equal((facts, evidence), proposals.proposal_to_legacy(proposal))


def test_unicode_and_multiple_fact_citations_remain_associated():
    note = "😀İ. OSA. Sleep study completed 2024-05-18. AHI 22. PT for 6 weeks. PT for 8 weeks."
    proposal = proposals.extract_regex_proposal(note)
    facts, evidence = proposals.proposal_to_legacy(proposal)
    assert facts["conservative_therapy_weeks"] == REVIEW_REQUIRED_FACT
    assert len(evidence["conservative_therapy_weeks"]) == 2
    assert evidence["osa_diagnosis"][0]["start"] == note.index("OSA")
    for spans in evidence.values():
        for span in spans:
            assert note[span["start"] : span["end"]] == span["text"]


def test_truncation_counts_survive_without_recounting_capped_spans():
    note = " ".join(f"PT for {weeks} weeks." for weeks in range(1, 16))
    legacy = extract_facts(note)
    assert legacy[1].total_counts["conservative_therapy_weeks"] == 15
    proposal = proposals.proposal_from_legacy(note, legacy, source="test")
    assert len(proposal.snapshot.content["evidence"]["conservative_therapy_weeks"]) == MAX_EVIDENCE_SPANS
    assert_legacy_equal(legacy, proposals.proposal_to_legacy(proposal))


@pytest.mark.parametrize("count", [True, 10, 10.5, "15", -1])
def test_invalid_truncation_counts_are_rejected(count):
    note = " ".join(f"PT for {weeks} weeks." for weeks in range(1, 16))
    facts, evidence = extract_facts(note)
    evidence.total_counts["conservative_therapy_weeks"] = count
    with pytest.raises(ValueError):
        proposals.proposal_from_legacy(note, (facts, evidence), source="test")


def test_uncapped_or_unknown_evidence_and_inconsistent_states_are_rejected():
    note = "OSA."
    facts, evidence = extract_facts(note)
    for mapping in ({"unknown": []}, {"osa_diagnosis": evidence["osa_diagnosis"] * 11}):
        with pytest.raises(ValueError):
            proposals.proposal_from_legacy(note, (facts, mapping), source="test")
    proposal = proposals.extract_regex_proposal(note)
    snapshot = proposal.snapshot.content
    snapshot["states"]["osa_diagnosis"] = "MISSING"
    from engine.policies import canonical_json, content_hash
    from engine.schemas import OriginalProposal

    invalid = OriginalProposal(snapshot_json=canonical_json(snapshot), content_hash=content_hash(snapshot))
    with pytest.raises(ValueError):
        proposals.ExtractionProposal(note_text=note, source="test", snapshot=invalid)


def test_source_and_diagnostics_are_separate_and_round_trips_are_fresh():
    legacy = extract_facts("OSA.")
    before = deepcopy(legacy)
    proposal = proposals.proposal_from_legacy("OSA.", legacy, source="recorded:fixture-v1", diagnostics=("fixture_only",))
    assert proposal.source == "recorded:fixture-v1"
    assert proposal.diagnostics == ("fixture_only",)
    assert proposal.snapshot == capture_original(*legacy)
    first = proposals.proposal_to_legacy(proposal)
    first[0]["osa_diagnosis"] = None
    first[1]["osa_diagnosis"][0]["text"] = "mutated"
    first[1].total_counts["osa_diagnosis"] = 20
    assert_legacy_equal(before, proposals.proposal_to_legacy(proposal))
    assert_legacy_equal(before, legacy)
    assert isinstance(proposals.proposal_to_legacy(proposal)[1], EvidenceMap)


@pytest.mark.parametrize("source", ["", " ", " regex", 1])
def test_source_identity_is_required_without_coercion(source):
    with pytest.raises(ValueError):
        proposals.proposal_from_legacy("", extract_facts(""), source=source)


def test_outbound_adapter_revalidates_bypassed_model_copies():
    proposal = proposals.extract_regex_proposal("OSA")
    invalid = proposal.model_copy(update={"note_text": "xxx"})
    with pytest.raises(ValueError):
        proposals.proposal_to_legacy(invalid)


def test_nested_snapshot_model_copy_cannot_bypass_proposal_validation():
    proposal = proposals.extract_regex_proposal("OSA")
    invalid = proposal.snapshot.model_copy(update={"content_hash": "0" * 64})
    with pytest.raises(ValueError, match="content hash"):
        proposals.ExtractionProposal(note_text="OSA", source="test", snapshot=invalid)


def test_regex_adapter_calls_existing_extraction_once(monkeypatch):
    calls = []

    def capture(note):
        calls.append(note)
        return extract_facts(note)

    monkeypatch.setattr(proposals, "extract_facts", capture)
    proposal = proposals.extract_regex_proposal("OSA")
    proposals.proposal_to_legacy(proposal)
    assert calls == ["OSA"]
