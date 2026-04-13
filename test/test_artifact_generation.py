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

    drift_payload = json.loads((tmp_path / "drift_status.json").read_text(encoding="utf-8"))
    assert drift_payload["sources"][0]["days_since_last_checked"] == "__DAYS_SINCE_LAST_CHECKED__"

    registry_payload = json.loads((tmp_path / "supported_procedures.json").read_text(encoding="utf-8"))
    assert any(item["procedure_code"] == "MRI_CERVICAL" for item in registry_payload)
    assert any(item["procedure_code"] == "MRI_KNEE" for item in registry_payload)

    featured_payload = json.loads((tmp_path / "featured_demo_cases.json").read_text(encoding="utf-8"))
    assert any(item["id"] == "MRI-CERV-01-ready" for item in featured_payload)
    assert any(item["id"] == "MRI-KNEE-01-ready" for item in featured_payload)

    rulebook_payload = json.loads((tmp_path / "rulebook_status.json").read_text(encoding="utf-8"))
    assert rulebook_payload["active_release_id"] == "2026-04-09-active-v0.5"
