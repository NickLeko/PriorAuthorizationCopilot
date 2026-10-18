import json
from hashlib import sha256

import pytest
from dual_extraction_helpers import synthetic_response

from engine.corrections import note_hash
from experiments.dual_extraction.errors import ExperimentFailure
from experiments.dual_extraction.recorded import adapt_recorded_response
from experiments.dual_extraction.recordings import RecordingRef, load_manifest, load_recording

NOTICE = "Hand-authored synthetic recordings; no model was called."


def stored_recording(tmp_path, note="OSA", response_id="synthetic-test-recording", filename="recording.json"):
    response = synthetic_response(note, {"osa_diagnosis": True})
    response["recording"]["response_id"] = response_id
    recorded = adapt_recorded_response(note, response)
    data = recorded.model_dump_json(indent=2).encode()
    (tmp_path / filename).write_bytes(data)
    ref = RecordingRef(
        case_id="EXTRACTION_CONTRACT.md#osa_positive",
        path=filename,
        note_sha256=note_hash(note),
        stored_sha256=sha256(data).hexdigest(),
        recording_sha256=recorded.recording_sha256,
        recording=recorded.recording,
    )
    return recorded, ref


def test_validated_recording_reloads_without_hash_repair_or_source_mutation(tmp_path):
    original, ref = stored_recording(tmp_path)
    before = (tmp_path / ref.path).read_bytes()
    assert load_recording("OSA", ref, tmp_path) == original
    assert before == (tmp_path / ref.path).read_bytes()


@pytest.mark.parametrize("tamper", ["value", "quote", "model", "prompt", "response_id", "stored_hash"])
def test_tampering_is_rejected_against_trusted_reference(tmp_path, tamper):
    _, ref = stored_recording(tmp_path)
    path = tmp_path / ref.path
    data = json.loads(path.read_text())
    if tamper in {"model", "prompt", "response_id"}:
        key = {"model": "model_id", "prompt": "prompt_version", "response_id": "response_id"}[tamper]
        data["recording"][key] = "synthetic-modified"
    elif tamper == "stored_hash":
        data["recording_sha256"] = "0" * 64
    else:
        data["proposal"]["note_text"] = "MODIFIED_PRIVATE_SYNTHETIC_NOTE"
    path.write_text(json.dumps(data))
    with pytest.raises(ExperimentFailure, match="RECORDING_INTEGRITY_FAILURE") as caught:
        load_recording("OSA", ref, tmp_path)
    assert "MODIFIED_PRIVATE" not in str(caught.value)


def test_valid_but_modified_content_fails_normalized_recording_hash(tmp_path):
    original, ref = stored_recording(tmp_path)
    # All fields remain structurally valid, but the stored content hash is wrong.
    modified = original.model_copy(update={"recording_sha256": "0" * 64})
    data = modified.model_dump_json().encode()
    (tmp_path / ref.path).write_bytes(data)
    ref = ref.model_copy(update={"stored_sha256": sha256(data).hexdigest(), "recording_sha256": "0" * 64})
    with pytest.raises(ExperimentFailure, match="RECORDING_INTEGRITY_FAILURE"):
        load_recording("OSA", ref, tmp_path)


def test_changed_valid_proposal_content_cannot_keep_original_recording_hash(tmp_path):
    from engine.policies import canonical_json, content_hash
    from engine.schemas import OriginalProposal

    original, ref = stored_recording(tmp_path)
    snapshot = original.proposal.snapshot.content
    snapshot["states"]["osa_diagnosis"] = "MISSING"
    snapshot["facts"]["osa_diagnosis"] = None
    snapshot["evidence"] = {}
    changed = OriginalProposal(snapshot_json=canonical_json(snapshot), content_hash=content_hash(snapshot))
    modified = original.model_copy(update={"proposal": original.proposal.model_copy(update={"snapshot": changed})})
    data = modified.model_dump_json().encode()
    (tmp_path / ref.path).write_bytes(data)
    ref = ref.model_copy(update={"stored_sha256": sha256(data).hexdigest()})
    with pytest.raises(ExperimentFailure, match="RECORDING_INTEGRITY_FAILURE"):
        load_recording("OSA", ref, tmp_path)


def test_note_and_swapped_response_identity_are_verified(tmp_path):
    _, first = stored_recording(tmp_path, response_id="synthetic-one", filename="one.json")
    _, second = stored_recording(tmp_path, response_id="synthetic-two", filename="two.json")
    with pytest.raises(ExperimentFailure, match="RECORDING_NOTE_MISMATCH"):
        load_recording("OSA ", first, tmp_path)
    swapped = first.model_copy(update={"path": second.path, "stored_sha256": second.stored_sha256})
    with pytest.raises(ExperimentFailure, match="RECORDING_IDENTITY_FAILURE"):
        load_recording("OSA", swapped, tmp_path)


def test_missing_malformed_and_integrity_failures_are_distinct(tmp_path):
    _, ref = stored_recording(tmp_path)
    (tmp_path / ref.path).unlink()
    with pytest.raises(ExperimentFailure, match="MISSING_RECORDING"):
        load_recording("OSA", ref, tmp_path)
    data = b'{"invalid":'
    (tmp_path / ref.path).write_bytes(data)
    malformed = ref.model_copy(update={"stored_sha256": sha256(data).hexdigest()})
    with pytest.raises(ExperimentFailure, match="MALFORMED_RECORDING"):
        load_recording("OSA", malformed, tmp_path)
    with pytest.raises(ExperimentFailure, match="RECORDING_INTEGRITY_FAILURE"):
        load_recording("OSA", ref, tmp_path)


@pytest.mark.parametrize("duplicate_case", [False, True])
def test_manifest_rejects_duplicate_recording_and_case_identities(tmp_path, duplicate_case):
    _, first = stored_recording(tmp_path, response_id="synthetic-one", filename="one.json")
    _, second = stored_recording(tmp_path, response_id="synthetic-two", filename="two.json")
    entries = [first.model_dump(mode="json"), second.model_dump(mode="json")]
    if not duplicate_case:
        entries[1]["case_id"] = "another-case"
        entries[1]["recording"]["response_id"] = entries[0]["recording"]["response_id"]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema_version": 1, "notice": NOTICE, "recordings": entries}))
    with pytest.raises(ExperimentFailure, match="RECORDING_IDENTITY_FAILURE"):
        load_manifest(path)
