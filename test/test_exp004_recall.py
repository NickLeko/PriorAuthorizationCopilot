"""Independent paraphrases, authored before each general grammar implementation."""

import json
from pathlib import Path

import pytest

from engine.extract import extract_facts
from engine.schemas import PARequest
from engine.service import ReadinessService

ROOT = Path(__file__).resolve().parents[1]
CASES = [case for path in sorted((ROOT / "autoloop/exp-004/cases").glob("*.json")) for case in json.loads(path.read_text())]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_exp004_paraphrase(case):
    request = PARequest.model_validate({key: case[key] for key in ("payer", "procedure_code", "note_text")})
    result = ReadinessService().evaluate(request)
    assert result.overall_status == case["expected_overall_status"]
    assert result.overall_status != "READY"
    assert result.submission_readiness is False
    assert all(item.verification.state == "UNVERIFIED" for item in result.results)
    if case["pair_role"] == "negative":
        assert result.overall_status != "PENDING_VERIFICATION"
        assert any(item.status != "MET" for item in result.results)
    # Expected extraction facts include the review sentinel. Public service
    # facts intentionally expose None with a separate NEEDS_REVIEW state.
    raw_facts, _ = extract_facts(case["note_text"])
    for key, expected in case.get("expected_facts", {}).items():
        assert raw_facts[key] == expected
        if expected == "__REVIEW_REQUIRED__":
            assert result.facts[key] is None
            assert result.captured_fact_states[key] == "NEEDS_REVIEW"
    for spans in result.evidence_map.values():
        for span in spans:
            assert case["note_text"][span.start : span.end] == span.text
