import json

import pytest
from fastapi.testclient import TestClient

import api
from api import app
from engine.service import ReadinessService

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Prior Authorization Readiness Copilot"
    assert payload["app_version"] == "2.7.0"
    assert "synthetic_only" not in payload


def test_supported_procedures_endpoint():
    response = client.get("/supported-procedures")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["procedure_code"] == "MRI_LUMBAR" for item in payload)
    assert any(item["procedure_code"] == "MRI_CERVICAL" for item in payload)
    assert any(item["procedure_code"] == "MRI_KNEE" for item in payload)
    cervical = next(item for item in payload if item["procedure_code"] == "MRI_CERVICAL")
    assert cervical["metadata"]["category"] == "advanced_imaging"
    assert cervical["provenance"]["rule_source_label"] == "Human-curated summary of cervical spine MRI administrative criteria"
    knee = next(item for item in payload if item["procedure_code"] == "MRI_KNEE")
    assert knee["metadata"]["rule_family"] == "extremity_mri_conservative_therapy"


def test_evaluate_endpoint_matches_service_behavior():
    service = ReadinessService()
    request = service.get_demo_case_request("MRI-08-edge-below-threshold")

    response = client.post("/evaluate", json=request.model_dump(mode="json"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] == "NOT_READY"
    assert payload["submission_readiness"] is False
    assert payload["blockers"]["not_met"]


def test_evaluate_endpoint_rejects_unsupported_scope():
    response = client.post(
        "/evaluate",
        json={
            "payer": "Aetna",
            "procedure_code": "UNKNOWN_PROC",
            "dx_codes": ["Z00.00"],
            "site_of_care": "outpatient",
            "specialty": "Primary Care",
            "note_text": "Synthetic note.",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "unsupported_scope"


def test_drift_status_endpoint():
    response = client.get("/drift-status")

    assert response.status_code == 200
    payload = response.json()
    assert "sources" in payload
    assert payload["sources"][0]["source_name"].startswith("Aetna CPB 0236")
    assert "freshness_status" in payload["sources"][0]


def test_rulebook_status_endpoint():
    response = client.get("/rulebook")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_release_id"] == "2026-08-22-active-v1.0"
    assert payload["validation_errors"] == []


def test_rulebook_diff_endpoint():
    response = client.get(
        "/rulebook/diff",
        params={
            "from_release_id": "2026-04-09-reviewed-v0.4",
            "to_release_id": "2026-08-22-active-v1.0",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["added_procedures"] == ["Aetna:MRI_KNEE"]


PRIVATE_MARKER = "SYNTHETIC_PRIVATE_NOTE_DO_NOT_REFLECT"


def invalid_correction_request():
    return {
        "payer": "Aetna",
        "procedure_code": "CPAP_DEVICE",
        "note_text": PRIVATE_MARKER,
        "corrections": [
            {
                "requirement_key": "osa_diagnosis",
                "action": "SET_VALUE",
                "value": True,
                "reason": "incorrect_value",
                "editor": "Synthetic reviewer",
                "edited_at": "2026-01-01T00:00:00Z",
                "note_hash": "0" * 64,
                "evidence_spans": [{"start": 0, "end": 3, "text": PRIVATE_MARKER[:3]}],
            }
        ],
    }


@pytest.mark.parametrize("model_level", [False, True])
def test_validation_errors_never_serialize_submitted_input_or_context(model_level):
    payload = (
        invalid_correction_request()
        if model_level
        else {"payer": "Aetna", "procedure_code": "CPAP_DEVICE", "note_text": PRIVATE_MARKER + " 1234567"}
    )
    response = client.post("/evaluate", json=payload)

    assert response.status_code == 422
    assert response.json() == {
        "error": "invalid_request",
        "detail": [{"type": "value_error", "loc": ["body"] if model_level else ["body", "note_text"], "msg": "Invalid request."}],
    }
    assert PRIVATE_MARKER not in response.text


@pytest.mark.parametrize("depth", [600, 1200, 6000])
def test_deep_invalid_json_returns_controlled_client_error(depth):
    # Keep TestClient's default exception propagation: an unhandled failure must fail the test.
    raw = "[" * depth + json.dumps(PRIVATE_MARKER) + "]" * depth
    response = client.post("/evaluate", content=raw, headers={"Content-Type": "application/json"})

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
    assert response.json()["detail"][0]["type"] in {"model_attributes_type", "json_invalid"}
    assert response.json()["detail"][0]["loc"] == ["body"]
    assert PRIVATE_MARKER not in response.text


@pytest.mark.parametrize("key", [PRIVATE_MARKER, "reviewer"])
def test_validation_locations_redact_dictionary_keys_even_when_they_are_field_names(key):
    response = client.post(
        "/evaluate",
        json={
            "payer": "Aetna",
            "procedure_code": "CPAP_DEVICE",
            "fact_verifications": {key: {"state": PRIVATE_MARKER}},
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == [
        {"type": "literal_error", "loc": ["body", "fact_verifications", "<key>", "state"], "msg": "Invalid request."}
    ]
    assert PRIVATE_MARKER not in response.text


def test_validation_locations_preserve_nested_fields_and_indices_but_redact_extra_fields():
    payload = invalid_correction_request()
    del payload["corrections"][0]["edited_at"]
    payload["corrections"][0][PRIVATE_MARKER * 100] = PRIVATE_MARKER
    response = client.post("/evaluate", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == [
        {"type": "missing", "loc": ["body", "corrections", 0, "edited_at"], "msg": "Invalid request."},
        {"type": "extra_forbidden", "loc": ["body", "corrections", 0, "<field>"], "msg": "Invalid request."},
    ]
    assert PRIVATE_MARKER not in response.text


def test_validation_error_output_is_bounded_for_many_invalid_items():
    response = client.post("/evaluate", json={"payer": "Aetna", "procedure_code": "CPAP_DEVICE", "dx_codes": [None] * 2000})

    assert response.status_code == 422
    assert len(response.json()["detail"]) == 20
    assert response.json()["detail"][0]["loc"] == ["body", "dx_codes", 0]
    assert len(response.content) < 4096


def test_malformed_json_does_not_expose_parser_context_or_body():
    response = client.post(
        "/evaluate", content='{"note_text": "' + PRIVATE_MARKER + '", "payer": }', headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": "invalid_request",
        "detail": [{"type": "json_invalid", "loc": ["body"], "msg": "Invalid request."}],
    }
    assert PRIVATE_MARKER not in response.text


def test_missing_query_parameter_keeps_declared_location_without_echoing_other_values():
    response = client.get("/rulebook/diff", params={"from_release_id": PRIVATE_MARKER})

    assert response.status_code == 422
    assert response.json()["detail"] == [{"type": "missing", "loc": ["query", "to_release_id"], "msg": "Invalid request."}]
    assert PRIVATE_MARKER not in response.text


@pytest.mark.parametrize("failure", [RecursionError, ValueError])
def test_decoder_limit_errors_are_controlled_without_returning_exception_messages(monkeypatch, failure):
    def reject_number(_):
        raise failure(PRIVATE_MARKER)

    monkeypatch.setattr(api, "finite_json_number", reject_number)
    response = client.post("/evaluate", content='{"value": 1.0}', headers={"Content-Type": "application/json"})

    assert response.status_code == 422
    assert response.json() == {
        "error": "invalid_request",
        "detail": [{"type": "json_invalid", "loc": ["body"], "msg": "Invalid request."}],
    }
    assert PRIVATE_MARKER not in response.text


@pytest.mark.parametrize("unsupported_scope", [False, True])
def test_service_client_errors_preserve_status_and_code_without_reflecting_values(unsupported_scope):
    payload = {"payer": "Aetna", "procedure_code": "CPAP_DEVICE", "note_text": PRIVATE_MARKER}
    if unsupported_scope:
        payload["procedure_code"] = PRIVATE_MARKER
    else:
        payload["fact_verifications"] = {PRIVATE_MARKER: {"state": "UNVERIFIED"}}
    response = client.post("/evaluate", json=payload)

    assert response.status_code == (422 if unsupported_scope else 400)
    assert response.json()["error"] == ("unsupported_scope" if unsupported_scope else "invalid_request")
    assert PRIVATE_MARKER not in response.text
