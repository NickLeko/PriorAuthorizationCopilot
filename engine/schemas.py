from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

RequirementStatus = Literal["MET", "NOT_MET", "NOT_DOCUMENTED", "NEEDS_REVIEW"]
OverallStatus = Literal["READY", "NOT_READY", "CANNOT_DETERMINE", "NEEDS_REVIEW", "UNKNOWN"]
LetterType = Literal["submission_cover_letter", "missing_info_request", "appeal_template"]
PolicyTrustLevel = Literal["demo", "verified"]
RequirementType = Literal["number", "boolean", "enum"]
RulebookStage = Literal["draft", "reviewed", "active"]


class PARequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payer: str
    procedure_code: str
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


class LetterRequestMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payer: str
    procedure_code: str
    dx_codes: List[str] = Field(default_factory=list)
    site_of_care: str = "outpatient"
    specialty: str = "unknown"

    @field_validator("payer", "procedure_code", "site_of_care", "specialty")
    @classmethod
    def _strip_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("dx_codes")
    @classmethod
    def _ensure_dx_codes_not_none(cls, value: List[str]) -> List[str]:
        return [str(code) for code in value if str(code).strip()]


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int
    end: int
    text: str

    @field_validator("start", "end")
    @classmethod
    def _validate_offsets(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Evidence span offsets must be non-negative.")
        return value

    @field_validator("text")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()


class RequirementDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    type: RequirementType = "boolean"
    min: Optional[float] = None
    allowed: List[str] = Field(default_factory=list)
    evidence: Optional[str] = None

    @field_validator("key", "label")
    @classmethod
    def _strip_required_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("allowed")
    @classmethod
    def _normalize_allowed(cls, value: List[str]) -> List[str]:
        return [str(item).strip() for item in value if str(item).strip()]

    @field_validator("evidence")
    @classmethod
    def _normalize_evidence(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class RequirementResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    status: RequirementStatus
    reason: str
    evidence: Optional[str] = None
    evidence_snippets: List[str] = Field(default_factory=list)
    evidence_spans: List[EvidenceSpan] = Field(default_factory=list)

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


class LetterDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: LetterRequestMetadata
    met_count: int
    not_met_count: int
    not_documented_count: int
    needs_review_count: int = 0
    results: List[RequirementResult]
    policy_trust_level: PolicyTrustLevel = "demo"

    @field_validator("met_count", "not_met_count", "not_documented_count", "needs_review_count")
    @classmethod
    def _validate_non_negative_counts(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Counts must be non-negative.")
        return value


class BlockingIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    status: RequirementStatus
    reason: str

    @field_validator("key", "label", "reason")
    @classmethod
    def _strip_strings(cls, value: str) -> str:
        return value.strip()


class BlockingIssueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    not_documented: List[BlockingIssue] = Field(default_factory=list)
    not_met: List[BlockingIssue] = Field(default_factory=list)
    needs_review: List[BlockingIssue] = Field(default_factory=list)


class EvaluationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extraction_success_rate: float
    extraction_failure_count: int
    compliance_rate: Optional[float] = None
    compliant_count: int
    non_compliant_count: int
    needs_review_count: int = 0


class ProcedureMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    rule_family: str
    summary: str
    supported_sites: List[str] = Field(default_factory=list)
    last_rule_update: Optional[str] = None
    notes: List[str] = Field(default_factory=list)

    @field_validator("category", "rule_family", "summary")
    @classmethod
    def _strip_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("supported_sites", "notes")
    @classmethod
    def _normalize_lists(cls, value: List[str]) -> List[str]:
        return [str(item).strip() for item in value if str(item).strip()]


class ProcedureProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: Optional[str] = None
    source_type: Optional[str] = None
    status: Optional[str] = None
    source_url: Optional[str] = None
    rule_source_label: Optional[str] = None
    last_reviewed: Optional[str] = None
    rule_last_updated: Optional[str] = None
    monitored_source_id: Optional[str] = None
    monitored_source_name: Optional[str] = None
    monitored_source_url: Optional[str] = None
    monitored_check_frequency: Optional[str] = None
    monitored_source_owner: Optional[str] = None
    notes: Optional[str] = None

    @field_validator(
        "source_name",
        "source_type",
        "status",
        "source_url",
        "rule_source_label",
        "last_reviewed",
        "rule_last_updated",
        "monitored_source_id",
        "monitored_source_name",
        "monitored_source_url",
        "monitored_check_frequency",
        "monitored_source_owner",
        "notes",
    )
    @classmethod
    def _strip_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SupportedProcedure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payer: str
    procedure_code: str
    display_name: str
    monitored_for_drift: bool = False
    policy_trust_level: PolicyTrustLevel = "demo"
    required_field_keys: List[str] = Field(default_factory=list)
    metadata: ProcedureMetadata
    provenance: ProcedureProvenance = Field(default_factory=ProcedureProvenance)
    requirements: List[RequirementDefinition] = Field(default_factory=list)

    @field_validator("payer", "procedure_code", "display_name")
    @classmethod
    def _strip_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("required_field_keys")
    @classmethod
    def _normalize_required_field_keys(cls, value: List[str]) -> List[str]:
        return [str(item).strip() for item in value if str(item).strip()]


class DemoCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    payer: str
    procedure_code: str
    dx_codes: List[str] = Field(default_factory=list)
    site_of_care: str = "outpatient"
    specialty: str = "unknown"
    note_text: str = ""
    expected_label: Optional[str] = None
    showcase: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "payer", "procedure_code", "site_of_care", "specialty", "note_text")
    @classmethod
    def _strip_strings(cls, value: str) -> str:
        return value.strip()


class AuditTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    timestamp_utc: str
    note_hash: str
    note_length: int
    payer: str
    procedure_code: str
    procedure_name: str
    site_of_care: str
    specialty: str
    rules_version: Optional[str] = None
    rulebook_active_release_id: Optional[str] = None
    policy_trust_level: PolicyTrustLevel
    provenance_snapshot: Dict[str, Any] = Field(default_factory=dict)
    facts_extracted: Dict[str, Any] = Field(default_factory=dict)
    evidence_map: Dict[str, List[EvidenceSpan]] = Field(default_factory=dict)
    requirements_checked: List[str] = Field(default_factory=list)
    overall_status: OverallStatus
    submission_readiness: bool
    blocking_issues: BlockingIssueSummary
    metrics: EvaluationMetrics
    invariant_errors: List[str] = Field(default_factory=list)
    evaluation_warnings: List[str] = Field(default_factory=list)

    @field_validator(
        "run_id",
        "timestamp_utc",
        "note_hash",
        "payer",
        "procedure_code",
        "procedure_name",
        "site_of_care",
        "specialty",
    )
    @classmethod
    def _strip_strings(cls, value: str) -> str:
        return value.strip()


class ReadinessReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_score: int
    not_documented_count: int
    not_met_count: int
    met_count: int
    needs_review_count: int = 0
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

    @field_validator("not_documented_count", "not_met_count", "met_count", "needs_review_count")
    @classmethod
    def _validate_non_negative_counts(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Counts must be non-negative.")
        return value

    @field_validator("rule_reasons")
    @classmethod
    def _normalize_rule_reasons(cls, value: List[str]) -> List[str]:
        return [str(reason).strip() for reason in value if str(reason).strip()]


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: PARequest
    supported_procedure: SupportedProcedure
    overall_status: OverallStatus
    submission_readiness: bool
    readiness_score: int
    results: List[RequirementResult]
    rule_reasons: List[str] = Field(default_factory=list)
    facts: Dict[str, Any] = Field(default_factory=dict)
    evidence_map: Dict[str, List[EvidenceSpan]] = Field(default_factory=dict)
    blockers: BlockingIssueSummary
    metrics: EvaluationMetrics
    warnings: List[str] = Field(default_factory=list)
    policy_trust_level: PolicyTrustLevel
    provenance: Dict[str, Any] = Field(default_factory=dict)
    audit_trail: AuditTrace
    report: ReadinessReport


class DriftSourceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    payer: str
    procedure_code: str
    source_name: Optional[str] = None
    source_type: str
    url: str
    trust_level: str
    check_frequency: str
    owner: str
    status: str
    last_checked_utc: Optional[str] = None
    days_since_last_checked: Optional[int] = None
    freshness_status: Optional[str] = None
    latest_hash: Optional[str] = None
    latest_event: Optional[str] = None
    latest_snapshot_path: Optional[str] = None
    latest_diff_path: Optional[str] = None
    rule_source_label: Optional[str] = None
    last_rule_reviewed: Optional[str] = None
    review_reason: Optional[str] = None
    notes: Optional[str] = None


class DriftStatusReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: List[DriftSourceStatus] = Field(default_factory=list)
    any_review_required: bool = False
    stale_source_count: int = 0


class RulebookFileSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules_path: str
    provenance_path: str
    policy_sources_path: str


class RulebookRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: str
    stage: Optional[RulebookStage] = None
    summary: str
    created_at: Optional[str] = None
    based_on_release_id: Optional[str] = None
    rules_version: Optional[str] = None
    procedures: List[str] = Field(default_factory=list)
    files: RulebookFileSet
    reviewer: Optional[str] = None
    reviewed_at: Optional[str] = None
    runtime_matches: Optional[bool] = None
    notes: List[str] = Field(default_factory=list)


class RulebookStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: Optional[str] = None
    active_release_id: Optional[str] = None
    stage_assignments: Dict[str, Optional[str]] = Field(default_factory=dict)
    runtime_rules_version: Optional[str] = None
    releases: List[RulebookRelease] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)


class RulebookDiffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_release_id: str
    to_release_id: str
    from_stage: Optional[RulebookStage] = None
    to_stage: Optional[RulebookStage] = None
    rules_version_from: Optional[str] = None
    rules_version_to: Optional[str] = None
    added_procedures: List[str] = Field(default_factory=list)
    removed_procedures: List[str] = Field(default_factory=list)
    changed_procedures: List[str] = Field(default_factory=list)
    changed_provenance: List[str] = Field(default_factory=list)
    changed_policy_sources: List[str] = Field(default_factory=list)
    summary_lines: List[str] = Field(default_factory=list)


class StatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    rules_version: Optional[str] = None
    rulebook_active_release_id: Optional[str] = None
    rulebook_active_rules_version: Optional[str] = None
    supported_procedures: int
    demo_cases: int
    monitored_policy_sources: int


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: str
    detail: str
