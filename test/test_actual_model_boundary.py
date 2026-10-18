"""Simulated actual-origin capture only: every byte here is hand-authored."""

import json
from copy import deepcopy
from hashlib import sha256

import pytest
from dual_extraction_helpers import synthetic_response
from test_raw_response_attempts import attempt_manifest, case_attempts

from engine.decision_store import DecisionStore
from experiments.dual_extraction import runner
from experiments.dual_extraction.errors import ExperimentFailure
from experiments.dual_extraction.recorded import RecordingMetadata, adapt_recorded_response

NOTE = "😀İ. OSA."


def bare_response(note=NOTE):
    response = synthetic_response(note, {"osa_diagnosis": True})
    start = note.index("OSA")
    response["facts"]["osa_diagnosis"]["evidence"] = [dict(start=start, end=start + 3, text="OSA")]
    return {key: response[key] for key in ("facts", "evidence_counts")}


def metadata():
    return RecordingMetadata(
        source="simulated-capture",
        model_id="simulated-model",
        prompt_version="simulated-prompt-v1",
        response_id="simulated-response-id",
        origin="actual_model_response",
    )


def simulated_manifest(tmp_path, kinds):
    path, manifest = attempt_manifest(tmp_path, kinds)
    manifest["population"] = "simulated_actual_model_capture"
    for ref in manifest["attempts"]:
        ref["recording"]["origin"] = "actual_model_response"
        stored = tmp_path / ref["path"]
        if stored.exists() and ref["outcome"] == "response":
            payload = json.loads(stored.read_bytes())
            stored.write_bytes(json.dumps({key: payload[key] for key in ("facts", "evidence_counts")}, ensure_ascii=False).encode())
            ref["stored_sha256"] = sha256(stored.read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest))
    return path, manifest


def test_bare_actual_style_response_accepts_separate_trusted_identity_without_mutation():
    body = bare_response()
    before = deepcopy(body)
    result = adapt_recorded_response(NOTE, body, metadata=metadata())
    assert body == before
    assert result.recording == metadata()
    assert result.proposal.source == "simulated-capture"
    assert result.proposal.snapshot.content["evidence"]["osa_diagnosis"] == body["facts"]["osa_diagnosis"]["evidence"]
    assert result.proposal.snapshot.content["facts"]["osa_diagnosis"] is True
    assert not ({"recording", "note_sha256"} & set(body))


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_note",
        "offset",
        "fence",
        "prose",
        "malformed",
        "missing_key",
        "extra_key",
        "wrong_type",
        "unsupported_value",
        "uncited",
        "metadata_in_body",
        "duplicate_json",
    ],
)
def test_actual_content_rejections_are_strict_without_repair(mutation):
    body = bare_response()
    note = NOTE
    if mutation == "wrong_note":
        note = "Nothing about OSA here."
    elif mutation == "offset":
        body["facts"]["osa_diagnosis"]["evidence"][0].update(start=8, end=11)  # UTF-8 bytes, not Python [4,7)
    elif mutation == "missing_key":
        body["facts"].pop("ahi_documented")
    elif mutation == "extra_key":
        body["facts"]["invented_key"] = dict(state="MISSING", value=None, evidence=[])
    elif mutation == "wrong_type":
        body["facts"]["osa_diagnosis"]["value"] = "true"
    elif mutation == "unsupported_value":
        body["facts"]["osa_diagnosis"]["value"] = False
    elif mutation == "uncited":
        body["facts"]["osa_diagnosis"]["evidence"] = []
    elif mutation == "metadata_in_body":
        body["recording"] = metadata().model_dump()
    text = json.dumps(body, ensure_ascii=False)
    if mutation == "fence":
        text = "```json\n" + text + "\n```"
    elif mutation == "prose":
        text = "Here is the result: " + text
    elif mutation == "malformed":
        text = text[:-1]
    elif mutation == "duplicate_json":
        text = text[:-1] + ',"facts":{}}'
    with pytest.raises(ExperimentFailure, match="INVALID_RECORDED_RESPONSE"):
        adapt_recorded_response(note, text, metadata=metadata())


def test_runner_preserves_bare_bytes_and_manifest_identity_no_archives_or_recapture(tmp_path, monkeypatch):
    import engine.extract
    import engine.service

    path, manifest = simulated_manifest(tmp_path, ["valid", "offset", "provider", "missing", "valid", "valid", "valid"])
    refs = manifest["attempts"]
    # A missing provider response ID is a capture identity error, not a model schema error.
    refs[4]["recording"]["response_id"] = None
    refs[5]["note_sha256"] = "0" * 64
    raw = tmp_path / refs[6]["path"]
    raw.write_bytes(raw.read_bytes() + b"CHANGED")
    path.write_text(json.dumps(manifest))
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}

    def forbidden(*args, **kwargs):
        raise AssertionError("Recapture or archive write")

    monkeypatch.setattr(engine.extract, "extract_facts", forbidden)
    monkeypatch.setattr(engine.service, "extract_facts", forbidden)
    monkeypatch.setattr(DecisionStore, "record", forbidden)
    report = runner.build_report(manifest_path=path)
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}
    assert report["input_population"] == "simulated_actual_model_capture"
    assert report["provider_outcomes_authenticated"] is False
    cases = case_attempts(report)
    assert {case["attempt_status"] for case in cases} == {
        "VALID_RESPONSE",
        "INVALID_RESPONSE",
        "EXTRACTION_FAILURE",
        "MISSING_RECORDING",
        "RECORDING_IDENTITY_FAILURE",
        "RECORDING_NOTE_MISMATCH",
        "STORED_FILE_INTEGRITY_FAILURE",
    }
    accounting = report["response_accounting"]["synthetic_raw_demonstration"]
    assert accounting["attempted_cases"] == 7
    assert accounting["invalid_recorded_response_rate"]["numerator"] == 1
    assert accounting["invalid_recorded_response_rate"]["denominator"] == 2
    assert accounting["end_to_end_usable_response_rate"]["numerator"] == 1
    assert accounting["end_to_end_usable_response_rate"]["denominator"] == 7
    assert accounting["capture_identity_failures"] == 1
    assert accounting["note_identity_failures"] == 1
    assert report["response_accounting"]["actual_model"]["attempted_cases"] == 0
    valid = next(case for case in cases if case["attempt_status"] == "VALID_RESPONSE")
    assert valid["comparison"]["recorded_llm"]["recording"] == refs[0]["recording"]
    assert not valid["comparison"]["clinical_verification"]
    for result in valid["evaluations"].values():
        assert not result["submission_readiness"]
        assert all(item["verification"]["state"] == "UNVERIFIED" for item in result["results"])


def test_legacy_external_identity_mismatch_is_a_capture_failure(tmp_path):
    path, manifest = attempt_manifest(tmp_path, ["valid"])
    manifest["attempts"][0]["recording"]["response_id"] = "wrong-capture-identity"
    path.write_text(json.dumps(manifest))
    report = runner.build_report(manifest_path=path)
    case = case_attempts(report)[0]
    assert case["attempt_status"] == "RECORDING_IDENTITY_FAILURE"
    stats = report["response_accounting"]["synthetic_raw_demonstration"]
    assert stats["invalid_responses"] == 0
    assert stats["invalid_recorded_response_rate"]["denominator"] == 0
    assert stats["end_to_end_usable_response_rate"]["denominator"] == 1


def test_declared_provider_failure_with_valid_response_bytes_is_not_authenticated(tmp_path):
    path, manifest = attempt_manifest(tmp_path, ["valid"])
    manifest["attempts"][0]["outcome"] = "extraction_failure"
    path.write_text(json.dumps(manifest))
    report = runner.build_report(manifest_path=path)
    case = case_attempts(report)[0]
    assert case["attempt_status"] == "EXTRACTION_FAILURE"
    assert case["comparison"] is None and case["evaluations"] is None
    assert report["provider_outcomes_authenticated"] is False
    stats = report["response_accounting"]["synthetic_raw_demonstration"]
    assert stats["extraction_failures"] == 1
    assert stats["invalid_recorded_response_rate"]["denominator"] == 0
    assert stats["end_to_end_usable_response_rate"]["denominator"] == 1


def test_committed_bare_examples_are_simulated_and_keep_raw_integrity():
    path = runner.DIRECTORY / "fixtures/actual-model-boundary/manifest.json"
    manifest = json.loads(path.read_text())
    before = {ref["path"]: (path.parent / ref["path"]).read_bytes() for ref in manifest["attempts"]}
    assert all(set(json.loads(data)) == {"facts", "evidence_counts"} for data in before.values())
    report = runner.build_report(manifest_path=path)
    assert "no model was called" in report["notice"]
    stats = report["response_accounting"]["synthetic_raw_demonstration"]
    assert stats["attempted_cases"] == 2
    assert stats["valid_adapted_responses"] == stats["invalid_responses"] == 1
    assert stats["invalid_recorded_response_rate"]["denominator"] == 2
    assert stats["end_to_end_usable_response_rate"]["denominator"] == 2
    assert report["response_accounting"]["actual_model"]["attempted_cases"] == 0
    assert before == {ref["path"]: (path.parent / ref["path"]).read_bytes() for ref in manifest["attempts"]}
