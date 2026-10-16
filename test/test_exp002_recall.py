"""Policy-derived positive/near-miss pairs; public service with no attestations."""

import json
from pathlib import Path

import pytest

from engine.schemas import PARequest
from engine.service import ReadinessService

ROOT = Path(__file__).resolve().parents[1]
CASES = [case for path in sorted((ROOT / "autoloop/exp-002/cases").glob("iteration-*.json")) for case in json.loads(path.read_text())]
REJECTED_NEGATIVES = [
    case
    for path in sorted((ROOT / "autoloop/exp-002/cases").glob("rejected-*.json"))
    for case in json.loads(path.read_text())
    if case["pair_role"] == "negative"
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_exp002_pair(case):
    result = ReadinessService().evaluate(PARequest(payer=case["payer"], procedure_code=case["procedure_code"], note_text=case["note_text"]))
    assert result.overall_status == case["expected_overall_status"]
    assert result.overall_status != "READY"
    assert result.submission_readiness is False
    assert all(item.verification.state == "UNVERIFIED" for item in result.results)
    if case["pair_role"] == "negative":
        assert result.overall_status != "PENDING_VERIFICATION"
        assert any(item.status != "MET" for item in result.results)
    for key, value in case.get("expected_facts", {}).items():
        assert result.facts[key] == value, key
    for spans in result.evidence_map.values():
        for span in spans:
            assert case["note_text"][span.start : span.end] == span.text


@pytest.mark.parametrize("case", REJECTED_NEGATIVES, ids=lambda case: case["id"])
def test_exp002_rejected_candidate_stays_nonpassing(case):
    # Keep the unsafe candidate's challenges executable. Two unresolved negative
    # exact-status misses remain in the scoreboard with their original labels.
    result = ReadinessService().evaluate(PARequest(payer=case["payer"], procedure_code=case["procedure_code"], note_text=case["note_text"]))
    assert result.overall_status not in {"READY", "PENDING_VERIFICATION"}
    assert result.submission_readiness is False
    assert any(item.status != "MET" for item in result.results)
