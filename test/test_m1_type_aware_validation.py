"""Type-preserving consistency checks at validation and archive boundaries."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.corrections import capture_original, note_hash
from engine.decision_store import DecisionStore, validate_archived_evaluation
from engine.policies import canonical_dump, canonical_json, content_hash
from engine.schemas import REVIEW_REQUIRED_FACT, EvaluationResult, EvaluationResultV15, PARequest
from engine.service import ReadinessService

ROOT = Path(__file__).resolve().parents[1]
GOLDENS = ROOT / "test/golden/evaluations"
RECORDS = ("reviewer-corrected-full-projection", "MRI-01-human-verified")
MUTATIONS = ("true_to_int", "true_to_float", "false_to_zero", "weeks_to_float")
RESULT_MISMATCH = "Requirement result does not match evaluation of effective facts"
METRIC_FIELDS = (
    "total_requirements",
    "documented_requirement_count",
    "evaluable_requirement_count",
    "criteria_met_count",
    "criteria_not_met_count",
    "missing_requirement_count",
    "human_review_count",
    "documentation_coverage_pct",
)


def golden_record(name):
    payload = json.loads((GOLDENS / f"{name}.json").read_text())
    payload.pop("letter", None)
    if "original_snapshot_fingerprint" in payload:
        # Uncorrected goldens are display projections. Restore their omitted
        # envelope from captured values and prove its stored hash is unchanged.
        facts = {
            key: REVIEW_REQUIRED_FACT if payload["captured_fact_states"].get(key) == "NEEDS_REVIEW" else value
            for key, value in payload["audit_trail"]["facts_extracted"].items()
        }
        original = capture_original(facts, payload["evidence_map"])
        assert original.content_hash == payload.pop("original_snapshot_fingerprint")
        payload["original_snapshot"] = original.model_dump(mode="json")
        for audit in (payload["audit_trail"], payload["report"]["audit_trail"]):
            audit.update(uses_reviewer_corrections=False, corrected_requirement_keys=[])
    return EvaluationResult.model_validate(payload)


def false_record(record):
    """Derive a valid synthetic False proposal before mutating its display type."""
    request = record.request.model_dump(mode="json")
    request["fact_verifications"] = {}
    key = "back_pain_with_radiculopathy"
    request.setdefault("corrections", []).append(
        {
            "requirement_key": key,
            "action": "SET_VALUE",
            "value": False,
            "reason": "incorrect_value",
            "editor": "Synthetic type-test reviewer",
            "edited_at": "2026-01-03T00:00:00Z",
            "note_hash": note_hash(request["note_text"]),
            "evidence_spans": [span.model_dump(mode="json") for span in record.evidence_map[key]],
        }
    )
    result = ReadinessService().evaluate(PARequest.model_validate(request))
    assert result.facts[key] is False
    return result


def mutate_results(payload, mutation):
    changes = []
    for results in (payload["results"], payload["report"]["results"]):
        count = 0
        for result in results:
            value = result["fact_value"]
            if mutation in {"true_to_int", "true_to_float"} and value is True:
                result["fact_value"] = 1 if mutation == "true_to_int" else 1.0
            elif mutation == "false_to_zero" and value is False:
                result["fact_value"] = 0
            elif mutation == "weeks_to_float" and result["key"] == "cpb_0236_conservative_therapy_weeks":
                assert type(value) is int and value == 8
                result["fact_value"] = 8.0
            else:
                continue
            count += 1
        changes.append(count)
    assert changes[0] == changes[1] > 0


def unchecked_result(record, payload):
    forged = record.model_copy(deep=True)
    for models, values in ((forged.results, payload["results"]), (forged.report.results, payload["report"]["results"])):
        for model, value in zip(models, values, strict=True):
            model.fact_value = value["fact_value"]
    return forged


def insert_at_rest(store, policy, payload):
    store.add_policy(policy)
    digest = content_hash({"decision_id": "at-rest", "evaluation": payload})
    store.connection.execute(
        "INSERT INTO decisions VALUES (?, ?, ?, ?, ?)",
        ("at-rest", policy.policy_id, policy.version_id, canonical_json(payload), digest),
    )
    store.connection.commit()
    stored_payload, stored_hash = store.connection.execute("SELECT payload, content_hash FROM decisions").fetchone()
    assert content_hash({"decision_id": "at-rest", "evaluation": json.loads(stored_payload)}) == stored_hash


@pytest.mark.parametrize("record_name", RECORDS)
@pytest.mark.parametrize("mutation", MUTATIONS)
@pytest.mark.parametrize("boundary", ("validate", "record", "get_decision"))
def test_consistent_fact_type_mutations_are_rejected(tmp_path, record_name, mutation, boundary):
    genuine = golden_record(record_name)
    if mutation == "false_to_zero":
        genuine = false_record(genuine)
    payload = genuine.model_dump(mode="json")
    mutate_results(payload, mutation)
    # Mutate both display copies: agreement with one another is insufficient.
    assert canonical_dump(payload["results"]) == canonical_dump(payload["report"]["results"])
    if boundary == "validate":
        with pytest.raises(ValidationError, match=RESULT_MISMATCH):
            EvaluationResult.model_validate(payload)
        return
    with DecisionStore(tmp_path / "fresh.sqlite") as store:
        if boundary == "record":
            with pytest.raises(ValidationError, match=RESULT_MISMATCH):
                store.record(unchecked_result(genuine, payload))
            assert store.decision_ids() == []
            assert store.list_policies() == []
        else:
            insert_at_rest(store, genuine.policy_version, payload)
            with pytest.raises(ValidationError, match=RESULT_MISMATCH):
                store.get_decision("at-rest")


@pytest.mark.parametrize("record_name", RECORDS)
@pytest.mark.parametrize("field", METRIC_FIELDS)
@pytest.mark.parametrize("copies", ("typed", "all"))
def test_typed_metric_coercion_rejects_or_preserves_canonical_record(record_name, field, copies):
    genuine = golden_record(record_name)
    payload = genuine.model_dump(mode="json")
    containers = [payload["metrics"], payload["audit_trail"]["metrics"]]
    if copies == "all":
        containers.append(payload["report"]["audit_trail"]["metrics"])
    for metrics in containers:
        value = metrics[field]
        metrics[field] = int(value) if field == "documentation_coverage_pct" else float(value)
        assert type(metrics[field]) is not type(value)
    try:
        validated = EvaluationResult.model_validate(payload)
    except ValidationError:
        return
    assert canonical_dump(validated) == canonical_dump(genuine)


@pytest.mark.parametrize("mutated", (False, True), ids=("genuine", "true_to_int"))
def test_mixed_module_load_validation_preserves_types(mutated):
    script = textwrap.dedent(
        """
        import importlib
        import sys
        from pydantic import ValidationError
        from engine.service import ReadinessService

        cached = ReadinessService()
        request = cached.get_demo_case_request("MRI-01-complete")
        baseline = cached.evaluate(request)
        for name in list(sys.modules):
            if name == "engine" or name.startswith("engine."):
                del sys.modules[name]
        current = importlib.import_module("engine.service")
        equal_values = current.EvaluationMetrics(**baseline.metrics.model_dump())
        assert type(baseline.metrics) is not type(equal_values)
        assert baseline.metrics != equal_values
        result = cached.evaluate(request)
        payload = result.model_dump(mode="json")
        if sys.argv[1] == "False":
            assert current.EvaluationResult.model_validate(payload).overall_status == result.overall_status
        else:
            changed = 0
            for results in (payload["results"], payload["report"]["results"]):
                for item in results:
                    if item["fact_value"] is True:
                        item["fact_value"] = 1
                        changed += 1
            assert changed > 0
            try:
                current.EvaluationResult.model_validate(payload)
            except ValidationError as exc:
                assert "Requirement result does not match evaluation of effective facts" in str(exc)
            else:
                raise AssertionError("Mixed module loads must not relax value types")
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, str(mutated)],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize(
    "record_name", (*RECORDS, "MRI-01-complete", "MRI-08-edge-below-threshold", "CPAP-02-borderline", "MRI-KNEE-01-ready")
)
def test_genuine_golden_records_validate_and_archive(tmp_path, record_name):
    genuine = golden_record(record_name)
    assert canonical_dump(EvaluationResult.model_validate_json(genuine.model_dump_json())) == canonical_dump(genuine)
    with DecisionStore(tmp_path / "golden.sqlite") as store:
        store.record(genuine, "genuine")
        assert canonical_dump(store.get_decision("genuine")) == canonical_dump(genuine)


@pytest.mark.parametrize("version", ("1.5.0", "unversioned-v15", "1.4.0", "unversioned-legacy"))
def test_genuine_historical_records_remain_readable(tmp_path, version):
    payload = json.loads((ROOT / "test/fixtures/v1.5/MRI-01-complete.json").read_text())
    payload.pop("letter", None)
    historical = EvaluationResultV15.model_validate(payload)
    if version in {"1.4.0", "unversioned-legacy"}:
        payload["schema_version"] = "1.4.0"
        payload.pop("engine_version", None)
        for container in (payload["request"], payload["audit_trail"], payload["report"]["audit_trail"]):
            container.pop("fact_verifications", None)
        for results in (payload["results"], payload["report"]["results"]):
            for result in results:
                result.pop("verification", None)
                result.pop("verification_fingerprint", None)
    if version.startswith("unversioned"):
        payload.pop("schema_version", None)
    expected = validate_archived_evaluation(payload)
    with DecisionStore(tmp_path / "historical.sqlite") as store:
        insert_at_rest(store, historical.policy_version, payload)
        assert canonical_dump(store.get_decision("at-rest")) == canonical_dump(expected)


@pytest.mark.parametrize("left,right", ((True, 1), (True, 1.0), (False, 0), (8, 8.0)))
def test_canonical_dump_distinguishes_equal_python_scalars(left, right):
    assert left == right
    assert canonical_dump(left) != canonical_dump(right)


def test_canonical_dump_recurses_through_duck_typed_models_and_containers():
    class Duck:
        def model_dump(self, *, mode):
            assert mode == "json"
            return {"value": (True, {"count": 8})}

    class MappingWithMarker(dict):
        model_dump = None

    actual = canonical_dump(MappingWithMarker(z=[Duck()], a=(False,)))
    assert actual == '{"a":[false],"z":[{"value":[true,{"count":8}]}]}'


@pytest.mark.parametrize("value", (float("nan"), float("inf"), -float("inf")))
def test_canonical_dump_rejects_nonfinite_values(value):
    with pytest.raises(ValueError, match="Out of range float values"):
        canonical_dump({"nested": [(value,)]})
