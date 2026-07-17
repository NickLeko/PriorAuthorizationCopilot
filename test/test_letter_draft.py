import pytest
from pydantic import ValidationError

from engine.letter_draft import draft_letter
from engine.schemas import LetterDraftInput, LetterRequestMetadata, PARequest, RequirementResult


def _base_metadata():
    return LetterRequestMetadata(
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        dx_codes=["M54.5"],
        site_of_care="outpatient",
        specialty="orthopedics",
    )


def test_ready_letter():
    request = _base_metadata()
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
    draft_input = LetterDraftInput(
        request=request,
        not_documented_count=0,
        not_met_count=0,
        met_count=2,
        results=results,
    )

    text, meta = draft_letter(draft_input)
    assert "Overall Status: READY" in text
    assert "Missing Documentation" not in text
    assert meta["draft_blocked"] is False


def test_not_ready_letter():
    request = _base_metadata()
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
    draft_input = LetterDraftInput(
        request=request,
        not_documented_count=0,
        not_met_count=1,
        met_count=0,
        results=results,
    )

    text, meta = draft_letter(draft_input)
    assert "Overall Status: NOT_READY" in text
    assert meta["draft_blocked"] is False


def test_cannot_determine_letter_includes_checklist():
    request = _base_metadata()
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
    draft_input = LetterDraftInput(
        request=request,
        not_documented_count=1,
        not_met_count=0,
        met_count=0,
        results=results,
    )

    text, meta = draft_letter(draft_input)
    assert "Overall Status: CANNOT_DETERMINE" in text
    assert "Missing Documentation (Checklist):" in text
    assert "- AHI documented: Look for numeric AHI" in text
    assert meta["contains_missing_documentation"] is True
    assert meta["draft_blocked"] is False


def test_draft_blocked_on_count_mismatch():
    request = _base_metadata()
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
    draft_input = LetterDraftInput(
        request=request,
        not_documented_count=0,
        not_met_count=0,
        met_count=2,
        results=results,
    )

    text, meta = draft_letter(draft_input)
    assert text.startswith("DRAFT_BLOCKED")
    assert meta["draft_blocked"] is True


def test_administrative_diagnosis_label_does_not_block_missing_info_letter():
    request = LetterRequestMetadata(
        payer="Aetna",
        procedure_code="CPAP_DEVICE",
        dx_codes=["G47.33"],
        site_of_care="outpatient",
        specialty="Sleep Medicine",
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
    draft_input = LetterDraftInput(
        request=request,
        not_documented_count=1,
        not_met_count=0,
        met_count=1,
        results=results,
    )

    text, meta = draft_letter(draft_input, letter_type="missing_info_request")

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
    request = _base_metadata()
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
    draft_input = LetterDraftInput(
        request=request,
        not_documented_count=0,
        not_met_count=0,
        met_count=1,
        results=results,
    )

    text, meta = draft_letter(draft_input)

    assert text.startswith("DRAFT_BLOCKED")
    assert meta["draft_blocked"] is True
    assert any(prohibited_phrase in reason for reason in meta["draft_blocked_reasons"])


@pytest.mark.parametrize("blocked_term", ["dx", "impression", "assessment", "hx", "history"])
def test_clinical_shorthand_blocklist_terms_block_draft(blocked_term):
    request = _base_metadata()
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
    draft_input = LetterDraftInput(
        request=request,
        not_documented_count=0,
        not_met_count=0,
        met_count=1,
        results=results,
    )

    text, meta = draft_letter(draft_input)

    assert text.startswith("DRAFT_BLOCKED")
    assert meta["draft_blocked"] is True
    assert any(blocked_term in reason for reason in meta["draft_blocked_reasons"])


def test_letter_input_boundary_rejects_raw_note_text():
    with pytest.raises(ValidationError):
        LetterRequestMetadata(
            payer="Aetna",
            procedure_code="MRI_LUMBAR",
            site_of_care="outpatient",
            specialty="Orthopedics",
            note_text="Raw note text",
        )

    pa = PARequest(
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        site_of_care="outpatient",
        specialty="Orthopedics",
        note_text="Raw note text",
    )
    with pytest.raises(TypeError):
        draft_letter(pa)


@pytest.mark.parametrize(
    "reason",
    ["Take 10 mg daily.", "Administer 5 mL BID.", "Use 2 tablets every 8 hours.", "Inject 12 units q6h."],
)
def test_dosing_language_blocks_draft(reason):
    result = RequirementResult(
        key="symptom_duration_weeks",
        label="Symptom duration",
        status="MET",
        reason=reason,
        evidence_snippets=["Low back pain for 8 weeks."],
    )
    draft_input = LetterDraftInput(
        request=_base_metadata(),
        met_count=1,
        not_met_count=0,
        not_documented_count=0,
        results=[result],
    )

    text, meta = draft_letter(draft_input)

    assert text.startswith("DRAFT_BLOCKED")
    assert meta["draft_blocked"] is True
    assert any("Prohibited dosing language" in item for item in meta["draft_blocked_reasons"])


def test_benign_non_dosing_measurement_is_allowed():
    result = RequirementResult(
        key="prior_imaging_result",
        label="Prior imaging result",
        status="MET",
        reason="Documented 10 mm disc protrusion.",
        evidence_snippets=["10 mm disc protrusion"],
    )
    draft_input = LetterDraftInput(
        request=_base_metadata(),
        met_count=1,
        not_met_count=0,
        not_documented_count=0,
        results=[result],
    )

    text, meta = draft_letter(draft_input)

    assert not text.startswith("DRAFT_BLOCKED")
    assert meta["draft_blocked"] is False


def test_needs_review_letter_does_not_describe_threshold_failure():
    result = RequirementResult(
        key="prior_imaging_result",
        label="Prior imaging result",
        status="NEEDS_REVIEW",
        reason="Imaging category is unrecognized; human review is required.",
        evidence_snippets=["MRI showed edema"],
    )
    draft_input = LetterDraftInput(
        request=_base_metadata(),
        met_count=0,
        not_met_count=0,
        not_documented_count=0,
        needs_review_count=1,
        results=[result],
    )

    text, meta = draft_letter(draft_input)

    assert "Overall Status: NEEDS_REVIEW" in text
    assert "not an adjudicated criteria failure" in text
    assert "do not meet thresholds" not in text
    assert meta["overall_status"] == "NEEDS_REVIEW"


def test_missing_info_request_without_missing_results_omits_checklist():
    result = RequirementResult(
        key="symptom_duration_weeks",
        label="Symptom duration",
        status="MET",
        reason="Documented value: 8.",
        evidence_snippets=["Pain for 8 weeks."],
    )
    draft_input = LetterDraftInput(
        request=_base_metadata(),
        met_count=1,
        not_met_count=0,
        not_documented_count=0,
        results=[result],
    )

    text, meta = draft_letter(draft_input, letter_type="missing_info_request")

    assert "Missing Documentation (Checklist):" not in text
    assert meta["contains_missing_documentation"] is False
