"""Fresh deterministic counterexamples for exp-001; public service only."""

import json
from pathlib import Path

import pytest

from engine.citation_context import evaluation_citation_context
from engine.schemas import PARequest
from engine.service import ReadinessService

CASES = json.loads((Path(__file__).resolve().parents[1] / "autoloop/regression_cases.json").read_text())
CASES += json.loads((Path(__file__).resolve().parents[1] / "autoloop/rejected-diagnosis-cases.json").read_text())
CASES += json.loads((Path(__file__).resolve().parents[1] / "autoloop/rejected-date-cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_autoloop_regression(case):
    result = ReadinessService().evaluate(
        PARequest(
            payer=case["payer"],
            procedure_code=case["procedure_code"],
            note_text=case["note_text"],
        )
    )
    assert result.overall_status == case["expected_overall_status"]
    assert result.submission_readiness is False
    assert result.overall_status != "READY"
    for key, value in case.get("expected_facts", {}).items():
        assert result.facts[key] == value, key
    if "expected_date_evidence" in case:
        date = case["expected_date_evidence"]
        assert [span.text for span in result.evidence_map["sleep_study_date"]] == [date]
        contexts = evaluation_citation_context(result)["sleep_study_date"]
        assert contexts
        assert all(f"⟦{date}⟧" in context for context in contexts)
    requirements = {item.key: item for item in result.results}
    for key, status in case.get("expected_requirements", {}).items():
        assert requirements[key].status == status, key
    for spans in result.evidence_map.values():
        for span in spans:
            assert case["note_text"][span.start : span.end] == span.text
