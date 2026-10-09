import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest
from verification_helpers import attest

import api
from cli import main
from engine.acceptance import CORRECTED_ACCEPTANCE_NOTE, build_corrected_acceptance_payloads
from engine.corrections import note_hash
from engine.fact_contracts import get_fact_contract
from engine.schemas import EvaluationResult, PARequest
from engine.service import ReadinessService

TIMEOUT = 30
CORRECTED_KEY = "back_pain_with_radiculopathy"


def widget(at, kind, key):
    return next(item for item in getattr(at, kind) if item.key == key)


def button(at, label):
    return next(item for item in at.button if item.label == label)


def load_request(at, case, note):
    widget(at, "button", f"case_{case}").click().run(timeout=TIMEOUT)
    widget(at, "text_area", "note_text").set_value(note)
    button(at, "Run deterministic readiness review").click().run(timeout=TIMEOUT)
    assert not at.exception


def correct(at, key, quote, value):
    widget(at, "text_input", f"correction_quote_{key}").set_value(quote).run(timeout=TIMEOUT)
    note = at.session_state["last_eval_payload"]["request"]["note_text"]
    start = note.index(quote)
    widget(at, "multiselect", f"correction_spans_{key}").select((start, start + len(quote))).run(timeout=TIMEOUT)
    widget(at, "selectbox", f"correction_value_{key}").select(value)
    widget(at, "text_input", f"correction_editor_{key}").set_value("Surface correction editor")
    button(at, f"Apply correction: {key}").click().run(timeout=TIMEOUT)
    assert not at.exception


def verify(at):
    widget(at, "text_input", "human_verifier_name").set_value("Surface correction verifier")
    for checkbox in at.checkbox:
        if str(checkbox.key).startswith("verify_"):
            checkbox.check()
    button(at, "Record human verification").click().run(timeout=TIMEOUT)
    assert not at.exception


def assert_surface_parity(at, tmp_path, capsys, expected):
    ui = at.session_state["last_eval_payload"]
    response = TestClient(api.app).post("/evaluate", json=ui["request"])
    assert response.status_code == 200, response.text
    path = tmp_path / "correction-request.json"
    path.write_text(json.dumps(ui["request"]))
    capsys.readouterr()
    assert main(["evaluate", "--request-file", str(path), "--json"]) == 0
    command = json.loads(capsys.readouterr().out)
    keys = (
        "overall_status",
        "submission_readiness",
        "facts",
        "captured_fact_states",
        "results",
        "evidence_map",
        "request",
        "input_fingerprint",
        "fact_set_fingerprint",
        "uses_reviewer_corrections",
        "corrected_requirement_keys",
    )
    assert ui["overall_status"] == expected
    for payload in (response.json(), command):
        assert {key: payload[key] for key in keys} == {key: ui[key] for key in keys}


def test_corrected_request_pending_then_ready_parity_and_stale_letter_removal(tmp_path, capsys):
    at = AppTest.from_file("app.py").run(timeout=TIMEOUT)
    load_request(at, "MRI-01-complete", CORRECTED_ACCEPTANCE_NOTE)
    assert at.session_state["last_eval_payload"]["overall_status"] == "CANNOT_DETERMINE"
    assert any(get_fact_contract(CORRECTED_KEY).meaning in item.value for item in at.caption)
    quote = "Lumbosacral radicular syndrome documented."
    correct(at, CORRECTED_KEY, quote, True)
    assert_surface_parity(at, tmp_path, capsys, "PENDING_VERIFICATION")
    assert all(r["verification"]["state"] == "UNVERIFIED" for r in at.session_state["last_eval_payload"]["results"])
    verify(at)
    assert_surface_parity(at, tmp_path, capsys, "READY")
    button(at, "Generate deterministic letter").click().run(timeout=TIMEOUT)
    text = at.session_state["letter_text"]
    assert "Reviewer-supplied requirement fact" in text
    assert quote in text
    assert "Surface correction editor" in text and "Surface correction verifier" in text
    original = at.session_state["last_eval_payload"]["original_snapshot"]
    correct(at, CORRECTED_KEY, quote, True)
    assert at.session_state["letter_text"] == ""
    assert at.session_state["letter_meta"] == {}
    payload = at.session_state["last_eval_payload"]
    assert payload["overall_status"] == "PENDING_VERIFICATION"
    assert payload["request"]["fact_verifications"] == {}
    assert payload["original_snapshot"] == original
    assert len(payload["request"]["corrections"]) == 2
    assert all(r["verification"]["state"] == "UNVERIFIED" for r in payload["results"])


def test_osa_false_is_not_ready_on_all_surfaces(tmp_path, capsys):
    at = AppTest.from_file("app.py").run(timeout=TIMEOUT)
    note = "😀 İ. Patient denies OSA. Sleep study completed 2024-02-29. AHI 22."
    load_request(at, "CPAP-02-borderline", note)
    assert at.session_state["last_eval_payload"]["overall_status"] == "CANNOT_DETERMINE"
    correct(at, "osa_diagnosis", "Patient denies OSA.", False)
    assert_surface_parity(at, tmp_path, capsys, "NOT_READY")


def test_note_change_discards_corrections_even_after_failed_apply():
    at = AppTest.from_file("app.py").run(timeout=TIMEOUT)
    load_request(at, "MRI-01-complete", CORRECTED_ACCEPTANCE_NOTE)
    correct(at, CORRECTED_KEY, "Lumbosacral radicular syndrome documented.", True)
    widget(at, "text_input", f"correction_quote_{CORRECTED_KEY}").set_value("").run(timeout=TIMEOUT)
    button(at, f"Apply correction: {CORRECTED_KEY}").click().run(timeout=TIMEOUT)
    assert at.session_state["last_eval_payload"] is None
    widget(at, "text_area", "note_text").set_value("Back pain with radiculopathy.")
    button(at, "Run deterministic readiness review").click().run(timeout=TIMEOUT)
    assert not at.exception
    assert at.session_state["last_eval_payload"]["request"].get("corrections", []) == []
    assert not at.session_state["last_eval_payload"].get("uses_reviewer_corrections", False)
    assert at.session_state["letter_text"] == ""


@pytest.mark.parametrize(
    "action,expected",
    [("SET_MISSING", "CANNOT_DETERMINE"), ("SET_NEEDS_REVIEW", "NEEDS_REVIEW"), ("RESTORE_ORIGINAL", "PENDING_VERIFICATION")],
)
def test_nonvalue_ui_actions_preserve_original_and_clear_verification(action, expected):
    at = AppTest.from_file("app.py").run(timeout=TIMEOUT)
    widget(at, "button", "case_MRI-01-complete").click().run(timeout=TIMEOUT)
    original = at.session_state["last_eval_payload"]["original_snapshot"]
    widget(at, "selectbox", f"correction_action_{CORRECTED_KEY}").select(action).run(timeout=TIMEOUT)
    widget(at, "text_input", f"correction_editor_{CORRECTED_KEY}").set_value("Surface editor")
    button(at, f"Apply correction: {CORRECTED_KEY}").click().run(timeout=TIMEOUT)
    assert not at.exception
    payload = at.session_state["last_eval_payload"]
    assert payload["overall_status"] == expected
    assert payload["original_snapshot"] == original
    assert payload["request"]["fact_verifications"] == {}
    assert payload["uses_reviewer_corrections"]


def test_empty_quotation_cannot_apply_a_value_or_retain_old_letter():
    at = AppTest.from_file("app.py").run(timeout=TIMEOUT)
    widget(at, "button", "case_MRI-01-complete").click().run(timeout=TIMEOUT)
    button(at, "Generate deterministic letter").click().run(timeout=TIMEOUT)
    assert at.session_state["letter_text"]
    widget(at, "text_input", f"correction_editor_{CORRECTED_KEY}").set_value("Surface editor")
    button(at, f"Apply correction: {CORRECTED_KEY}").click().run(timeout=TIMEOUT)
    assert not at.exception
    assert at.session_state["last_eval_payload"] is None
    assert at.session_state["letter_text"] == ""
    assert any("requires quoted evidence" in error.value for error in at.text)  # Validation details render as literal text.


@pytest.mark.parametrize("case", ["MRI-01-complete", "CPAP-02-borderline", "MRI-KNEE-01-ready", "MRI-CERV-01-ready"])
def test_every_entry_renders_meaning_and_only_reviewer_enterable_values(case):
    at = AppTest.from_file("app.py").run(timeout=TIMEOUT)
    widget(at, "button", f"case_{case}").click().run(timeout=TIMEOUT)
    assert not at.exception
    for result in at.session_state["last_eval_payload"]["results"]:
        contract = get_fact_contract(result["key"])
        assert any(contract.meaning in caption.value for caption in at.caption)
        if contract.fact_kind in {"boolean", "date_presence", "enum"}:
            options = widget(at, "selectbox", f"correction_value_{result['key']}").options
            assert options == [str(value) for value in contract.reviewer_enterable]
            assert "unrecognized" not in options


@pytest.mark.parametrize(
    "field,value",
    [
        ("overall_status", "READY"),
        ("rule_reasons", []),
        ("effective_facts", {}),
        ("uses_reviewer_corrections", True),
        ("corrected_requirement_keys", []),
    ],
)
def test_api_and_cli_reject_client_derived_fields(tmp_path, capsys, field, value):
    payload = {"payer": "Aetna", "procedure_code": "CPAP_DEVICE", "note_text": "OSA.", field: value}
    assert TestClient(api.app).post("/evaluate", json=payload).status_code == 422
    path = tmp_path / "forged.json"
    path.write_text(json.dumps(payload))
    assert main(["evaluate", "--request-file", str(path), "--json"]) == 2
    assert "Extra inputs are not permitted" in capsys.readouterr().err


def test_corrected_goldens_pin_transitions_letter_and_full_envelope():
    payloads = build_corrected_acceptance_payloads(ReadinessService())
    for name, payload in payloads.items():
        assert payload == json.loads(Path("test/golden/evaluations", name + ".json").read_text())
    timeline = payloads["reviewer-corrected-e2e"]
    assert [stage["overall_status"] for stage in timeline["transitions"]] == ["CANNOT_DETERMINE", "PENDING_VERIFICATION", "READY"]
    full = payloads["reviewer-corrected-full-projection"]
    assert json.loads(full["original_snapshot"]["snapshot_json"])["facts"][CORRECTED_KEY] is None
    assert full["facts"][CORRECTED_KEY] is True
    assert full["request"]["corrections"][0]["comment"] == "AUDIT_ONLY_EXCLUDED_FROM_LETTER"
    assert "AUDIT_ONLY_EXCLUDED_FROM_LETTER" not in full["letter"]["text"]
    assert "not checked for recency or ordering" in full["letter"]["text"]


@pytest.mark.parametrize("kind", ["submission_cover_letter", "missing_info_request", "appeal_template"])
def test_all_letter_types_disclose_and_exclude_prohibited_audit_comment(kind):
    service = ReadinessService()
    full = build_corrected_acceptance_payloads(service)["reviewer-corrected-full-projection"]
    payload = full["request"]
    payload["fact_verifications"] = {}
    payload["corrections"][0]["comment"] = "will be approved; should take 500 mg daily"
    verified = service.evaluate(attest(service.evaluate(PARequest.model_validate(payload))))
    text, meta = service.generate_letter(verified, kind)
    assert not meta["draft_blocked"]
    assert "will be approved" not in text and "500 mg" not in text
    assert "Reviewer-supplied requirement fact" in text
    assert "Editor (self-reported): Synthetic correction editor" in text
    assert "Verifier (self-reported): Synthetic test reviewer" in text
    span = payload["corrections"][0]["evidence_spans"][0]
    assert f"Source quotation [{span['start']}:{span['end']}]" in text
    assert "not checked for recency or ordering" in text


def test_supporting_future_iso_date_is_detail_only_in_letter():
    service = ReadinessService()
    note = "OSA. Sleep study completed 2099-12-31. AHI 22."
    payload = {
        "payer": "Aetna",
        "procedure_code": "CPAP_DEVICE",
        "note_text": note,
        "corrections": [
            {
                "requirement_key": "sleep_study_date",
                "action": "SET_VALUE",
                "value": {"value": True, "supporting_date": "2099-12-31"},
                "reason": "incorrect_citation",
                "editor": "Synthetic editor",
                "edited_at": "2026-01-01T00:00:00Z",
                "note_hash": note_hash(note),
                "evidence_spans": [{"start": 5, "end": 36, "text": note[5:36]}],
            }
        ],
    }
    verified = service.evaluate(attest(service.evaluate(PARequest.model_validate(payload))))
    text, meta = service.generate_letter(verified)
    assert verified.overall_status == "READY"
    assert not meta["draft_blocked"]
    assert "Supporting date only: 2099-12-31" in text
    assert "not checked for recency or ordering" in text


def test_documented_api_correction_example_is_executable():
    import re

    text = Path("docs/api.md").read_text()
    payload = json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))
    response = TestClient(api.app).post("/evaluate", json=payload)
    assert response.status_code == 200
    result = EvaluationResult.model_validate(response.json())
    assert result.overall_status == "NOT_READY"
    assert result.facts["osa_diagnosis"] is False
    assert result.original_snapshot.content["facts"]["osa_diagnosis"] is None
