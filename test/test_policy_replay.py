import json
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError
from verification_helpers import attest

from cli import main
from engine.decision_store import DecisionStore
from engine.policies import create_policy
from engine.replay import replay, replay_decision
from engine.schemas import PARequest, PolicyVersion
from engine.service import InvalidRequestError, ReadinessService, UnsupportedScopeError
from scripts.replay_demo import INPUT_ROOT


@pytest.fixture(scope="module")
def policies():
    return {
        version: PolicyVersion.model_validate_json((INPUT_ROOT / "policies" / f"{version}.json").read_text())
        for version in ("v1", "v2", "v3")
    }


@pytest.fixture(scope="module")
def history(policies):
    service = ReadinessService()
    cases = json.loads((INPUT_ROOT / "cases.json").read_text())
    return {
        version: {case["id"]: service.evaluate(PARequest.model_validate(case["request"]), policy) for case in cases}
        for version, policy in policies.items()
    }


def revised(policy, **changes):
    fields = policy.content()
    fields["requirements"] = policy.requirements
    fields.pop("criteria_json")
    return create_policy(**(fields | changes))


def test_policy_is_deeply_immutable_and_roundtrips(policies):
    policy = policies["v1"]
    with pytest.raises(ValidationError):
        policy.version_id = "replacement"
    requirements = policy.requirements
    requirements[0]["min"] = 999
    assert policy.requirements[0]["min"] == 6
    assert PolicyVersion.model_validate_json(policy.model_dump_json()) == policy
    assert len(policy.content_hash) == 64


@pytest.mark.parametrize(
    "change",
    [
        {"effective_date": "2027-01-01"},
        {"payer": "Another payer"},
        {"version_id": "v99"},
        {"supported_sites": ["office"]},
    ],
)
def test_hash_binds_identity_scope_and_effective_date(policies, change):
    assert revised(policies["v1"], **change).content_hash != policies["v1"].content_hash


def test_policy_rejects_tampered_hash(policies):
    with pytest.raises(ValidationError, match="hash mismatch"):
        PolicyVersion.model_validate(policies["v1"].model_dump() | {"effective_date": "2027-01-01"})


@pytest.mark.parametrize("operation", ["evaluate", "replay"])
def test_execution_revalidates_unchecked_model_copies(policies, history, operation):
    target = policies["v1"].model_copy(update={"version_id": "unhashed-change"})
    with pytest.raises(ValueError, match="hash mismatch"):
        if operation == "replay":
            replay_decision(history["v1"]["C03"], target)
        else:
            ReadinessService().evaluate(history["v1"]["C03"].request, target)


def test_new_operator_cannot_reinterpret_captured_boolean_as_number(policies, history):
    requirements = policies["v2"].requirements
    requirement = next(item for item in requirements if item["key"] == "neuro_red_flags_documented")
    requirement.update(type="number", operator="minimum", min=0)
    target = revised(policies["v2"], version_id="changed-evidence-type", requirements=requirements)
    report = replay_decision(history["v2"]["C03"], target)
    assert report["overall_status"] == "NEEDS_REVIEW"
    assert report["incompatible_captured_evidence"] == ["neuro_red_flags_documented"]
    current = ReadinessService().evaluate(history["v2"]["C03"].request, target)
    assert current.overall_status == "NEEDS_REVIEW"
    assert current.facts["neuro_red_flags_documented"] is True
    assert replay_decision(current, target)["category"] == "UNCHANGED"


@pytest.mark.parametrize("mode", ["empty", "duplicate", "operator", "nonfinite", "blank_key"])
def test_invalid_policy_fails_closed(policies, mode):
    requirements = policies["v1"].requirements
    if mode == "empty":
        requirements = []
    elif mode == "duplicate":
        requirements.append(deepcopy(requirements[0]))
    elif mode == "operator":
        requirements[0]["operator"] = "llm_judgment"
    elif mode == "nonfinite":
        requirements[0]["min"] = float("nan")
    else:
        requirements[0]["key"] = " "
    with pytest.raises(ValueError):
        revised(policies["v1"], requirements=requirements)


def test_policy_registration_is_idempotent_but_never_replaces(tmp_path, policies):
    with DecisionStore(tmp_path / "store.sqlite") as store:
        store.add_policy(policies["v1"])
        store.add_policy(policies["v1"])
        with pytest.raises(ValueError, match="different content"):
            store.add_policy(revised(policies["v1"], effective_date="2027-01-01"))
        store.add_policy(policies["v2"])
        assert len(store.list_policies()) == 2
        assert store.get_policy(policies["v1"].policy_id, "v1") == policies["v1"]


@pytest.mark.parametrize(
    "table,operation", [(table, operation) for table in ("policies", "decisions") for operation in ("UPDATE", "DELETE", "REPLACE")]
)
def test_database_enforces_append_only(tmp_path, history, table, operation):
    with DecisionStore(tmp_path / "store.sqlite") as store:
        store.record(history["v1"]["C01"], "original")
        if operation == "UPDATE":
            sql = f"UPDATE {table} SET payload = '{{}}'"
        elif operation == "DELETE":
            sql = f"DELETE FROM {table}"
        else:
            sql = f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"
        with pytest.raises(sqlite3.IntegrityError):
            store.connection.execute(sql)
        assert store.get_decision("original") == history["v1"]["C01"]


def test_archive_roundtrip_independent_of_mutable_callers(tmp_path, history):
    original = history["v1"]["C01"].model_copy(deep=True)
    with DecisionStore(tmp_path / "store.sqlite") as store:
        store.record(original, "original")
        original.facts["conservative_therapy_weeks"] = 99
        loaded = store.get_decision("original")
        assert loaded.facts["conservative_therapy_weeks"] == 6
        loaded.results.clear()
        assert store.get_decision("original").results
        with pytest.raises(sqlite3.IntegrityError):
            store.record(original, "original")


@pytest.mark.parametrize(
    "source,target,case,category",
    [
        ("v1", "v2", "C01", "OUTCOME_CHANGED"),
        ("v1", "v2", "C06", "BECAME_UNDETERMINABLE"),
        ("v1", "v2", "C03", "REASONING_CHANGED"),
        ("v1", "v1", "C03", "UNCHANGED"),
        ("v2", "v3", "C09", "OUTCOME_CHANGED"),
        ("v2", "v3", "C10", "REFUSAL_RESOLVED"),
        ("v2", "v3", "C12", "REFUSAL_RESOLVED"),
        ("v3", "v2", "C12", "BECAME_REVIEW_REQUIRED"),
    ],
)
def test_each_differential_category(policies, history, source, target, case, category):
    report = replay_decision(history[source][case], policies[target])
    assert report["category"] == category
    assert report["submission_readiness"] is False
    assert report["human_review_required"] is True
    assert report["overall_status"] != "READY"


def test_flip_names_specific_threshold_and_values(policies, history):
    report = replay_decision(history["v1"]["C01"], policies["v2"])
    assert report["outcome_driving_criteria"] == ["conservative_therapy_weeks"]
    change = next(item for item in report["criterion_differences"] if item["criterion"] == "conservative_therapy_weeks")
    assert change["before"]["status"] == "MET"
    assert change["before"]["definition"]["min"] == 6
    assert change["after"]["status"] == "NOT_MET"
    assert change["after"]["definition"]["min"] == 8
    assert "(6)" in change["after"]["reason"]


@pytest.mark.parametrize("case", ["C06", "C07", "C08"])
def test_missing_new_evidence_is_refusal_even_with_threshold_failure(policies, history, case):
    report = replay_decision(history["v1"][case], policies["v2"])
    assert report["category"] == "BECAME_UNDETERMINABLE"
    assert report["overall_status"] == "CANNOT_DETERMINE"
    assert report["newly_required_missing_evidence"] == ["neuro_red_flags_documented"]
    assert report["outcome_driving_criteria"] == ["neuro_red_flags_documented"]
    if case != "C06":
        assert next(item for item in report["results"] if item["key"] == "conservative_therapy_weeks")["status"] == "NOT_MET"


@pytest.mark.parametrize("version", ["v1", "v2", "v3"])
@pytest.mark.parametrize("case,status", [("C11", "CANNOT_DETERMINE"), ("C13", "NEEDS_REVIEW")])
def test_missing_and_ambiguous_original_evidence_survives(policies, history, version, case, status):
    report = replay_decision(history["v1"][case], policies[version])
    assert report["overall_status"] == status
    assert report["refusal_preserved"] is True
    assert "__REVIEW_REQUIRED__" not in json.dumps(report)


def test_removed_criterion_can_resolve_refusal_without_manufacturing_readiness(policies, history):
    original = history["v2"]["C10"]
    report = replay_decision(original, policies["v3"])
    assert original.overall_status == "CANNOT_DETERMINE"
    assert report["category"] == "REFUSAL_RESOLVED"
    assert report["overall_status"] == "PENDING_VERIFICATION"
    assert report["criterion_differences"][0]["criterion"] == "prior_imaging_result"
    assert report["criterion_differences"][0]["change"] == "REMOVED"


def test_replay_never_reextracts_or_loads_current_rules(policies, history, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Replay must use the archived evidence and target snapshot only")

    monkeypatch.setattr("engine.service.extract_facts", forbidden)
    monkeypatch.setattr("engine.extract.extract_facts", forbidden)
    monkeypatch.setattr("engine.service.load_rules", forbidden)
    original = history["v1"]["C03"].model_copy(deep=True)
    # Even a value spelled out in the old note is unavailable unless captured at decision time.
    original.captured_fact_states.pop("neuro_red_flags_documented")
    assert replay_decision(original, policies["v2"])["overall_status"] == "CANNOT_DETERMINE"


def test_new_unextractable_fact_refuses(policies, history):
    requirements = policies["v1"].requirements + [
        {
            "key": "specialist_followup_date_documented",
            "label": "Specialist follow-up date documented",
            "type": "boolean",
            "operator": "documented",
        }
    ]
    target = revised(policies["v1"], version_id="v4", requirements=requirements)
    report = replay_decision(history["v1"]["C03"], target)
    assert report["category"] == "BECAME_UNDETERMINABLE"
    assert report["missing_evidence"] == ["specialist_followup_date_documented"]


def test_ambiguity_captured_outside_old_requirements_is_not_lost(policies, history):
    source = revised(
        policies["v1"],
        version_id="before-symptom-requirement",
        requirements=[item for item in policies["v1"].requirements if item["key"] != "symptom_duration_weeks"],
    )
    original = ReadinessService().evaluate(history["v1"]["C13"].request, source)
    assert original.overall_status == "PENDING_VERIFICATION"
    assert original.facts["symptom_duration_weeks"] is None
    assert original.captured_fact_states["symptom_duration_weeks"] == "NEEDS_REVIEW"
    report = replay_decision(original, policies["v1"])
    assert report["category"] == "BECAME_REVIEW_REQUIRED"
    assert report["overall_status"] == "NEEDS_REVIEW"


def test_changed_failure_to_met_is_never_automatically_ready(policies, history):
    original = ReadinessService().evaluate(attest(history["v2"]["C09"]), policies["v2"])
    assert original.overall_status == "NOT_READY"
    assert all(item.verification.state == "HUMAN_VERIFIED" for item in original.results)
    report = replay_decision(original, policies["v3"])
    assert report["category"] == "OUTCOME_CHANGED"
    assert report["outcome_driving_criteria"] == ["prior_imaging_result"]
    assert report["overall_status"] == "PENDING_VERIFICATION"
    assert report["submission_readiness"] is False


@pytest.mark.parametrize("version", ["v1", "v2", "v3"])
def test_ready_history_requires_fresh_verification_even_on_same_version(policies, history, version):
    original = ReadinessService().evaluate(attest(history["v1"]["C03"]), policies["v1"])
    assert original.overall_status == "READY"
    report = replay_decision(original, policies[version])
    assert report["category"] == ("UNCHANGED" if version == "v1" else "REASONING_CHANGED")
    assert report["original_overall_status"] == "READY"
    assert report["original_criteria_outcome"] == report["target_criteria_outcome"] == "CRITERIA_MET"
    assert report["overall_status"] == "PENDING_VERIFICATION"
    assert all(item["verification"]["state"] == "UNVERIFIED" for item in report["results"])


def test_stale_verification_rejected_for_new_policy_identity(policies, history):
    same_criteria_new_version = revised(policies["v1"], version_id="v1-reissued")
    with pytest.raises(InvalidRequestError, match="Stale or mismatched"):
        ReadinessService().evaluate(attest(history["v1"]["C03"]), same_criteria_new_version)


def test_policy_scope_mismatch_rejected(policies, history):
    target = revised(policies["v1"], procedure_code="CPAP_DEVICE")
    with pytest.raises(ValueError, match="same policy family"):
        replay_decision(history["v1"]["C03"], target)
    with pytest.raises(UnsupportedScopeError):
        ReadinessService().evaluate(history["v1"]["C03"].request, target)


def test_replay_is_deterministic_read_only_with_correct_denominators(tmp_path, policies, history):
    path = tmp_path / "store.sqlite"
    with DecisionStore(path) as store:
        for case, result in history["v1"].items():
            store.record(result, case)
        store.add_policy(policies["v2"])
    before = path.read_bytes()
    with DecisionStore(path, readonly=True) as store:
        ids = store.decision_ids()
        report = replay(store, ids, policies["v2"])
        assert replay(store, list(reversed(ids)), policies["v2"]) == report
        assert report["total_decisions"] == 14
        assert {key: value["count"] for key, value in report["categories"].items()} == {
            "OUTCOME_CHANGED": 2,
            "BECAME_UNDETERMINABLE": 3,
            "REASONING_CHANGED": 9,
            "UNCHANGED": 0,
            "BECAME_REVIEW_REQUIRED": 0,
            "REFUSAL_RESOLVED": 0,
        }
        assert all(value["denominator"] == 14 for value in report["categories"].values())
        assert sum(value["count"] for value in report["categories"].values()) == 14
        assert report["refusals_preserved"] == {"count": 4, "denominator": 4}
        with pytest.raises(ValueError, match="Duplicate"):
            replay(store, [ids[0], ids[0]], policies["v2"])
        with pytest.raises(ValueError, match="Unknown historical"):
            replay(store, ["not-found"], policies["v2"])
        empty = replay(store, [], policies["v2"])
        assert empty["total_decisions"] == 0
        assert all(value == {"count": 0, "denominator": 0} for value in empty["categories"].values())
    assert path.read_bytes() == before


def test_cli_archive_and_replay_workflow(tmp_path, policies, history, capsys, monkeypatch):
    path = str(tmp_path / "archive.sqlite")
    for version in policies:
        assert main(["policy-add", "--store", path, "--file", str(INPUT_ROOT / "policies" / f"{version}.json")]) == 0
        capsys.readouterr()
    assert main(["policy-list", "--store", path]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 3
    request = tmp_path / "request.json"
    request.write_text(history["v1"]["C06"].request.model_dump_json())
    assert (
        main(
            [
                "evaluate",
                "--request-file",
                str(request),
                "--store",
                path,
                "--policy-id",
                "synthetic-cervical-mri",
                "--policy-version",
                "v1",
                "--decision-id",
                "case-6",
                "--json",
            ]
        )
        == 0
    )
    original = json.loads(capsys.readouterr().out)
    assert original["policy_version"]["version_id"] == "v1"
    # Archive commands remain usable even if the current runtime bundle is unavailable.
    monkeypatch.setenv("PA_COPILOT_RULES_PATH", str(tmp_path / "missing-runtime-rules.yaml"))
    args = ["replay", "--store", path, "--policy-id", "synthetic-cervical-mri", "--target-version", "v2", "--from-version", "v1"]
    before = Path(path).read_bytes()
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["categories"]["BECAME_UNDETERMINABLE"] == {"count": 1, "denominator": 1}
    assert main(args + ["--output", path]) == 2
    assert "File exists" in capsys.readouterr().err
    assert Path(path).read_bytes() == before
    assert main(["decision-show", "--store", path, "--decision-id", "case-6"]) == 0
    assert json.loads(capsys.readouterr().out) == original


def test_runtime_evaluations_include_sealed_policy_snapshot():
    service = ReadinessService()
    result = service.evaluate(service.get_demo_case_request("MRI-01-complete"))
    assert result.policy_version == result.audit_trail.policy_version
    assert result.policy_version.procedure_code == "MRI_LUMBAR"
    assert result.policy_version.requirements == [item.model_dump(exclude_none=True) for item in result.supported_procedure.requirements]
    assert str(result.policy_version.effective_date) == "2026-08-22"


def test_archive_detects_decision_corruption(tmp_path, history):
    with DecisionStore(tmp_path / "store.sqlite") as store:
        store.record(history["v1"]["C03"], "original")
        # Simulate corruption outside the supported API; hash validation still fails closed.
        store.connection.execute("DROP TRIGGER decisions_no_update")
        store.connection.execute("UPDATE decisions SET content_hash = ?", ("0" * 64,))
        with pytest.raises(ValueError, match="content hash mismatch"):
            store.get_decision("original")
