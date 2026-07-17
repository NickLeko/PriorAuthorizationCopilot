import json

from scripts.generate_artifacts import main


def test_artifact_generation_writes_enriched_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv("PA_COPILOT_ARTIFACTS_DIR", str(tmp_path))

    exit_code = main()

    assert exit_code == 0
    assert (tmp_path / "MRI-CERV-01-ready.json").exists()
    assert (tmp_path / "MRI-KNEE-01-ready.json").exists()
    assert (tmp_path / "featured_demo_cases.json").exists()
    assert (tmp_path / "status.json").exists()
    assert (tmp_path / "rulebook_status.json").exists()
    assert (tmp_path / "rulebook_diff_reviewed_vs_active.json").exists()
    assert (tmp_path / "drift_report.md").exists()

    evaluation_payload = json.loads((tmp_path / "MRI-01-complete.json").read_text(encoding="utf-8"))
    assert evaluation_payload["audit_trail"]["run_id"] == "__RUN_ID__"
    assert evaluation_payload["audit_trail"]["timestamp_utc"] == "__TIMESTAMP_UTC__"
    assert evaluation_payload["letter"]["metadata"]["generated_timestamp_utc"] == "__TIMESTAMP_UTC__"
    assert evaluation_payload["letter"]["metadata"]["letter_hash_sha256_16"] == "__LETTER_HASH_SHA256_16__"
    assert "Generated: __TIMESTAMP_UTC__" in evaluation_payload["letter"]["text"]
    assert evaluation_payload["metrics"]["extraction_success_rate"] == 100.0
    assert evaluation_payload["metrics"]["compliance_rate"] == 100.0
    assert "fields_extracted_pct" not in evaluation_payload["metrics"]
    assert "documented_requirements_met_pct" not in evaluation_payload["metrics"]
    assert evaluation_payload["request"]["note_text"].endswith("[redacted for repository]")
    assert "Low back pain" not in evaluation_payload["request"]["note_text"]

    refusal_payload = json.loads((tmp_path / "CPAP-02-borderline.json").read_text(encoding="utf-8"))
    assert refusal_payload["overall_status"] == "CANNOT_DETERMINE"
    assert refusal_payload["letter"]["metadata"]["draft_blocked"] is False
    assert refusal_payload["letter"]["metadata"]["contains_missing_documentation"] is True
    assert "Missing Documentation (Checklist):" in refusal_payload["letter"]["text"]

    drift_payload = json.loads((tmp_path / "drift_status.json").read_text(encoding="utf-8"))
    assert drift_payload["sources"][0]["days_since_last_checked"] is None
    assert drift_payload["sources"][0]["status"] == "NO_BASELINE"
    assert drift_payload["sources"][0]["trust_level"] == "unverified"

    registry_payload = json.loads((tmp_path / "supported_procedures.json").read_text(encoding="utf-8"))
    assert any(item["procedure_code"] == "MRI_CERVICAL" for item in registry_payload)
    assert any(item["procedure_code"] == "MRI_KNEE" for item in registry_payload)
    lumbar = next(item for item in registry_payload if item["procedure_code"] == "MRI_LUMBAR")
    assert lumbar["provenance"]["status"] == "unverified"
    assert lumbar["provenance"]["source_url"] is None

    featured_payload = json.loads((tmp_path / "featured_demo_cases.json").read_text(encoding="utf-8"))
    assert any(item["id"] == "MRI-CERV-01-ready" for item in featured_payload)
    assert any(item["id"] == "MRI-KNEE-01-ready" for item in featured_payload)
    assert all(item["note_text"].endswith("[redacted for repository]") for item in featured_payload)

    rulebook_payload = json.loads((tmp_path / "rulebook_status.json").read_text(encoding="utf-8"))
    assert rulebook_payload["active_release_id"] == "2026-07-17-active-v0.6"
