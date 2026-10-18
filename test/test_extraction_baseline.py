import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

import engine.service as service_module
from engine.fact_contracts import FACT_CONTRACTS
from experiments.dual_extraction import baseline


def test_baseline_inventory_retains_existing_inputs():
    cases = baseline.case_inputs(Path.cwd())
    assert Counter(case["source"] for case in cases) == {
        "inputs/synthetic_cases.json": 52,
        "EXTRACTION_CONTRACT.md": 91,
        "test/fixtures/v210_independent.json": 20,
        "inputs/replay/cases.json": 14,
    }
    assert len({case["case_id"] for case in cases}) == 177
    assert sum(case["request"] is not None for case in cases) == 148


def test_baseline_is_reproducible_and_matches_frozen_release():
    first = baseline.build_baseline(Path.cwd())
    assert first == baseline.build_baseline(Path.cwd())
    assert baseline.encode_baseline(first) == baseline.DEFAULT_OUTPUT.read_text()
    manifest, *records = first
    assert manifest["case_count"] == 177
    assert manifest["evaluation_count"] == 148
    for record in records:
        assert set(record["facts"]) == set(record["fact_types"]) == set(record["states"]) == set(FACT_CONTRACTS)
        assert record["fact_types"] == {key: type(value).__name__ for key, value in record["facts"].items()}
        assert len(record["note_sha256"]) == 64
    # The capture records observed behavior, including known wrong behavior.
    assert sum(bool(record.get("known_failure")) for record in records) == 4


def test_baseline_captures_each_source_once(monkeypatch):
    cases = baseline.case_inputs(Path.cwd())
    selected = [cases[0], next(case for case in cases if case["request"] is None)]
    monkeypatch.setattr(baseline, "case_inputs", lambda root: selected)
    calls = []
    original = baseline.extract_facts

    def counted(note):
        calls.append(note)
        return original(note)

    monkeypatch.setattr(baseline, "extract_facts", counted)
    monkeypatch.setattr(service_module, "extract_facts", counted)
    records = baseline.build_baseline(Path.cwd())[1:]
    assert calls == [case["note"] for case in selected]
    assert records[0]["evaluation"] is not None
    assert records[1]["evaluation"] is None


def test_baseline_normalizes_only_volatile_audit_identity():
    raw = {
        "audit_trail": {"run_id": "one", "timestamp_utc": "now", "note_hash": "keep"},
        "report": {"audit_trail": {"run_id": "one", "timestamp_utc": "now", "note_hash": "keep"}},
        "original_snapshot": {"content_hash": "keep"},
        "fact_set_fingerprint": "keep",
    }
    before = deepcopy(raw)
    normalized = baseline.normalize_evaluation(raw)
    assert raw == before
    for audit in (normalized["audit_trail"], normalized["report"]["audit_trail"]):
        assert audit == {"run_id": "__RUN_ID__", "timestamp_utc": "__TIMESTAMP_UTC__", "note_hash": "keep"}
    assert normalized["original_snapshot"] == raw["original_snapshot"]
    assert normalized["fact_set_fingerprint"] == raw["fact_set_fingerprint"]


def test_baseline_cli_requires_explicit_write_and_detects_mismatch(tmp_path, capsys):
    output = tmp_path / "baseline.jsonl"
    with pytest.raises(SystemExit):
        baseline.main([])
    assert not output.exists()
    assert baseline.main(["--write", "--output", str(output)]) == 0
    assert baseline.main(["--check", "--output", str(output)]) == 0
    rows = output.read_text().splitlines()
    record = json.loads(rows[1])
    record["facts"]["symptom_duration_weeks"] = 999
    rows[1] = json.dumps(record)
    output.write_text("\n".join(rows) + "\n")
    assert baseline.main(["--check", "--output", str(output)]) == 1
    assert "differs" in capsys.readouterr().out
