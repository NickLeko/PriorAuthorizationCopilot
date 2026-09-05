import ast
import json
import re
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest
from verification_helpers import attest

import api
import engine.service as service_module
from cli import main
from engine.config import load_app_config
from engine.evaluate import compute_overall_status
from engine.extract import extract_facts
from engine.schemas import EvidenceSpan, FactVerification, PARequest, RequirementResult
from engine.service import GovernanceConfigError, InvalidRequestError, ReadinessService

CONTRACT = Path("EXTRACTION_CONTRACT.md").read_text()
EXAMPLES = json.loads(re.search(r"```json\n(.*?)\n```", CONTRACT, re.S).group(1))


def copied_service(tmp_path):
    for name in ("rules", "rulebook", "policy_snapshots", "inputs"):
        shutil.copytree(Path(name), tmp_path / name)
    return ReadinessService(load_app_config(tmp_path))


def assert_spans(note, mapping):
    for spans in mapping.values():
        for span in spans:
            data = span if isinstance(span, dict) else span.model_dump()
            assert 0 <= data["start"] < data["end"] <= len(note)
            assert data["text"] == note[data["start"] : data["end"]]


class TestExtractionContractAlignment:
    """Every numbered contract guarantee and every published example executes here."""

    def test_claim_inventory(self):
        claims = set(re.findall(r"\*\*(G\d+)\*\*", CONTRACT))
        covered = {name.split("_")[1] for name in dir(self) if name.startswith("test_G")}
        assert claims == covered == {f"G{i:02d}" for i in range(1, 8)}
        assert EXAMPLES[0]["id"] == "negation_first"
        fields = set(extract_facts("")[0])
        assert fields == {key for example in EXAMPLES for key in example["expected"]}

    @pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example["id"])
    def test_G01_exact_examples_and_determinism(self, example):
        note = example["note"]
        facts, evidence = extract_facts(note)
        assert (facts, evidence) == extract_facts(note)
        assert {key: facts[key] for key in example["expected"]} == example["expected"]
        assert_spans(note, evidence)
        if "procedure" in example:
            result = ReadinessService().evaluate(PARequest(payer="Aetna", procedure_code=example["procedure"], note_text=note))
            assert result.overall_status == example["status"]
            assert result.submission_readiness is False
            assert_spans(note, result.evidence_map)
            for requirement in result.results:
                assert_spans(note, {requirement.key: requirement.evidence_spans})

    def test_G01_no_language_model_or_nlp_dependency(self):
        tree = ast.parse(Path("engine/extract.py").read_text())
        imports = {
            node.module if isinstance(node, ast.ImportFrom) else alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in (node.names if isinstance(node, ast.Import) else [None])
        }
        assert imports <= {"__future__", "re", "dataclasses", "typing", "schemas"}

    @pytest.mark.parametrize("prefix", ["İ", "İİİ", "😀İ\n", "É\tİ\n", "ΟΣ İ "])
    def test_G02_unicode_offsets_and_literal_citations(self, prefix):
        note = prefix + " OSA. Sleep study completed 2024-05-18. AHI 22."
        result = ReadinessService().evaluate(PARequest(payer="Aetna", procedure_code="CPAP_DEVICE", note_text=note))
        assert_spans(note, result.evidence_map)
        assert result.evidence_map["osa_diagnosis"][0].text == "OSA"
        assert result.evidence_map["osa_diagnosis"][0].start == note.index("OSA")
        assert result.evidence_map["ahi_documented"][0].text == "AHI 22"
        assert EvidenceSpan(start=0, end=3, text=" x ").text == " x "

    def test_G03_defaults_partial_and_complete_attestations(self):
        service = ReadinessService()
        proposal = service.evaluate(service.get_demo_case_request("MRI-01-complete"))
        assert proposal.overall_status == "PENDING_VERIFICATION"
        for result in proposal.results:
            assert result.fact_value == proposal.facts[result.key]
            assert result.verification == FactVerification()
            assert len(result.verification_fingerprint) == 64
        partial = service.evaluate(attest(proposal, [proposal.results[0].key]))
        assert partial.overall_status == "PENDING_VERIFICATION"
        assert partial.submission_readiness is False
        verified = service.evaluate(attest(proposal))
        assert verified.overall_status == "READY"
        assert verified.submission_readiness is True
        for result in verified.results:
            assert result.verification.state == "HUMAN_VERIFIED"
            assert result.verification.reviewer == "Synthetic test reviewer"
            assert result.verification.verified_at.tzinfo is not None
            assert verified.audit_trail.fact_verifications[result.key] == result.verification

        reverted = service.evaluate(attest(verified, []))
        assert reverted.overall_status == "PENDING_VERIFICATION"
        assert all(result.verification == FactVerification() for result in reverted.results)

    def test_G02_unicode_prefix_across_entire_corpus(self):
        for case in json.loads(Path("inputs/synthetic_cases.json").read_text()):
            note = case["note_text"]
            expected, _ = extract_facts(note)
            prefixed = "İİ. " + note
            actual, spans = extract_facts(prefixed)
            assert actual == expected, case["id"]
            assert_spans(prefixed, spans)

    @pytest.mark.parametrize(
        "mutation",
        [
            {"reviewer": " "},
            {"verified_at": None},
            {"verified_at": "2026-01-01T00:00:00"},
            {"verified_at": "2099-01-01T00:00:00Z"},
            {"fingerprint": None},
            {"state": "UNVERIFIED"},
            {"value": True},
            {"state": "VERIFIED"},
        ],
    )
    def test_G03_invalid_attestations_rejected(self, mutation):
        record = {"state": "HUMAN_VERIFIED", "reviewer": "Reviewer", "verified_at": "2026-01-01T00:00:00Z", "fingerprint": "a" * 64}
        with pytest.raises(ValidationError):
            FactVerification.model_validate(record | mutation)

    @pytest.mark.parametrize(
        "statuses, expected",
        [
            ([], "CANNOT_DETERMINE"),
            (["MET"], "PENDING_VERIFICATION"),
            (["MET", "NOT_MET"], "NOT_READY"),
            (["NOT_MET", "NEEDS_REVIEW"], "NEEDS_REVIEW"),
            (["NOT_MET", "NEEDS_REVIEW", "NOT_DOCUMENTED"], "CANNOT_DETERMINE"),
        ],
    )
    def test_G04_precedence_unchanged(self, statuses, expected):
        results = [RequirementResult(key=str(i), label="criterion", reason="test", status=status) for i, status in enumerate(statuses)]
        assert compute_overall_status(results) == {"overall_status": expected, "submission_readiness": False}
        for result in results:
            result.verification = FactVerification(
                state="HUMAN_VERIFIED", reviewer="Reviewer", verified_at="2026-01-01T00:00:00Z", fingerprint="a" * 64
            )
        if expected == "PENDING_VERIFICATION":
            assert compute_overall_status(results) == {"overall_status": "READY", "submission_readiness": True}
        else:
            assert compute_overall_status(results) == {"overall_status": expected, "submission_readiness": False}

    @pytest.mark.parametrize("field,value", [("note_text", "Changed note."), ("dx_codes", ["OTHER"]), ("specialty", "Changed")])
    def test_G05_changed_request_invalidates_attestations(self, field, value):
        service = ReadinessService()
        request = attest(service.evaluate(service.get_demo_case_request("MRI-01-complete")))
        with pytest.raises(InvalidRequestError, match="Stale or mismatched"):
            service.evaluate(PARequest.model_validate(request.model_dump() | {field: value}))

    def test_G05_unknown_and_wrong_fingerprints_rejected(self):
        service = ReadinessService()
        request = attest(service.evaluate(service.get_demo_case_request("MRI-01-complete")))
        record = next(iter(request.fact_verifications.values()))
        with pytest.raises(InvalidRequestError, match="Unknown verification"):
            service.evaluate(request.model_copy(update={"fact_verifications": {"unknown": record}}))
        payload = request.model_dump(mode="json")
        next(iter(payload["fact_verifications"].values()))["fingerprint"] = "f" * 64
        with pytest.raises(InvalidRequestError, match="Stale or mismatched"):
            service.evaluate(PARequest.model_validate(payload))

    def test_G06_review_marker_public_null_with_spans(self):
        service = ReadinessService()
        note = (
            "Low back pain with suspected radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with minimal improvement."
        )
        result = service.evaluate(PARequest(payer="Aetna", procedure_code="MRI_LUMBAR", note_text=note))
        assert result.overall_status == "NEEDS_REVIEW"
        assert result.facts["back_pain_with_radiculopathy"] is None
        requirement = result.results[0]
        assert requirement.fact_value is None
        assert requirement.status == "NEEDS_REVIEW"
        assert requirement.evidence_spans
        assert "__REVIEW_REQUIRED__" not in result.model_dump_json()
        verified = service.evaluate(attest(result))
        assert verified.overall_status == "NEEDS_REVIEW"
        assert [r.status for r in verified.results] == [r.status for r in result.results]

    @pytest.mark.parametrize("mode", ["demo", "stale", "invalid_rulebook", "unknown_frequency"])
    def test_G07_verification_cannot_bypass_policy_trust(self, tmp_path, mode):
        service = copied_service(tmp_path)
        case = "MRI-01-complete"
        if mode == "demo":
            case = "CPAP-01-complete"
        elif mode in {"stale", "unknown_frequency"}:
            path = service.config.snapshot_root / "aetna_mri_lumbar/latest.json"
            snapshot = json.loads(path.read_text())
            snapshot["last_checked_utc"] = "2020-01-01T00:00:00Z"
            snapshot["fetched_at_utc"] = "2020-01-01T00:00:00Z"
            path.write_text(json.dumps(snapshot))
            if mode == "unknown_frequency":
                path = service.config.policy_sources_path
                path.write_text(path.read_text().replace("monthly", "monthy"))
                # Keep runtime and active snapshot aligned, so freshness alone blocks trust.
                manifest = yaml.safe_load(service.config.rulebook_manifest_path.read_text())
                release_path = manifest["releases"][manifest["stages"]["active"]]["files"]["policy_sources"]
                (tmp_path / release_path).write_bytes(path.read_bytes())
                assert service._rulebook_is_trustworthy(service.get_rulebook_status())
                drift = service.get_drift_status(payer="Aetna", procedure_code="MRI_LUMBAR")
                assert drift.any_review_required
                assert drift.sources[0].freshness_status == "UNKNOWN"
        else:
            path = service.config.rules_path
            path.write_text(path.read_text().replace("version: 1.0", "version: unpromoted"))
        proposal = service.evaluate(service.get_demo_case_request(case))
        verified = service.evaluate(attest(proposal))
        assert verified.overall_status == "READY"
        assert verified.submission_readiness is False
        assert verified.policy_trust_level == "demo"

    def test_G07_borrowed_date_remains_contained_by_demo_submission_gate(self):
        example = next(example for example in EXAMPLES if example["id"] == "borrowed_date")
        service = ReadinessService()
        proposal = service.evaluate(PARequest(payer="Aetna", procedure_code="CPAP_DEVICE", note_text=example["note"]))
        # Deliberately incorrect synthetic attestations demonstrate the independent trust gate.
        result = service.evaluate(attest(proposal))
        assert result.overall_status == "READY"
        assert result.submission_readiness is False


def test_mid_evaluation_rule_bundle_change_fails_for_retry(tmp_path, monkeypatch):
    service = copied_service(tmp_path)
    original_extract = service_module.extract_facts

    def change_during_extraction(note):
        service.config.rules_path.write_text(service.config.rules_path.read_text() + "\n# concurrent promotion\n")
        return original_extract(note)

    monkeypatch.setattr(service_module, "extract_facts", change_during_extraction)
    with pytest.raises(GovernanceConfigError, match="changed during evaluation"):
        service.evaluate(service.get_demo_case_request("MRI-01-complete"))


def test_running_api_rereads_changed_rule_bundle_and_rejects_old_attestation(tmp_path, monkeypatch):
    service = copied_service(tmp_path)
    monkeypatch.setattr(api, "service", service)
    client = TestClient(api.app)
    request = service.get_demo_case_request("MRI-01-complete")
    proposal = service.evaluate(request)
    verified_request = attest(proposal)
    assert client.post("/evaluate", json=verified_request.model_dump(mode="json")).json()["overall_status"] == "READY"
    rules = yaml.safe_load(service.config.rules_path.read_text())
    requirements = rules["payers"]["Aetna"]["procedures"]["MRI_LUMBAR"]["required"]
    next(item for item in requirements if item["key"] == "cpb_0236_conservative_therapy_weeks")["min"] = 10
    service.config.rules_path.write_text(yaml.safe_dump(rules, sort_keys=False))
    # Simulate a completed promotion: new release, matching runtime bytes and manifest.
    manifest = yaml.safe_load(service.config.rulebook_manifest_path.read_text())
    release_id = "2026-09-04-test-promotion"
    release = deepcopy(manifest["releases"][manifest["stages"]["active"]])
    directory = tmp_path / "rulebook/releases" / release_id
    directory.mkdir()
    for key, path in {
        "rules": service.config.rules_path,
        "provenance": service.config.provenance_path,
        "policy_sources": service.config.policy_sources_path,
    }.items():
        target = directory / path.name
        shutil.copyfile(path, target)
        release["files"][key] = target.relative_to(tmp_path).as_posix()
    manifest["releases"][release_id] = release
    manifest["stages"]["active"] = release_id
    service.config.rulebook_manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    assert service._rulebook_is_trustworthy(service.get_rulebook_status())
    response = client.post("/evaluate", json=request.model_dump(mode="json"))
    assert response.status_code == 200
    assert response.json()["overall_status"] == "NOT_READY"
    assert response.json()["audit_trail"]["rulebook_active_release_id"] == release_id
    assert response.json()["policy_trust_level"] == "verified"
    assert client.post("/evaluate", json=verified_request.model_dump(mode="json")).status_code == 400


@pytest.mark.parametrize("verified", [False, True])
def test_identical_request_status_across_streamlit_fastapi_cli(tmp_path, capsys, verified):
    at = AppTest.from_file("app.py").run(timeout=15)
    next(button for button in at.button if button.key == "case_MRI-01-complete").click().run(timeout=15)
    assert not at.exception
    if verified:
        next(widget for widget in at.text_input if widget.key == "human_verifier_name").set_value("Surface test reviewer")
        for checkbox in at.checkbox:
            if str(checkbox.key).startswith("verify_"):
                checkbox.check()
        next(button for button in at.button if button.label == "Record human verification").click().run(timeout=15)
        assert not at.exception
    ui = at.session_state["last_eval_payload"]
    request = ui["request"]
    response = TestClient(api.app).post("/evaluate", json=request)
    assert response.status_code == 200
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    assert main(["evaluate", "--request-file", str(path), "--json"]) == 0
    command = json.loads(capsys.readouterr().out)
    expected = "READY" if verified else "PENDING_VERIFICATION"
    for payload in (ui, response.json(), command):
        assert payload["overall_status"] == expected
        assert payload["submission_readiness"] is verified
        assert [result["verification"] for result in payload["results"]] == [result["verification"] for result in ui["results"]]
