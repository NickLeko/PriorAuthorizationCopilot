from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


RequirementStatus = Literal["MET", "NOT_MET", "NOT_DOCUMENTED"]
OverallStatus = Literal["READY", "NOT_READY", "CANNOT_DETERMINE", "UNKNOWN"]
LetterType = Literal["submission_cover_letter", "missing_info_request", "appeal_template"]
PolicyTrustLevel = Literal["demo", "verified"]


class PARequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payer: str
    procedure_code: str  # e.g., "MRI_LUMBAR"
    dx_codes: List[str] = Field(default_factory=list)
    site_of_care: str = "outpatient"
    specialty: str = "unknown"
    note_text: str = ""

    @field_validator("payer", "procedure_code", "site_of_care", "specialty")
    @classmethod
    def _strip_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("dx_codes")
    @classmethod
    def _ensure_dx_codes_not_none(cls, value: List[str]) -> List[str]:
        return [str(code) for code in value if str(code).strip()]


class RequirementResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    status: RequirementStatus
    reason: str
    evidence: Optional[str] = None  # "what to look for" hint from policy/rules
    evidence_snippets: List[str] = Field(default_factory=list)  # snippets from the note that triggered extraction

    @field_validator("key", "label", "reason")
    @classmethod
    def _strip_required_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("evidence")
    @classmethod
    def _strip_optional_evidence(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("evidence_snippets")
    @classmethod
    def _normalize_snippets(cls, value: List[str]) -> List[str]:
        snippets: List[str] = []
        for snippet in value:
            text = str(snippet).strip()
            if text:
                snippets.append(text)
        return snippets


class ReadinessReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_score: int
    not_documented_count: int
    not_met_count: int
    met_count: int
    results: List[RequirementResult]
    rule_reasons: List[str]
    audit_trail: Dict[str, Any]
    letter_draft: str

    @field_validator("readiness_score")
    @classmethod
    def _validate_score(cls, value: int) -> int:
        if value < 0 or value > 100:
            raise ValueError("readiness_score must be between 0 and 100.")
        return value

    @field_validator("not_documented_count", "not_met_count", "met_count")
    @classmethod
    def _validate_non_negative_counts(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Counts must be non-negative.")
        return value

    @field_validator("rule_reasons")
    @classmethod
    def _normalize_rule_reasons(cls, value: List[str]) -> List[str]:
        return [str(reason).strip() for reason in value if str(reason).strip()]
