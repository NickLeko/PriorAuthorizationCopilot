"""Read-only integrity boundary for pinned recordings and declared raw attempts."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engine.corrections import note_hash
from engine.policies import canonical_json, content_hash

from .errors import ExperimentFailure
from .recorded import IDENTIFIER_PATTERN, RecordedLLMProposal, RecordingMetadata, _reject_constant, _unique_object

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


class AttemptMetadata(RecordingMetadata):
    # A provider failure can precede creation of a response identity.
    response_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)


class RawAttemptRef(BaseModel):
    """Identity lives outside the raw bytes so even unparsable responses survive."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    case_id: str = Field(min_length=1)
    attempt_id: str = Field(pattern=IDENTIFIER_PATTERN)
    path: str = Field(min_length=1)
    note_sha256: str = Field(pattern=HASH_PATTERN)
    stored_sha256: str = Field(pattern=HASH_PATTERN)
    recording: AttemptMetadata
    provider_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    outcome: Literal["response", "extraction_failure"]


class RawAttemptManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    schema_version: Literal[2]
    notice: Literal["Offline response attempts; provenance is declared per population."]
    population: Literal["synthetic_raw_demonstration", "actual_model_study"]
    selected_attempted_case_ids: list[str]
    attempts: list[RawAttemptRef]


def load_manifest(path: Path) -> RecordingManifest | RawAttemptManifest:
    try:
        data = json.loads(path.read_bytes(), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        if type(data) is not dict:
            raise ValueError("Expected manifest object.")
        schema = RawAttemptManifest if data.get("schema_version") == 2 else RecordingManifest
        manifest = schema.model_validate(data, strict=True)
        entries = manifest.attempts if isinstance(manifest, RawAttemptManifest) else manifest.recordings
        cases = [entry.case_id for entry in entries]
        identities = [(entry.recording.source, entry.recording.response_id) for entry in entries if entry.recording.response_id is not None]
        if len(set(cases)) != len(cases) or len(set(identities)) != len(identities):
            raise ExperimentFailure("RECORDING_IDENTITY_FAILURE")
        if isinstance(manifest, RawAttemptManifest):
            selected = manifest.selected_attempted_case_ids
            if len(selected) != len(set(selected)) or set(selected) != set(cases):
                raise ExperimentFailure("INVALID_RECORDING_MANIFEST")
            if len({entry.attempt_id for entry in entries}) != len(entries):
                raise ExperimentFailure("RECORDING_IDENTITY_FAILURE")
            origin = "actual_model_response" if manifest.population == "actual_model_study" else "hand_authored_synthetic"
            if any(entry.recording.origin != origin for entry in entries):
                raise ExperimentFailure("INVALID_RECORDING_MANIFEST")
        elif any(entry.recording.origin != "hand_authored_synthetic" for entry in entries):
            # Legacy adapted fixtures never acquire measured model-attempt status.
            raise ExperimentFailure("INVALID_RECORDING_MANIFEST")
        return manifest
    except ExperimentFailure:
        raise
    except (OSError, ValueError, TypeError):
        raise ExperimentFailure("INVALID_RECORDING_MANIFEST") from None


def load_raw_attempt(note_text: str, ref: RawAttemptRef, directory: Path) -> bytes:
    """Only verify storage here. The runner must attempt adaptation of raw replies."""
    try:
        ref = RawAttemptRef.model_validate_json(ref.model_dump_json(warnings=False))
        path = (directory / ref.path).resolve()
        if not path.is_relative_to(directory.resolve()) or note_hash(note_text) != ref.note_sha256:
            raise ValueError("Invalid stored identity.")
        try:
            stored = path.read_bytes()
        except FileNotFoundError:
            raise ExperimentFailure("MISSING_RECORDING") from None
        if sha256(stored).hexdigest() != ref.stored_sha256:
            raise ExperimentFailure("STORED_FILE_INTEGRITY_FAILURE")
        return stored
    except ExperimentFailure:
        raise
    except (OSError, ValueError, TypeError, AttributeError):
        raise ExperimentFailure("MALFORMED_ATTEMPT_STORAGE") from None


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
