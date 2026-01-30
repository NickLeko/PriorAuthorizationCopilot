from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class PARequest(BaseModel):
    payer: str
    procedure_code: str  # e.g., "MRI_LUMBAR"
    dx_codes: List[str] = Field(default_factory=list)
    site_of_care: str = "outpatient"
    specialty: str = "unknown"
    note_text: str = ""


class RequirementResult(BaseModel):
    key: str
    label: str
    status: str  # "met" | "missing" | "weak" | "unknown"
    reason: str
    evidence: Optional[str] = None


class ReadinessReport(BaseModel):
    readiness_score: int
    missing_count: int
    weak_count: int
    met_count: int
    results: List[RequirementResult]
    rule_reasons: List[str]
    audit_trail: Dict[str, Any]
    letter_draft: str
