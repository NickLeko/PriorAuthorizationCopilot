import json
from copy import deepcopy
from pathlib import Path

import pytest
from dual_extraction_helpers import synthetic_response

from engine.fact_contracts import FACT_CONTRACTS
from engine.schemas import REVIEW_REQUIRED_FACT
from experiments.dual_extraction.errors import ExperimentFailure
from experiments.dual_extraction.proposals import proposal_to_legacy
from experiments.dual_extraction.recorded import RecordingMetadata, adapt_recorded_response

FIXTURES = sorted(Path("experiments/dual_extraction/fixtures/recorded").glob("*.json"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_explicitly_hand_authored_recordings_validate_and_transport(path):
    fixture = json.loads(path.read_text())
    result = adapt_recorded_response(fixture["note_text"], fixture["recorded_response"])
    assert result.recording.origin == "hand_authored_synthetic"
    assert result.recording.model_id == "synthetic-no-model"
    assert result.proposal.source == result.recording.source
    assert len(result.recording_sha256) == 64
    facts, _ = proposal_to_legacy(result.proposal)
    assert set(facts) == set(FACT_CONTRACTS)
    assert result == adapt_recorded_response(fixture["note_text"], json.dumps(fixture["recorded_response"]))


@pytest.mark.parametrize("key", FACT_CONTRACTS)
def test_all_recorded_keys_are_required(key):
    response = synthetic_response("Synthetic note.")
    del response["facts"][key]
    with pytest.raises(ExperimentFailure, match="INVALID_RECORDED_RESPONSE"):
        adapt_recorded_response("Synthetic note.", response)


@pytest.mark.parametrize(
    "key,value",
    [
        ("back_pain_with_radiculopathy", 1),
        ("osa_diagnosis", False),
        ("osa_diagnosis", None),
        ("osa_diagnosis", REVIEW_REQUIRED_FACT),
        ("conservative_therapy_weeks", True),
        ("conservative_therapy_weeks", 6.0),
        ("conservative_therapy_weeks", "6"),
        ("conservative_therapy_weeks", -1),
        ("prior_imaging_result", "unsupported"),
        ("sleep_study_date", "2026-03-09"),
        ("ahi_documented", 22),
    ],
)
def test_recorded_values_use_exact_extractor_vocabulary(key, value):
    with pytest.raises(ExperimentFailure, match="INVALID_RECORDED_RESPONSE"):
        adapt_recorded_response("Synthetic citation.", synthetic_response("Synthetic citation.", {key: value}))


@pytest.mark.parametrize("state", ["MISSING", "NEEDS_REVIEW"])
def test_non_captured_states_require_null_without_erasing_evidence(state):
    note = "OSA?"
    response = synthetic_response(note, states={"osa_diagnosis": state})
    response["facts"]["osa_diagnosis"]["evidence"] = [{"start": 0, "end": 3, "text": "OSA"}]
    result = adapt_recorded_response(note, response)
    facts, evidence = proposal_to_legacy(result.proposal)
    assert facts["osa_diagnosis"] == (None if state == "MISSING" else REVIEW_REQUIRED_FACT)
    assert evidence["osa_diagnosis"] == response["facts"]["osa_diagnosis"]["evidence"]
    response["facts"]["osa_diagnosis"]["value"] = True
    with pytest.raises(ExperimentFailure):
        adapt_recorded_response(note, response)


@pytest.mark.parametrize("payload", [None, [], 1, "{", "null", "[]", '{"facts":{},"facts":{}}', '{"value":NaN}', '{"value":Infinity}'])
def test_malformed_responses_never_become_missing(payload):
    with pytest.raises(ExperimentFailure, match="INVALID_RECORDED_RESPONSE"):
        adapt_recorded_response("private synthetic note", payload)


def test_provider_error_is_explicit_and_diagnostics_do_not_log_payload(caplog):
    note = "PRIVATE_SYNTHETIC_NOTE_SENTINEL"
    for response in ({"error": {"message": note}}, json.dumps({"error": note})):
        with pytest.raises(ExperimentFailure, match="RECORDED_EXTRACTION_FAILURE") as caught:
            adapt_recorded_response(note, response)
        assert note not in str(caught.value)
        assert note not in repr(caught.value)
    bad = synthetic_response(note)
    bad["facts"]["osa_diagnosis"]["state"] = note
    with pytest.raises(ExperimentFailure) as caught:
        adapt_recorded_response(note, bad)
    assert note not in str(caught.value)
    assert note not in caplog.text


def test_no_citation_repair_or_truncation_and_unicode_is_exact():
    note = "😀İ. OSA."
    response = synthetic_response(note, {"osa_diagnosis": True})
    response["facts"]["osa_diagnosis"]["evidence"] = [{"start": 4, "end": 7, "text": "OSA"}]
    valid = adapt_recorded_response(note, response)
    assert proposal_to_legacy(valid.proposal)[1]["osa_diagnosis"][0]["start"] == 4
    for span in (
        {"start": 8, "end": 11, "text": "OSA"},  # UTF-8 byte offsets are not character offsets.
        {"start": "4", "end": 7, "text": "OSA"},
        {"start": True, "end": 7, "text": "OSA"},
        {"start": 4, "end": 7, "text": "osa"},
    ):
        invalid = deepcopy(response)
        invalid["facts"]["osa_diagnosis"]["evidence"] = [span]
        with pytest.raises(ExperimentFailure):
            adapt_recorded_response(note, invalid)
    for spans in ([], response["facts"]["osa_diagnosis"]["evidence"] * 11):
        invalid = deepcopy(response)
        invalid["facts"]["osa_diagnosis"]["evidence"] = spans
        with pytest.raises(ExperimentFailure):
            adapt_recorded_response(note, invalid)


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "unknown_fact",
        "missing_cell_state",
        "missing_cell_value",
        "missing_cell_evidence",
        "note_hash",
        "count",
        "origin",
        "model_type",
    ],
)
def test_recorded_structure_and_identity_are_strict(mutation):
    response = synthetic_response("OSA", {"osa_diagnosis": True})
    if mutation == "extra":
        response["confidence"] = 1.0
    elif mutation == "unknown_fact":
        response["facts"]["unsupported_fact"] = response["facts"]["osa_diagnosis"]
    elif mutation == "missing_cell_state":
        del response["facts"]["osa_diagnosis"]["state"]
    elif mutation == "missing_cell_value":
        del response["facts"]["osa_diagnosis"]["value"]
    elif mutation == "missing_cell_evidence":
        del response["facts"]["osa_diagnosis"]["evidence"]
    elif mutation == "note_hash":
        response["note_sha256"] = "0" * 64
    elif mutation == "count":
        response["evidence_counts"]["osa_diagnosis"] = 15
    elif mutation == "origin":
        response["recording"]["origin"] = "generated_by_real_model"
    else:
        response["recording"]["model_id"] = 1
    with pytest.raises(ExperimentFailure, match="INVALID_RECORDED_RESPONSE"):
        adapt_recorded_response("OSA", response)


def test_metadata_does_not_enter_proposal_snapshot_or_legacy_facts():
    response = synthetic_response("OSA", {"osa_diagnosis": True})
    first = adapt_recorded_response("OSA", response)
    response["recording"].update(model_id="synthetic-alternative", prompt_version="synthetic-v2", response_id="synthetic-two")
    second = adapt_recorded_response("OSA", response)
    assert first.recording != second.recording
    assert first.recording_sha256 != second.recording_sha256
    assert first.proposal.snapshot == second.proposal.snapshot
    assert proposal_to_legacy(first.proposal) == proposal_to_legacy(second.proposal)


def test_raw_recording_must_not_accept_validation_bypassing_model_objects():
    response = synthetic_response("OSA", {"osa_diagnosis": True})
    response["recording"] = RecordingMetadata.model_construct(**(response["recording"] | {"origin": "not_synthetic"}))
    with pytest.raises(ExperimentFailure, match="INVALID_RECORDED_RESPONSE"):
        adapt_recorded_response("OSA", response)


def test_recorded_order_and_pre_cap_counts_survive_without_repair():
    note = "OSA. " * 15
    response = synthetic_response(note, {"osa_diagnosis": True})
    response["facts"]["osa_diagnosis"]["evidence"] = [{"start": i * 5, "end": i * 5 + 3, "text": "OSA"} for i in reversed(range(10))]
    response["evidence_counts"] = {"osa_diagnosis": 15}
    result = adapt_recorded_response(note, response)
    _, evidence = proposal_to_legacy(result.proposal)
    assert evidence["osa_diagnosis"] == response["facts"]["osa_diagnosis"]["evidence"]
    assert evidence.total_counts == {"osa_diagnosis": 15}


@pytest.mark.parametrize("key", FACT_CONTRACTS)
def test_every_existing_fact_has_a_valid_cited_recorded_representation(key):
    contract = FACT_CONTRACTS[key]
    values = (0, 6) if contract.fact_kind == "duration_weeks" else contract.extractor_emittable
    for value in values:
        note = "Explicit synthetic source quotation."
        recorded = adapt_recorded_response(note, synthetic_response(note, {key: value}))
        actual = proposal_to_legacy(recorded.proposal)[0][key]
        assert type(actual) is type(value)
        assert actual == value
