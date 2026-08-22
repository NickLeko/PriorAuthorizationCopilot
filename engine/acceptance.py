from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from .rendering import export_evaluation_payload
from .service import ReadinessService

DEFAULT_ACCEPTANCE_CASE_IDS = [
    "MRI-01-complete",
    "MRI-08-edge-below-threshold",
    "CPAP-02-borderline",
    "MRI-KNEE-01-ready",
]


def _normalize_audit_trail(audit: Dict[str, Any]) -> Dict[str, Any]:
    normalized = deepcopy(audit)
    if normalized.get("run_id"):
        normalized["run_id"] = "__RUN_ID__"
    if normalized.get("timestamp_utc"):
        normalized["timestamp_utc"] = "__TIMESTAMP_UTC__"
    return normalized


def normalize_evaluation_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = deepcopy(payload)
    if isinstance(normalized.get("audit_trail"), dict):
        normalized["audit_trail"] = _normalize_audit_trail(normalized["audit_trail"])
    report = normalized.get("report")
    if isinstance(report, dict) and isinstance(report.get("audit_trail"), dict):
        report["audit_trail"] = _normalize_audit_trail(report["audit_trail"])
    return normalized


def normalize_drift_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = deepcopy(payload)
    for source in normalized.get("sources") or []:
        if source.get("days_since_last_checked") is not None:
            source["days_since_last_checked"] = "__DAYS_SINCE_LAST_CHECKED__"
    return normalized


def build_acceptance_evaluation_payload(service: ReadinessService, case_id: str) -> Dict[str, Any]:
    request = service.get_demo_case_request(case_id)
    evaluation = service.evaluate(request)
    return normalize_evaluation_payload(export_evaluation_payload(evaluation))


def build_acceptance_governance_payloads(service: ReadinessService) -> Dict[str, Dict[str, Any]]:
    return {
        "drift_status": normalize_drift_payload(service.get_drift_status().model_dump(mode="json")),
        "rulebook_status": service.get_rulebook_status().model_dump(mode="json"),
        "rulebook_diff_reviewed_vs_active": service.get_rulebook_diff(
            "2026-04-09-reviewed-v0.4",
            "2026-08-22-active-v1.0",
        ).model_dump(mode="json"),
    }
