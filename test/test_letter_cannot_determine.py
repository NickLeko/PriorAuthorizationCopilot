from engine.letter_draft import draft_letter
from engine.schemas import LetterDraftInput, LetterRequestMetadata, RequirementResult


def test_cannot_determine_letter_includes_missing_checklist_and_demo_trust_line():
    request = LetterRequestMetadata(
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        dx_codes=["M54.5"],
        site_of_care="outpatient",
        specialty="Orthopedics",
    )

    results = [
        RequirementResult(
            key="ahi",
            label="AHI documented",
            status="NOT_DOCUMENTED",
            reason="AHI not found in note.",
            evidence="Look for numeric AHI (e.g., 'AHI 22').",
            evidence_snippets=["AHI not stated."],
        ),
        RequirementResult(
            key="symptom_duration_weeks",
            label="Symptom duration documented",
            status="MET",
            reason="Documented value: 8.",
            evidence="Look for explicit duration in weeks/months.",
            evidence_snippets=["2 months"],
        ),
    ]

    draft_input = LetterDraftInput(
        request=request,
        not_documented_count=1,
        not_met_count=0,
        met_count=1,
        results=results,
    )

    letter, meta = draft_letter(
        draft_input,
        letter_type="missing_info_request",
    )

    # Status must follow frozen invariants
    assert "Overall Status: CANNOT_DETERMINE" in letter
    assert meta["overall_status"] == "CANNOT_DETERMINE"

    # Missing documentation checklist must appear
    assert "Missing Documentation (Checklist):" in letter
    assert "AHI documented" in letter
    assert "Look for numeric AHI" in letter

    # Demo trust line must be present
    assert "Policy trust level: DEMO" in letter

    # Ensure we are not claiming readiness
    assert "administratively ready" not in letter.lower()
