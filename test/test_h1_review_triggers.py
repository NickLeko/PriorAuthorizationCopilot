"""Sentence-scoped review cues; open classes are correct-value strict xfails."""

import json

import pytest
from verification_helpers import attest

from engine.extract import RADICULOPATHY_RE, _finding_is_uncertain, extract_facts
from engine.schemas import REVIEW_REQUIRED_FACT, PARequest
from engine.service import ReadinessService

B = "back_pain_with_radiculopathy"
OBJECTIVE = "objective_motor_or_reflex_change_in_root_distribution"
D = "cpb_0236_conservative_therapy_weeks"
R = "cpb_0236_conservative_therapy_no_improvement"
N1 = (
    "PREVIOUS NOTE (2019): low back pain with radiculopathy, right L5 distribution strength 4/5, "
    "NSAIDs for 8 weeks with no improvement. TODAY: asymptomatic."
)
N2 = "ROS: [ ] low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with no improvement."
N3 = "Low back pain with radiculopathy no longer present. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with no improvement."
N4 = "Low back pain with radiculopathy.\nRight L5 distribution: strength 4/5.\nNSAIDs for 8 weeks with no improvement\nNow much improved"
N5 = (
    "Low back pain with left leg radiculopathy. Exam: right L5 distribution strength 4/5 from prior hip surgery. "
    "NSAIDs for 8 weeks with no improvement."
)
CROSS_SENTENCE = (
    "Copied from 2019 visit. Low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with no improvement."
)

VARIANTS = [
    ("no_longer_uppercase", "LOW BACK PAIN WITH RADICULOPATHY NO LONGER PRESENT!", B),
    ("no_longer_evident", "Low back pain with radiculopathy is no longer evident.", B),
    ("no_longer_noted", "Low back pain with radiculopathy; no longer noted.", B),
    ("no_longer_seen", "Low back pain with radiculopathy, no longer seen.", B),
    ("no_longer_active", "Low back pain with radiculopathy is no longer active.", B),
    ("no_longer_has", "Patient no longer has low back pain with radiculopathy.", B),
    ("no_longer_have", "Patients no longer have low back pain with radiculopathy.", B),
    ("no_longer_reports", "No longer reports low back pain with radiculopathy.", B),
    ("no_longer_direct", "Low back pain with radiculopathy no longer.", B),
    ("previous_note", "Previous note: low back pain with radiculopathy.", B),
    ("prior_note_uppercase", "PRIOR NOTE: low back pain with radiculopathy.", B),
    ("copied_from_date", "Copied from 03/2021 visit: low back pain with radiculopathy.", B),
    ("copied_forward", "COPIED FORWARD — low back pain with radiculopathy.", B),
    ("copied_forward_hyphen", "Copied-forward: low back pain with radiculopathy.", B),
    ("carried_forward", "Carried forward (review): low back pain with radiculopathy.", B),
    ("from_prior_note", "From prior note: low back pain with radiculopathy.", B),
    ("from_previous_visit", "From the previous visit, low back pain with radiculopathy.", B),
    ("from_prior_encounter", "From the prior encounter: low back pain with radiculopathy.", B),
    ("per_prior_note", "Per prior note: low back pain with radiculopathy.", B),
    ("per_previous_visit", "PER THE PREVIOUS VISIT: low back pain with radiculopathy.", B),
    ("note_dated_year", "Note dated 2019: low back pain with radiculopathy.", B),
    ("visit_from_iso_date", "Visit from 2021-03-09: low back pain with radiculopathy.", B),
    ("encounter_dated_us_date", "Encounter dated 03/09/2021: low back pain with radiculopathy.", B),
    ("note_from_month_year", "Note from 03/2021: low back pain with radiculopathy.", B),
    ("checkbox_empty", "[ ] low back pain with radiculopathy.", B),
    ("checkbox_checked", "[x] radicular pain with low back pain.", B),
    ("checkbox_uppercase", "ROS: [X] LOW BACK PAIN WITH RADICULOPATHY!", B),
    ("checkbox_unicode_empty", "☐ low back pain with radiculopathy", B),
    ("checkbox_unicode_checked", "ROS: ☑ low back pain with radiculopathy.", B),
    ("checkbox_unicode_cross", "☒ low back pain with radiculopathy; exam discussed.", B),
]


@pytest.mark.parametrize(
    "note,affected", [(N1, (B, OBJECTIVE, D, R)), (N2, (B,)), (N3, (B,))], ids=("copy_forward", "template", "no_longer")
)
def test_exact_audit_notes_require_review_even_with_all_attestations(note, affected):
    facts, _ = extract_facts(note)
    assert all(facts[key] == REVIEW_REQUIRED_FACT for key in affected)
    service = ReadinessService()  # conftest pins governance to 2026-09-01.
    proposal = service.evaluate(PARequest(payer="Aetna", procedure_code="MRI_LUMBAR", note_text=note))
    assert proposal.overall_status == "NEEDS_REVIEW"
    assert all(proposal.captured_fact_states[key] == "NEEDS_REVIEW" for key in affected)
    reviewed = service.evaluate(attest(proposal))
    assert len(reviewed.results) == 4
    assert all(item.verification.state == "HUMAN_VERIFIED" for item in reviewed.results)
    assert reviewed.overall_status == "NEEDS_REVIEW"
    assert reviewed.submission_readiness is False


@pytest.mark.parametrize("name,note,key", VARIANTS, ids=[case[0] for case in VARIANTS])
def test_review_trigger_variants(name, note, key):
    assert extract_facts(note)[0][key] == REVIEW_REQUIRED_FACT


@pytest.mark.parametrize("prefix", ("PRIOR NOTE: ", "ROS: [x] ", "No longer present: "))
@pytest.mark.parametrize(
    "finding,key",
    [
        ("Reports locking.", "mechanical_symptoms_documented"),
        ("OSA.", "osa_diagnosis"),
        ("Sleep study 2026-03-09.", "sleep_study_date"),
        ("AHI 32.", "ahi_documented"),
        ("Prior MRI showed abnormal findings.", "prior_imaging_result"),
        ("Pain for 8 weeks.", "symptom_duration_weeks"),
        ("Denies weakness.", "neuro_red_flags_documented"),
        ("PT for 8 weeks.", "conservative_therapy_weeks"),
        ("Right L5 distribution: strength 4/5.", OBJECTIVE),
        ("NSAIDs for 8 weeks with no improvement.", D),
        ("NSAIDs for 8 weeks with no improvement.", R),
    ],
)
def test_review_triggers_use_the_shared_finding_path(prefix, finding, key):
    assert extract_facts(prefix + finding)[0][key] == REVIEW_REQUIRED_FACT


def test_standalone_radiculopathy_phrase_uses_review_helper_without_inventing_back_pain():
    note = "Radiculopathy is no longer evident."
    lower = note.lower()
    assert _finding_is_uncertain(lower, RADICULOPATHY_RE.search(lower))
    assert extract_facts(note)[0][B] is None


@pytest.mark.xfail(strict=True, reason="cross-sentence therapy response: improvement on the next line is not linked")
def test_improved_newline_response_should_require_review():
    assert extract_facts(N4)[0][R] == REVIEW_REQUIRED_FACT


def test_left_vs_right_objective_finding_should_require_review():
    assert extract_facts(N5)[0][OBJECTIVE] == REVIEW_REQUIRED_FACT


@pytest.mark.xfail(strict=True, reason="cross-sentence copy-forward: header does not scope later sentences")
def test_cross_sentence_copy_forward_should_require_review():
    assert extract_facts(CROSS_SENTENCE)[0][B] == REVIEW_REQUIRED_FACT


# Literal baseline facts and spans captured before changing the 3b863a9 extractor.
CONTROLS = [
    (
        "Low back pain with right leg radiculopathy x 8 weeks. NSAIDs for 8 weeks with minimal improvement; PT also "
        "completed. Objective motor exam in the right L5 distribution: ankle dorsiflexion strength 4/5. Denies bowel/bladder "
        "incontinence. No saddle anesthesia. Prior imaging: lumbar xray inconclusive.",
        {
            "conservative_therapy_weeks": 8,
            "cpb_0236_conservative_therapy_weeks": 8,
            "cpb_0236_conservative_therapy_no_improvement": True,
            "back_pain_with_radiculopathy": True,
            "objective_motor_or_reflex_change_in_root_distribution": True,
            "neuro_red_flags_documented": True,
            "prior_imaging_result": "inconclusive",
            "symptom_duration_weeks": 8,
            "mechanical_symptoms_documented": None,
            "osa_diagnosis": None,
            "sleep_study_date": None,
            "ahi_documented": None,
        },
        {
            "conservative_therapy_weeks": [{"start": 54, "end": 72, "text": "NSAIDs for 8 weeks"}],
            "cpb_0236_conservative_therapy_weeks": [{"start": 54, "end": 97, "text": "NSAIDs for 8 weeks with minimal improvement"}],
            "cpb_0236_conservative_therapy_no_improvement": [
                {"start": 54, "end": 97, "text": "NSAIDs for 8 weeks with minimal improvement"}
            ],
            "back_pain_with_radiculopathy": [{"start": 0, "end": 52, "text": "Low back pain with right leg radiculopathy x 8 weeks"}],
            "objective_motor_or_reflex_change_in_root_distribution": [
                {"start": 118, "end": 200, "text": "Objective motor exam in the right L5 distribution: ankle dorsiflexion strength 4/5"}
            ],
            "symptom_duration_weeks": [{"start": 45, "end": 52, "text": "8 weeks"}],
            "neuro_red_flags_documented": [
                {"start": 202, "end": 235, "text": "Denies bowel/bladder incontinence"},
                {"start": 237, "end": 257, "text": "No saddle anesthesia"},
            ],
            "prior_imaging_result": [{"start": 286, "end": 298, "text": "inconclusive"}],
        },
    ),
    (
        "Low back pain with right leg radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with minimal improvement.",
        {
            "conservative_therapy_weeks": 8,
            "cpb_0236_conservative_therapy_weeks": 8,
            "cpb_0236_conservative_therapy_no_improvement": True,
            "back_pain_with_radiculopathy": True,
            "objective_motor_or_reflex_change_in_root_distribution": True,
            "neuro_red_flags_documented": None,
            "prior_imaging_result": None,
            "symptom_duration_weeks": None,
            "mechanical_symptoms_documented": None,
            "osa_diagnosis": None,
            "sleep_study_date": None,
            "ahi_documented": None,
        },
        {
            "conservative_therapy_weeks": [{"start": 81, "end": 99, "text": "NSAIDs for 8 weeks"}],
            "cpb_0236_conservative_therapy_weeks": [{"start": 81, "end": 124, "text": "NSAIDs for 8 weeks with minimal improvement"}],
            "cpb_0236_conservative_therapy_no_improvement": [
                {"start": 81, "end": 124, "text": "NSAIDs for 8 weeks with minimal improvement"}
            ],
            "back_pain_with_radiculopathy": [{"start": 0, "end": 42, "text": "Low back pain with right leg radiculopathy"}],
            "objective_motor_or_reflex_change_in_root_distribution": [
                {"start": 44, "end": 79, "text": "Right L5 distribution: strength 4/5"}
            ],
        },
    ),
    (
        "Note: right L5 distribution strength 4/5.",
        {
            "conservative_therapy_weeks": None,
            "cpb_0236_conservative_therapy_weeks": None,
            "cpb_0236_conservative_therapy_no_improvement": None,
            "back_pain_with_radiculopathy": None,
            "objective_motor_or_reflex_change_in_root_distribution": True,
            "neuro_red_flags_documented": None,
            "prior_imaging_result": None,
            "symptom_duration_weeks": None,
            "mechanical_symptoms_documented": None,
            "osa_diagnosis": None,
            "sleep_study_date": None,
            "ahi_documented": None,
        },
        {
            "objective_motor_or_reflex_change_in_root_distribution": [
                {"start": 0, "end": 40, "text": "Note: right L5 distribution strength 4/5"}
            ]
        },
    ),
]


@pytest.mark.parametrize("note,expected_facts,expected_spans", CONTROLS, ids=("MRI-01-complete", "minimal-improvement", "plain-note"))
def test_untriggered_controls_keep_exact_facts_and_spans(note, expected_facts, expected_spans):
    facts, spans = extract_facts(note)

    def encode(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    assert encode(facts) == encode(expected_facts)
    assert encode(spans) == encode(expected_spans)


@pytest.mark.parametrize(
    "note",
    [
        "Low back pain with radiculopathy [ ].",
        "Low back pain with radiculopathy. PRIOR NOTE: administrative header.",
        "Low back pain with radiculopathy, walking for no longer than 8 weeks.",
    ],
)
def test_trigger_position_and_comparative_controls_keep_lumbar_finding(note):
    assert extract_facts(note)[0][B] is True
