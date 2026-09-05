from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Dict, List, Tuple

from .schemas import (
    LetterDraftInput,
    LetterType,
    OverallStatus,
    PolicyTrustLevel,
    RequirementStatus,
)

ALLOWED_STATUSES: set[RequirementStatus] = {"MET", "NOT_MET", "NOT_DOCUMENTED", "NEEDS_REVIEW"}
ALLOWED_LETTER_TYPES: set[LetterType] = {"submission_cover_letter", "missing_info_request", "appeal_template"}
ALLOWED_POLICY_TRUST: set[PolicyTrustLevel] = {"demo", "verified"}

# Enumerated phrases checked as lowercased substrings in composed output.
# This is a narrow phrase-list guard, not a semantic guarantee against every
# clinical or approval-language variant. Administrative references to documented
# diagnoses or Dx codes are allowed as source/request labels.
PROHIBITED_SUBSTRINGS = [
    "clinical diagnosis",
    "new diagnosis",
    "diagnosed with",
    "dx",
    "impression",
    "assessment",
    "hx",
    "history",
    "treatment",
    "recommended",
    "should start",
    "should take",
    "high risk",
    "risk score",
    "probability of approval",
    "approval is expected",
    "approval likely",
    "likely to be approved",
    "will be approved",
    "guaranteed approval",
    "authorization approved",
    "payer will authorize",
    "clinically indicated",
    "meets medical necessity",
    "medical necessity determination",
    # Note: "medically necessary" is prohibited by default per contract.
    "medically necessary",
]

PROHIBITED_DOSING_PATTERNS = [
    re.compile(
        r"\b(?:\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?|iu|tablets?|capsules?)|"
        r"(?:mg|mcg|g|ml|units?|iu|tablets?|capsules?)\s*\d+(?:\.\d+)?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:daily|bid|tid|qid)\b", re.IGNORECASE),
    re.compile(r"\bq\s*\d+\s*h\b", re.IGNORECASE),
    re.compile(r"\bevery\s+\d+\s+hours?\b", re.IGNORECASE),
    re.compile(r"\b\d+\s+times?\s+per\s+day\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class LetterMeta:
    letter_version: str
    generated_timestamp_utc: str
    overall_status: OverallStatus
    letter_type: LetterType
    policy_trust_level: PolicyTrustLevel
    cited_snippets_count: int
    contains_missing_documentation: bool
    draft_blocked: bool
    draft_blocked_reasons: List[str]
    letter_hash_sha256_16: str  # short hash for audit linkage


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def letter_hash(text: str) -> str:
    """Return a short deterministic hash of the letter text for audit linkage."""
    h = sha256((text or "").encode("utf-8")).hexdigest()
    return h[:16]


def _derive_overall_status(draft_input: LetterDraftInput) -> OverallStatus:
    # Frozen invariant mapping:
    # - Any NOT_DOCUMENTED => CANNOT_DETERMINE
    # - Else any NEEDS_REVIEW => NEEDS_REVIEW
    # - Else any NOT_MET => NOT_READY
    # - Else any unverified fact => PENDING_VERIFICATION; otherwise READY
    if draft_input.not_documented_count > 0:
        return "CANNOT_DETERMINE"
    if draft_input.needs_review_count > 0:
        return "NEEDS_REVIEW"
    if draft_input.not_met_count > 0:
        return "NOT_READY"
    if any(result.verification.state != "HUMAN_VERIFIED" for result in draft_input.results):
        return "PENDING_VERIFICATION"
    return "READY"


def _sanitize_dx_codes(dx_codes: List[str]) -> List[str]:
    """
    Conservative sanitation:
      - strip spaces
      - uppercase
      - remove '%' and ASCII spaces
    No validation against ICD catalogs (no inference).
    """
    out: List[str] = []
    for c in dx_codes or []:
        s = (c or "").strip().upper().replace(" ", "").replace("%", "")
        if s:
            out.append(s)
    # Dedup preserve order
    dedup: List[str] = []
    seen = set()
    for s in out:
        if s not in seen:
            seen.add(s)
            dedup.append(s)
    return dedup


def _validate_inputs(
    draft_input: LetterDraftInput,
    letter_type: str,
) -> List[str]:
    reasons: List[str] = []
    request = draft_input.request

    if not request.payer or not request.payer.strip():
        reasons.append("Missing payer.")
    if not request.procedure_code or not request.procedure_code.strip():
        reasons.append("Missing procedure_code.")
    if letter_type not in ALLOWED_LETTER_TYPES:
        reasons.append(f"Invalid letter_type: {letter_type}")
    if draft_input.policy_trust_level not in ALLOWED_POLICY_TRUST:
        reasons.append(f"Invalid policy_trust_level: {draft_input.policy_trust_level}")

    if not isinstance(draft_input.results, list) or len(draft_input.results) == 0:
        reasons.append("Missing requirement results.")
    else:
        for r in draft_input.results:
            if r.status not in ALLOWED_STATUSES:
                reasons.append(f"Invalid requirement status for '{r.key}': {r.status}")
            if not r.reason or not r.reason.strip():
                reasons.append(f"Missing reason for requirement '{r.key}'.")
            if r.evidence_snippets is None:
                reasons.append(f"evidence_snippets is None for requirement '{r.key}'.")

    # Cross-check counts (block if inconsistent; prevents subtle downstream confusion)
    calc = {"MET": 0, "NOT_MET": 0, "NOT_DOCUMENTED": 0, "NEEDS_REVIEW": 0}
    for r in draft_input.results or []:
        if r.status in calc:
            calc[r.status] += 1

    if draft_input.met_count != calc["MET"]:
        reasons.append("met_count does not match results.")
    if draft_input.not_met_count != calc["NOT_MET"]:
        reasons.append("not_met_count does not match results.")
    if draft_input.not_documented_count != calc["NOT_DOCUMENTED"]:
        reasons.append("not_documented_count does not match results.")
    if draft_input.needs_review_count != calc["NEEDS_REVIEW"]:
        reasons.append("needs_review_count does not match results.")

    return reasons


def _format_snippet(s: str, max_words: int = 25) -> str:
    # Copy supplied snippet words and normalize spacing when truncating.
    words = (s or "").strip().split()
    if len(words) <= max_words:
        return (s or "").strip()
    return " ".join(words[:max_words]) + "…"


def _policy_trust_line(policy_trust_level: str) -> str | None:
    """
    Returns a single-line policy trust disclaimer to be injected into the header.
    """
    if policy_trust_level == "demo":
        return "Policy trust level: DEMO — criteria are illustrative only. Verify against the official payer policy before submission."
    if policy_trust_level == "verified":
        return "Policy trust level: VERIFIED — criteria derived from documented payer policy sources."
    return None


def _title_for(letter_type: str) -> str:
    if letter_type == "missing_info_request":
        return "PRIOR AUTHORIZATION MISSING INFORMATION REQUEST"
    if letter_type == "appeal_template":
        return "PRIOR AUTHORIZATION APPEAL TEMPLATE (ADMINISTRATIVE)"
    return "PRIOR AUTHORIZATION ADMINISTRATIVE READINESS SUMMARY"


def _hard_block_if_prohibited(letter_text: str) -> List[str]:
    scan_text = "\n".join(line for line in (letter_text or "").splitlines() if not line.strip().lower().startswith("dx codes:"))
    low = scan_text.lower()
    hits = []
    for p in PROHIBITED_SUBSTRINGS:
        if p in {"dx", "hx"}:
            if re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", low):
                hits.append(p)
        elif p in low:
            hits.append(p)
    if hits:
        reasons = [f"Prohibited language detected: '{h}'" for h in hits]
    else:
        reasons = []
    dosing_hits = []
    for pattern in PROHIBITED_DOSING_PATTERNS:
        match = pattern.search(scan_text)
        if match:
            dosing_hits.append(match.group(0))
    reasons.extend(f"Prohibited dosing language detected: '{hit}'" for hit in dict.fromkeys(dosing_hits))
    return reasons


def draft_letter(
    draft_input: LetterDraftInput,
    letter_type: LetterType = "submission_cover_letter",
) -> Tuple[str, Dict]:
    """
    Write-only letter drafting from supplied structured inputs.

    - Accepts only no-note request metadata plus supplied requirement results, snippets, and hints.
    - Does not mutate requirement statuses; standard templates do not promise approval.
    - Applies the enumerated PROHIBITED_SUBSTRINGS check; this is not a semantic filter.
    - Diagnosis-code sanitation is limited to trim, uppercase, and removal of spaces and '%'.
    Returns (letter_text, letter_metadata_dict).
    """
    if not isinstance(draft_input, LetterDraftInput):
        raise TypeError("draft_letter requires LetterDraftInput.")

    ts = _now_utc_iso()
    request = draft_input.request
    policy_trust_level = draft_input.policy_trust_level
    blocked_reasons = _validate_inputs(draft_input, letter_type)

    if blocked_reasons:
        text = (
            "DRAFT_BLOCKED\n\n"
            "The letter could not be generated due to input validation errors:\n" + "\n".join([f"- {r}" for r in blocked_reasons]) + "\n"
        )
        meta = LetterMeta(
            letter_version="1.2",
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

    overall = _derive_overall_status(draft_input)

    # Apply the minimal DX-code normalization described in the drafting contract.
    dx_codes = _sanitize_dx_codes(request.dx_codes)

    # Header
    header_lines = [
        f"Payer: {request.payer}",
        f"Procedure: {request.procedure_code}",
        f"Site of care: {request.site_of_care}",
        f"Specialty: {request.specialty}",
        f"Generated: {ts}",
    ]
    if dx_codes:
        header_lines.append(f"Dx codes: {', '.join(dx_codes)}")

    trust_line = _policy_trust_line(policy_trust_level)
    if trust_line:
        header_lines.append(trust_line)

    # Summary framing (administrative only)
    if letter_type == "missing_info_request" and draft_input.not_documented_count > 0:
        summary = (
            "Summary:\n"
            "The documentation provided is insufficient to determine administrative readiness because "
            "one or more required elements are not documented. "
            "This does not imply criteria failure and does not guarantee payer approval.\n"
        )
    elif letter_type == "missing_info_request":
        summary = (
            "Summary:\n"
            "No requirements are currently marked NOT_DOCUMENTED, so this missing-information template "
            "does not contain a missing-documentation checklist. "
            "This does not guarantee payer approval.\n"
        )
    elif letter_type == "appeal_template":
        summary = (
            "Summary:\n"
            "This template summarizes documentation-based administrative criteria relevant to the "
            "request and is intended to support an appeal or reconsideration packet. "
            "It does not provide clinical recommendations and does not guarantee payer approval.\n"
        )
    else:
        if overall == "READY" and policy_trust_level != "verified":
            summary = (
                "Summary:\n"
                "The documentation satisfies the configured demonstration criteria, but this is not a "
                "submission-ready determination because policy trust is not verified. "
                "Verify the criteria against the current official payer policy before use.\n"
            )
        elif overall == "READY":
            summary = (
                "Summary:\n"
                "This letter supports administrative submission readiness based on the documentation present in the record. "
                "This does not guarantee payer approval.\n"
            )
        elif overall == "PENDING_VERIFICATION":
            summary = (
                "Summary:\n"
                "Automated extraction is a drafting aid. Proposed criteria pass, but human verification "
                "of every fact and its evidence is required before READY. "
                "This does not guarantee payer approval.\n"
            )
        elif overall == "NOT_READY":
            summary = (
                "Summary:\n"
                "The request is not administratively ready for submission because one or more "
                "documented requirements do not meet thresholds. "
                "This does not represent a clinical judgment and does not guarantee payer approval.\n"
            )
        elif overall == "NEEDS_REVIEW":
            summary = (
                "Summary:\n"
                "Administrative readiness requires human review because one or more documented results "
                "could not be evaluated against the configured categories. "
                "This is not an adjudicated criteria failure and does not guarantee payer approval.\n"
            )
        else:
            summary = (
                "Summary:\n"
                "Administrative readiness cannot be determined because one or more required elements "
                "are not documented in the record provided. "
                "This does not imply criteria failure and does not guarantee payer approval.\n"
            )

    # Requirements section
    req_lines: List[str] = ["Requirements:"]
    missing_checklist: List[str] = []

    # Track unique, non-empty snippets actually included
    cited_snips_unique: List[str] = []
    cited_seen = set()

    for r in draft_input.results:
        req_lines.append(f"- {r.label} ({r.key}): {r.status}")
        req_lines.append(f"  Reason: {r.reason}")

        if r.evidence_snippets:
            req_lines.append("  Evidence:")
            for snip in r.evidence_snippets[:5]:
                s = str(snip or "").strip()
                if not s:
                    continue
                s_fmt = _format_snippet(s)
                req_lines.append(f'   - "{s_fmt}"')
                if s_fmt not in cited_seen:
                    cited_seen.add(s_fmt)
                    cited_snips_unique.append(s_fmt)
        else:
            req_lines.append("  Evidence: No supporting snippet available.")

        if r.status == "NOT_DOCUMENTED":
            hint = (r.evidence or "").strip()
            if hint:
                missing_checklist.append(f"- {r.label}: {hint}")
            else:
                missing_checklist.append(f"- {r.label}: Documentation not present (no hint provided).")

    missing_section = ""
    if missing_checklist:
        missing_section = "\nMissing Documentation (Checklist):\n" + "\n".join(missing_checklist) + "\n"

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

    # Hard-block prohibited language (post-compose so we catch anything accidental)
    prohibited_hits = _hard_block_if_prohibited(letter)
    if prohibited_hits:
        blocked_reasons = prohibited_hits
        text = (
            "DRAFT_BLOCKED\n\nThe letter was blocked due to prohibited language:\n" + "\n".join([f"- {r}" for r in blocked_reasons]) + "\n"
        )
        meta = LetterMeta(
            letter_version="1.2",
            generated_timestamp_utc=ts,
            overall_status=overall,
            letter_type=letter_type,
            policy_trust_level=policy_trust_level,
            cited_snippets_count=0,
            contains_missing_documentation=(draft_input.not_documented_count > 0),
            draft_blocked=True,
            draft_blocked_reasons=blocked_reasons,
            letter_hash_sha256_16=letter_hash(text),
        )
        return text, meta.__dict__

    meta = LetterMeta(
        letter_version="1.2",
        generated_timestamp_utc=ts,
        overall_status=overall,
        letter_type=letter_type,
        policy_trust_level=policy_trust_level,
        cited_snippets_count=len(cited_snips_unique),
        contains_missing_documentation=(draft_input.not_documented_count > 0),
        draft_blocked=False,
        draft_blocked_reasons=[],
        letter_hash_sha256_16=letter_hash(letter),
    )
    return letter, meta.__dict__
