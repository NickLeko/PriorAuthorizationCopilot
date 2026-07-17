from engine.letter_draft import draft_letter
from engine.schemas import LetterDraftInput, LetterRequestMetadata, RequirementResult


def _make_ready_input(request: LetterRequestMetadata) -> LetterDraftInput:
    return LetterDraftInput(
        request=request,
        met_count=1,
        not_met_count=0,
        not_documented_count=0,
        results=[
            RequirementResult(
                key="symptom_duration_weeks",
                label="Symptom duration",
                status="MET",
                reason="Documented value: 8.",
                evidence=None,
                evidence_snippets=["2 months"],
            )
        ],
    )


def test_dx_codes_are_sanitized_in_letter_output():
    request = LetterRequestMetadata(
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        dx_codes=["M%4.5", " M54.5 "],
        site_of_care="outpatient",
        specialty="Orthopedics",
    )

    draft_input = _make_ready_input(request)

    letter, meta = draft_letter(draft_input)

    # DX codes should appear normalized
    assert "M54.5" in letter

    # The configured percent character is removed by minimal DX normalization.
    assert "%" not in letter
