import json
from copy import deepcopy

import pytest
from pydantic import ValidationError
from verification_helpers import attest

from cli import main
from engine.decision_store import DecisionStore
from engine.policies import canonical_json, content_hash
from engine.replay import replay_decision
from engine.schemas import EvaluationResult, LegacyEvaluationRecord, PARequest
from engine.service import ReadinessService


@pytest.fixture
def proposal():
    service = ReadinessService()
    return service.evaluate(service.get_demo_case_request("MRI-01-complete"))


def set_status(payload, status, readiness):
    for copy in (payload, payload["audit_trail"], payload["report"]["audit_trail"]):
        copy.update(overall_status=status, submission_readiness=readiness)


def insert_historical(store, proposal, payload):
    """Simulate a preexisting archive without going through today's strict writer."""
    store.add_policy(proposal.policy_version)
    store.connection.execute(
        "INSERT INTO decisions VALUES (?, ?, ?, ?, ?)",
        (
            "historical",
            proposal.policy_version.policy_id,
            proposal.policy_version.version_id,
            canonical_json(payload),
            content_hash({"decision_id": "historical", "evaluation": payload}),
        ),
    )
    store.connection.commit()


def test_exact_audit_forgery_rejected_by_schema_and_archive_writer(tmp_path, proposal):
    payload = proposal.model_dump(mode="json")
    set_status(payload, "READY", True)
    assert len(payload["results"]) == 4
    assert all(result["verification"]["state"] == "UNVERIFIED" for result in payload["results"])
    with pytest.raises(ValidationError, match="READY requires"):
        EvaluationResult.model_validate(payload)
    # Mutable model copies bypass schema validation; the archive must revalidate.
    forged = proposal.model_copy(deep=True)
    forged.overall_status = "READY"
    forged.submission_readiness = True
    forged.audit_trail.overall_status = "READY"
    forged.audit_trail.submission_readiness = True
    forged.report.audit_trail.update(overall_status="READY", submission_readiness=True)
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        with pytest.raises(ValidationError, match="READY requires"):
            store.record(forged)
        assert store.decision_ids() == []
        assert store.list_policies() == []


@pytest.mark.parametrize("version", ["1.5.0", "1.10.0", "2.0.0", None])
def test_modern_archive_reads_reject_forgery(tmp_path, proposal, version):
    payload = proposal.model_dump(mode="json")
    if version is None:
        payload.pop("schema_version")  # Existing unversioned v1.5 records stay strict.
    else:
        payload["schema_version"] = version
    set_status(payload, "READY", True)
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        insert_historical(store, proposal, payload)
        with pytest.raises(ValidationError, match="READY requires"):
            store.get_decision("historical")


@pytest.mark.parametrize("mode", ["empty", "omitted", "failed", "partial"])
def test_ready_requires_complete_passing_verified_requirements(proposal, mode):
    service = ReadinessService()
    payload = service.evaluate(attest(proposal)).model_dump(mode="json")
    if mode == "empty":
        payload["results"] = []
    elif mode == "omitted":
        payload["results"].pop()
    elif mode == "failed":
        payload["results"][0]["status"] = "NOT_MET"
    else:
        key = payload["results"][0]["key"]
        payload["results"][0]["verification"] = {"state": "UNVERIFIED"}
        payload["request"]["fact_verifications"].pop(key)
        for audit in (payload["audit_trail"], payload["report"]["audit_trail"]):
            audit["fact_verifications"][key] = {"state": "UNVERIFIED"}
    payload["report"]["results"] = deepcopy(payload["results"])
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(payload)


@pytest.mark.parametrize("copy", ["audit_trail", "report_audit", "request", "report_results"])
def test_status_and_verification_copies_must_agree(proposal, copy):
    payload = proposal.model_dump(mode="json")
    if copy == "audit_trail":
        payload[copy]["overall_status"] = "READY"
    elif copy == "report_audit":
        payload["report"]["audit_trail"]["submission_readiness"] = True
    elif copy == "request":
        service = ReadinessService()
        payload["request"] = attest(proposal).model_dump(mode="json")
        assert service.evaluate(PARequest.model_validate(payload["request"])).overall_status == "READY"
    else:
        payload["report"]["results"][0]["status"] = "NOT_MET"
    with pytest.raises(ValidationError, match="disagree"):
        EvaluationResult.model_validate(payload)


def test_submission_readiness_requires_ready_and_verified_policy(proposal):
    payload = proposal.model_dump(mode="json")
    set_status(payload, "PENDING_VERIFICATION", True)
    with pytest.raises(ValidationError, match="submission_readiness requires"):
        EvaluationResult.model_validate(payload)
    service = ReadinessService()
    demo = service.evaluate(service.get_demo_case_request("CPAP-01-complete"))
    payload = service.evaluate(attest(demo)).model_dump(mode="json")
    set_status(payload, "READY", True)
    with pytest.raises(ValidationError, match="verified policy trust"):
        EvaluationResult.model_validate(payload)


def test_borrowed_date_verified_ready_without_submission_readiness_roundtrips(tmp_path):
    service = ReadinessService()
    proposal = service.evaluate(
        PARequest(
            payer="Aetna",
            procedure_code="CPAP_DEVICE",
            note_text="OSA. Visit date 2024-05-18. Sleep study date not recorded. AHI 22.",
        )
    )
    # Deliberately incorrect test attestations preserve the known extraction error.
    result = service.evaluate(attest(proposal))
    assert result.overall_status == "READY"
    assert result.submission_readiness is False
    assert result.policy_trust_level == "demo"
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        store.record(result, "borrowed-date")
        assert store.get_decision("borrowed-date") == result


@pytest.mark.parametrize("version", ["1.4.0", None])
def test_legacy_v14_record_loads_flagged_without_migration(tmp_path, proposal, version, capsys):
    payload = proposal.model_dump(mode="json")
    if version is None:
        payload.pop("schema_version")
    else:
        payload["schema_version"] = version
    set_status(payload, "READY", True)
    # v1.4-style records lack the later verification and replay fields.
    payload.pop("policy_version")
    payload.pop("captured_fact_states")
    payload["request"].pop("fact_verifications")
    for results in (payload["results"], payload["report"]["results"]):
        for result in results:
            result.pop("verification")
            result.pop("verification_fingerprint")
    for audit in (payload["audit_trail"], payload["report"]["audit_trail"]):
        audit.pop("fact_verifications")
        audit.pop("policy_version")
    path = tmp_path / "archive.sqlite"
    with DecisionStore(path) as store:
        insert_historical(store, proposal, payload)
    before = path.read_bytes()
    with DecisionStore(path, readonly=True) as store:
        legacy = store.get_decision("historical")
        assert isinstance(legacy, LegacyEvaluationRecord)
        assert legacy.legacy_record is True
        assert legacy.payload == payload
        with pytest.raises(ValueError, match="Legacy records"):
            replay_decision(legacy, proposal.policy_version)
    assert main(["decision-show", "--store", str(path), "--decision-id", "historical"]) == 0
    assert json.loads(capsys.readouterr().out) == {"legacy_record": True, "payload": payload}
    assert path.read_bytes() == before
    with DecisionStore(path) as store:
        with pytest.raises(ValueError, match="Legacy records"):
            store.record(legacy, "copy")


def test_legacy_version_cannot_relax_new_writes(tmp_path, proposal):
    forged = proposal.model_copy(update={"schema_version": "1.4.0", "overall_status": "READY", "submission_readiness": True})
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        with pytest.raises(ValidationError, match="READY requires"):
            store.record(forged)
        with pytest.raises(ValueError, match="version >= 1.5.0"):
            store.record(proposal.model_copy(update={"schema_version": "1.4.0"}))


def test_current_and_unversioned_valid_records_load_strictly(tmp_path, proposal):
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        store.record(proposal, "current")
        assert store.get_decision("current") == proposal
        payload = proposal.model_dump(mode="json")
        payload.pop("schema_version")
        insert_historical(store, proposal, payload)
        assert store.get_decision("historical") == proposal


@pytest.mark.parametrize("version", ["invalid", "1.5", "1.x.0"])
def test_invalid_archive_version_fails_closed(tmp_path, proposal, version):
    payload = proposal.model_dump(mode="json") | {"schema_version": version}
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        insert_historical(store, proposal, payload)
        with pytest.raises(ValueError, match="Invalid archived"):
            store.get_decision("historical")


@pytest.mark.parametrize("schema_version", ["1.4.0", None])
def test_modern_engine_version_keeps_reads_strict(tmp_path, proposal, schema_version):
    payload = proposal.model_dump(mode="json") | {"engine_version": "1.5.0"}
    if schema_version is None:
        payload.pop("schema_version")
    else:
        payload["schema_version"] = schema_version
    set_status(payload, "READY", True)
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        insert_historical(store, proposal, payload)
        with pytest.raises(ValidationError, match="READY requires"):
            store.get_decision("historical")


@pytest.mark.parametrize("copy", ["audit_trail", "report_audit", "proposal_fingerprint"])
def test_verified_fact_metadata_must_agree(proposal, copy):
    payload = ReadinessService().evaluate(attest(proposal)).model_dump(mode="json")
    key = payload["results"][0]["key"]
    if copy == "proposal_fingerprint":
        payload["results"][0]["verification_fingerprint"] = "f" * 64
        payload["report"]["results"] = deepcopy(payload["results"])
    else:
        audit = payload["audit_trail"] if copy == "audit_trail" else payload["report"]["audit_trail"]
        audit["fact_verifications"][key] = {"state": "UNVERIFIED"}
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(payload)
