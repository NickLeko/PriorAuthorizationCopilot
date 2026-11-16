"""Label schema for requirement-level evaluation.

A label states what a careful reader would assign to ONE requirement of ONE note,
using the fact meaning in engine/fact_contracts.py and the rule operator. It is a
reading of synthetic text, never a clinical finding.

Three review tiers are kept apart everywhere:

- ``verified``     a named human reviewed the label. An agent can never set this.
- ``provisional``  agent-authored, defensible from the note text; not independently reviewed.
- ``needs_review`` the text or the contract does not settle the label. Never scored.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

RequirementState = Literal["MET", "NOT_MET", "NOT_DOCUMENTED", "NEEDS_REVIEW"]
STATES: tuple[str, ...] = ("MET", "NOT_MET", "NOT_DOCUMENTED", "NEEDS_REVIEW")
ReviewStatus = Literal["verified", "provisional", "needs_review"]
SCORED_TIERS: tuple[str, ...] = ("verified", "provisional")
Split = Literal["regression", "challenge", "holdout"]

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = Path(__file__).resolve().parent / "datasets"


class HoldoutSealedError(RuntimeError):
    """Raised when a sealed holdout is loaded without an explicit, deliberate override."""


def note_sha256(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


class LabelProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author_type: Literal["agent", "human"]
    author: str = Field(min_length=1)
    authored_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    # True only if the label was written before its author saw this note's extractor output.
    blind_to_extractor_output: bool
    basis: str = Field(min_length=1)


class RequirementLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_key: str = Field(min_length=1)
    review_status: ReviewStatus
    # For needs_review this is only a proposal for the reviewer and is never scored.
    expected_state: Optional[RequirementState] = None
    # Other states a careful reader could also defend (for example a conservative
    # NEEDS_REVIEW). MET is listed only when asserting the fact would be correct.
    acceptable_states: List[RequirementState] = Field(default_factory=list)
    # Exact substring of the note that supports the label; null when nothing in the note addresses it.
    evidence_quote: Optional[str] = None
    rationale: str = Field(min_length=1)
    uncertainty: Literal["low", "medium", "high"]
    uncertainty_note: Optional[str] = None
    provenance: Optional[LabelProvenance] = None
    reviewer: Optional[str] = None
    reviewer_type: Optional[Literal["human"]] = None
    reviewed_on: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def _validate(self) -> "RequirementLabel":
        if self.review_status == "needs_review":
            if self.acceptable_states:
                raise ValueError("needs_review labels are unscored and cannot declare acceptable states.")
            if not (self.uncertainty_note or "").strip():
                raise ValueError("needs_review labels must say what a reviewer has to decide.")
            return self
        if self.expected_state is None:
            raise ValueError("Scored labels need an expected state.")
        if not self.acceptable_states:
            self.acceptable_states = [self.expected_state]
        if self.expected_state not in self.acceptable_states or len(set(self.acceptable_states)) != len(self.acceptable_states):
            raise ValueError("acceptable_states must be unique and include expected_state.")
        if self.expected_state != "NOT_DOCUMENTED" and not self.evidence_quote:
            raise ValueError("A label other than NOT_DOCUMENTED needs an evidence quote from the note.")
        if self.review_status == "verified":
            if not (self.reviewer or "").strip() or self.reviewer_type != "human" or not self.reviewed_on:
                raise ValueError("verified labels need a named human reviewer and a review date.")
        elif self.reviewer or self.reviewer_type or self.reviewed_on:
            raise ValueError("Only verified labels carry reviewer fields.")
        return self


class LabeledCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    payer: str
    procedure_code: str
    note_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    # Inline datasets carry the note; reference datasets resolve it from notes_source.
    note_text: Optional[str] = None
    phenomena: List[str] = Field(default_factory=list)
    # True when this exact note was run through the extractor before its labels were written.
    extractor_output_seen_before_labeling: bool = False
    labels: List[RequirementLabel] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_keys(self) -> "LabeledCase":
        keys = [label.requirement_key for label in self.labels]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate requirement labels in case {self.case_id}.")
        return self


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    dataset_version: int = Field(ge=1)
    split: Split
    sealed: bool = False
    description: str = Field(min_length=1)
    note_authorship: str = Field(min_length=1)
    selection: str = Field(min_length=1)
    independent_clinical_ground_truth: Literal[False] = False
    notes_source: Optional[str] = None
    label_defaults: Optional[LabelProvenance] = None
    cases: List[LabeledCase]

    @model_validator(mode="after")
    def _validate(self) -> "Dataset":
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate case IDs.")
        if self.split == "holdout" and not self.sealed:
            raise ValueError("A holdout must be sealed.")
        if self.sealed and any(case.labels for case in self.cases):
            raise ValueError("A sealed holdout carries no labels until a human unseals and labels it.")
        for case in self.cases:
            for label in case.labels:
                if label.provenance is None:
                    if self.label_defaults is None:
                        raise ValueError(f"Label without provenance: {case.case_id}/{label.requirement_key}")
                    label.provenance = self.label_defaults
        return self


def _resolve_notes(dataset: Dataset, repo_root: Path) -> None:
    referenced: Dict[str, str] = {}
    if dataset.notes_source:
        payload = json.loads((repo_root / dataset.notes_source).read_text(encoding="utf-8"))
        referenced = {item["id"]: item.get("note_text", "") or "" for item in payload}
    for case in dataset.cases:
        if case.note_text is None:
            if case.case_id not in referenced:
                raise ValueError(f"No note for case {case.case_id}.")
            case.note_text = referenced[case.case_id]
        if note_sha256(case.note_text) != case.note_sha256:
            raise ValueError(f"Note text changed since labeling: {case.case_id}. Labels must be re-reviewed.")
        for label in case.labels:
            if label.evidence_quote is not None and label.evidence_quote not in case.note_text:
                raise ValueError(f"Evidence quote is not an exact substring of the note: {case.case_id}/{label.requirement_key}")


def load_dataset(path: Path, *, repo_root: Path = REPO_ROOT, allow_sealed_holdout: bool = False) -> Dataset:
    raw: Dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    if (raw.get("sealed") or raw.get("split") == "holdout") and not allow_sealed_holdout:
        raise HoldoutSealedError(
            f"{Path(path).name} is a sealed holdout. It is not evaluated until a human labels it and a reviewer approves a single run."
        )
    dataset = Dataset.model_validate(raw)
    _resolve_notes(dataset, repo_root)
    return dataset


def dataset_file_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()
