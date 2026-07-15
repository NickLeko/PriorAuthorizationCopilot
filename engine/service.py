from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from functools import cached_property
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List

from .config import AppConfig, load_app_config
from .demo_cases import demo_case_to_request, get_demo_case, list_demo_cases
from .evaluate import compute_overall_status, compute_readiness_score, evaluate_requirements
from .extract import extract_facts
from .letter_draft import draft_letter
from .logging_utils import configure_logging, get_logger, log_event
from .policy_monitor import load_policy_sources, read_latest_snapshot
from .provenance import (
    get_provenance_entry,
    load_provenance,
    normalized_dx_codes,
    policy_trust_from_provenance,
)
from .rulebook import RulebookError, get_rulebook_diff, get_rulebook_status
from .rules_loader import load_rules
from .schemas import (
    AuditTrace,
    BlockingIssue,
    BlockingIssueSummary,
    DemoCase,
    DriftSourceStatus,
    DriftStatusReport,
    EvaluationMetrics,
    EvaluationResult,
    EvidenceSpan,
    LetterType,
    PARequest,
    ProcedureMetadata,
    ProcedureProvenance,
    ReadinessReport,
    RequirementDefinition,
    RequirementResult,
    RulebookDiffResponse,
    RulebookFileSet,
    RulebookStatusResponse,
    StatusResponse,
    SupportedProcedure,
)


class ServiceError(Exception):
    code = "service_error"


class InvalidRequestError(ServiceError):
    code = "invalid_request"


class UnsupportedScopeError(ServiceError):
    code = "unsupported_scope"


class GovernanceConfigError(ServiceError):
    code = "governance_config_error"


def _hash_note(note_text: str) -> str:
    return sha256((note_text or "").encode("utf-8")).hexdigest()[:16]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _freshness_window_days(check_frequency: str) -> int | None:
    mapping = {
        "hourly": 1,
        "daily": 2,
        "weekly": 8,
        "monthly": 35,
    }
    return mapping.get(str(check_frequency or "").strip().lower())


def _display_repo_relative_path(repo_root: Path, raw_path: str | Path | None) -> str | None:
    if raw_path is None:
        return None
    path = Path(str(raw_path))
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _compute_metrics(score_info: Dict[str, int]) -> EvaluationMetrics:
    total = int(score_info.get("total", 0) or 0)
    met = int(score_info.get("met_count", 0) or 0)
    not_met = int(score_info.get("not_met_count", 0) or 0)
    not_doc = int(score_info.get("not_documented_count", 0) or 0)

    extraction_success_rate = round(((met + not_met) / total * 100), 1) if total else 0.0
    compliance_rate = round((met / (met + not_met) * 100), 1) if (met + not_met) > 0 else None

    return EvaluationMetrics(
        extraction_success_rate=extraction_success_rate,
        extraction_failure_count=not_doc,
        compliance_rate=compliance_rate,
        compliant_count=met,
        non_compliant_count=not_met,
    )


def _read_drift_log(log_path: Path) -> List[Dict[str, Any]]:
    if not log_path.exists():
        return []

    events: List[Dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
    return events


class ReadinessService:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_app_config()
        configure_logging(self.config.log_level)
        self.logger = get_logger("pa_copilot.service")

    @cached_property
    def rules(self) -> Dict[str, Any]:
        return load_rules(str(self.config.rules_path))

    @cached_property
    def provenance(self) -> Dict[str, Any]:
        return load_provenance(self.config.provenance_path)

    @cached_property
    def policy_sources(self):
        return load_policy_sources(self.config.policy_sources_path)

    @cached_property
    def policy_source_by_procedure(self) -> Dict[tuple[str, str], Any]:
        return {(source.payer, source.procedure_code): source for source in self.policy_sources}

    @cached_property
    def demo_cases(self) -> List[DemoCase]:
        return list_demo_cases(self.config)

    def list_supported_procedures(self) -> List[SupportedProcedure]:
        out: List[SupportedProcedure] = []

        for payer, payer_config in self.rules["payers"].items():
            for procedure_code, procedure in payer_config["procedures"].items():
                provenance_entry = get_provenance_entry(self.provenance, payer, procedure_code)
                requirements = [RequirementDefinition.model_validate(requirement) for requirement in procedure.get("required", [])]
                metadata = self._build_procedure_metadata(procedure, requirements)
                provenance = self._build_procedure_provenance(payer, procedure_code, provenance_entry)
                out.append(
                    SupportedProcedure(
                        payer=payer,
                        procedure_code=procedure_code,
                        display_name=procedure.get("display_name", procedure_code),
                        monitored_for_drift=(payer, procedure_code) in self.policy_source_by_procedure,
                        policy_trust_level=policy_trust_from_provenance(provenance_entry),
                        required_field_keys=[requirement.key for requirement in requirements],
                        metadata=metadata,
                        provenance=provenance,
                        requirements=requirements,
                    )
                )

        return sorted(out, key=lambda item: (item.payer, item.procedure_code))

    def get_supported_procedure(self, payer: str, procedure_code: str) -> SupportedProcedure:
        for supported in self.list_supported_procedures():
            if supported.payer == payer and supported.procedure_code == procedure_code:
                return supported
        raise UnsupportedScopeError(
            f"Unsupported request scope: payer='{payer}', procedure_code='{procedure_code}'. "
            "Use /supported-procedures or the CLI list command to inspect current demo support."
        )

    def list_demo_case_summaries(self) -> List[DemoCase]:
        return self.demo_cases

    def get_rulebook_status(self) -> RulebookStatusResponse:
        try:
            return get_rulebook_status(
                self.config.repo_root,
                self.config.rulebook_manifest_path,
                RulebookFileSet(
                    rules_path=self.config.rules_path.as_posix(),
                    provenance_path=self.config.provenance_path.as_posix(),
                    policy_sources_path=self.config.policy_sources_path.as_posix(),
                ),
            )
        except RulebookError as exc:
            raise GovernanceConfigError(str(exc)) from exc

    def get_rulebook_diff(self, from_release_id: str, to_release_id: str) -> RulebookDiffResponse:
        try:
            return get_rulebook_diff(
                self.config.repo_root,
                self.config.rulebook_manifest_path,
                from_release_id=from_release_id,
                to_release_id=to_release_id,
            )
        except RulebookError as exc:
            raise GovernanceConfigError(str(exc)) from exc

    def get_demo_case_request(self, case_id: str) -> PARequest:
        case = get_demo_case(case_id, self.config)
        return demo_case_to_request(case)

    def validate_request(self, request: PARequest) -> List[str]:
        warnings: List[str] = []
        supported = self.get_supported_procedure(request.payer, request.procedure_code)
        supported_sites = supported.metadata.supported_sites

        if request.site_of_care not in supported_sites:
            raise UnsupportedScopeError(
                f"Unsupported site_of_care '{request.site_of_care}' for {request.payer} {request.procedure_code}. "
                f"Supported demo sites: {', '.join(supported_sites)}."
            )

        if not request.note_text.strip():
            warnings.append("No note text provided; missing requirements will force CANNOT_DETERMINE.")

        if not request.dx_codes:
            warnings.append("No diagnosis codes supplied; readiness is evaluated from note content and rule scope only.")

        specialty = request.specialty.strip().lower()
        if not specialty or specialty == "unknown":
            warnings.append("Ordering specialty not supplied; retained as 'unknown' for audit trace completeness.")

        return warnings

    def evaluate(self, request: PARequest) -> EvaluationResult:
        normalized_request = request.model_copy(
            update={
                "dx_codes": normalized_dx_codes(request.dx_codes),
                "specialty": request.specialty or "unknown",
            }
        )
        warnings = self.validate_request(normalized_request)
        supported = self.get_supported_procedure(normalized_request.payer, normalized_request.procedure_code)

        raw_facts, raw_evidence_map = extract_facts(normalized_request.note_text)
        requirement_payloads = [requirement.model_dump(exclude_none=True) for requirement in supported.requirements]
        results, reasons = evaluate_requirements(requirement_payloads, raw_facts, evidence_map=raw_evidence_map)

        if raw_facts.get("prior_imaging_result") == "unrecognized" and any(
            result.key == "prior_imaging_result" for result in results
        ):
            review_reason = "Imaging result is documented but its category is unrecognized; human review is required."
            results = [
                result.model_copy(update={"status": "NOT_MET", "reason": review_reason})
                if result.key == "prior_imaging_result"
                else result
                for result in results
            ]
            reasons = [
                f"{result.label}: {result.status} — {result.reason}"
                for result in results
                if result.status in ("NOT_DOCUMENTED", "NOT_MET")
            ]
            warnings.append(review_reason)

        overall = compute_overall_status(results)
        score_info = compute_readiness_score(results)
        metrics = _compute_metrics(score_info)
        blockers = self._build_blockers(results)
        invariant_errors = self._compute_invariant_errors(blockers, overall["overall_status"])

        provenance_entry = get_provenance_entry(self.provenance, normalized_request.payer, normalized_request.procedure_code)
        policy_trust_level = policy_trust_from_provenance(provenance_entry)
        if policy_trust_level != "verified":
            warnings.append("Policy trust remains DEMO for this procedure. Verify against official policy before real-world use.")

        structured_provenance = supported.provenance.model_dump(mode="json")
        rulebook_status = self.get_rulebook_status()

        audit = AuditTrace(
            run_id=str(uuid.uuid4()),
            timestamp_utc=_utc_now_iso(),
            note_hash=_hash_note(normalized_request.note_text),
            note_length=len(normalized_request.note_text or ""),
            payer=normalized_request.payer,
            procedure_code=normalized_request.procedure_code,
            procedure_name=supported.display_name,
            site_of_care=normalized_request.site_of_care,
            specialty=normalized_request.specialty,
            rules_version=str(self.rules.get("version")) if self.rules.get("version") is not None else None,
            rulebook_active_release_id=rulebook_status.active_release_id,
            policy_trust_level=policy_trust_level,
            provenance_snapshot=structured_provenance,
            facts_extracted=raw_facts,
            evidence_map=self._coerce_evidence_map(raw_evidence_map),
            requirements_checked=[result.key for result in results],
            overall_status=overall["overall_status"],
            submission_readiness=bool(overall["submission_readiness"]),
            blocking_issues=blockers,
            metrics=metrics,
            invariant_errors=invariant_errors,
            evaluation_warnings=warnings,
        )

        report = ReadinessReport(
            readiness_score=int(score_info.get("readiness_score", 0) or 0),
            not_documented_count=int(score_info.get("not_documented_count", 0) or 0),
            not_met_count=int(score_info.get("not_met_count", 0) or 0),
            met_count=int(score_info.get("met_count", 0) or 0),
            results=results,
            rule_reasons=reasons,
            audit_trail=audit.model_dump(mode="json"),
            letter_draft="",
        )

        result = EvaluationResult(
            request=normalized_request,
            supported_procedure=supported,
            overall_status=overall["overall_status"],
            submission_readiness=bool(overall["submission_readiness"]),
            readiness_score=report.readiness_score,
            results=results,
            rule_reasons=reasons,
            facts=raw_facts,
            evidence_map=self._coerce_evidence_map(raw_evidence_map),
            blockers=blockers,
            metrics=metrics,
            warnings=warnings,
            policy_trust_level=policy_trust_level,
            provenance=structured_provenance,
            audit_trail=audit,
            report=report,
        )

        log_event(
            self.logger,
            logging.INFO,
            "readiness_evaluated",
            payer=normalized_request.payer,
            procedure_code=normalized_request.procedure_code,
            overall_status=result.overall_status,
            submission_readiness=result.submission_readiness,
            note_hash=audit.note_hash,
            blockers_missing=len(blockers.not_documented),
            blockers_not_met=len(blockers.not_met),
        )
        return result

    def generate_letter(
        self, evaluation: EvaluationResult, letter_type: LetterType = "submission_cover_letter"
    ) -> tuple[str, Dict[str, Any]]:
        return draft_letter(
            evaluation.request.model_copy(update={"note_text": ""}),
            evaluation.report,
            letter_type=letter_type,
            policy_trust_level=evaluation.policy_trust_level,
        )

    def get_drift_status(self) -> DriftStatusReport:
        events = _read_drift_log(self.config.snapshot_root / "drift_log.jsonl")
        latest_event_by_id = {str(event.get("id")): event for event in events if event.get("id")}

        statuses: List[DriftSourceStatus] = []
        any_review_required = False
        stale_source_count = 0

        for source in self.policy_sources:
            latest_snapshot = read_latest_snapshot(self.config.snapshot_root, source.id)
            status = "NO_BASELINE" if latest_snapshot is None else "OK"
            event = latest_event_by_id.get(source.id, {})
            if event.get("event") == "POLICY_DRIFT_DETECTED":
                status = "REVIEW_REQUIRED"
                any_review_required = True

            provenance_entry = get_provenance_entry(self.provenance, source.payer, source.procedure_code)
            last_checked_utc = (latest_snapshot or {}).get("fetched_at_utc")
            last_checked_dt = _parse_utc_iso(last_checked_utc)
            freshness_window_days = _freshness_window_days(source.check_frequency)
            days_since_last_checked = None
            freshness_status = "UNKNOWN"
            review_reason = None

            if last_checked_dt is not None:
                age_seconds = max((datetime.now(timezone.utc) - last_checked_dt).total_seconds(), 0)
                days_since_last_checked = int(age_seconds // 86400)
                freshness_status = "CURRENT"
                if freshness_window_days is not None and age_seconds > freshness_window_days * 86400:
                    freshness_status = "STALE"
                    stale_source_count += 1
                    any_review_required = True
                    review_reason = f"Snapshot exceeds the configured {source.check_frequency} monitoring window."
            elif latest_snapshot is None:
                any_review_required = True
                review_reason = "No baseline snapshot exists yet for this monitored source."

            if status == "REVIEW_REQUIRED":
                review_reason = "Detected policy drift requires human rule review before the related rule should be trusted."

            statuses.append(
                DriftSourceStatus(
                    id=source.id,
                    payer=source.payer,
                    procedure_code=source.procedure_code,
                    source_name=source.source_name,
                    source_type=source.source_type,
                    url=source.url,
                    trust_level=source.trust_level,
                    check_frequency=source.check_frequency,
                    owner=source.owner,
                    status=status,
                    last_checked_utc=last_checked_utc,
                    days_since_last_checked=days_since_last_checked,
                    freshness_status=freshness_status,
                    latest_hash=(latest_snapshot or {}).get("content_hash_sha256"),
                    latest_event=event.get("event"),
                    latest_snapshot_path=_display_repo_relative_path(
                        self.config.repo_root,
                        self.config.snapshot_root / source.id / "latest.json",
                    ),
                    latest_diff_path=_display_repo_relative_path(self.config.repo_root, event.get("diff_path")),
                    rule_source_label=str(
                        provenance_entry.get("rule_source_label") or provenance_entry.get("source_name") or ""
                    )
                    or None,
                    last_rule_reviewed=str(provenance_entry.get("last_reviewed") or "") or None,
                    review_reason=review_reason,
                    notes=str(source.notes or provenance_entry.get("notes") or "").strip() or None,
                )
            )

        return DriftStatusReport(
            sources=sorted(statuses, key=lambda item: (item.payer, item.procedure_code)),
            any_review_required=any_review_required,
            stale_source_count=stale_source_count,
        )

    def get_status(self) -> StatusResponse:
        rulebook_status = self.get_rulebook_status()
        return StatusResponse(
            service="Prior Authorization Readiness Copilot",
            rules_version=str(self.rules.get("version")) if self.rules.get("version") is not None else None,
            rulebook_active_release_id=rulebook_status.active_release_id,
            rulebook_active_rules_version=rulebook_status.runtime_rules_version,
            supported_procedures=len(self.list_supported_procedures()),
            demo_cases=len(self.demo_cases),
            monitored_policy_sources=len(self.policy_sources),
        )

    @staticmethod
    def _coerce_evidence_map(raw_evidence_map: Dict[str, Any]) -> Dict[str, List[EvidenceSpan]]:
        out: Dict[str, List[EvidenceSpan]] = {}
        for key, spans in (raw_evidence_map or {}).items():
            out[key] = []
            for span in spans or []:
                if not isinstance(span, dict):
                    continue
                start = span.get("start")
                end = span.get("end")
                text = str(span.get("text", "")).strip()
                if not isinstance(start, int) or not isinstance(end, int) or end <= start or start < 0 or not text:
                    continue
                out[key].append(EvidenceSpan(start=start, end=end, text=text))
        return out

    @staticmethod
    def _build_blockers(results: List[RequirementResult]) -> BlockingIssueSummary:
        missing = [
            BlockingIssue(key=result.key, label=result.label, status=result.status, reason=result.reason)
            for result in results
            if result.status == "NOT_DOCUMENTED"
        ]
        not_met = [
            BlockingIssue(key=result.key, label=result.label, status=result.status, reason=result.reason)
            for result in results
            if result.status == "NOT_MET"
        ]
        return BlockingIssueSummary(not_documented=missing, not_met=not_met)

    @staticmethod
    def _compute_invariant_errors(blockers: BlockingIssueSummary, overall_status: str) -> List[str]:
        errors: List[str] = []
        if blockers.not_documented and overall_status != "CANNOT_DETERMINE":
            errors.append("Invariant violation: NOT_DOCUMENTED blockers exist but overall_status is not CANNOT_DETERMINE.")
        if (not blockers.not_documented) and blockers.not_met and overall_status == "READY":
            errors.append("Invariant violation: NOT_MET blockers exist but overall_status is READY.")
        if (not blockers.not_documented) and (not blockers.not_met) and overall_status != "READY":
            errors.append("Invariant violation: no blockers exist but overall_status is not READY.")
        return errors

    @staticmethod
    def _build_procedure_metadata(
        procedure: Dict[str, Any], requirements: List[RequirementDefinition]
    ) -> ProcedureMetadata:
        raw_metadata = procedure.get("metadata") or {}
        return ProcedureMetadata(
            category=str(raw_metadata.get("category") or "administrative_review"),
            rule_family=str(raw_metadata.get("rule_family") or "deterministic_readiness"),
            summary=str(raw_metadata.get("summary") or procedure.get("display_name") or "Procedure rule set"),
            supported_sites=[str(site) for site in raw_metadata.get("supported_sites") or ["outpatient"]],
            last_rule_update=raw_metadata.get("last_rule_update"),
            notes=[str(note) for note in raw_metadata.get("notes") or []],
        )

    def _build_procedure_provenance(
        self, payer: str, procedure_code: str, provenance_entry: Dict[str, Any]
    ) -> ProcedureProvenance:
        policy_source = self.policy_source_by_procedure.get((payer, procedure_code))
        return ProcedureProvenance(
            source_name=provenance_entry.get("source_name"),
            source_type=provenance_entry.get("source_type"),
            source_url=provenance_entry.get("source_url"),
            rule_source_label=provenance_entry.get("rule_source_label") or provenance_entry.get("source_name"),
            last_reviewed=provenance_entry.get("last_reviewed"),
            rule_last_updated=provenance_entry.get("rule_last_updated"),
            monitored_source_id=policy_source.id if policy_source else provenance_entry.get("monitored_source_id"),
            monitored_source_name=policy_source.source_name if policy_source else None,
            monitored_source_url=policy_source.url if policy_source else None,
            monitored_check_frequency=policy_source.check_frequency if policy_source else None,
            monitored_source_owner=policy_source.owner if policy_source else None,
            notes=provenance_entry.get("notes") or (policy_source.notes if policy_source else None),
        )
