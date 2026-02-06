from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Dict, List, Tuple, Optional

from .schemas import PARequest, ReadinessReport


ALLOWED_STATUSES = {"MET", "NOT_MET", "NOT_DOCUMENTED"}
ALLOWED_LETTER_TYPES = {"submission_cover_letter", "missing_info_request", "appeal_template"}
ALLOWED_POLICY_TRUST = {"demo", "verified"}


@dataclass(frozen=True)
class LetterMeta:
    letter_version: str
    generated_timestamp_utc: str
    overall_status: str  # READY | NOT_READY | CANNOT_DETERMINE
    letter_type: str  # submission_cover_letter | missing_info_request | appeal_template
    policy_trust_level: str  # demo | verified
    cited_snippets_count: int
    contains_missing_documentation: bool
    draft_blocked: bool
    draft_blocked_reasons: List[str]
    letter_hash_sha256_16: str  # short hash for audit linkage


def letter_hash(text: str) -> str:
    """Short deterministic hash of the letter text for audit linkage (no raw content)."""
    h = sha256((text or "").encode("utf-8")).hexdigest()
    return h[:16]


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


def _validate_inputs(
    pa: PARequest,
    report: ReadinessReport,
    letter_type: str,
    policy_trust_level: str,
) -> List[str]:
    reasons: List[str] = []

    if not pa.payer or not pa.payer.strip():
        reasons.append("Missing payer.")
    if not pa.procedure_code or not pa.procedure_code.strip():
        reasons.append("Missing procedure_code.")
    if letter_type not in ALLOWED_LETTER_TYPES:
        reasons.append(f"Invalid letter_type: {letter_type}")
    if policy_trust_level not in ALLOWED_POLICY_TRUST:
        reasons.append(f"Invalid policy_trust_level: {policy_trust_level}")

    if not isinstance(report.results, list) or len(report.results) == 0:
        reasons.append("Missing requirement results.")
    else:
        for r in report.results:
            if r.status not in ALLOWED_STATUSES:
                reasons.append(f"Invalid requirement status for '{r.key}': {r.status}")
            if not r.reason or not r.reason.strip():
                reasons.append(f"Missing reason for requirement '{r.key}'.")
            if r.evidence_snippets is None:
                reasons.append(f"evidence_snippets is None for requirement '{r.key}'.")

    # Cross-check counts (block if inconsistent; prevents subtle downstream confusion)
    calc = {"MET": 0, "NOT_MET": 0, "NOT_DOCUMENTED": 0}
    for r in (report.results or []):
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
    words = (s or "").strip().split()
    if len(words) <= max_words:
        return (s or "").strip()
    return " ".join(words[:max_words]) + "…"


def _policy_trust_line(policy_trust_level: str) -> str | None:
    """
    Returns a single-line policy trust disclaimer to be injected
    into the letter header. Presentation-only; no logic impact.
    """
    if policy_trust_level == "demo":
        return (
            "Policy trust level: DEMO — criteria are illustrative only. "
            "Verify against the official payer policy before submission."
        )

    if policy_trust_level == "verified":
        return (
            "Policy trust level: VERIFIED — criteria derived from documented payer policy sources."
        )

    return None



def _title_for(letter_type: str) -> str:
    if letter_type == "missing_info_request":
        return "PRIOR AUTHORIZATION MISSING INFORMATION REQUEST"
    if letter_type == "appeal_template":
        return "PRIOR AUTHORIZATION APPEAL TEMPLATE (ADMINISTRATIVE)"
    return "PRIOR AUTHORIZATION ADMINISTRATIVE READINESS SUMMARY"


def draft_letter(
    pa: PARequest,
    report: ReadinessReport,
    letter_type: str = "submission_cover_letter",
    policy_trust_level: str = "demo",
) -> Tuple[str, Dict]:
    """
    Write-only letter drafting.

    - Uses ONLY requirement results + snippets/hints already present.
    - Does not change statuses, does not infer, does not promise approval.
    - Policy trust phrasing is injected based on policy_trust_level.
    Returns (letter_text, letter_metadata_dict).
    """
    ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    blocked_reasons = _validate_inputs(pa, report, letter_type, policy_trust_level)

    if blocked_reasons:
        text = (
            "DRAFT_BLOCKED\n\n"
            "The letter could not be generated due to input validation errors:\n"
            + "\n".join([f"- {r}" for r in blocked_reasons])
            + "\n"
        )
        meta = LetterMeta(
            letter_version="1.1",
            generated_timestamp_utc=ts,
            overall_status="UNKNOWN",
            letter_type=letter_type,
            policy_trust_level=policy_trust_level,
            cited_snippets_count=0,
            contains_missing_documentation=False,
            draft_blocked=True,
            draft_blocked_reasons=blocked_reasons,
            letter_hash_sha256_16=letter_hash(text),
        )
        return text, meta.__dict__

    overall = _derive_overall_status(report)

    # Aggregate snippet usage
    all_snips: List[str] = []
    for r in report.results:
        all_snips.extend(r.evidence_snippets or [])
    cited_count = len([s for s in all_snips if s and str(s).strip()])

        # Header
    header_lines = [
        f"Payer: {pa.payer}",
        f"Procedure: {pa.procedure_code}",
        f"Site of care: {pa.site_of_care}",
        f"Specialty: {pa.specialty}",
        f"Generated: {ts}",
    ]
    
    if pa.dx_codes:
        header_lines.append(f"Diagnosis codes: {', '.join(pa.dx_codes)}")
    
    trust_line = _policy_trust_line(policy_trust_level)
    if trust_line:
        header_lines.append(trust_line)

    # Letter-type conditioned framing (still administrative)
    # NOTE: letter_type does not change readiness logic; only presentation emphasis.
    if letter_type == "missing_info_request":
        summary = (
            "Summary:\n"
            "The documentation provided is insufficient to determine administrative readiness because one or more required elements are not documented. "
            "This does not imply criteria failure and does not guarantee payer approval.\n"
        )
    elif letter_type == "appeal_template":
        summary = (
            "Summary:\n"
            "This template summarizes documentation-based administrative criteria relevant to the request and is intended to support an appeal or reconsideration packet. "
            "It does not provide clinical recommendations and does not guarantee payer approval.\n"
        )
    else:
        # Default: submission_cover_letter
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
        else:
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

        if r.evidence_snippets:
            req_lines.append("  Evidence:")
            for snip in r.evidence_snippets[:5]:
                if snip and str(snip).strip():
                    req_lines.append(f'   - "{_format_snippet(str(snip))}"')
        else:
            req_lines.append("  Evidence: No supporting snippet available.")

        if r.status == "NOT_DOCUMENTED":
            hint = (r.evidence or "").strip()
            if hint:
                missing_checklist.append(f"- {r.label}: {hint}")
            else:
                missing_checklist.append(f"- {r.label}: Documentation not present (no hint provided).")

    # Missing documentation section only when needed / relevant
    include_missing_section = (overall == "CANNOT_DETERMINE") or (letter_type == "missing_info_request")
    missing_section = ""
    if include_missing_section and missing_checklist:
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

    title = _title_for(letter_type)
    letter = (
        f"{title}\n\n"
        + "\n".join(header_lines)
        + "\n\n"
        + f"Overall Status: {overall}\n\n"
        + summary
        + "\n"
        + "\n".join(req_lines)
        + missing_section
        + closing
    )

    meta = LetterMeta(
        letter_version="1.1",
        generated_timestamp_utc=ts,
        overall_status=overall,
        letter_type=letter_type,
        policy_trust_level=policy_trust_level,
        cited_snippets_count=cited_count,
        contains_missing_documentation=(report.not_documented_count > 0),
        draft_blocked=False,
        draft_blocked_reasons=[],
        letter_hash_sha256_16=letter_hash(letter),
    )
    return letter, meta.__dict__
