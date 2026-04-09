from fastapi.testclient import TestClient

from api import app
from engine.service import ReadinessService

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Prior Authorization Readiness Copilot"
    assert payload["synthetic_only"] is True


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
    assert payload["sources"][0]["source_name"] == "Aetna CPB 0157"
    assert "freshness_status" in payload["sources"][0]


def test_rulebook_status_endpoint():
    response = client.get("/rulebook")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_release_id"] == "2026-04-09-active-v0.5"
    assert payload["validation_errors"] == []


def test_rulebook_diff_endpoint():
    response = client.get(
        "/rulebook/diff",
        params={
            "from_release_id": "2026-04-09-reviewed-v0.4",
            "to_release_id": "2026-04-09-active-v0.5",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["added_procedures"] == ["MRI_KNEE"]
