"""Validated, lossless extraction captures; no new clinical vocabulary or inference."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from engine import __version__
from engine.corrections import capture_original, materialize, validate_spans
from engine.extract import extract_facts
from engine.fact_contracts import FACT_CONTRACTS, get_fact_contract, validate_fact_value
from engine.note_context import MAX_EVIDENCE_SPANS, EvidenceMap, validate_note
from engine.schemas import REVIEW_REQUIRED_FACT, OriginalProposal

LegacyExtraction = tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]


class ExtractionProposal(BaseModel):
    """Note-bound immutable capture; source/diagnostics never enter clinical facts.

    The existing canonical snapshot carries values, states, evidence, and counts.
    It is immutable JSON, so nested caller mutations cannot change a proposal.
    Validation proves representation and source location, not semantic support.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    note_text: str
    source: str = Field(min_length=1)
    snapshot: OriginalProposal
    diagnostics: tuple[str, ...] = ()

    @field_validator("note_text")
    @classmethod
    def _validate_note(cls, value: str) -> str:
        return validate_note(value)

    @field_validator("source")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("Extraction source must be nonblank and unpadded.")
        return value

    @model_validator(mode="after")
    def _validate_capture(self):
        snapshot = self.snapshot.content
        if set(snapshot["facts"]) != set(FACT_CONTRACTS):
            raise ValueError("Extraction fact keys must match all existing fact contracts exactly.")
        if any(len(spans) > MAX_EVIDENCE_SPANS for spans in snapshot["evidence"].values()):
            raise ValueError("Extraction evidence exceeds the existing citation cap.")
        # Reuse strict extractor vocabulary, state, and exact note-slice validation.
        materialize(self.snapshot, [], self.note_text, FACT_CONTRACTS)
        return self


def proposal_from_legacy(
    note_text: str,
    legacy: LegacyExtraction,
    *,
    source: str,
    diagnostics: tuple[str, ...] = (),
) -> ExtractionProposal:
    facts, evidence = legacy
    if set(facts) != set(FACT_CONTRACTS):
        raise ValueError("Extraction fact keys must match all existing fact contracts exactly.")
    # Validate raw values/offsets before JSON capture can normalize their types.
    for key, value in facts.items():
        if value is not None and value != REVIEW_REQUIRED_FACT:
            validate_fact_value(get_fact_contract(key), value, vocabulary="extractor_emittable")
    for spans in evidence.values():
        validate_spans(spans, note_text)
    return ExtractionProposal(
        note_text=note_text,
        source=source,
        snapshot=capture_original(facts, evidence),
        diagnostics=diagnostics,
    )


def proposal_to_legacy(proposal: ExtractionProposal) -> tuple[dict[str, Any], EvidenceMap]:
    # Frozen Pydantic model_copy/model_construct can bypass validation; recheck at
    # this consumption boundary, as the service does for mutable requests.
    proposal = ExtractionProposal.model_validate_json(proposal.model_dump_json())
    snapshot = proposal.snapshot.content
    facts = {key: REVIEW_REQUIRED_FACT if snapshot["states"][key] == "NEEDS_REVIEW" else value for key, value in snapshot["facts"].items()}
    evidence = EvidenceMap(snapshot["evidence"])
    # The lists are already capped. Recounting them would lose original totals.
    evidence.total_counts = dict(snapshot.get("evidence_counts", {}))
    return facts, evidence


def extract_regex_proposal(note_text: str) -> ExtractionProposal:
    return proposal_from_legacy(note_text, extract_facts(note_text), source=f"regex:{__version__}")
