"""Laterality qualification shared by existing objective-exam recognition routes."""

import re

import pytest
from verification_helpers import attest

import engine.extract as extraction
from engine.schemas import REVIEW_REQUIRED_FACT, PARequest
from engine.service import InvalidRequestError, ReadinessService

OBJECTIVE = "objective_motor_or_reflex_change_in_root_distribution"
ROUTES = [
    pytest.param("{side} L5 distribution: strength {score}/5.", id="slash"),
    pytest.param("{side} L5 distribution: strength {score} of 5.", id="word"),
    pytest.param("{side} L5 distribution: ankle dorsiflexion {score}/5.", id="typed-motor"),
    pytest.param("{side} L5 distribution: patellar reflex {reflex}+.", id="typed-reflex"),
    pytest.param("{side} L5 distribution: {denial}objective weakness.", id="descriptive-weakness"),
    pytest.param("{side} L5 distribution: reflexes {descriptor}.", id="descriptive-reflex"),
]


def exam(template, side, normal=False):
    return template.format(
        side=side,
        score=5 if normal else 4,
        reflex=2 if normal else 1,
        denial="no " if normal else "",
        descriptor="normal" if normal else "diminished",
    ).strip()


def note(exam_text, diagnosis_side="right"):
    return f"Low back pain with {diagnosis_side} leg radiculopathy. {exam_text} NSAIDs for 8 weeks with no improvement."


def request(text):
    return PARequest(payer="Aetna", procedure_code="MRI_LUMBAR", note_text=text)


def assert_spans(text, mapping):
    for spans in mapping.values():
        for span in spans:
            data = span if isinstance(span, dict) else span.model_dump()
            assert text[data["start"] : data["end"]] == data["text"]


@pytest.mark.parametrize("value", [True, False, REVIEW_REQUIRED_FACT])
@pytest.mark.parametrize("diagnosis_side,exam_side", [("right", "left"), ("left", "right")])
def test_shared_stage_qualifies_opposite_side_without_changing_offsets(value, diagnosis_side, exam_side):
    clause = f"{exam_side} l5 distribution: strength 4/5"
    text = note(clause, diagnosis_side).lower()
    start = text.index(clause)
    candidates = [(value, start, start + len(clause))]
    assert extraction._objective_candidates_with_laterality_guards(text, candidates) == [(REVIEW_REQUIRED_FACT, start, start + len(clause))]
    assert candidates == [(value, start, start + len(clause))]


@pytest.mark.parametrize(
    "diagnosis_side,exam_side",
    [
        ("right", "right"),
        ("left", "left"),
        ("right", ""),
        ("", "left"),
        ("right", "bilateral"),
        ("bilateral", "left"),
        ("right", "left and right"),
    ],
)
@pytest.mark.parametrize("value", [True, False, REVIEW_REQUIRED_FACT])
def test_shared_stage_preserves_matching_unsided_and_bilateral_candidates(diagnosis_side, exam_side, value):
    clause = f"{exam_side} l5 distribution: strength 4/5".strip()
    text = note(clause, diagnosis_side).lower()
    start = text.index(clause)
    candidates = [(value, start, start + len(clause))]
    assert extraction._objective_candidates_with_laterality_guards(text, candidates) == candidates


@pytest.mark.parametrize("qualifier", ["patient reports", "by history", "exam not performed", "exam deferred"])
def test_source_exclusion_precedes_laterality(qualifier):
    clause = f"{qualifier}: left l5 distribution strength 4/5"
    text = note(clause).lower()
    start = text.index(clause)
    assert extraction._objective_candidates_with_source_guards(text, [(True, start, start + len(clause))]) == []


@pytest.mark.parametrize("template", ROUTES)
def test_recognition_candidates_retain_side_and_root(monkeypatch, template):
    captured = []
    original = extraction._objective_candidates_with_source_guards

    def capture(text, candidates):
        captured.extend(text[start:end] for _, start, end in candidates)
        return original(text, candidates)

    monkeypatch.setattr(extraction, "_objective_candidates_with_source_guards", capture)
    extraction.extract_facts(note(exam(template, "left")))
    assert len(captured) == 1
    assert "left l5 distribution" in captured[0]


@pytest.mark.parametrize("template", ROUTES)
@pytest.mark.parametrize("normal", [False, True], ids=["abnormal", "normal"])
@pytest.mark.parametrize("diagnosis_side", ["left", "right"])
def test_recognition_routes_share_laterality_qualification(template, normal, diagnosis_side):
    opposite = {"left": "right", "right": "left"}[diagnosis_side]
    matching_note = note(exam(template, diagnosis_side, normal), diagnosis_side)
    mismatch_note = note(exam(template, opposite, normal), diagnosis_side)
    matching, _ = extraction.extract_facts(matching_note)
    mismatched, evidence = extraction.extract_facts(mismatch_note)
    assert matching[OBJECTIVE] is (not normal)
    assert mismatched[OBJECTIVE] == REVIEW_REQUIRED_FACT
    assert {key: value for key, value in matching.items() if key != OBJECTIVE} == {
        key: value for key, value in mismatched.items() if key != OBJECTIVE
    }
    assert_spans(mismatch_note, evidence)


@pytest.mark.parametrize("template", ROUTES)
@pytest.mark.parametrize("normal", [False, True], ids=["abnormal", "normal"])
def test_unsided_exams_preserve_recognition(template, normal):
    facts, _ = extraction.extract_facts(note(exam(template, "", normal)))
    assert facts[OBJECTIVE] is (not normal)


@pytest.mark.parametrize("template", ROUTES)
def test_bilateral_exams_preserve_recognition(template):
    facts, _ = extraction.extract_facts(note(exam(template, "bilateral")))
    # The word recognizer deliberately requires a full match and never recognized
    # a leading bilateral qualifier. This change must not expand recognition.
    expected = None if " of 5" in template else True
    assert facts[OBJECTIVE] is expected


@pytest.mark.parametrize("template", ROUTES)
@pytest.mark.parametrize("normal", [False, True], ids=["abnormal", "normal"])
def test_service_mismatch_requires_review_with_exact_citations(template, normal):
    text = "İ😀. " + note(exam(template, "left", normal))
    result = ReadinessService().evaluate(request(text))
    requirement = next(item for item in result.results if item.key == OBJECTIVE)
    assert requirement.status == result.overall_status == "NEEDS_REVIEW"
    assert result.captured_fact_states[OBJECTIVE] == "NEEDS_REVIEW"
    assert result.facts[OBJECTIVE] is None
    assert result.submission_readiness is False
    assert [item.key for item in result.blockers.needs_review] == [OBJECTIVE]
    expected = exam(template, "left", normal).removesuffix(".")
    start = text.index(expected)
    assert [span.model_dump() for span in result.evidence_map[OBJECTIVE]] == [
        {"start": start, "end": start + len(expected), "text": expected}
    ]
    assert_spans(text, result.evidence_map)
    assert_spans(text, result.audit_trail.evidence_map)
    assert len(requirement.verification_fingerprint) == 64


@pytest.mark.parametrize("template", ROUTES)
@pytest.mark.parametrize("mismatch", [False, True], ids=["matching", "opposite"])
@pytest.mark.parametrize("normal", [False, True], ids=["abnormal", "normal"])
def test_unilateral_single_candidate_side_mirroring(monkeypatch, template, mismatch, normal):
    count = []
    original = extraction._objective_candidates_with_source_guards

    def capture(text, candidates):
        count.append(len(candidates))
        return original(text, candidates)

    monkeypatch.setattr(extraction, "_objective_candidates_with_source_guards", capture)
    text = note(exam(template, "left" if mismatch else "right", normal))
    mirrored = re.sub(r"\b(left|right)\b", lambda match: {"left": "right", "right": "left"}[match[0]], text)
    facts, evidence = extraction.extract_facts(text)
    mirrored_facts, mirrored_evidence = extraction.extract_facts(mirrored)
    assert count == [1, 1]
    assert facts == mirrored_facts
    expected = REVIEW_REQUIRED_FACT if mismatch else not normal
    assert facts[OBJECTIVE] == expected
    assert_spans(text, evidence)
    assert_spans(mirrored, mirrored_evidence)


def test_existing_generic_root_route_is_qualified():
    text = note("Left nerve-root distribution: strength 4/5.")
    assert extraction.extract_facts(text)[0][OBJECTIVE] == REVIEW_REQUIRED_FACT


def test_conflicting_and_source_qualified_candidates_keep_review():
    text = note("Left L5 distribution: strength 4/5. Right L5 distribution: strength 5/5.")
    result = ReadinessService().evaluate(request(text))
    assert result.overall_status == "NEEDS_REVIEW"
    assert len(result.evidence_map[OBJECTIVE]) == 2
    text = note("Patient reports left L5 distribution: strength 4/5. On exam right L5 distribution: strength 5/5.")
    result = ReadinessService().evaluate(request(text))
    assert result.overall_status == "NEEDS_REVIEW"
    assert len(result.evidence_map[OBJECTIVE]) == 2


def test_changed_qualification_invalidates_old_attestation(monkeypatch):
    text = note("Left L5 distribution: strength 4/5.")
    service = ReadinessService()
    corrected = service.evaluate(request(text))
    assert corrected.overall_status == "NEEDS_REVIEW"
    # Emulate the old qualification for exactly the same input, not a note edit.
    with monkeypatch.context() as patch:
        patch.setattr(extraction, "_objective_candidates_with_laterality_guards", lambda text, candidates: list(candidates))
        legacy = service.evaluate(request(text))
    assert legacy.overall_status == "PENDING_VERIFICATION"
    assert corrected.input_fingerprint == legacy.input_fingerprint
    assert corrected.original_snapshot.content_hash != legacy.original_snapshot.content_hash
    assert corrected.fact_set_fingerprint != legacy.fact_set_fingerprint
    assert corrected.evidence_map == legacy.evidence_map
    with pytest.raises(InvalidRequestError, match="Stale or mismatched verification"):
        service.evaluate(attest(legacy))


MIXED_DIAGNOSES = [
    pytest.param(
        "History of left leg radiculopathy. Low back pain with current right leg radiculopathy.",
        id="historical-contralateral",
    ),
    pytest.param("No left leg radiculopathy. Low back pain with right leg radiculopathy.", id="negated-contralateral"),
]


@pytest.mark.parametrize("diagnoses", MIXED_DIAGNOSES)
@pytest.mark.parametrize("template", ROUTES)
@pytest.mark.parametrize("normal", [False, True], ids=["abnormal", "normal"])
@pytest.mark.parametrize("exam_side", ["left", "right"], ids=["opposite-current", "matching-current"])
def test_mixed_diagnosis_mentions_require_notation_parity(diagnoses, template, normal, exam_side):
    # Existing inline semantics are literal: either exam side has an opposite
    # mention here. This does not resolve historical or negated diagnoses.
    text = f"{diagnoses} {exam(template, exam_side, normal)} NSAIDs for 8 weeks with no improvement."
    result = ReadinessService().evaluate(request(text))
    requirement = next(item for item in result.results if item.key == OBJECTIVE)
    assert result.overall_status == requirement.status == "NEEDS_REVIEW"
    assert result.facts[OBJECTIVE] is None
    assert result.captured_fact_states[OBJECTIVE] == "NEEDS_REVIEW"
    assert result.submission_readiness is False
    assert len(result.evidence_map[OBJECTIVE]) == 1
    assert_spans(text, result.evidence_map)
    quote = exam(template, exam_side, normal).removesuffix(".")
    span = result.evidence_map[OBJECTIVE][0]
    assert (span.start, span.end, span.text) == (text.index(quote), text.index(quote) + len(quote), quote)


@pytest.mark.parametrize("diagnoses", MIXED_DIAGNOSES)
@pytest.mark.parametrize("template", ROUTES)
@pytest.mark.parametrize("normal", [False, True], ids=["abnormal", "normal"])
@pytest.mark.parametrize("exam_side", ["", "bilateral"], ids=["unsided", "bilateral"])
def test_mixed_diagnoses_preserve_unsided_and_bilateral_exams(diagnoses, template, normal, exam_side):
    text = f"{diagnoses} {exam(template, exam_side, normal)} NSAIDs for 8 weeks with no improvement."
    facts, evidence = extraction.extract_facts(text)
    expected = None if exam_side == "bilateral" and " of 5" in template else not normal
    assert facts[OBJECTIVE] is expected
    assert_spans(text, evidence)


@pytest.mark.parametrize("value", [True, False, REVIEW_REQUIRED_FACT])
def test_shared_stage_uses_existing_literal_opposite_mention_semantics(value):
    clause = "left l5 distribution: strength 4/5"
    text = note(clause, "left and right").lower()
    start = text.index(clause)
    assert extraction._objective_candidates_with_laterality_guards(text, [(value, start, start + len(clause))]) == [
        (REVIEW_REQUIRED_FACT, start, start + len(clause))
    ]


def test_mixed_side_correction_invalidates_reviewed_branch_attestation(monkeypatch):
    text = "No left leg radiculopathy. Low back pain with right leg radiculopathy. Right L5 distribution: strength 4/5."
    text += " NSAIDs for 8 weeks with no improvement."
    service = ReadinessService()
    corrected = service.evaluate(request(text))
    assert corrected.overall_status == "NEEDS_REVIEW"
    # On 2c762a8, both diagnosis sides caused this shared step to return unchanged.
    with monkeypatch.context() as patch:
        patch.setattr(extraction, "_objective_candidates_with_laterality_guards", lambda text, candidates: list(candidates))
        reviewed = service.evaluate(request(text))
    assert reviewed.overall_status == "PENDING_VERIFICATION"
    assert corrected.input_fingerprint == reviewed.input_fingerprint
    assert corrected.bundle_fingerprint == reviewed.bundle_fingerprint
    assert corrected.contract_version == reviewed.contract_version
    assert corrected.evidence_map == reviewed.evidence_map
    assert corrected.original_snapshot.content_hash != reviewed.original_snapshot.content_hash
    assert corrected.fact_set_fingerprint != reviewed.fact_set_fingerprint
    assert all(a.verification_fingerprint != b.verification_fingerprint for a, b in zip(corrected.results, reviewed.results, strict=True))
    assert {k: v for k, v in corrected.facts.items() if k != OBJECTIVE} == {k: v for k, v in reviewed.facts.items() if k != OBJECTIVE}
    with pytest.raises(InvalidRequestError, match="Stale or mismatched verification"):
        service.evaluate(attest(reviewed))
