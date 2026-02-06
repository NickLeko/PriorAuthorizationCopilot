from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

from .schemas import PARequest, ReadinessReport, RequirementResult


ALLOWED_STATUSES = {"MET", "NOT_MET", "NOT_DOCUMENTED"}


@dataclass(frozen=True)
class LetterMeta:
    letter_version: str
    generated_timestamp_utc: str
    overall_status: str  # READY | NOT_READY | CANNOT_DETERMINE
    cited_snippets_count: int
    contains_missing_documentation: bool
    draft_blocked: bool
    draft_blocked_reasons: List[str]


def _derive_overall_status(report: ReadinessReport) -> str:
    # Frozen invariant mapping:
    # - Any NOT_DOCUMENTED => CANNOT_DETERMINE
    # - Else any NOT_MET => NOT_READY
    # - Else READY
    if report.not_documented_count > 0:
        return "CANNOT_DETERMINE"
    if report.not_met_count > 0:
        return "NOT_READY"
    return "READY"


def _validate_inputs(pa: PARequest, report: ReadinessReport) -> List[str]:
    reasons: List[str] = []

    if not pa.payer or not pa.payer.strip():
        reasons.append("Missing payer.")
    if not pa.procedure_code or not pa.procedure_code.strip():
        reasons.append("Missing procedure_code.")
    if not isinstance(report.results, list) or len(report.results) == 0:
        reasons.append("Missing requirement results.")
    else:
        for r in report.results:
            if r.status not in ALLOWED_STATUSES:
                reasons.append(f"Invalid requirement status for '{r.key}': {r.status}")
            # Reason must exist for auditability
            if not r.reason or not r.reason.strip():
                reasons.append(f"Missing reason for requirement '{r.key}'.")
            # evidence_snippets must be a list (may be empty)
            if r.evidence_snippets is None:
                reasons.append(f"evidence_snippets is None for requirement '{r.key}'.")

    # Cross-check counts (soft validation; block only if obviously inconsistent)
    calc = {
        "MET": 0,
        "NOT_MET": 0,
        "NOT_DOCUMENTED": 0,
    }
    if isinstance(report.results, list):
        for r in report.results:
            if r.status in calc:
                calc[r.status] += 1

    if report.met_count != calc["MET"]:
        reasons.append("met_count does not match results.")
    if report.not_met_count != calc["NOT_MET"]:
        reasons.append("not_met_count does not match results.")
    if report.not_documented_count != calc["NOT_DOCUMENTED"]:
        reasons.append("not_documented_count does not match results.")

    return reasons


def _format_snippet(s: str, max_words: int = 25) -> str:
    # Keep snippets short and verbatim; never paraphrase.
    words = s.strip().split()
    if len(words) <= max_words:
        return s.strip()
    return " ".join(words[:max_words]) + "…"


def draft_letter(pa: PARequest, report: ReadinessReport) -> Tuple[str, Dict]:
    """
    Write-only letter drafting.
    - Uses ONLY requirement results + snippets/hints already present.
    - Does not change statuses, does not infer, does not promise approval.
    Returns (letter_text, letter_metadata_dict).
    """
    blocked_reasons = _validate_inputs(pa, report)
    ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    if blocked_reasons:
        meta = LetterMeta(
            letter_version="1.0",
            generated_timestamp_utc=ts,
            overall_status="UNKNOWN",
            cited_snippets_count=0,
            contains_missing_documentation=False,
            draft_blocked=True,
            draft_blocked_reasons=blocked_reasons,
        )
        text = (
            "DRAFT_BLOCKED\n\n"
            "The letter could not be generated due to input validation errors:\n"
            + "\n".join([f"- {r}" for r in blocked_reasons])
            + "\n"
        )
        return text, meta.__dict__

    overall = _derive_overall_status(report)

    # Aggregate snippet usage
    all_snips: List[str] = []
    for r in report.results:
        all_snips.extend(r.evidence_snippets or [])

    cited_count = len([s for s in all_snips if s and s.strip()])

    meta = LetterMeta(
        letter_version="1.0",
        generated_timestamp_utc=ts,
        overall_status=overall,
        cited_snippets_count=cited_count,
        contains_missing_documentation=(report.not_documented_count > 0),
        draft_blocked=False,
        draft_blocked_reasons=[],
    )

    header_lines = [
        f"Payer: {pa.payer}",
        f"Procedure: {pa.procedure_code}",
        f"Site of care: {pa.site_of_care}",
        f"Specialty: {pa.specialty}",
        f"Generated: {ts}",
    ]
    if pa.dx_codes:
        header_lines.append(f"Diagnosis codes: {', '.join(pa.dx_codes)}")

    # Status-specific framing (administrative readiness only)
    if overall == "READY":
        summary = (
            "Summary:\n"
            "This letter supports administrative submission readiness based on the documentation present in the record. "
            "This does not guarantee payer approval.\n"
        )
    elif overall == "NOT_READY":
        summary = (
            "Summary:\n"
            "The request is not administratively ready for submission because one or more documented requirements do not meet thresholds. "
            "This does not represent a clinical judgment and does not guarantee payer approval.\n"
        )
    else:  # CANNOT_DETERMINE
        summary = (
            "Summary:\n"
            "Administrative readiness cannot be determined because one or more required elements are not documented in the record provided. "
            "This does not imply criteria failure and does not guarantee payer approval.\n"
        )

    # Requirements section
    req_lines: List[str] = ["Requirements:"]
    missing_checklist: List[str] = []

    for r in report.results:
        req_lines.append(f"- {r.label} ({r.key}): {r.status}")
        req_lines.append(f"  Reason: {r.reason}")

        # Evidence snippets (verbatim, short)
        if r.evidence_snippets:
            req_lines.append("  Evidence:")
            for snip in r.evidence_snippets[:5]:  # cap verbosity
                if snip and snip.strip():
                    req_lines.append(f'   - "{_format_snippet(snip)}"')
        else:
            req_lines.append("  Evidence: No supporting snippet available.")

        # Missing checklist: only for NOT_DOCUMENTED
        if r.status == "NOT_DOCUMENTED":
            hint = (r.evidence or "").strip()
            if hint:
                missing_checklist.append(f"- {r.label}: {hint}")
            else:
                missing_checklist.append(f"- {r.label}: Documentation not present (no hint provided).")

    # Missing documentation section only when needed
    missing_section = ""
    if overall == "CANNOT_DETERMINE" and missing_checklist:
        missing_section = (
            "\nMissing Documentation (Checklist):\n"
            + "\n".join(missing_checklist)
            + "\n"
        )

    closing = (
        "\nClosing:\n"
        "This letter summarizes documentation-based administrative readiness for prior authorization submission. "
        "It does not provide clinical recommendations and does not predict approval outcomes.\n"
    )

    letter = (
        "PRIOR AUTHORIZATION ADMINISTRATIVE READINESS SUMMARY\n\n"
        + "\n".join(header_lines)
        + "\n\n"
        + f"Overall Status: {overall}\n\n"
        + summary
        + "\n"
        + "\n".join(req_lines)
        + missing_section
        + closing
    )

    return letter, meta.__dict__
