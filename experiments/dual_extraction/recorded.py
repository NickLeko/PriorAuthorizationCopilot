"""Strict response adapter; recording origin is explicit, never verification."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine.corrections import note_hash
from engine.fact_contracts import FACT_CONTRACTS, FactState, get_fact_contract, validate_fact_value
from engine.note_context import MAX_EVIDENCE_SPANS, EvidenceMap
from engine.policies import canonical_json, content_hash
from engine.schemas import REVIEW_REQUIRED_FACT, EvidenceSpan

from .errors import ExperimentFailure
from .proposals import ExtractionProposal, proposal_from_legacy

IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/+\-]{0,127}$"


class RecordingMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    source: str = Field(pattern=IDENTIFIER_PATTERN)
    model_id: str = Field(pattern=IDENTIFIER_PATTERN)
    prompt_version: str = Field(pattern=IDENTIFIER_PATTERN)
    response_id: str = Field(pattern=IDENTIFIER_PATTERN)
    origin: Literal["hand_authored_synthetic", "actual_model_response"]


class RecordedLLMProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    recording: RecordingMetadata
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposal: ExtractionProposal

    @model_validator(mode="after")
    def _source_matches(self):
        if self.recording.source != self.proposal.source:
            raise ValueError("Recorded source identity mismatch.")
        return self


class _RecordedFact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    state: FactState
    value: Any
    evidence: list[EvidenceSpan] = Field(max_length=MAX_EVIDENCE_SPANS)


class _RecordedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    recording: RecordingMetadata
    note_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    facts: dict[str, _RecordedFact]
    evidence_counts: dict[str, int] = Field(default_factory=dict)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Nonfinite JSON number.")


def adapt_recorded_response(note_text: str, payload: str | dict) -> RecordedLLMProposal:
    """Validate before legacy conversion; errors contain fixed codes, never payloads.

    The recording hash addresses the normalized accepted recording, including its
    metadata. It is experimental provenance, not a production attestation.
    """
    try:
        decoded = (
            json.loads(payload, object_pairs_hook=_unique_object, parse_constant=_reject_constant) if type(payload) is str else payload
        )
        if type(decoded) is not dict:
            raise ValueError("Expected an object.")
        if "error" in decoded:
            raise ExperimentFailure("RECORDED_EXTRACTION_FAILURE")
        # Raw responses must be JSON data, not Python model objects whose
        # validation may have been bypassed with model_construct/model_copy.
        canonical_json(decoded)
        response = _RecordedResponse.model_validate(decoded, strict=True)
        if set(response.facts) != set(FACT_CONTRACTS) or response.note_sha256 != note_hash(note_text):
            raise ValueError("Recording scope mismatch.")
        facts, evidence = {}, {}
        for key, item in response.facts.items():
            if item.state == "CAPTURED":
                facts[key] = validate_fact_value(get_fact_contract(key), item.value, vocabulary="extractor_emittable")
            else:
                if item.value is not None:
                    raise ValueError("Non-captured values must be null.")
                facts[key] = REVIEW_REQUIRED_FACT if item.state == "NEEDS_REVIEW" else None
            if item.evidence:
                evidence[key] = [span.model_dump() for span in item.evidence]
        bounded_evidence = EvidenceMap(evidence)
        bounded_evidence.total_counts = response.evidence_counts.copy()
        proposal = proposal_from_legacy(
            note_text,
            (facts, bounded_evidence),
            source=response.recording.source,
            diagnostics=("HAND_AUTHORED_SYNTHETIC" if response.recording.origin == "hand_authored_synthetic" else "ACTUAL_MODEL_RESPONSE",),
        )
        return RecordedLLMProposal(
            recording=response.recording,
            recording_sha256=content_hash(response.model_dump(mode="json")),
            proposal=proposal,
        )
    except ExperimentFailure:
        raise
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ExperimentFailure("INVALID_RECORDED_RESPONSE") from None
