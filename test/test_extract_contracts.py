from pathlib import Path

import pytest

from engine.evaluate import compute_overall_status, evaluate_requirements
from engine.extract import extract_facts
from engine.schemas import REVIEW_REQUIRED_FACT

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


@pytest.mark.parametrize(
    "note, expected_weeks",
    [
        ("Seen 3 months ago. Back pain for 2 weeks.", 2),
        ("Follow-up occurred 4 months ago. Neck pain x 3 weeks.", 3),
        ("The prior visit was 6 months ago. Symptoms have persisted for 5 weeks.", 5),
    ],
)
def test_unrelated_duration_does_not_override_anchored_symptom_duration(note, expected_weeks):
    facts, evidence = extract_facts(note)

    assert facts["symptom_duration_weeks"] == expected_weeks
    assert evidence["symptom_duration_weeks"][0]["text"].endswith("weeks")


@pytest.mark.parametrize(
    "note",
    [
        "Seen 3 months ago. Back pain continues without a documented duration.",
        "Follow-up was 6 weeks ago. Knee pain is ongoing.",
    ],
)
def test_unrelated_duration_without_symptom_anchor_remains_missing(note):
    facts, evidence = extract_facts(note)

    assert facts["symptom_duration_weeks"] is None
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


def test_empty_requirement_set_fails_closed():
    results, reasons = evaluate_requirements([], {})
    overall = compute_overall_status(results)

    assert results == []
    assert reasons == []
    assert overall == {"overall_status": "CANNOT_DETERMINE", "submission_readiness": False}


@pytest.mark.parametrize(
    "requirement, fact_value, expected_status",
    [
        ({"key": "addressed", "label": "Addressed", "type": "boolean", "operator": "documented"}, False, "MET"),
        ({"key": "present", "label": "Present", "type": "boolean", "operator": "equals_true"}, False, "NOT_MET"),
        ({"key": "weeks", "label": "Weeks", "type": "number", "operator": "minimum", "min": 6}, 5, "NOT_MET"),
        (
            {
                "key": "result",
                "label": "Result",
                "type": "enum",
                "operator": "one_of",
                "allowed": ["normal"],
            },
            "normal",
            "MET",
        ),
    ],
)
def test_explicit_requirement_operators_have_distinct_semantics(requirement, fact_value, expected_status):
    results, _ = evaluate_requirements([requirement], {requirement["key"]: fact_value})

    assert results[0].status == expected_status


def test_legacy_boolean_without_operator_defaults_to_conservative_equals_true():
    requirement = {"key": "legacy_flag", "label": "Legacy flag", "type": "boolean"}

    results, _ = evaluate_requirements([requirement], {"legacy_flag": False})

    assert results[0].status == "NOT_MET"


def test_extraction_contract_describes_current_shapes_and_limits():
    contract = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "Automated extraction is a drafting aid, not a decision gate." in contract
    assert "contradicted by `Patient does not have low back pain with radiculopathy`" in contract
    assert "not by making extraction match the old contract" in contract
    assert "TestExtractionContractAlignment" in contract
    assert "source-location integrity" in contract
    assert "PENDING_VERIFICATION" in contract


@pytest.mark.parametrize(
    "note, fact_key, expected",
    [
        ("Low back pain with right leg radiculopathy.", "back_pain_with_radiculopathy", True),
        ("Low back pain without radiculopathy.", "back_pain_with_radiculopathy", False),
        (
            "Objective motor exam in the right L5 distribution: ankle dorsiflexion strength 4/5.",
            "objective_motor_or_reflex_change_in_root_distribution",
            True,
        ),
        (
            "Objective motor exam in the right L5 distribution: ankle dorsiflexion strength 5/5.",
            "objective_motor_or_reflex_change_in_root_distribution",
            False,
        ),
        (
            "NSAIDs for 8 weeks with minimal improvement.",
            "cpb_0236_conservative_therapy_no_improvement",
            True,
        ),
        (
            "NSAIDs for 8 weeks with significant improvement.",
            "cpb_0236_conservative_therapy_no_improvement",
            False,
        ),
    ],
)
def test_verified_lumbar_branch_facts_preserve_explicit_positive_and_negative_meaning(note, fact_key, expected):
    facts, evidence = extract_facts(note)

    assert facts[fact_key] is expected
    assert fact_key in evidence


def test_subjective_weakness_does_not_become_objective_root_distribution_finding():
    facts, evidence = extract_facts("Patient reports weakness in the right L5 distribution.")

    assert facts["objective_motor_or_reflex_change_in_root_distribution"] is None
    assert "objective_motor_or_reflex_change_in_root_distribution" not in evidence


def test_pt_duration_does_not_satisfy_cpb_0236_footnote_therapy_fact():
    facts, evidence = extract_facts("PT for 8 weeks with no improvement.")

    assert facts["conservative_therapy_weeks"] == 8
    assert facts["cpb_0236_conservative_therapy_weeks"] is None
    assert facts["cpb_0236_conservative_therapy_no_improvement"] is None
    assert "cpb_0236_conservative_therapy_weeks" not in evidence


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


@pytest.mark.parametrize(
    "note",
    [
        "Patient does not have OSA.",
        "Patient does not have obstructive sleep apnea.",
        "There is no diagnosis of OSA.",
        "Patient is negative for OSA.",
        "The clinician ruled out OSA.",
    ],
)
def test_common_osa_negation_variants_are_not_extracted_as_diagnosis(note):
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


@pytest.mark.parametrize(
    "note, expected_evidence",
    [
        ("Prior x-ray was normal.", "normal"),
        ("CT was unremarkable.", "unremarkable"),
        ("MRI showed no acute findings.", "no acute findings"),
    ],
)
def test_recognized_normal_imaging_result_has_distinct_category(note, expected_evidence):
    facts, evidence = extract_facts(note)

    assert facts["prior_imaging_result"] == "normal"
    assert evidence["prior_imaging_result"][0]["text"] == expected_evidence


def test_recognized_abnormal_imaging_result_remains_categorized():
    facts, evidence = extract_facts("MRI abnormal.")

    assert facts["prior_imaging_result"] == "abnormal"
    assert evidence["prior_imaging_result"][0]["text"] == "abnormal"


@pytest.mark.parametrize(
    "note",
    [
        "Prior x-ray showed no fracture.",
        "CT demonstrated no acute fracture.",
        "Prior xray was negative for fracture.",
        "MRI showed no evidence of stenosis.",
    ],
)
def test_negated_imaging_findings_are_not_classified_as_abnormal(note):
    facts, evidence = extract_facts(note)

    assert facts["prior_imaging_result"] == "negative"
    assert facts["prior_imaging_result"] != "abnormal"
    assert "prior_imaging_result" in evidence


def test_affirmative_abnormal_finding_wins_over_distinct_negated_finding():
    facts, _ = extract_facts("X-ray showed no fracture but did show degenerative changes.")

    assert facts["prior_imaging_result"] == "abnormal"


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
            "operator": "one_of",
            "allowed": ["none", "inconclusive", "abnormal"],
        }
    ]

    results, reasons = evaluate_requirements(requirements, {"prior_imaging_result": "unrecognized"})
    overall = compute_overall_status(results)

    assert results[0].status == "NEEDS_REVIEW"
    assert overall["overall_status"] == "NEEDS_REVIEW"
    assert overall["submission_readiness"] is False
    assert any("NEEDS_REVIEW" in reason for reason in reasons)


def test_recognized_normal_imaging_result_fails_rule_when_not_allowed():
    requirements = [
        {
            "key": "prior_imaging_result",
            "label": "Prior imaging result",
            "type": "enum",
            "operator": "one_of",
            "allowed": ["none", "inconclusive", "abnormal"],
        }
    ]

    results, _ = evaluate_requirements(requirements, {"prior_imaging_result": "normal"})
    overall = compute_overall_status(results)

    assert results[0].status == "NOT_MET"
    assert overall == {"overall_status": "NOT_READY", "submission_readiness": False}


def test_conflicting_red_flag_evidence_requires_review():
    note = (
        "Neck pain x 8 weeks. PT x 8 weeks. Denies weakness earlier in visit. "
        "Later note: reports progressive weakness and urinary retention. Prior CT abnormal."
    )

    facts, evidence = extract_facts(note)

    assert facts["neuro_red_flags_documented"] == REVIEW_REQUIRED_FACT
    assert "neuro_red_flags_documented" in evidence
    assert len(evidence["neuro_red_flags_documented"]) == 2
    assert any("progressive weakness" in span["text"].lower() for span in evidence["neuro_red_flags_documented"])


def test_mechanical_symptom_denial_is_captured_as_explicit_documentation():
    note = "Right knee pain x 8 weeks. PT x 8 weeks. Denies locking or instability. Prior knee xray normal."

    facts, evidence = extract_facts(note)

    assert facts["mechanical_symptoms_documented"] is False
    assert "mechanical_symptoms_documented" in evidence
    assert any("denies locking" in span["text"].lower() for span in evidence["mechanical_symptoms_documented"])


def test_conflicting_mechanical_symptoms_require_review():
    note = (
        "Right knee pain x 8 weeks. PT x 8 weeks. Denies locking earlier in visit. "
        "Later note: reports buckling with stairs. Prior knee xray normal."
    )

    facts, evidence = extract_facts(note)

    assert facts["mechanical_symptoms_documented"] == REVIEW_REQUIRED_FACT
    assert "mechanical_symptoms_documented" in evidence
    assert len(evidence["mechanical_symptoms_documented"]) == 2
    assert any("buckling" in span["text"].lower() for span in evidence["mechanical_symptoms_documented"])


def test_same_sentence_mechanical_contradiction_requires_review():
    facts, evidence = extract_facts("Patient denies locking but later reports buckling with stairs.")

    assert facts["mechanical_symptoms_documented"] == REVIEW_REQUIRED_FACT
    assert evidence["mechanical_symptoms_documented"]


def test_review_required_fact_bypasses_rule_operator_and_fails_closed():
    requirement = {
        "key": "criterion",
        "label": "Criterion",
        "type": "boolean",
        "operator": "equals_true",
    }

    results, _ = evaluate_requirements([requirement], {"criterion": REVIEW_REQUIRED_FACT})
    overall = compute_overall_status(results)

    assert results[0].status == "NEEDS_REVIEW"
    assert overall == {"overall_status": "NEEDS_REVIEW", "submission_readiness": False}
