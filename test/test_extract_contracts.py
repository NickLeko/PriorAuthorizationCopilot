from pathlib import Path

from engine.evaluate import compute_overall_status, evaluate_requirements
from engine.extract import extract_facts


CONTRACT_PATH = Path("EXTRACTION_CONTRACT.md")


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


def test_extraction_contract_describes_current_shapes_and_limits():
    contract = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "implemented and deterministic; no LLM is used anywhere in the extraction path" in contract
    assert "The current implementation does not require explicit symptom context for this field." in contract
    assert 'Type: `"none" | "inconclusive" | "abnormal" | null`' in contract
    assert "Imaging mention without a result is treated as documented `inconclusive`, not `null`." in contract
    assert "This field records whether a contextualized date was found. It does not return the parsed date value." in contract
    assert "This field records whether the numeric value is documented. It does not return the numeric value itself." in contract
    assert "Possible Extensions" in contract


def test_extraction_contract_examples_match_current_behavior():
    facts, evidence = extract_facts("Prior MRI reviewed.")
    assert facts["prior_imaging_result"] == "inconclusive"
    assert "prior_imaging_result" in evidence

    facts, _ = extract_facts("OSA listed. Sleep study completed 2024-05-18. AHI 22 documented.")
    assert facts["osa_diagnosis"] is True
    assert facts["sleep_study_date"] is True
    assert facts["ahi_documented"] is True

    facts, _ = extract_facts("Back pain x 2 months. Completed PT and NSAIDs, duration not specified.")
    assert facts["symptom_duration_weeks"] == 8
    assert facts["conservative_therapy_weeks"] is None
