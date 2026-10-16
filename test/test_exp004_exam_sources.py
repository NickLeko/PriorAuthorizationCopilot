"""Requirement-level checks for the owner-reported objective-source defect."""

import json
from pathlib import Path

import pytest

from engine.schemas import PARequest
from engine.service import ReadinessService

CASES = json.loads((Path(__file__).resolve().parents[1] / "autoloop/exp-004/cases/iteration-5.json").read_text())
OBJECTIVE = "objective_motor_or_reflex_change_in_root_distribution"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_objective_source_requirement(case):
    request = PARequest.model_validate({key: case[key] for key in ("payer", "procedure_code", "note_text")})
    result = ReadinessService().evaluate(request)
    requirement = next(item for item in result.results if item.key == OBJECTIVE)
    assert requirement.status == case["expected_objective_status"]
    if requirement.status == "NOT_DOCUMENTED":
        assert result.facts[OBJECTIVE] is None
        assert result.captured_fact_states[OBJECTIVE] == "MISSING"
        assert not result.evidence_map.get(OBJECTIVE)
    elif requirement.status == "NEEDS_REVIEW":
        assert result.facts[OBJECTIVE] is None
        assert result.captured_fact_states[OBJECTIVE] == "NEEDS_REVIEW"
        spans = result.evidence_map[OBJECTIVE]
        assert len(spans) >= 2
        assert any("on exam" in span.text.lower() for span in spans)
        for span in spans:
            assert case["note_text"][span.start : span.end] == span.text
