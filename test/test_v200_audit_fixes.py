"""Regressions for the 4468a6c adversarial audit; no extraction changes."""

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest
from test_corrections import NOTE, THERAPY_KEY, event, request
from test_v200_surfaces import TIMEOUT, button, correct, load_request, verify, widget
from verification_helpers import attest

import api
from engine.acceptance import CORRECTED_ACCEPTANCE_NOTE
from engine.corrections import validate_note_evidence
from engine.decision_store import DecisionStore
from engine.schemas import CorrectionSpan, EvidenceSpan
from engine.service import InvalidRequestError, ReadinessService


def corrected_ready():
    service = ReadinessService()
    quote = "Lumbosacral radicular syndrome documented."
    proposal = service.evaluate(
        request(
            CORRECTED_ACCEPTANCE_NOTE,
            events=[
                event(
                    CORRECTED_ACCEPTANCE_NOTE,
                    key="back_pain_with_radiculopathy",
                    value=True,
                    evidence_spans=[{"start": 0, "end": len(quote), "text": quote}],
                )
            ],
        )
    )
    return service, service.evaluate(attest(proposal))


def ready_app():
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT).run()
    load_request(at, "MRI-01-complete", CORRECTED_ACCEPTANCE_NOTE)
    correct(at, "back_pain_with_radiculopathy", "Lumbosacral radicular syndrome documented.", True)
    verify(at)
    assert at.session_state["last_eval_payload"]["submission_readiness"] is True
    button(at, "Generate deterministic letter").click().run(timeout=TIMEOUT)
    assert at.session_state["letter_text"]
    assert at.session_state["result_context"] == at.session_state["attestation_context"] == at.session_state["letter_context"]
    return at


def assert_caches_cleared(at):
    assert not at.exception
    assert at.session_state["last_eval_payload"] is None
    assert at.session_state["letter_text"] == ""
    assert at.session_state["letter_meta"] == {}
    for key in ("result_context", "attestation_context", "letter_context"):
        assert at.session_state[key] is None
    assert not any(str(key).startswith("verify_") for key in at.session_state.filtered_state)


def test_streamlit_governance_expiration_clears_all_cached_outputs(monkeypatch):
    at = ready_app()
    monkeypatch.setattr("engine.service.utc_now", lambda: datetime(2026, 10, 6, tzinfo=timezone.utc))
    at.run(timeout=TIMEOUT)
    assert_caches_cleared(at)
    assert any("context changed: governance" in w.value for w in at.warning)


def test_streamlit_bundle_change_clears_all_cached_outputs(monkeypatch):
    at = ready_app()
    monkeypatch.setattr(ReadinessService, "_bundle_digest", lambda self: "f" * 64)
    at.run(timeout=TIMEOUT)
    assert_caches_cleared(at)
    assert any("bundle_digest" in w.value for w in at.warning)


@pytest.mark.parametrize("key", ["attestation_context", "letter_context"])
def test_streamlit_missing_context_key_clears_cached_outputs(key):
    at = ready_app()
    at.session_state[key] = None
    at.run(timeout=TIMEOUT)
    assert_caches_cleared(at)
    assert any("changed or missing" in w.value for w in at.warning)


@pytest.mark.parametrize("error_type", [InvalidRequestError, OSError, RuntimeError])
def test_streamlit_failed_reverification_clears_all_cached_outputs(monkeypatch, error_type):
    at = ready_app()
    original = ReadinessService.evaluate

    def fail_verification(self, request, *args, **kwargs):
        if request.fact_verifications:
            raise error_type("Stale or mismatched verification; audit reproduction.")
        return original(self, request, *args, **kwargs)

    monkeypatch.setattr(ReadinessService, "evaluate", fail_verification)
    button(at, "Record human verification").click().run(timeout=TIMEOUT)
    assert_caches_cleared(at)
    assert any("cleared after failed re-verification" in e.value for e in at.error)


@pytest.mark.parametrize("mutation", ["appended", "emptied"])
def test_letter_rejects_inconsistent_correction_envelope(mutation):
    service, result = corrected_ready()
    if mutation == "appended":
        result.request.corrections.append(result.request.corrections[0].model_copy(update={"value": False}))
    else:
        result.request.corrections = []
    with pytest.raises(ValueError):
        service.generate_letter(result)


def test_letter_rejects_301_character_quotation():
    note = NOTE + " " + "x" * 301
    start = len(NOTE) + 1
    result = ReadinessService().evaluate(
        request(
            note,
            events=[
                event(
                    note,
                    evidence_spans=[
                        {"start": start, "end": start + 300, "text": "x" * 300},
                    ],
                )
            ],
        )
    )
    result = ReadinessService().evaluate(attest(result))
    assert result.overall_status == "READY"
    result.request.corrections[0] = result.request.corrections[0].model_copy(
        update={
            "evidence_spans": (CorrectionSpan(start=start, end=start + 301, text="x" * 301),),
        }
    )
    result.evidence_map[THERAPY_KEY] = [EvidenceSpan(start=start, end=start + 301, text="x" * 301)]
    with pytest.raises(ValueError, match="at most 300 characters each"):
        ReadinessService().generate_letter(result)


def test_streamlit_fractional_weeks_rejected_without_truncation():
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT).run()
    button_case = widget(at, "button", "case_MRI-CERV-01-ready")
    button_case.click().run(timeout=TIMEOUT)
    note = at.session_state["last_eval_payload"]["request"]["note_text"]
    quote = note[:40]
    key = "symptom_duration_weeks"
    widget(at, "text_input", f"correction_quote_{key}").set_value(quote).run(timeout=TIMEOUT)
    widget(at, "multiselect", f"correction_spans_{key}").select((0, len(quote))).run(timeout=TIMEOUT)
    widget(at, "text_input", f"correction_value_{key}").set_value("6.5")
    widget(at, "text_input", f"correction_editor_{key}").set_value("Audit")
    button(at, f"Apply correction: {key}").click().run(timeout=TIMEOUT)
    assert_caches_cleared(at)
    assert any("expected_integer_weeks" in e.value for e in at.error)
    assert at.session_state["corrections"] == []


def test_streamlit_integer_weeks_retains_integer_representation():
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT).run()
    widget(at, "button", "case_MRI-CERV-01-ready").click().run(timeout=TIMEOUT)
    note = at.session_state["last_eval_payload"]["request"]["note_text"]
    key = "symptom_duration_weeks"
    widget(at, "text_input", f"correction_quote_{key}").set_value(note[:40]).run(timeout=TIMEOUT)
    widget(at, "multiselect", f"correction_spans_{key}").select((0, 40)).run(timeout=TIMEOUT)
    widget(at, "text_input", f"correction_value_{key}").set_value("6")
    widget(at, "text_input", f"correction_editor_{key}").set_value("Audit")
    button(at, f"Apply correction: {key}").click().run(timeout=TIMEOUT)
    assert not at.exception
    value = at.session_state["last_eval_payload"]["request"]["corrections"][0]["value"]
    assert type(value) is int and value == 6


def test_streamlit_overlength_audit_comment_rejected_without_truncation():
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT).run()
    load_request(at, "MRI-01-complete", CORRECTED_ACCEPTANCE_NOTE)
    key = "back_pain_with_radiculopathy"
    quote = "Lumbosacral radicular syndrome documented."
    widget(at, "text_input", f"correction_quote_{key}").set_value(quote).run(timeout=TIMEOUT)
    widget(at, "multiselect", f"correction_spans_{key}").select((0, len(quote))).run(timeout=TIMEOUT)
    widget(at, "selectbox", f"correction_value_{key}").select(True)
    widget(at, "text_input", f"correction_editor_{key}").set_value("Audit")
    widget(at, "text_input", f"correction_comment_{key}").set_value("x" * 1001)
    button(at, f"Apply correction: {key}").click().run(timeout=TIMEOUT)
    assert_caches_cleared(at)
    assert at.session_state[f"correction_comment_{key}"] == "x" * 1001
    assert any("at most 1000 characters" in e.value for e in at.error)


def test_archive_rejects_matching_but_forged_metric_copies(tmp_path):
    _, result = corrected_ready()
    result.metrics.criteria_met_count = 0
    result.metrics.total_requirements = 999
    result.audit_trail.metrics = result.metrics.model_copy(deep=True)
    result.report.audit_trail = result.audit_trail.model_dump(mode="json")
    with DecisionStore(tmp_path / "audit.sqlite") as store:
        with pytest.raises(ValueError, match="Metrics disagree"):
            store.record(result)
        assert store.decision_ids() == []
        assert store.list_policies() == []


def test_archive_rejects_demo_supported_procedure_with_verified_trust_copies(tmp_path):
    service = ReadinessService()
    note = "OSA. Sleep study completed 2024-02-29. AHI 22."
    proposal = service.evaluate(
        request(
            note,
            procedure="CPAP_DEVICE",
            events=[
                event(
                    note,
                    key="osa_diagnosis",
                    value=True,
                    evidence_spans=[{"start": 0, "end": 4, "text": "OSA."}],
                )
            ],
        )
    )
    result = service.evaluate(attest(proposal))
    assert result.overall_status == "READY" and result.submission_readiness is False
    assert result.supported_procedure.policy_trust_level == "demo"
    result.policy_trust_level = "verified"
    result.submission_readiness = True
    result.audit_trail.policy_trust_level = "verified"
    result.audit_trail.submission_readiness = True
    result.report.audit_trail = result.audit_trail.model_dump(mode="json")
    with DecisionStore(tmp_path / "audit.sqlite") as store:
        with pytest.raises(ValueError, match="Supported-procedure policy trust disagrees"):
            store.record(result)
        assert store.decision_ids() == []
        assert store.list_policies() == []


@pytest.mark.parametrize("token", ["1e1000", "NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("media_type", ["application/json", "application/vnd.pa+json", None])
def test_api_nonfinite_and_overflow_numbers_return_structured_422(token, media_type):
    payload = request(events=[event()]).model_dump(mode="json")
    raw = json.dumps(payload).replace('"value": 8', f'"value": {token}')
    response = TestClient(api.app).post("/evaluate", content=raw, headers={"Content-Type": media_type} if media_type else {})
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
    assert "finite" in response.json()["detail"]


@pytest.mark.parametrize("count", [3, 4])
def test_set_value_span_count_at_correction_archive_and_letter_boundaries(count, tmp_path):
    quote = "Low back pain"
    spans = [{"start": 0, "end": len(quote), "text": quote}] * count
    payload = event(evidence_spans=spans)
    if count == 4:
        with pytest.raises(ValueError, match="at most 3 spans"):
            request(events=[payload])
        result = ReadinessService().evaluate(request(events=[event(evidence_spans=spans[:3])]))
        result.request.corrections[0] = result.request.corrections[0].model_copy(
            update={
                "evidence_spans": tuple(CorrectionSpan(**span) for span in spans),
            }
        )
        with pytest.raises(ValueError, match="at most 3 spans"):
            validate_note_evidence(result.request.corrections[0], NOTE)
        with pytest.raises(ValueError, match="at most 3 spans"):
            ReadinessService().generate_letter(result)
        with DecisionStore(tmp_path / "audit.sqlite") as store:
            with pytest.raises(ValueError, match="at most 3 spans"):
                store.record(result)
            assert store.decision_ids() == []
    else:
        result = ReadinessService().evaluate(request(events=[payload]))
        text, metadata = ReadinessService().generate_letter(result)
        assert not metadata["draft_blocked"]
        assert quote in text
        with DecisionStore(tmp_path / "audit.sqlite") as store:
            store.record(result, "three")
            assert len(store.get_decision("three").request.corrections[0].evidence_spans) == 3
