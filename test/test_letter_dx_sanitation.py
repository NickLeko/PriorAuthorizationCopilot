from engine.letter_draft import draft_letter
from engine.schemas import PARequest, ReadinessReport, RequirementResult


def _make_ready_report() -> ReadinessReport:
    return ReadinessReport(
        readiness_score=100,
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
        rule_reasons=[],
        audit_trail={},
        letter_draft="",
    )


def test_dx_codes_are_sanitized_in_letter_output():
    pa = PARequest(
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        dx_codes=["M%4.5", " M54.5 "],
        site_of_care="outpatient",
        specialty="Orthopedics",
        note_text="",
    )

    report = _make_ready_report()

    letter, meta = draft_letter(pa, report)

    # DX codes should appear normalized
    assert "M54.5" in letter

    # Garbage characters must never leak into payer-facing artifacts
    assert "%" not in letter
