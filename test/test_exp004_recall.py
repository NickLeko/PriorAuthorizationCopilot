"""Independent paraphrases, authored before each general grammar implementation."""

import json
from pathlib import Path

import pytest

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
    for key, expected in case.get("expected_facts", {}).items():
        assert result.facts[key] == expected
    for spans in result.evidence_map.values():
        for span in spans:
            assert case["note_text"][span.start : span.end] == span.text
