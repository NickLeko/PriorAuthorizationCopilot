"""Frozen independent notes; now regressions, no longer a held-out measure."""

import json
from pathlib import Path

import pytest

from engine.citation_context import evaluation_citation_context
from engine.extract import extract_facts
from engine.schemas import REVIEW_REQUIRED_FACT, PARequest
from engine.service import ReadinessService

CASES = json.loads(Path("test/fixtures/v210_independent.json").read_text())


def evaluate(case):
    return ReadinessService().evaluate(PARequest(payer="Aetna", procedure_code=case["procedure"], note_text=case["note"]))


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(case, marks=pytest.mark.xfail(strict=True, reason="cross-sentence temporality"))
        if case["id"] == 12
        else pytest.param(case, marks=pytest.mark.xfail(strict=True, reason="intact reflex recognition"))
        if case["id"] == 18
        else case
        for case in CASES
    ],
    ids=lambda case: f"independent_{case['id']:02}_{case['name']}",
)
def test_independent_correct_values_and_states(case):
    expected = dict(case["expected"])
    # The secondary analgesic refusal has its own correct-value strict xfail.
    if case["id"] == 2:
        expected.pop("conservative_therapy_weeks")
    facts, _ = extract_facts(case["note"])
    result = evaluate(case)
    for key, value in expected.items():
        assert facts[key] == value, key
        state = "NEEDS_REVIEW" if value == REVIEW_REQUIRED_FACT else "MISSING" if value is None else "CAPTURED"
        assert result.captured_fact_states[key] == state, key
        assert result.facts[key] == (None if value == REVIEW_REQUIRED_FACT else value), key
    assert result.submission_readiness is False
    assert {item.key: item.status for item in result.results} == case["expected_requirements"]
    assert result.overall_status == case["expected_overall"]


def test_independent_02_citation_contains_current_relief():
    contexts = evaluation_citation_context(evaluate(CASES[1]))
    for key in ("cpb_0236_conservative_therapy_weeks", "cpb_0236_conservative_therapy_no_improvement"):
        assert all("however, she now reports good relief" in context for context in contexts[key])
        assert contexts[key]


@pytest.mark.xfail(strict=True, reason="generic therapy vocabulary does not recognize analgesics")
def test_independent_02_secondary_analgesic_duration_correct_value():
    assert extract_facts(CASES[1]["note"])[0]["conservative_therapy_weeks"] == 8
    assert evaluate(CASES[1]).facts["conservative_therapy_weeks"] == 8


@pytest.mark.xfail(strict=True, reason="study citation borrows unrelated appointment date")
def test_independent_17_study_citation_correct_sentence():
    result = evaluate(CASES[16])
    assert result.facts["sleep_study_date"] is True
    assert evaluation_citation_context(result)["sleep_study_date"] == ["⟦Sleep study completed⟧, but the study date cannot be located."]


@pytest.mark.parametrize(
    "trigger",
    [
        "ordered",
        "prescribed",
        "recommended",
        "not yet started",
        "has not started",
        "not completed",
        "never completed",
        "cancelled",
        "canceled",
    ],
)
@pytest.mark.parametrize("placement", ["before", "after", "semicolon"])
def test_sentence_scoped_exclusion_not_adjacency(trigger, placement):
    candidate = "NSAIDs for 8 weeks with minimal improvement"
    note = {
        "before": f"The course was {trigger} yesterday and the documented plan lists {candidate}.",
        "after": f"{candidate}, and at today's visit the course was {trigger}.",
        "semicolon": f"{candidate}; at today's visit the course was {trigger}.",
    }[placement]
    facts, _ = extract_facts(note)
    for key in ("conservative_therapy_weeks", "cpb_0236_conservative_therapy_weeks", "cpb_0236_conservative_therapy_no_improvement"):
        assert facts[key] is None
    study_note = f"Sleep study completed 2026-03-09; at today's visit the study was {trigger}."
    assert extract_facts(study_note)[0]["sleep_study_date"] is None


@pytest.mark.parametrize("qualifier", ["resolved", "history of", "prior episode", "previous episode"])
def test_sentence_scoped_review_across_semicolon(qualifier):
    note = f"Low back pain with radiculopathy; the specialist described this as {qualifier}."
    assert extract_facts(note)[0]["back_pain_with_radiculopathy"] == REVIEW_REQUIRED_FACT


@pytest.mark.parametrize("prefix", ["was definitively", "had reportedly been", "is", "has been", "was"])
def test_sentence_scoped_ruled_out_across_semicolon(prefix):
    assert extract_facts(f"OSA discussed; the diagnosis {prefix} ruled out.")[0]["osa_diagnosis"] is None


@pytest.mark.parametrize("marker", ["however", "but", "though", "although", "yet", "whereas", ""])
def test_semicolon_response_contrast(marker):
    note = f"NSAIDs for 8 weeks with little improvement; {marker} she reports good relief."
    assert extract_facts(note)[0]["cpb_0236_conservative_therapy_no_improvement"] == REVIEW_REQUIRED_FACT


def test_sentence_trigger_does_not_cross_real_boundary():
    facts, _ = extract_facts("NSAIDs for 8 weeks with minimal improvement. PT was ordered.")
    assert facts["conservative_therapy_weeks"] == 8
    assert facts["cpb_0236_conservative_therapy_no_improvement"] is True
