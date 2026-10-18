import pytest

from engine.corrections import capture_original
from engine.fact_contracts import FACT_CONTRACTS
from engine.note_context import EvidenceMap
from engine.schemas import REVIEW_REQUIRED_FACT
from experiments.dual_extraction.proposals import ExtractionProposal, proposal_from_legacy


def missing_facts():
    return dict.fromkeys(FACT_CONTRACTS)


def test_exact_uncited_osa_reproduction_is_rejected():
    facts = missing_facts()
    facts["osa_diagnosis"] = True
    with pytest.raises(ValueError, match="retained source citation"):
        proposal_from_legacy("OSA.", (facts, {}), source="synthetic:uncited-reproduction")


@pytest.mark.parametrize("key", FACT_CONTRACTS)
def test_citation_gate_applies_to_every_captured_key_and_direct_envelopes(key):
    facts = missing_facts()
    contract = FACT_CONTRACTS[key]
    facts[key] = 1 if contract.fact_kind == "duration_weeks" else contract.extractor_emittable[0]
    note = "Synthetic quoted documentation."
    with pytest.raises(ValueError, match="retained source citation"):
        ExtractionProposal(note_text=note, source="synthetic:gate", snapshot=capture_original(facts, {}))
    evidence = {key: [{"start": 0, "end": len(note), "text": note}]}
    assert proposal_from_legacy(note, (facts, evidence), source="synthetic:gate").snapshot.content["states"][key] == "CAPTURED"


@pytest.mark.parametrize("value,state", [(None, "MISSING"), (REVIEW_REQUIRED_FACT, "NEEDS_REVIEW")])
def test_missing_and_review_evidence_semantics_are_unchanged(value, state):
    facts = missing_facts()
    facts["osa_diagnosis"] = value
    for evidence in ({}, {"osa_diagnosis": [{"start": 0, "end": 3, "text": "OSA"}]}):
        proposal = proposal_from_legacy("OSA", (facts, evidence), source="synthetic:gate")
        assert proposal.snapshot.content["states"]["osa_diagnosis"] == state
        assert proposal.snapshot.content["evidence"] == evidence


def test_count_metadata_cannot_replace_retained_citations():
    facts = missing_facts()
    facts["osa_diagnosis"] = True
    evidence = EvidenceMap({"osa_diagnosis": []})
    evidence.total_counts["osa_diagnosis"] = 15
    with pytest.raises(ValueError):
        proposal_from_legacy("OSA", (facts, evidence), source="synthetic:gate")
