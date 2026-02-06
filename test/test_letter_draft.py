import pytest

from engine.schemas import PARequest, ReadinessReport, RequirementResult
from engine.letter_draft import draft_letter


def _base_pa():
    return PARequest(
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        dx_codes=["M54.5"],
        site_of_care="outpatient",
        specialty="orthopedics",
        note_text="(not used by letter drafting)",
    )


def test_ready_letter():
    pa = _base_pa()
    results = [
        RequirementResult(
            key="symptom_duration_weeks",
            label="Symptom duration documented",
            status="MET",
            reason="Duration documented at or above threshold.",
            evidence="Look for explicit duration in weeks/months.",
            evidence_snippets=["Low back pain for 3 months."],
        ),
        RequirementResult(
            key="conservative_therapy_weeks",
            label="Conservative therapy documented",
            status="MET",
            reason="Therapy duration meets threshold.",
            evidence="Look for PT/NSAIDs + duration.",
            evidence_snippets=["Completed PT for 8 weeks."],
        ),
    ]
    report = ReadinessReport(
        readiness_score=100,
        not_documented_count=0,
        not_met_count=0,
        met_count=2,
        results=results,
        rule_reasons=[],
        audit_trail={},
        letter_draft="",
    )

    text, meta = draft_letter(pa, report)
    assert "Overall Status: READY" in text
    assert "Missing Documentation" not in text
    assert meta["draft_blocked"] is False


def test_not_ready_letter():
    pa = _base_pa()
    results = [
        RequirementResult(
            key="conservative_therapy_weeks",
            label="Conservative therapy documented",
            status="NOT_MET",
            reason="Therapy duration below threshold.",
            evidence="Look for PT/NSAIDs + duration.",
            evidence_snippets=["Tried PT for 2 weeks."],
        )
    ]
    report = ReadinessReport(
        readiness_score=40,
        not_documented_count=0,
        not_met_count=1,
        met_count=0,
        results=results,
        rule_reasons=[],
        audit_trail={},
        letter_draft="",
    )

    text, meta = draft_letter(pa, report)
    assert "Overall Status: NOT_READY" in text
    assert meta["draft_blocked"] is False


def test_cannot_determine_letter_includes_checklist():
    pa = _base_pa()
    results = [
        RequirementResult(
            key="ahi",
            label="AHI documented",
            status="NOT_DOCUMENTED",
            reason="AHI not found in note.",
            evidence="Look for numeric AHI (e.g., 'AHI 22').",
            evidence_snippets=["AHI not stated."],
        )
    ]
    report = ReadinessReport(
        readiness_score=0,
        not_documented_count=1,
        not_met_count=0,
        met_count=0,
        results=results,
        rule_reasons=[],
        audit_trail={},
        letter_draft="",
    )

    text, meta = draft_letter(pa, report)
    assert "Overall Status: CANNOT_DETERMINE" in text
    assert "Missing Documentation (Checklist):" in text
    assert "- AHI documented: Look for numeric AHI" in text
    assert meta["contains_missing_documentation"] is True
    assert meta["draft_blocked"] is False


def test_draft_blocked_on_count_mismatch():
    pa = _base_pa()
    results = [
        RequirementResult(
            key="symptom_duration_weeks",
            label="Symptom duration documented",
            status="MET",
            reason="Duration documented.",
            evidence_snippets=["Pain for 8 weeks."],
        )
    ]
    # met_count is wrong on purpose (should be 1)
    report = ReadinessReport(
        readiness_score=0,
        not_documented_count=0,
        not_met_count=0,
        met_count=2,
        results=results,
        rule_reasons=[],
        audit_trail={},
        letter_draft="",
    )

    text, meta = draft_letter(pa, report)
    assert text.startswith("DRAFT_BLOCKED")
    assert meta["draft_blocked"] is True
