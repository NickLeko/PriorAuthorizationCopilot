"""Pure structural comparison of captured sources; no clinical adjudication."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from engine.fact_contracts import FACT_CONTRACTS, FactState
from engine.note_context import MAX_EVIDENCE_SPANS, EvidenceMap
from engine.schemas import REVIEW_REQUIRED_FACT

from .errors import ExperimentFailure
from .proposals import ExtractionProposal, proposal_from_legacy
from .recorded import RecordedLLMProposal

THERAPY_KEYS = ("cpb_0236_conservative_therapy_weeks", "cpb_0236_conservative_therapy_no_improvement")
Reason = Literal["AGREED_CAPTURE", "BOTH_MISSING", "STATE_DISAGREEMENT", "VALUE_DISAGREEMENT", "REVIEW_REQUIRED"]
AnalysisFlag = Literal["REGEX_NUMERIC_NOT_LITERAL_IN_RETAINED_CITATIONS", "LLM_NUMERIC_NOT_LITERAL_IN_RETAINED_CITATIONS"]


class FactComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    key: str
    disposition: FactState
    reason: Reason
    state_disagreement: bool
    values_agree: bool | None
    retained_citation_sets_equal: bool
    retained_citation_order_equal: bool
    total_citation_counts_equal: bool
    citation_comparison_complete: bool
    evidence_source: Literal["regex", "llm", "both", "none"]
    dual_citation_sources: tuple[tuple[Literal["regex", "llm"], ...], ...]
    dual_complete_citation_count: int | None
    dual_observed_unique_citation_count: int
    dual_evidence_capped: bool
    analysis_flags: tuple[AnalysisFlag, ...]


class ReconciliationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    reconciliation_version: Literal["structural-v2"] = "structural-v2"
    regex: ExtractionProposal
    recorded_llm: RecordedLLMProposal
    dual: ExtractionProposal
    comparisons: tuple[FactComparison, ...]
    jointly_captured_therapy_citation_source: Literal["regex"] | None
    clinical_verification: Literal[False] = False


def _citation_set(spans):
    return {(span["start"], span["end"], span["text"]) for span in spans}


def _numeric_flags(left, right, key) -> tuple[AnalysisFlag, ...]:
    """Advisory lexical-support check, including valid unit-normalization cases.

    No magnitude cutoff, policy threshold, unit conversion, or fact change. An
    absent literal can flag an implausible proposal but cannot establish one.
    """
    flags = []
    for snapshot, flag in (
        (left, "REGEX_NUMERIC_NOT_LITERAL_IN_RETAINED_CITATIONS"),
        (right, "LLM_NUMERIC_NOT_LITERAL_IN_RETAINED_CITATIONS"),
    ):
        value = snapshot["facts"][key]
        if snapshot["states"][key] == "CAPTURED" and type(value) is int:
            pattern = rf"(?<![\w.]){re.escape(str(value))}(?![\w.])"
            if not any(re.search(pattern, span["text"]) for span in snapshot["evidence"].get(key, [])):
                flags.append(flag)
    return tuple(flags)


def _dual_evidence(left, right, key, combine):
    le, revidence = left["evidence"].get(key, []), right["evidence"].get(key, [])
    lc = left.get("evidence_counts", {}).get(key, len(le))
    rc = right.get("evidence_counts", {}).get(key, len(revidence))
    if combine and le and revidence:
        # Interleave before capping so a long regex list cannot hide all LLM
        # passages. Deduplicate by exact span identity, preserving source order.
        spans, seen = [], set()
        for index in range(max(len(le), len(revidence))):
            for source in (le, revidence):
                if index < len(source):
                    span = source[index]
                    identity = (span["start"], span["end"], span["text"])
                    if identity not in seen:
                        seen.add(identity)
                        spans.append(span)
        retained = spans[:MAX_EVIDENCE_SPANS]
        ls, rs = _citation_set(le), _citation_set(revidence)
        origins = tuple(
            tuple(role for role, identities in (("regex", ls), ("llm", rs)) if (s["start"], s["end"], s["text"]) in identities)
            for s in retained
        )
        total = len(spans) if lc == len(le) and rc == len(revidence) else None
        return retained, origins, total, len(spans)
    source, role, total = (le, "regex", lc) if le else (revidence, "llm", rc)
    return source, tuple((role,) for _ in source), total, len(_citation_set(source))


def _reconcile_validated(regex: ExtractionProposal, recorded: RecordedLLMProposal) -> ReconciliationRecord:
    left, right = regex.snapshot.content, recorded.proposal.snapshot.content
    facts, evidence, counts, comparisons = {}, {}, {}, []
    diagnostics = ["STRUCTURAL_COMPARISON_ONLY"]
    for key in FACT_CONTRACTS:
        ls, rs = left["states"][key], right["states"][key]
        lv, rv = left["facts"][key], right["facts"][key]
        agree = (type(lv) is type(rv) and lv == rv) if ls == rs == "CAPTURED" else None
        if "NEEDS_REVIEW" in (ls, rs):
            state, reason = "NEEDS_REVIEW", "REVIEW_REQUIRED"
        elif ls == rs == "MISSING":
            state, reason = "MISSING", "BOTH_MISSING"
        elif ls != rs:
            state, reason = "NEEDS_REVIEW", "STATE_DISAGREEMENT"
        elif agree:
            state, reason = "CAPTURED", "AGREED_CAPTURE"
        else:
            state, reason = "NEEDS_REVIEW", "VALUE_DISAGREEMENT"
        facts[key] = lv if state == "CAPTURED" else REVIEW_REQUIRED_FACT if state == "NEEDS_REVIEW" else None
        le, revidence = left["evidence"].get(key, []), right["evidence"].get(key, [])
        lc = left.get("evidence_counts", {}).get(key, len(le))
        rc = right.get("evidence_counts", {}).get(key, len(revidence))
        combine = reason in {"STATE_DISAGREEMENT", "VALUE_DISAGREEMENT"} or (
            state == "NEEDS_REVIEW" and bool(le) and bool(revidence) and le != revidence
        )
        retained, origins, complete_count, observed_count = _dual_evidence(left, right, key, combine)
        roles = {role for group in origins for role in group}
        source = "both" if len(roles) == 2 else next(iter(roles)) if roles else "none"
        if retained:
            evidence[key] = retained
            if complete_count is not None and complete_count > MAX_EVIDENCE_SPANS:
                counts[key] = complete_count
        if combine and le and revidence:
            if "COMPETING_CITATIONS_NOT_A_SHARED_INTERPRETATION" not in diagnostics:
                diagnostics.append("COMPETING_CITATIONS_NOT_A_SHARED_INTERPRETATION")
            if complete_count is None and "COMBINED_CITATION_TOTAL_UNKNOWN" not in diagnostics:
                diagnostics.append("COMBINED_CITATION_TOTAL_UNKNOWN")
        comparisons.append(
            FactComparison(
                key=key,
                disposition=state,
                reason=reason,
                state_disagreement=ls != rs,
                values_agree=agree,
                retained_citation_sets_equal=_citation_set(le) == _citation_set(revidence),
                retained_citation_order_equal=le == revidence,
                total_citation_counts_equal=lc == rc,
                citation_comparison_complete=lc == len(le) and rc == len(revidence),
                evidence_source=source,
                dual_citation_sources=origins,
                dual_complete_citation_count=complete_count,
                dual_observed_unique_citation_count=observed_count,
                dual_evidence_capped=complete_count is None or complete_count > len(retained),
                analysis_flags=_numeric_flags(left, right, key),
            )
        )
    bounded_evidence = EvidenceMap(evidence)
    bounded_evidence.total_counts = counts
    dual = proposal_from_legacy(
        regex.note_text,
        (facts, bounded_evidence),
        source="dual:structural-v2",
        diagnostics=tuple(diagnostics),
    )
    jointly_captured = all(dual.snapshot.content["states"][key] == "CAPTURED" for key in THERAPY_KEYS)
    return ReconciliationRecord(
        regex=regex,
        recorded_llm=recorded,
        dual=dual,
        comparisons=tuple(comparisons),
        jointly_captured_therapy_citation_source="regex" if jointly_captured else None,
    )


def reconcile(regex: ExtractionProposal, recorded_llm: RecordedLLMProposal) -> ReconciliationRecord:
    """Compare two validated, note-bound captures; preserve both original inputs.

    Revalidation rejects validation-bypassing model copies at this boundary.
    There are no extractions, model calls, logging, service calls, or archive writes.
    """
    try:
        if not isinstance(regex, ExtractionProposal) or not isinstance(recorded_llm, RecordedLLMProposal):
            raise ValueError("Expected validated proposals.")
        # Malformed model copies can emit serializer warnings containing values.
        # Suppress those warnings, then strictly validate the serialized data.
        regex = ExtractionProposal.model_validate_json(regex.model_dump_json(warnings=False))
        recorded_llm = RecordedLLMProposal.model_validate_json(recorded_llm.model_dump_json(warnings=False))
        if regex.note_text != recorded_llm.proposal.note_text:
            raise ExperimentFailure("NOTE_MISMATCH")
        return _reconcile_validated(regex, recorded_llm)
    except ExperimentFailure:
        raise
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ExperimentFailure("INVALID_PROPOSAL") from None
