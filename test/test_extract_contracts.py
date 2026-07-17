from pathlib import Path

import pytest

from engine.evaluate import compute_overall_status, evaluate_requirements
from engine.extract import extract_facts

CONTRACT_PATH = Path("EXTRACTION_CONTRACT.md")


def test_extract_facts_is_deterministic_for_same_note():
    note = "Low back pain for 8 weeks. Completed PT for 6 weeks. Denies weakness, bowel or bladder changes. No prior imaging documented."

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


def test_negated_therapy_duration_does_not_extract_false_met():
    # Regression: previously extracted false MET from negation.
    facts, evidence = extract_facts("Patient denies completing PT x 8 weeks.")

    assert facts["conservative_therapy_weeks"] is None
    assert "conservative_therapy_weeks" not in evidence


@pytest.mark.parametrize(
    "note",
    [
        "Pt has not completed any PT.",
        "No conservative therapy attempted.",
        "PT was recommended but patient declined.",
        "Patient did not complete PT for 6 weeks.",
    ],
)
def test_negated_therapy_duration_variations_return_none(note):
    facts, evidence = extract_facts(note)

    assert facts["conservative_therapy_weeks"] is None
    assert "conservative_therapy_weeks" not in evidence


def test_future_therapy_duration_does_not_extract_false_met():
    # Regression: previously extracted false MET from future-tense.
    facts, evidence = extract_facts("Will start PT for 6 weeks next month.")

    assert facts["conservative_therapy_weeks"] is None
    assert "conservative_therapy_weeks" not in evidence


@pytest.mark.parametrize(
    "note",
    [
        "PT ordered, to begin next week for 4 weeks.",
        "Plan: 6 weeks of PT starting 1/15.",
        "Referral placed for PT x 8 weeks.",
    ],
)
def test_future_therapy_duration_variations_return_none(note):
    facts, evidence = extract_facts(note)

    assert facts["conservative_therapy_weeks"] is None
    assert "conservative_therapy_weeks" not in evidence


def test_therapy_duration_does_not_leak_into_symptom_duration():
    # Regression: previously extracted false MET from therapy-leak.
    note = "Completed PT for 6 weeks. Low back pain ongoing."

    facts, evidence = extract_facts(note)

    assert facts["conservative_therapy_weeks"] == 6
    assert facts["symptom_duration_weeks"] is None
    assert "symptom_duration_weeks" not in evidence


def test_therapy_context_duration_is_skipped_when_extracting_later_symptom_months():
    facts, evidence = extract_facts("6 weeks of PT completed. Symptoms present for 3 months.")

    assert facts["conservative_therapy_weeks"] == 6
    assert facts["symptom_duration_weeks"] == 12
    assert evidence["symptom_duration_weeks"][0]["text"] == "3 months"


@pytest.mark.parametrize(
    "note, expected_therapy, expected_symptom",
    [
        ("PT x 8 weeks completed. Low back pain ongoing.", 8, None),
        ("Physical therapy for 4 weeks completed; neck pain continues.", 4, None),
        ("Completed 8 weeks of chiropractic care. Symptoms x 10 weeks.", 8, 10),
    ],
)
def test_therapy_context_duration_does_not_drive_symptom_duration(note, expected_therapy, expected_symptom):
    facts, evidence = extract_facts(note)

    assert facts["conservative_therapy_weeks"] == expected_therapy
    assert facts["symptom_duration_weeks"] == expected_symptom
    if expected_symptom is None:
        assert "symptom_duration_weeks" not in evidence


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
    assert 'Type: `"none" | "inconclusive" | "abnormal" | "unrecognized" | null`' in contract
    assert "Imaging mention without a stated result remains `null`." in contract
    assert "### `mechanical_symptoms_documented`" in contract
    assert (
        "Positive phrasing takes precedence if the note contains both denial and later affirmative "
        "mechanical-symptom language." in contract
    )
    assert "This field records whether a contextualized date was found. It does not return the parsed date value." in contract
    assert "This field records whether the numeric value is documented. It does not return the numeric value itself." in contract
    assert "Possible Extensions" in contract


def test_extraction_contract_examples_match_current_behavior():
    facts, evidence = extract_facts("Prior MRI reviewed.")
    assert facts["prior_imaging_result"] is None
    assert "prior_imaging_result" not in evidence

    facts, _ = extract_facts("OSA listed. Sleep study completed 2024-05-18. AHI 22 documented.")
    assert facts["osa_diagnosis"] is True
    assert facts["sleep_study_date"] is True
    assert facts["ahi_documented"] is True

    facts, _ = extract_facts("Back pain x 2 months. Completed PT and NSAIDs, duration not specified.")
    assert facts["symptom_duration_weeks"] == 8
    assert facts["conservative_therapy_weeks"] is None

    facts, _ = extract_facts("Denies locking or instability. Prior knee xray normal.")
    assert facts["mechanical_symptoms_documented"] is False


@pytest.mark.parametrize(
    "note",
    [
        "No OSA.",
        "Denies OSA.",
        "Without OSA.",
        "OSA ruled out.",
        "No evidence of OSA.",
        "OSA absent.",
        "OSA negative.",
        "OSA not present.",
        "No obstructive sleep apnea.",
        "Denies obstructive sleep apnea.",
        "Obstructive sleep apnea ruled out.",
        "No evidence of obstructive sleep apnea.",
        "Obstructive sleep apnea absent.",
        "Obstructive sleep apnea negative.",
        "Obstructive sleep apnea not present.",
    ],
)
def test_negated_osa_mentions_are_not_extracted_as_diagnosis(note):
    facts, evidence = extract_facts(note)

    assert facts["osa_diagnosis"] is None
    assert "osa_diagnosis" not in evidence


def test_affirmative_osa_mention_is_not_suppressed_by_distinct_negated_mention():
    facts, evidence = extract_facts("No OSA in father, patient has OSA.")

    assert facts["osa_diagnosis"] is True
    assert evidence["osa_diagnosis"][0]["text"] == "OSA"


def test_imaging_mention_without_result_remains_undocumented():
    facts, evidence = extract_facts("Prior imaging performed.")

    assert facts["prior_imaging_result"] is None
    assert "prior_imaging_result" not in evidence


def test_recognized_imaging_result_remains_categorized():
    facts, evidence = extract_facts("MRI abnormal.")

    assert facts["prior_imaging_result"] == "abnormal"
    assert evidence["prior_imaging_result"][0]["text"] == "abnormal"


@pytest.mark.parametrize("note", ["MRI showed edema.", "MRI equivocal.", "CT showed a mass."])
def test_unrecognized_imaging_result_is_documented_separately(note):
    facts, evidence = extract_facts(note)

    assert facts["prior_imaging_result"] == "unrecognized"
    assert "prior_imaging_result" in evidence


def test_unrecognized_imaging_result_evaluates_to_needs_review():
    requirements = [
        {
            "key": "prior_imaging_result",
            "label": "Prior imaging result",
            "type": "enum",
            "allowed": ["none", "inconclusive", "abnormal"],
        }
    ]

    results, reasons = evaluate_requirements(requirements, {"prior_imaging_result": "unrecognized"})
    overall = compute_overall_status(results)

    assert results[0].status == "NEEDS_REVIEW"
    assert overall["overall_status"] == "NEEDS_REVIEW"
    assert overall["submission_readiness"] is False
    assert any("NEEDS_REVIEW" in reason for reason in reasons)


def test_positive_red_flag_evidence_takes_precedence_when_note_contains_conflict():
    note = (
        "Neck pain x 8 weeks. PT x 8 weeks. Denies weakness earlier in visit. "
        "Later note: reports progressive weakness and urinary retention. Prior CT abnormal."
    )

    facts, evidence = extract_facts(note)

    assert facts["neuro_red_flags_documented"] is True
    assert "neuro_red_flags_documented" in evidence
    assert any("progressive weakness" in span["text"].lower() for span in evidence["neuro_red_flags_documented"])


def test_mechanical_symptom_denial_is_captured_as_explicit_documentation():
    note = "Right knee pain x 8 weeks. PT x 8 weeks. Denies locking or instability. Prior knee xray normal."

    facts, evidence = extract_facts(note)

    assert facts["mechanical_symptoms_documented"] is False
    assert "mechanical_symptoms_documented" in evidence
    assert any("denies locking" in span["text"].lower() for span in evidence["mechanical_symptoms_documented"])


def test_positive_mechanical_symptoms_take_precedence_when_note_contains_conflict():
    note = (
        "Right knee pain x 8 weeks. PT x 8 weeks. Denies locking earlier in visit. "
        "Later note: reports buckling with stairs. Prior knee xray normal."
    )

    facts, evidence = extract_facts(note)

    assert facts["mechanical_symptoms_documented"] is True
    assert "mechanical_symptoms_documented" in evidence
    assert any("buckling" in span["text"].lower() for span in evidence["mechanical_symptoms_documented"])
