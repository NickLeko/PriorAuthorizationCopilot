from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .schemas import DriftStatusReport, EvaluationResult, RulebookDiffResponse, RulebookStatusResponse


def export_evaluation_payload(
    evaluation: EvaluationResult,
    letter_text: Optional[str] = None,
    letter_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = evaluation.model_dump(mode="json")
    if letter_text is not None or letter_meta is not None:
        payload["letter"] = {
            "text": letter_text or "",
            "metadata": letter_meta or {},
        }
    return payload


def write_json_artifact(payload: Dict[str, Any], output_path: str | Path) -> Path:
    artifact_path = Path(output_path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact_path


def render_cli_evaluation(evaluation: EvaluationResult) -> str:
    source_label = (
        evaluation.supported_procedure.provenance.rule_source_label or evaluation.supported_procedure.provenance.source_name or "n/a"
    )
    lines = [
        "Prior Authorization Readiness Copilot",
        f"Payer: {evaluation.request.payer}",
        f"Procedure: {evaluation.request.procedure_code} ({evaluation.supported_procedure.display_name})",
        f"Category: {evaluation.supported_procedure.metadata.category}",
        f"Rule family: {evaluation.supported_procedure.metadata.rule_family}",
        f"Rule source: {source_label}",
        f"Rulebook release: {evaluation.audit_trail.rulebook_active_release_id or 'n/a'}",
        f"Overall status: {evaluation.overall_status}",
        f"Submission readiness: {'YES' if evaluation.submission_readiness else 'NO'}",
        f"Documentation coverage: {evaluation.metrics.documentation_coverage_pct:.1f}%",
        (
            "Criteria met among evaluable requirements: "
            f"{evaluation.metrics.criteria_met_count}/{evaluation.metrics.evaluable_requirement_count}"
        ),
        f"Policy trust level: {evaluation.policy_trust_level.upper()}",
        "",
        "Blocking summary:",
        f"- Missing requirements: {len(evaluation.blockers.not_documented)}",
        f"- Documented but not met: {len(evaluation.blockers.not_met)}",
        f"- Documented but requiring review: {len(evaluation.blockers.needs_review)}",
    ]

    if evaluation.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend([f"- {warning}" for warning in evaluation.warnings])

    lines.extend(["", "Requirement results:"])
    for result in evaluation.results:
        lines.append(f"- {result.label}: {result.status} | {result.reason} | verification={result.verification.state}")
        if result.verification.state == "HUMAN_VERIFIED":
            lines.append(f"  Verified by {result.verification.reviewer} at {result.verification.verified_at.isoformat()}")

    return "\n".join(lines)


def render_drift_status(report: DriftStatusReport) -> str:
    lines = [
        "Policy Drift Status",
        f"Review required: {'YES' if report.any_review_required else 'NO'}",
        f"Stale monitored sources: {report.stale_source_count}",
        "",
    ]
    for source in report.sources:
        lines.append(
            f"- {source.payer} {source.procedure_code} | {source.source_name or 'unnamed source'} | {source.status} | "
            f"trust={source.trust_level} | check={source.check_frequency} | "
            f"freshness={source.freshness_status or 'UNKNOWN'} | last_checked={source.last_checked_utc or 'n/a'}"
        )
    return "\n".join(lines)


def render_rulebook_status(report: RulebookStatusResponse) -> str:
    lines = [
        "Rulebook Status",
        f"Active release: {report.active_release_id or 'n/a'}",
        f"Runtime rules version: {report.runtime_rules_version or 'n/a'}",
        "",
    ]
    for release in report.releases:
        runtime = f" | runtime_match={'yes' if release.runtime_matches else 'no'}" if release.runtime_matches is not None else ""
        lines.append(
            f"- {release.release_id} | stage={release.stage or 'unassigned'} | "
            f"rules_version={release.rules_version or 'n/a'} | procedures={len(release.procedures)}{runtime}"
        )
    if report.validation_errors:
        lines.extend(["", "Validation errors:"])
        lines.extend([f"- {item}" for item in report.validation_errors])
    return "\n".join(lines)


def render_rulebook_diff(report: RulebookDiffResponse) -> str:
    lines = [
        "Rulebook Diff",
        f"From: {report.from_release_id} ({report.from_stage or 'unassigned'})",
        f"To: {report.to_release_id} ({report.to_stage or 'unassigned'})",
        "",
    ]
    lines.extend([f"- {line}" for line in report.summary_lines])
    return "\n".join(lines)


def render_drift_markdown(report: DriftStatusReport) -> str:
    lines = [
        "# Drift Report",
        "",
        f"- Review required: {'YES' if report.any_review_required else 'NO'}",
        f"- Stale monitored sources: {report.stale_source_count}",
        "",
        "## Sources",
    ]
    for source in report.sources:
        lines.extend(
            [
                "",
                f"### {source.payer} {source.procedure_code}",
                f"- Source: {source.source_name or 'unnamed source'}",
                f"- Status: {source.status}",
                f"- Freshness: {source.freshness_status or 'UNKNOWN'}",
                f"- Last checked: {source.last_checked_utc or 'n/a'}",
                f"- Rule source label: {source.rule_source_label or 'n/a'}",
                f"- Last rule reviewed: {source.last_rule_reviewed or 'n/a'}",
                f"- Review reason: {source.review_reason or 'n/a'}",
                f"- Snapshot path: {source.latest_snapshot_path or 'n/a'}",
                f"- Diff path: {source.latest_diff_path or 'n/a'}",
            ]
        )
    return "\n".join(lines) + "\n"


def render_rulebook_diff_markdown(report: RulebookDiffResponse) -> str:
    lines = [
        "# Rulebook Diff",
        "",
        f"- From: `{report.from_release_id}` ({report.from_stage or 'unassigned'})",
        f"- To: `{report.to_release_id}` ({report.to_stage or 'unassigned'})",
        "",
        "## Summary",
    ]
    lines.extend([f"- {line}" for line in report.summary_lines])
    return "\n".join(lines) + "\n"
