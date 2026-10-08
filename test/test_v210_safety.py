"""Reproduced v2.1 errors: correct expectations, including strict known failures."""

import json
import shutil
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

import api
import engine.service as service_module
from cli import main
from engine.citation_context import citation_context, evaluation_citation_context
from engine.config import load_app_config
from engine.extract import extract_facts
from engine.schemas import REVIEW_REQUIRED_FACT, EvaluationResult, PARequest
from engine.service import GovernanceConfigError, ReadinessService, _load_bundle, _parsed_manifest

CONTRAST_NOTE = (
    "Low back pain with right leg radiculopathy. NSAIDs for 8 weeks with no improvement in sleep "
    "but significant improvement in pain. Ankle dorsiflexion strength 4/5 in the right L5 distribution."
)


@pytest.mark.parametrize("marker", ["but", "however", "though", "although", "yet", "whereas"])
def test_contrast_without_modality_requires_review(marker):
    facts, _ = extract_facts(CONTRAST_NOTE.replace("but", marker))
    assert facts["cpb_0236_conservative_therapy_no_improvement"] == REVIEW_REQUIRED_FACT


@pytest.mark.parametrize("passive", ["was", "were", "has been", "had been"])
def test_osa_passive_ruled_out_is_missing(passive):
    assert extract_facts(f"OSA {passive} ruled out.")[0]["osa_diagnosis"] is None


@pytest.mark.parametrize(
    "note",
    [
        pytest.param("PT x 8 weeks was never completed", id="never_completed"),
        pytest.param("PT x 8 weeks was not completed", id="not_completed"),
        pytest.param("Stopped PT after 1 week. PT x 8 weeks was prescribed.", id="stopped_then_prescribed"),
        pytest.param("PT x 8 weeks was recommended", id="recommended"),
        pytest.param("PT x 8 weeks was ordered", id="ordered"),
    ],
)
def test_uncompleted_therapy_duration_is_missing(note):
    assert extract_facts(note)[0]["conservative_therapy_weeks"] is None


@pytest.mark.parametrize("qualifier", ["never completed", "not completed", "prescribed", "recommended", "ordered"])
def test_uncompleted_cpb_therapy_does_not_donate_duration(qualifier):
    facts, _ = extract_facts(f"NSAIDs for 8 weeks was {qualifier} with no improvement.")
    assert facts["cpb_0236_conservative_therapy_weeks"] is None


@pytest.mark.parametrize("spelling", ["cancelled", "canceled"])
def test_cancelled_sleep_study_is_missing(spelling):
    assert extract_facts(f"Sleep study 2026-01-05 was {spelling}.")[0]["sleep_study_date"] is None


@pytest.mark.parametrize("unrelated", ["Allergies: N/A.", "Bed partner unknown."])
def test_ahi_missingness_is_scoped_to_own_sentence(unrelated):
    assert extract_facts(f"OSA confirmed on PSG 2026-01-05, AHI 32. {unrelated}")[0]["ahi_documented"] is True


@pytest.mark.parametrize("note", ["AHI unknown.", "AHI 32 but value unknown.", "AHI N/A.", "AHI missing.", "AHI 32.5 unknown."])
def test_ahi_own_sentence_missingness_still_refuses(note):
    assert extract_facts(note)[0]["ahi_documented"] is None


@pytest.mark.parametrize(
    "note,key",
    [
        ("Low back pain with radiculopathy resolved.", "back_pain_with_radiculopathy"),
        ("Right L5 distribution: strength 4/5, weakness resolved.", "objective_motor_or_reflex_change_in_root_distribution"),
        ("Reports locking, now resolved.", "mechanical_symptoms_documented"),
        ("OSA resolved.", "osa_diagnosis"),
    ],
)
def test_resolved_finding_in_same_sentence_requires_review(note, key):
    assert extract_facts(note)[0][key] == REVIEW_REQUIRED_FACT


@pytest.mark.xfail(strict=True, reason="temporality: resolved historical episode across sentences requires coreference")
def test_resolved_historical_episode_across_sentences_requires_review():
    facts, _ = extract_facts("Low back pain with radiculopathy. It resolved last year.")
    assert facts["back_pain_with_radiculopathy"] == REVIEW_REQUIRED_FACT


def copied_service(tmp_path):
    for directory in ("rules", "rulebook", "policy_snapshots", "inputs"):
        shutil.copytree(directory, tmp_path / directory)
    return ReadinessService(load_app_config(tmp_path))


def test_long_lived_service_loads_changed_disk_bundle_on_next_evaluation(tmp_path):
    service = copied_service(tmp_path)
    request = service.get_demo_case_request("MRI-01-complete")
    before = service.evaluate(request)
    rules = yaml.safe_load(service.config.rules_path.read_text())
    requirements = rules["payers"]["Aetna"]["procedures"]["MRI_LUMBAR"]["required"]
    next(item for item in requirements if item["key"] == "cpb_0236_conservative_therapy_weeks")["min"] = 10
    service.config.rules_path.write_text(yaml.safe_dump(rules))
    after = service.evaluate(request)
    assert before.overall_status == "PENDING_VERIFICATION"
    assert after.overall_status == "NOT_READY"
    assert after.bundle_fingerprint != before.bundle_fingerprint
    assert after.fact_set_fingerprint != before.fact_set_fingerprint


def test_release_only_change_invalidates_digest_and_cached_status(tmp_path):
    service = copied_service(tmp_path)
    request = service.get_demo_case_request("MRI-01-complete")
    before = service.evaluate(request)
    manifest = yaml.safe_load(service.config.rulebook_manifest_path.read_text())
    path = tmp_path / manifest["releases"][manifest["stages"]["active"]]["files"]["rules"]
    path.write_text(path.read_text().replace("version: 1.0", "version: mismatch"))
    after = service.evaluate(request)
    assert after.bundle_fingerprint != before.bundle_fingerprint
    assert service.get_rulebook_status().validation_errors
    assert after.policy_trust_level == "demo"


def test_mid_evaluation_release_change_fails_for_retry(tmp_path, monkeypatch):
    service = copied_service(tmp_path)
    manifest = yaml.safe_load(service.config.rulebook_manifest_path.read_text())
    path = tmp_path / manifest["releases"][manifest["stages"]["active"]]["files"]["rules"]
    extract = service_module.extract_facts

    def mutate(note):
        path.write_text(path.read_text() + "\n# concurrent release change\n")
        return extract(note)

    monkeypatch.setattr(service_module, "extract_facts", mutate)
    with pytest.raises(GovernanceConfigError, match="changed during evaluation"):
        service.evaluate(service.get_demo_case_request("MRI-01-complete"))


def test_cached_bundle_is_immutable_and_only_loaded_once(tmp_path):
    _load_bundle.cache_clear()
    _parsed_manifest.cache_clear()
    service = copied_service(tmp_path)
    request = service.get_demo_case_request("MRI-01-complete")
    with (
        patch("yaml.safe_load", wraps=yaml.safe_load) as loads,
        patch("engine.service.get_rulebook_status", wraps=service_module.get_rulebook_status) as status,
        patch.object(service, "_digest_for_snapshot", wraps=service._digest_for_snapshot) as digest,
    ):
        result = service.evaluate(request)
        assert digest.call_count == 2  # initial identity and final mutation guard
        assert loads.call_count == len(service._bundle_snapshot())
        assert status.call_count == 1
        loads.reset_mock()
        status.reset_mock()
        service.evaluate(request)
        assert loads.call_count == status.call_count == 0
    bundle = service._current_bundle()
    with pytest.raises(TypeError):
        bundle.rules["version"] = "poison"
    with pytest.raises(TypeError):
        bundle.rules["payers"]["Aetna"]["procedures"]["MRI_LUMBAR"]["required"][0]["key"] = "poison"
    rules = service.rules
    rules["version"] = "caller mutation"
    service.get_rulebook_status().validation_errors.append("caller mutation")
    assert service.evaluate(request).bundle_fingerprint == result.bundle_fingerprint
    assert not service.get_rulebook_status().validation_errors


def test_citation_context_keeps_contrast_without_changing_record():
    service = ReadinessService()
    result = service.evaluate(PARequest(payer="Aetna", procedure_code="MRI_LUMBAR", note_text=CONTRAST_NOTE))
    contexts = evaluation_citation_context(result)
    context = contexts["cpb_0236_conservative_therapy_no_improvement"][0]
    assert context == "⟦NSAIDs for 8 weeks with no improvement in sleep⟧ but significant improvement in pain."
    assert result.evidence_map["cpb_0236_conservative_therapy_no_improvement"][0].text == "NSAIDs for 8 weeks with no improvement in sleep"
    assert "citation_context" not in result.model_dump()
    assert EvaluationResult.model_validate_json(result.model_dump_json()) == result
    assert result.schema_version == "2.0.0"


@pytest.mark.parametrize(
    "note,quote,expected",
    [
        ("First sentence. Second sentence. Third.", "sentence. Second", "First ⟦sentence. Second⟧ sentence."),
        ("AHI 32.5 documented. Allergies N/A.", "AHI 32.5", "⟦AHI 32.5⟧ documented."),
        ("İ. OSA confirmed.", "OSA", "⟦OSA⟧ confirmed."),
        ("OSA confirmed.", "OSA confirmed.", "⟦OSA confirmed.⟧"),
    ],
)
def test_citation_context_offsets_multisentence_and_decimal(note, quote, expected):
    start = note.index(quote)
    assert citation_context(note, start, start + len(quote)) == expected


def test_api_and_cli_result_context_matches(tmp_path, capsys):
    request = PARequest(payer="Aetna", procedure_code="MRI_LUMBAR", note_text=CONTRAST_NOTE)
    response = TestClient(api.app).post("/evaluate", json=request.model_dump(mode="json"))
    assert response.status_code == 200
    path = tmp_path / "request.json"
    path.write_text(request.model_dump_json())
    assert main(["evaluate", "--request-file", str(path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["citation_context"] == response.json()["citation_context"]
    canonical = EvaluationResult.model_validate(payload)
    assert canonical.engine_version == "2.1.1"
    assert "citation_context" not in canonical.model_dump()
    with pytest.raises(ValidationError, match="Derived citation context"):
        EvaluationResult.model_validate(payload | {"citation_context": {}})
    assert "but significant improvement in pain" in str(payload["citation_context"])
    assert main(["evaluate", "--request-file", str(path)]) == 0
    assert "but significant improvement in pain" in capsys.readouterr().out
    export = tmp_path / "review.json"
    assert main(["export-report", "--demo-case", "MRI-01-complete", "--output", str(export)]) == 0
    capsys.readouterr()
    exported = json.loads(export.read_text())
    assert exported["citation_context"]
    assert "citation_context" not in EvaluationResult.model_validate(exported).model_dump()


def test_streamlit_verification_and_correction_show_full_contrast_context():
    at = AppTest.from_file("app.py").run(timeout=15)
    assert not at.exception
    next(button for button in at.button if button.key == "case_MRI-01-complete").click().run(timeout=15)
    assert not at.exception
    # Preserve the normal UI review setup while reproducing the exact note.
    next(widget for widget in at.text_area if widget.key == "note_text").set_value(CONTRAST_NOTE)
    next(button for button in at.button if button.label == "Run deterministic readiness review").click().run(timeout=15)
    assert not at.exception
    payload = at.session_state["last_eval_payload"]
    assert payload["overall_status"] == "NEEDS_REVIEW"
    assert payload["submission_readiness"] is False
    assert any("status-panel" in item.value and "NEEDS_REVIEW" in item.value for item in at.markdown)
    assert any(item.value == "#### Correct requirement facts" for item in at.markdown)
    assert any(item.value == "#### Verify proposed facts" for item in at.markdown)
    context = "⟦NSAIDs for 8 weeks with no improvement in sleep⟧ but significant improvement in pain."
    therapy_keys = ("cpb_0236_conservative_therapy_weeks", "cpb_0236_conservative_therapy_no_improvement")
    for key in therapy_keys:
        result = next(result for result in payload["results"] if result["key"] == key)
        assert result["status"] == "NEEDS_REVIEW"
        assert result["fact_value"] is None
        expander = next(item for item in at.expander if item.label == f"Correct {result['label']}")
        assert any(item.value == "Effective citations in sentence context (⟦quoted span⟧):" for item in expander.caption)
        assert any(item.value == "Original proposal citations in sentence context:" for item in expander.caption)
        assert [item.value for item in expander.text] == [context, context]
        assert any(f"{result['label']}: proposed None | NEEDS_REVIEW" == item.value for item in at.markdown)
        assert any(item.label == f"I verified {key} against the original note and rule" for item in at.checkbox)
    # Two correction copies per therapy fact plus one verification copy each.
    assert [item.value for item in at.text].count(context) == 6
    key = therapy_keys[1]
    next(item for item in at.text_input if item.key == f"correction_quote_{key}").set_value(
        "NSAIDs for 8 weeks with no improvement in sleep"
    ).run(timeout=15)
    assert not at.exception
    occurrences = next(item for item in at.multiselect if item.key == f"correction_spans_{key}")
    assert occurrences.options == [context]
    start = CONTRAST_NOTE.index("NSAIDs")
    occurrences.set_value([(start, start + len("NSAIDs for 8 weeks with no improvement in sleep"))]).run(timeout=15)
    assert not at.exception
    assert at.session_state["last_eval_payload"]["overall_status"] == "NEEDS_REVIEW"
    assert [item.value for item in at.text].count(context) == 7


def test_streamlit_engine_version_change_builds_new_service(monkeypatch):
    import engine

    instances = []

    def build_service(*args, **kwargs):
        instance = ReadinessService(*args, **kwargs)
        instances.append(instance)
        return instance

    monkeypatch.setattr(service_module, "ReadinessService", build_service)
    monkeypatch.setattr(engine, "__version__", "99.0.1")
    at = AppTest.from_file("app.py").run(timeout=15)
    assert not at.exception
    assert len(instances) == 2  # Digest probe, then cached factory.
    first_service = instances[-1]
    at.run(timeout=15)
    assert not at.exception
    assert len(instances) == 3  # Only the probe; factory reused its instance.
    monkeypatch.setattr(engine, "__version__", "99.0.2")
    at.run(timeout=15)
    assert not at.exception
    assert len(instances) == 5
    assert instances[-1] is not first_service
