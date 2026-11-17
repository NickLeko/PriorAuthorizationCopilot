"""Phase 2: per-course, per-fact resolution of CPB 0236 class-name therapy courses.

Every case comes from docs/evaluation/phase2_spec.md sections 5.2 and 5.3. "review" means
the fact is routed to human review. Each note follows the standard lumbar diagnosis and
exam sentences, so only the therapy facts vary.
"""

import pytest

from engine.extract import extract_facts
from engine.schemas import REVIEW_REQUIRED_FACT, PARequest
from engine.service import ReadinessService
from evaluation.schema import DATASET_DIR, load_dataset

BASE = "Low back pain with right leg radiculopathy. Objective motor exam in the right L5 distribution: strength 4/5. "
WEEKS = "cpb_0236_conservative_therapy_weeks"
RESPONSE = "cpb_0236_conservative_therapy_no_improvement"
REVIEW = "review"


def therapy(note):
    facts, _ = extract_facts(BASE + note)
    return tuple(REVIEW if facts[key] == REVIEW_REQUIRED_FACT else facts[key] for key in (WEEKS, RESPONSE))


# Spec 5.2: each framing allowance, and a note that allowance must not let through.
FRAMING_PAIRS = [
    (
        "pronoun",
        "She completed NSAIDs for 8 weeks with no improvement.",
        "She missed NSAIDs for 8 weeks with no improvement.",
        (REVIEW, REVIEW),
    ),
    (
        "header",
        "Conservative therapy: NSAIDs for 8 weeks with no improvement.",
        "Conservative therapy (2019): NSAIDs for 8 weeks with no improvement.",
        (REVIEW, REVIEW),
    ),
    (
        "modifier",
        "Over-the-counter NSAIDs for 8 weeks with no improvement.",
        "Over-the-counter NSAIDs for 8 weeks in 2019 with no improvement.",
        (REVIEW, REVIEW),
    ),
    (
        "response object",
        "NSAIDs for 8 weeks with no improvement in her pain.",
        "NSAIDs for 8 weeks with no improvement in sleep.",
        (8, REVIEW),
    ),
    ("qualifier", "NSAIDs for 8 weeks with no improvement so far.", "NSAIDs for 8 weeks with no improvement at the time.", (8, REVIEW)),
    (
        "use verb",
        "Has been on NSAIDs for 8 weeks with no improvement.",
        "Has been off NSAIDs for 8 weeks with no improvement.",
        (REVIEW, REVIEW),
    ),
    (
        "response verb",
        "NSAIDs for 9 weeks produced no improvement.",
        "NSAIDs for 8 weeks provided little improvement initially.",
        (8, REVIEW),
    ),
]


@pytest.mark.parametrize(("allowance", "valid", "invalid", "invalid_expected"), FRAMING_PAIRS, ids=[row[0] for row in FRAMING_PAIRS])
def test_each_framing_allowance_keeps_valid_courses_and_rejects_its_paired_hole(allowance, valid, invalid, invalid_expected):
    weeks, response = therapy(valid)
    assert type(weeks) is int and response is True
    assert therapy(invalid) == invalid_expected


# Spec 5.3: multiple courses, historical courses and response changes, as (duration, response).
COURSE_CASES = [
    ("Analgesics for 2 weeks were stopped. NSAIDs and muscle relaxants for 6 weeks with no improvement.", (6, True)),
    ("Missed muscle relaxants for 2 weeks. NSAIDs for 8 weeks with no improvement.", (8, True)),
    # Independent-course principle: a separate shorter uncertain course does not invalidate a clean course.
    ("In 2019, NSAIDs for 4 weeks with no improvement. Muscle relaxants for 6 weeks with no improvement.", (6, True)),
    # Option A: an uncertain course longer than the clean one sends both facts to review.
    (
        "Muscle relaxants for 6 weeks with no improvement. Intermittent NSAIDs for 10 weeks, taken twice total, with no improvement.",
        (REVIEW, REVIEW),
    ),
    ("Muscle relaxants for 2 weeks produced no improvement, whereas NSAIDs for 8 weeks were also documented.", (REVIEW, REVIEW)),
    ("In 2019, NSAIDs for 8 weeks with no improvement.", (REVIEW, REVIEW)),
    ("NSAIDs for 8 weeks with no improvement at the time; that was before the current flare began last week.", (REVIEW, REVIEW)),
    ("Prior visit note (2019): NSAIDs for 8 weeks with no improvement.", (REVIEW, REVIEW)),
    ("NSAIDs for 8 weeks with no improvement so far.", (8, True)),
    ("Patient completed NSAIDs for 8 weeks with minimal improvement; PT also completed.", (8, True)),
    ("NSAIDs for 8 weeks with no improvement initially, now much improved.", (8, REVIEW)),
    ("NSAIDs for 8 weeks with no improvement in sleep.", (8, REVIEW)),
    ("NSAIDs for 8 weeks provided little improvement initially.", (8, REVIEW)),
    ("NSAIDs for 8 weeks with no improvement, then marked improvement after week 6.", (8, REVIEW)),
    ("NSAIDs for 8 weeks with no improvement in sleep but significant improvement in pain.", (REVIEW, REVIEW)),
    ("NSAIDs for 8 weeks with significant improvement.", (8, False)),
]


@pytest.mark.parametrize(("note", "expected"), COURSE_CASES, ids=[f"case-{index:02d}" for index in range(1, len(COURSE_CASES) + 1)])
def test_courses_are_resolved_per_course_and_per_fact(note, expected):
    assert therapy(note) == expected


def test_a_documented_duration_stays_met_when_only_the_response_changes():
    service = ReadinessService()
    note = BASE + "NSAIDs for 8 weeks with no improvement initially, now much improved."
    result = service.evaluate(PARequest(payer="Aetna", procedure_code="MRI_LUMBAR", note_text=note))
    statuses = {item.key: item.status for item in result.results}
    assert statuses[WEEKS] == "MET"
    assert statuses[RESPONSE] == "NEEDS_REVIEW"
    assert result.overall_status == "NEEDS_REVIEW"


def test_every_framing_control_keeps_its_valid_course():
    controls = load_dataset(DATASET_DIR / "framing_controls_v1.json")
    known_misses = {("PC-05", WEEKS), ("PC-20", RESPONSE)}
    for case in controls.cases:
        facts, _ = extract_facts(case.note_text)
        for key in (WEEKS, RESPONSE):
            if (case.case_id, key) in known_misses:
                continue
            assert facts[key] not in (None, REVIEW_REQUIRED_FACT), (case.case_id, key)


# Sibling-clause commentary (owner request, November 17). A sibling clause that names no
# therapy is treated as commentary on the course unless it is one of a small, closed set of
# clearly independent, non-treatment statements. Anything else still sends the course to review.
INDEPENDENT_COMMENTARY = [
    "NSAIDs for 8 weeks with no improvement; pain is severe.",
    "NSAIDs for 8 weeks with no improvement; MRI requested.",
    "Patient completed NSAIDs for 8 weeks with no improvement; referred to spine clinic.",
    "NSAIDs for 8 weeks with no improvement, though she still works full time.",
    "NSAIDs for 8 weeks with no improvement, but she declines injections.",
    "NSAIDs for 8 weeks with no improvement; see attached records.",
]

COURSE_COMMENTARY = [
    # Modifies the course.
    "NSAIDs for 8 weeks with no improvement; stopped after 3 days.",
    # CH-15: refers back to the course and changes its timing.
    "NSAIDs for 8 weeks with no improvement at the time; that was before the current flare began last week.",
    # Unrecognized commentary is not assumed to be independent.
    "NSAIDs for 8 weeks with no improvement; she works as a nurse.",
    # A recognized form only counts when it is the whole clause.
    "NSAIDs for 8 weeks with no improvement; MRI requested after she stopped them.",
    "NSAIDs for 8 weeks with no improvement; referred to spine clinic, stopped after 3 days.",
    "NSAIDs for 8 weeks with no improvement; pain is severe but now improving.",
    "NSAIDs for 8 weeks with no improvement; pain is no longer severe.",
]


@pytest.mark.parametrize("note", INDEPENDENT_COMMENTARY, ids=[f"independent-{index}" for index in range(1, 7)])
def test_independent_commentary_does_not_downgrade_a_clean_course(note):
    assert therapy(note) == (8, True)


@pytest.mark.parametrize("note", COURSE_COMMENTARY, ids=[f"course-commentary-{index}" for index in range(1, len(COURSE_COMMENTARY) + 1)])
def test_commentary_that_modifies_or_is_not_recognized_still_requires_review(note):
    assert therapy(note) == (REVIEW, REVIEW)


def test_independent_commentary_does_not_change_existing_multi_course_resolution():
    # Two clean paired courses with different durations already go to review in 2.7.0.
    note = "Muscle relaxants for 6 weeks with no improvement. NSAIDs for 8 weeks with no improvement; MRI requested."
    assert therapy(note) == (REVIEW, REVIEW)
    note = "In 2019, NSAIDs for 4 weeks with no improvement. Muscle relaxants for 6 weeks with no improvement; see attached records."
    assert therapy(note) == (6, True)
