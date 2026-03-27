from engine.evaluate import compute_overall_status, evaluate_requirements
from engine.extract import extract_facts


def test_extract_facts_is_deterministic_for_same_note():
    note = (
        "Low back pain for 8 weeks. Completed PT for 6 weeks. "
        "Denies weakness, bowel or bladder changes. No prior imaging documented."
    )

    facts_one, evidence_one = extract_facts(note)
    facts_two, evidence_two = extract_facts(note)

    assert facts_one == facts_two
    assert evidence_one == evidence_two


def test_therapy_duration_does_not_leak_from_symptom_duration():
    note = "Low back pain for 8 weeks. Tried rest at home. No PT duration documented."

    facts, evidence = extract_facts(note)

    assert facts["symptom_duration_weeks"] == 8
    assert facts["conservative_therapy_weeks"] is None
    assert "conservative_therapy_weeks" not in evidence


def test_missing_required_item_forces_cannot_determine():
    requirements = [
        {
            "key": "symptom_duration_weeks",
            "label": "Symptom duration",
            "type": "number",
            "min": 6,
            "evidence": "Duration documented",
        },
        {
            "key": "neuro_red_flags_documented",
            "label": "Neuro red flags addressed",
            "type": "boolean",
            "evidence": "Explicit statement present or denied",
        },
    ]
    facts = {
        "symptom_duration_weeks": 8,
        "neuro_red_flags_documented": None,
    }

    results, reasons = evaluate_requirements(requirements, facts)
    overall = compute_overall_status(results)

    assert overall["overall_status"] == "CANNOT_DETERMINE"
    assert overall["submission_readiness"] is False
    assert any("NOT_DOCUMENTED" in reason for reason in reasons)
