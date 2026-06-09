import pytest

from engine.letter_draft import draft_letter
from engine.schemas import PARequest, ReadinessReport, RequirementResult


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


def test_administrative_diagnosis_label_does_not_block_missing_info_letter():
    pa = PARequest(
        payer="Aetna",
        procedure_code="CPAP_DEVICE",
        dx_codes=["G47.33"],
        site_of_care="outpatient",
        specialty="Sleep Medicine",
        note_text="(not used by letter drafting)",
    )
    results = [
        RequirementResult(
            key="osa_diagnosis",
            label="OSA diagnosis documented",
            status="MET",
            reason="Explicitly addressed in documentation (present/affirmed).",
            evidence="Diagnosis present",
            evidence_snippets=["OSA"],
        ),
        RequirementResult(
            key="sleep_study_date",
            label="Sleep study date documented",
            status="NOT_DOCUMENTED",
            reason="Not found in note. Add explicit statement.",
            evidence="Date in chart",
            evidence_snippets=[],
        ),
    ]
    report = ReadinessReport(
        readiness_score=50,
        not_documented_count=1,
        not_met_count=0,
        met_count=1,
        results=results,
        rule_reasons=[],
        audit_trail={},
        letter_draft="",
    )

    text, meta = draft_letter(pa, report, letter_type="missing_info_request")

    assert "Overall Status: CANNOT_DETERMINE" in text
    assert "OSA diagnosis documented" in text
    assert "Missing Documentation (Checklist):" in text
    assert meta["draft_blocked"] is False


@pytest.mark.parametrize(
    "prohibited_phrase",
    [
        "clinical diagnosis",
        "new diagnosis",
        "diagnosed with",
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
        "medically necessary",
    ],
)
def test_prohibited_clinical_authorization_and_medical_necessity_language_blocks_draft(prohibited_phrase):
    pa = _base_pa()
    results = [
        RequirementResult(
            key="symptom_duration_weeks",
            label="Symptom duration",
            status="MET",
            reason=f"This request is {prohibited_phrase}.",
            evidence="Duration documented.",
            evidence_snippets=["Low back pain for 8 weeks."],
        )
    ]
    report = ReadinessReport(
        readiness_score=100,
        not_documented_count=0,
        not_met_count=0,
        met_count=1,
        results=results,
        rule_reasons=[],
        audit_trail={},
        letter_draft="",
    )

    text, meta = draft_letter(pa, report)

    assert text.startswith("DRAFT_BLOCKED")
    assert meta["draft_blocked"] is True
    assert any(prohibited_phrase in reason for reason in meta["draft_blocked_reasons"])


@pytest.mark.parametrize("blocked_term", ["dx", "impression", "assessment", "hx", "history"])
def test_clinical_shorthand_blocklist_terms_block_draft(blocked_term):
    pa = _base_pa()
    results = [
        RequirementResult(
            key="symptom_duration_weeks",
            label="Symptom duration",
            status="MET",
            reason=f"Clinical source text included {blocked_term}.",
            evidence="Duration documented.",
            evidence_snippets=["Low back pain for 8 weeks."],
        )
    ]
    report = ReadinessReport(
        readiness_score=100,
        not_documented_count=0,
        not_met_count=0,
        met_count=1,
        results=results,
        rule_reasons=[],
        audit_trail={},
        letter_draft="",
    )

    text, meta = draft_letter(pa, report)

    assert text.startswith("DRAFT_BLOCKED")
    assert meta["draft_blocked"] is True
    assert any(blocked_term in reason for reason in meta["draft_blocked_reasons"])
