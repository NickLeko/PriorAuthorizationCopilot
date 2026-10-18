"""Read-only integrity boundary for pinned, explicitly synthetic recordings."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engine.corrections import note_hash
from engine.policies import canonical_json, content_hash

from .errors import ExperimentFailure
from .recorded import RecordedLLMProposal, RecordingMetadata, _reject_constant, _unique_object

NOTICE = "Hand-authored synthetic recordings; no model was called."
HASH_PATTERN = r"^[0-9a-f]{64}$"


class RecordingRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    case_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    note_sha256: str = Field(pattern=HASH_PATTERN)
    stored_sha256: str = Field(pattern=HASH_PATTERN)
    recording_sha256: str = Field(pattern=HASH_PATTERN)
    recording: RecordingMetadata
    demonstration: Literal["known_shared_error"] | None = None


class RecordingManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    schema_version: Literal[1]
    notice: Literal["Hand-authored synthetic recordings; no model was called."]
    recordings: list[RecordingRef]


def load_manifest(path: Path) -> RecordingManifest:
    try:
        data = json.loads(path.read_bytes(), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        manifest = RecordingManifest.model_validate(data, strict=True)
        cases = [entry.case_id for entry in manifest.recordings]
        identities = [(entry.recording.source, entry.recording.response_id) for entry in manifest.recordings]
        if len(set(cases)) != len(cases) or len(set(identities)) != len(identities):
            raise ExperimentFailure("RECORDING_IDENTITY_FAILURE")
        return manifest
    except ExperimentFailure:
        raise
    except (OSError, ValueError, TypeError):
        raise ExperimentFailure("INVALID_RECORDING_MANIFEST") from None


def _normalized_recording_hash(recorded: RecordedLLMProposal) -> str:
    snapshot = recorded.proposal.snapshot.content
    # Reconstruct the adapter's normalized accepted response. All 12 cells were
    # mandatory, with explicit nulls and empty lists; no evidence is invented.
    return content_hash(
        dict(
            recording=recorded.recording.model_dump(mode="json"),
            note_sha256=note_hash(recorded.proposal.note_text),
            facts={
                key: dict(state=snapshot["states"][key], value=value, evidence=snapshot["evidence"].get(key, []))
                for key, value in snapshot["facts"].items()
            },
            evidence_counts=snapshot.get("evidence_counts", {}),
        )
    )


def load_recording(note_text: str, ref: RecordingRef, directory: Path) -> RecordedLLMProposal:
    """Verify identity and both hashes; never rewrite or restamp stored records."""
    try:
        ref = RecordingRef.model_validate_json(ref.model_dump_json(warnings=False))
        path = (directory / ref.path).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Recording path is outside its manifest directory.")
        try:
            stored = path.read_bytes()
        except FileNotFoundError:
            raise ExperimentFailure("MISSING_RECORDING") from None
        if sha256(stored).hexdigest() != ref.stored_sha256:
            raise ExperimentFailure("RECORDING_INTEGRITY_FAILURE")
        data = json.loads(stored, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        recorded = RecordedLLMProposal.model_validate_json(canonical_json(data))
        if recorded.recording != ref.recording:
            raise ExperimentFailure("RECORDING_IDENTITY_FAILURE")
        if recorded.proposal.note_text != note_text or note_hash(note_text) != ref.note_sha256:
            raise ExperimentFailure("RECORDING_NOTE_MISMATCH")
        if _normalized_recording_hash(recorded) != recorded.recording_sha256 or recorded.recording_sha256 != ref.recording_sha256:
            raise ExperimentFailure("RECORDING_INTEGRITY_FAILURE")
        return recorded
    except ExperimentFailure:
        raise
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        raise ExperimentFailure("MALFORMED_RECORDING") from None
