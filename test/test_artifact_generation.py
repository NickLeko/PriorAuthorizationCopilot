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
    assert (tmp_path / "safety_metrics.json").exists()
    assert (tmp_path / "rulebook_status.json").exists()
    assert (tmp_path / "rulebook_diff_reviewed_vs_active.json").exists()
    assert (tmp_path / "drift_report.md").exists()

    evaluation_payload = json.loads((tmp_path / "MRI-01-complete.json").read_text(encoding="utf-8"))
    assert evaluation_payload["audit_trail"]["run_id"] == "__RUN_ID__"
    assert evaluation_payload["audit_trail"]["timestamp_utc"] == "__TIMESTAMP_UTC__"
    assert evaluation_payload["letter"]["metadata"]["generated_timestamp_utc"] == "__TIMESTAMP_UTC__"
    assert evaluation_payload["letter"]["metadata"]["letter_hash_sha256_16"] == "__LETTER_HASH_SHA256_16__"
    assert "Generated: __TIMESTAMP_UTC__" in evaluation_payload["letter"]["text"]
    assert evaluation_payload["metrics"]["documentation_coverage_pct"] == 100.0
    assert evaluation_payload["metrics"]["criteria_met_count"] == 4
    assert evaluation_payload["metrics"]["evaluable_requirement_count"] == 4
    assert "compliance_rate" not in evaluation_payload["metrics"]
    assert evaluation_payload["request"]["note_text"].endswith("[redacted for repository]")
    assert "Low back pain" not in evaluation_payload["request"]["note_text"]

    refusal_payload = json.loads((tmp_path / "CPAP-02-borderline.json").read_text(encoding="utf-8"))
    assert refusal_payload["overall_status"] == "CANNOT_DETERMINE"
    assert refusal_payload["letter"]["metadata"]["draft_blocked"] is False
    assert refusal_payload["letter"]["metadata"]["contains_missing_documentation"] is True
    assert "Missing Documentation (Checklist):" in refusal_payload["letter"]["text"]

    drift_payload = json.loads((tmp_path / "drift_status.json").read_text(encoding="utf-8"))
    assert drift_payload["sources"][0]["days_since_last_checked"] == "__DAYS_SINCE_LAST_CHECKED__"
    assert drift_payload["sources"][0]["status"] == "OK"
    assert drift_payload["sources"][0]["trust_level"] == "verified"

    registry_payload = json.loads((tmp_path / "supported_procedures.json").read_text(encoding="utf-8"))
    assert any(item["procedure_code"] == "MRI_CERVICAL" for item in registry_payload)
    assert any(item["procedure_code"] == "MRI_KNEE" for item in registry_payload)
    lumbar = next(item for item in registry_payload if item["procedure_code"] == "MRI_LUMBAR")
    assert lumbar["policy_trust_level"] == "verified"
    assert lumbar["provenance"]["status"] == "verified"
    assert lumbar["provenance"]["policy_identifier"] == "CPB 0236"
    assert lumbar["provenance"]["source_url"] == "https://www.aetna.com/cpb/medical/data/200_299/0236.html"

    safety_metrics = json.loads((tmp_path / "safety_metrics.json").read_text(encoding="utf-8"))
    assert safety_metrics["total_labeled_cases"] == 52
    assert safety_metrics["expected_non_ready_count"] == 52
    assert safety_metrics["exact_status_correct_count"] == 52
    assert safety_metrics["false_ready_count"] == 0
    assert safety_metrics["abstention_count"] == 42

    featured_payload = json.loads((tmp_path / "featured_demo_cases.json").read_text(encoding="utf-8"))
    assert any(item["id"] == "MRI-CERV-01-ready" for item in featured_payload)
    assert any(item["id"] == "MRI-KNEE-01-ready" for item in featured_payload)
    assert all(item["note_text"].endswith("[redacted for repository]") for item in featured_payload)

    rulebook_payload = json.loads((tmp_path / "rulebook_status.json").read_text(encoding="utf-8"))
    assert rulebook_payload["active_release_id"] == "2026-08-22-active-v1.0"
