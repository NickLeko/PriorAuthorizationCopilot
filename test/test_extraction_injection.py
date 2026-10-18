import json
from pathlib import Path

import pytest
from verification_helpers import attest

import engine.service as service_module
from engine.acceptance import ACCEPTANCE_GOVERNANCE_NOW
from engine.config import load_app_config
from engine.decision_store import DecisionStore
from engine.extract import extract_facts
from engine.replay import replay_decision
from engine.schemas import PARequest
from engine.service import InvalidRequestError, ReadinessService
from experiments.dual_extraction.baseline import normalize_evaluation
from experiments.dual_extraction.proposals import extract_regex_proposal, proposal_to_legacy

CASES = json.loads(Path("inputs/synthetic_cases.json").read_text())


def round_trip_extractor(note):
    return proposal_to_legacy(extract_regex_proposal(note))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_default_explicit_and_adapted_regex_have_full_service_parity(case):
    default = ReadinessService()
    request = default.get_demo_case_request(case["id"])
    expected = default.evaluate(request)
    for extractor in (extract_facts, round_trip_extractor):
        actual = ReadinessService(extractor=extractor).evaluate(request)
        assert normalize_evaluation(actual.model_dump(mode="json")) == normalize_evaluation(expected.model_dump(mode="json"))
        assert actual.fact_set_fingerprint == expected.fact_set_fingerprint
        assert [r.verification_fingerprint for r in actual.results] == [r.verification_fingerprint for r in expected.results]


@pytest.mark.parametrize("stale", [False, True])
def test_injected_proposals_preserve_attestation_archive_replay_and_governance(tmp_path, stale, monkeypatch):
    config = load_app_config()
    if stale:
        config = config.model_copy(update={"snapshot_root": tmp_path / "no-monitoring"})
    default = ReadinessService(config, utc_now_provider=lambda: ACCEPTANCE_GOVERNANCE_NOW)
    proposal = default.evaluate(default.get_demo_case_request("MRI-01-complete"))
    request = attest(proposal)
    expected = default.evaluate(request)
    injected = ReadinessService(config, extractor=round_trip_extractor, utc_now_provider=lambda: ACCEPTANCE_GOVERNANCE_NOW)
    actual = injected.evaluate(request)
    assert actual.overall_status == expected.overall_status == "READY"
    assert actual.submission_readiness == expected.submission_readiness == (not stale)
    assert normalize_evaluation(actual.model_dump(mode="json")) == normalize_evaluation(expected.model_dump(mode="json"))
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        identifier = store.record(actual)

        def forbidden(note):
            raise AssertionError("Archive validation and replay must not re-extract.")

        monkeypatch.setattr(service_module, "extract_facts", forbidden)
        restored = store.get_decision(identifier)
        assert restored.model_dump(mode="json") == actual.model_dump(mode="json")
        assert replay_decision(restored, restored.policy_version) == replay_decision(expected, expected.policy_version)


def test_seam_is_per_service_explicit_and_calls_once_with_original_note():
    note = "😀İ. OSA. Sleep study completed 2024-05-18. AHI 22."
    calls = []
    captured = round_trip_extractor(note)

    def recorded(text):
        calls.append(text)
        return captured

    request = PARequest(payer="Aetna", procedure_code="CPAP_DEVICE", note_text=note)
    actual = ReadinessService(extractor=recorded).evaluate(request)
    expected = ReadinessService().evaluate(request)
    assert calls == [note]
    assert normalize_evaluation(actual.model_dump(mode="json")) == normalize_evaluation(expected.model_dump(mode="json"))


def test_capped_citations_preserve_service_counts_and_fingerprints():
    note = "😀İ. Neck pain for 8 weeks. Denies weakness. X-ray normal. " + " ".join(f"PT for {weeks} weeks." for weeks in range(1, 16))
    request = PARequest(payer="Aetna", procedure_code="MRI_CERVICAL", note_text=note)
    expected = ReadinessService().evaluate(request)
    actual = ReadinessService(extractor=round_trip_extractor).evaluate(request)
    assert actual.evidence_counts["conservative_therapy_weeks"] == 15
    assert len(actual.evidence_map["conservative_therapy_weeks"]) == 10
    assert normalize_evaluation(actual.model_dump(mode="json")) == normalize_evaluation(expected.model_dump(mode="json"))


def test_default_retains_existing_module_patch_behavior(monkeypatch):
    service = ReadinessService()
    calls = []

    def recorded(note):
        calls.append(note)
        return extract_facts(note)

    monkeypatch.setattr(service_module, "extract_facts", recorded)
    service.evaluate(PARequest(payer="Aetna", procedure_code="CPAP_DEVICE", note_text="OSA"))
    assert calls == ["OSA"]


def test_falsey_callable_is_not_replaced_by_default():
    class FalseyExtractor:
        def __bool__(self):
            return False

        def __call__(self, note):
            raise ValueError("Explicit extractor was used")

    with pytest.raises(InvalidRequestError, match="Explicit extractor was used"):
        ReadinessService(extractor=FalseyExtractor()).evaluate(PARequest(payer="Aetna", procedure_code="CPAP_DEVICE", note_text="OSA"))


def test_injected_citations_still_pass_existing_service_validation():
    def invalid(note):
        facts, evidence = extract_facts(note)
        evidence["osa_diagnosis"][0]["text"] = "wrong"
        return facts, evidence

    with pytest.raises(InvalidRequestError, match="Evidence offsets/text"):
        ReadinessService(extractor=invalid).evaluate(PARequest(payer="Aetna", procedure_code="CPAP_DEVICE", note_text="OSA"))
