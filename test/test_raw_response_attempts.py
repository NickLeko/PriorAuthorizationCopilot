"""All attempts here are hand-authored simulations, never actual model calls."""

import json
from copy import deepcopy
from hashlib import sha256

import pytest
from dual_extraction_helpers import synthetic_response

from engine.corrections import note_hash
from engine.decision_store import DecisionStore
from experiments.dual_extraction import runner
from experiments.dual_extraction.errors import ExperimentFailure

NOTICE = "Offline response attempts; provenance is declared per population."


def attempt_manifest(tmp_path, kinds):
    rows = runner.load_frozen_baseline()[1:]
    unicode = next(row for row in rows if row["case_id"] == "EXTRACTION_CONTRACT.md#unicode")
    rows = [unicode] + [row for row in rows if row != unicode]
    attempts = []
    for index, kind in enumerate(kinds):
        row = rows[index]
        note = row["note_text"]
        payload = synthetic_response(note, {"osa_diagnosis": True})
        payload["recording"]["response_id"] = f"simulated-response-{index}"
        if kind == "offset":
            payload["facts"]["osa_diagnosis"]["evidence"] = [{"start": 4, "end": 7, "text": "OSA"}]  # UTF-8 offsets, not Python offsets
        elif kind == "type":
            payload["facts"]["osa_diagnosis"]["value"] = "true"
        elif kind == "uncited":
            payload["facts"]["osa_diagnosis"]["evidence"] = []
        metadata = deepcopy(payload["recording"])
        if kind == "provider":
            payload = {"error": {"code": "simulated-provider-failure", "message": "PRIVATE_SIMULATED_PAYLOAD"}}
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode()
        if kind == "malformed":
            data = b"{ PRIVATE_SIMULATED_PAYLOAD"
        path = tmp_path / f"attempt-{index}.json"
        if kind != "missing":
            path.write_bytes(data)
        attempts.append(
            dict(
                case_id=row["case_id"],
                attempt_id=f"simulated-attempt-{index}",
                path=path.name,
                stored_sha256=sha256(data).hexdigest(),
                note_sha256=note_hash(note),
                recording=metadata,
                provider_id="synthetic-no-provider",
                outcome="extraction_failure" if kind == "provider" else "response",
            )
        )
        if kind == "integrity":
            path.write_bytes(data + b" ")
    manifest = dict(
        schema_version=2,
        notice=NOTICE,
        population="synthetic_raw_demonstration",
        selected_attempted_case_ids=[a["case_id"] for a in attempts],
        attempts=attempts,
    )
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, manifest


def case_attempts(report):
    return [case for case in report["cases"] if case.get("attempt") is not None]


def test_raw_attempts_reach_adapter_and_all_outcomes_enter_denominators(tmp_path, monkeypatch):
    import experiments.dual_extraction.recorded as recorded

    path, _ = attempt_manifest(tmp_path, ["valid", "offset", "type", "uncited", "provider", "missing", "integrity", "malformed"])
    calls = []
    original = recorded.adapt_recorded_response

    def adapt(note, payload):
        calls.append(payload)
        return original(note, payload)

    monkeypatch.setattr(recorded, "adapt_recorded_response", adapt)
    report = runner.build_report(manifest_path=path)
    statuses = {case["attempt"]["attempt_id"]: case["attempt_status"] for case in case_attempts(report)}
    assert list(statuses.values()).count("VALID_RESPONSE") == 1
    assert list(statuses.values()).count("INVALID_RESPONSE") == 4
    assert set(statuses.values()) == {
        "VALID_RESPONSE",
        "INVALID_RESPONSE",
        "EXTRACTION_FAILURE",
        "MISSING_RECORDING",
        "STORED_FILE_INTEGRITY_FAILURE",
    }
    assert len(calls) == 5  # byte integrity must pass first; provider errors aren't adaptation requests
    accounting = report["response_accounting"]["synthetic_raw_demonstration"]
    assert accounting["attempted_cases"] == 8
    assert accounting["responses_received"] == 5
    assert accounting["valid_adapted_responses"] == 1
    assert accounting["invalid_responses"] == 4
    assert accounting["extraction_failures"] == 1
    assert accounting["missing_stored_responses"] == 1
    assert accounting["file_integrity_failures"] == 1
    assert accounting["not_attempted_cases"] == 169
    assert accounting["invalid_recorded_response_rate"]["numerator"] == 4
    assert accounting["invalid_recorded_response_rate"]["denominator"] == 5
    assert accounting["end_to_end_usable_response_rate"]["numerator"] == 1
    assert accounting["end_to_end_usable_response_rate"]["denominator"] == 8
    assert report["response_accounting"]["actual_model"]["attempted_cases"] == 0
    assert report["response_accounting"]["actual_model"]["invalid_recorded_response_rate"]["percent"] is None
    for case in case_attempts(report):
        if case["attempt_status"] != "VALID_RESPONSE":
            assert case["comparison"] is None and case["evaluations"] is None
    assert "PRIVATE_SIMULATED_PAYLOAD" not in json.dumps(report)


@pytest.mark.parametrize("kind", ["offset", "type", "uncited", "malformed"])
def test_adapter_rejections_are_invalid_responses_not_absent_or_storage_failures(tmp_path, kind):
    path, _ = attempt_manifest(tmp_path, [kind])
    case = case_attempts(runner.build_report(manifest_path=path))[0]
    assert case["attempt_status"] == "INVALID_RESPONSE"
    assert case["error_code"] == "INVALID_RECORDED_RESPONSE"
    assert case["attempt"]["recording"]["response_id"] == "simulated-response-0"


def test_attempt_roster_cannot_silently_drop_unsuccessful_attempt(tmp_path):
    path, manifest = attempt_manifest(tmp_path, ["valid", "missing"])
    manifest["attempts"].pop()
    path.write_text(json.dumps(manifest))
    with pytest.raises(ExperimentFailure, match="INVALID_RECORDING_MANIFEST"):
        runner.build_report(manifest_path=path)


def test_recorded_sources_are_immutable_and_no_archive_or_regex_recapture(tmp_path, monkeypatch):
    import engine.extract
    import engine.service

    path, _ = attempt_manifest(tmp_path, ["valid", "offset", "provider"])
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}

    def forbidden(*args, **kwargs):
        raise AssertionError("Recapture or archive write")

    monkeypatch.setattr(engine.extract, "extract_facts", forbidden)
    monkeypatch.setattr(engine.service, "extract_facts", forbidden)
    monkeypatch.setattr(DecisionStore, "record", forbidden)
    report = runner.build_report(manifest_path=path)
    assert report == runner.build_report(manifest_path=path)
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}
    for case in case_attempts(report):
        if case["comparison"]:
            assert case["comparison"]["clinical_verification"] is False
            for result in (case["evaluations"] or {}).values():
                assert not result["submission_readiness"]
                assert all(item["verification"]["state"] == "UNVERIFIED" for item in result["results"])


def test_actual_model_accounting_is_separate_from_hand_authored_statistics(tmp_path):
    # Schema-only simulation of future actual-origin storage. No model was called.
    path, manifest = attempt_manifest(tmp_path, ["valid", "provider", "missing"])
    manifest["population"] = "actual_model_study"
    for attempt in manifest["attempts"]:
        attempt["recording"]["origin"] = "actual_model_response"
        p = tmp_path / attempt["path"]
        if p.exists() and attempt["outcome"] == "response":
            payload = json.loads(p.read_text())
            payload["recording"]["origin"] = "actual_model_response"
            p.write_text(json.dumps(payload))
            attempt["stored_sha256"] = sha256(p.read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest))
    report = runner.build_report(manifest_path=path)
    actual = report["response_accounting"]["actual_model"]
    assert actual["attempted_cases"] == 3
    assert actual["valid_adapted_responses"] == 1
    assert actual["end_to_end_usable_response_rate"]["denominator"] == 3
    assert report["response_accounting"]["synthetic_raw_demonstration"]["attempted_cases"] == 0
    historical = runner.build_report()
    assert historical["response_accounting"]["hand_authored_adapted"]["valid_recordings"] == 4
    assert historical["response_accounting"]["actual_model"]["attempted_cases"] == 0
    assert historical["response_accounting"]["actual_model"]["invalid_recorded_response_rate"]["denominator"] == 0


def test_provider_failure_without_response_id_and_storage_failures_are_not_invalid_output(tmp_path):
    path, manifest = attempt_manifest(tmp_path, ["provider", "valid"])
    manifest["attempts"][0]["recording"]["response_id"] = None
    manifest["attempts"][1]["note_sha256"] = "0" * 64
    path.write_text(json.dumps(manifest))
    report = runner.build_report(manifest_path=path)
    attempts = case_attempts(report)
    assert {case["attempt_status"] for case in attempts} == {"EXTRACTION_FAILURE", "MALFORMED_STORAGE"}
    provider = next(case for case in attempts if case["attempt_status"] == "EXTRACTION_FAILURE")
    assert provider["attempt"]["recording"]["response_id"] is None
    accounting = report["response_accounting"]["synthetic_raw_demonstration"]
    assert accounting["invalid_recorded_response_rate"]["denominator"] == 0
    assert accounting["malformed_storage_failures"] == 1
    assert accounting["end_to_end_usable_response_rate"]["denominator"] == 2


@pytest.mark.parametrize("change", ["response_identity", "note_identity", "non_utf8", "unknown_vocabulary"])
def test_raw_rejections_preserve_external_identity_without_repair(tmp_path, change):
    path, manifest = attempt_manifest(tmp_path, ["valid"])
    ref = manifest["attempts"][0]
    raw = tmp_path / ref["path"]
    payload = json.loads(raw.read_bytes())
    if change == "response_identity":
        payload["recording"]["response_id"] = "different-response"
    elif change == "note_identity":
        payload["note_sha256"] = "0" * 64
    elif change == "unknown_vocabulary":
        payload["facts"]["unknown_fact"] = payload["facts"].pop("osa_diagnosis")
    data = b"\xff\xfe" if change == "non_utf8" else json.dumps(payload).encode()
    raw.write_bytes(data)
    ref["stored_sha256"] = sha256(data).hexdigest()
    path.write_text(json.dumps(manifest))
    before = raw.read_bytes()
    case = case_attempts(runner.build_report(manifest_path=path))[0]
    assert case["attempt_status"] == "INVALID_RESPONSE"
    assert case["attempt"]["recording"]["response_id"] == "simulated-response-0"
    assert before == raw.read_bytes()


@pytest.mark.parametrize("change", ["duplicate_case", "duplicate_attempt", "duplicate_response", "mixed_origin", "unknown_case"])
def test_ambiguous_or_mixed_raw_manifest_is_rejected_before_comparison(tmp_path, change):
    path, manifest = attempt_manifest(tmp_path, ["valid", "provider"])
    first, second = manifest["attempts"]
    if change == "duplicate_case":
        second["case_id"] = first["case_id"]
    elif change == "duplicate_attempt":
        second["attempt_id"] = first["attempt_id"]
    elif change == "duplicate_response":
        second["recording"]["response_id"] = first["recording"]["response_id"]
    elif change == "mixed_origin":
        second["recording"]["origin"] = "actual_model_response"
    else:
        second["case_id"] = "unknown-case"
        manifest["selected_attempted_case_ids"][1] = "unknown-case"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ExperimentFailure):
        runner.build_report(manifest_path=path)


def test_bundled_raw_demonstration_and_artifacts_are_reproducible():
    directory = runner.DIRECTORY
    manifest = directory / "fixtures/phase3-fixes/manifest.json"
    output = directory / "artifacts/phase3-fixes/raw-attempts"
    assert runner.main(["--check", "--manifest", str(manifest), "--output-dir", str(output)]) == 0
    report = runner.build_report(manifest_path=manifest)
    population = report["response_accounting"]["synthetic_raw_demonstration"]
    assert population["attempted_cases"] == 8
    assert population["invalid_recorded_response_rate"]["numerator"] == 4
    assert population["invalid_recorded_response_rate"]["denominator"] == 5
    assert population["end_to_end_usable_response_rate"]["numerator"] == 1
    assert population["end_to_end_usable_response_rate"]["denominator"] == 8
    assert population["successful_three_mode_evaluations"] == 1
