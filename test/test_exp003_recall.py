"""Prospective drug-table pairs through the public service, without attestations."""

import json
from pathlib import Path

import pytest

from engine.schemas import PARequest
from engine.service import ReadinessService

ROOT = Path(__file__).resolve().parents[1]
CASES = [case for path in sorted((ROOT / "autoloop/exp-003/cases").glob("iteration-*.json")) for case in json.loads(path.read_text())]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_exp003_pair(case):
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


def test_drug_table_is_small_and_outside_governance_bundle():
    from engine.note_context import DRUG_TABLE_PATH

    table = json.loads(DRUG_TABLE_PATH.read_text())
    assert 20 <= len(table["drugs"]) <= 40
    assert "need human review" in table["notice"]
    assert DRUG_TABLE_PATH.resolve().as_posix() not in {path for path, _ in ReadinessService()._bundle_snapshot()}


@pytest.mark.parametrize(
    "code,therapy_class",
    [
        ("N05BA01", "muscle relaxants"),  # diazepam, outside allowed groups
        ("H02AB07", "analgesics"),  # prednisone
        ("M02AA15", "NSAIDs"),  # topical diclofenac
        ("M03AC09", "muscle relaxants"),  # rocuronium
        ("M03AX01", "muscle relaxants"),  # botulinum toxin
        ("M01AE01", "analgesics"),  # allowed code, wrong reviewed class
        ("N02BE01", "NSAIDs"),
        ("M01A", "NSAIDs"),  # group alone is not a substance code
    ],
)
def test_drug_table_rejects_outside_groups_and_class_disagreement(monkeypatch, code, therapy_class):
    from engine.note_context import DRUG_TABLE_PATH, load_drug_classes

    table = json.loads(DRUG_TABLE_PATH.read_text())
    table["drugs"][0]["atc_code"] = code
    table["drugs"][0]["class"] = therapy_class
    # Supply in-memory corrupt data; do not mutate the versioned artifact.
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: json.dumps(table))
    with pytest.raises(ValueError, match="ATC code and Footnote 1 class"):
        load_drug_classes()
