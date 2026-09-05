import json
from pathlib import Path

from cli import main
from engine.service import ReadinessService
from engine.test_suites import run_cases, summarize_safety_metrics

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_reviewer_docs_include_quick_path_scope_and_artifact_guidance():
    readme = _read("README.md")
    guide = _read("docs/reviewer_guide.md")
    artifacts_readme = _read("docs/artifacts/README.md")

    for text in (readme, guide):
        assert "Quick Reviewer Path" in text
        assert "make install PYTHON=python3.12" in text
        assert "make reviewer-demo" in text
        assert "make acceptance" in text
        assert "synthetic" in text.lower()
        assert "does not" in text.lower()
        assert "payer approval" in text.lower()
        assert "medical necessity" in text.lower()
        assert "CANNOT_DETERMINE" in text

    assert "docs/artifacts/MRI-01-complete.json" in guide
    assert "docs/artifacts/MRI-08-edge-below-threshold.json" in guide
    assert "docs/artifacts/CPAP-02-borderline.json" in guide
    assert "/tmp/pa-copilot-reviewer-demo.json" in readme
    assert "/tmp/pa-copilot-reviewer-demo.json" in artifacts_readme


def test_documented_fixture_metrics_match_the_bundled_labeled_suite():
    metrics = summarize_safety_metrics(run_cases("rules/payer_rules.yaml", "inputs/synthetic_cases.json"))
    expected_claims = [
        f"{metrics['exact_status_correct_count']}/{metrics['total_labeled_cases']} exact overall statuses",
        (f"{metrics['false_ready_count']} false `READY` results among {metrics['expected_non_ready_count']} expected non-`READY` cases"),
        f"{metrics['needs_review_count']} `NEEDS_REVIEW` results ({metrics['needs_review_rate_pct']:.1f}%)",
    ]

    for path in ("README.md", "docs/testing.md", "docs/reviewer_guide.md"):
        text = _read(path)
        assert all(claim in text for claim in expected_claims)


def test_reviewer_demo_cases_preserve_status_meanings_and_audit_fields():
    service = ReadinessService()

    ready = service.evaluate(service.get_demo_case_request("MRI-01-complete"))
    assert ready.overall_status == "PENDING_VERIFICATION"
    assert ready.submission_readiness is False
    assert not ready.blockers.not_documented
    assert not ready.blockers.not_met
    assert ready.evidence_map["cpb_0236_conservative_therapy_weeks"]
    assert ready.audit_trail.rules_version == "1.0"
    assert ready.audit_trail.rulebook_active_release_id == "2026-08-22-active-v1.0"
    assert ready.policy_trust_level == "verified"
    assert ready.audit_trail.note_hash

    not_ready = service.evaluate(service.get_demo_case_request("MRI-08-edge-below-threshold"))
    assert not_ready.overall_status == "NOT_READY"
    assert not_ready.submission_readiness is False
    assert not not_ready.blockers.not_documented
    assert {blocker.key for blocker in not_ready.blockers.not_met} == {"cpb_0236_conservative_therapy_weeks"}

    cannot_determine = service.evaluate(service.get_demo_case_request("CPAP-02-borderline"))
    assert cannot_determine.overall_status == "CANNOT_DETERMINE"
    assert cannot_determine.submission_readiness is False
    assert {blocker.key for blocker in cannot_determine.blockers.not_documented} == {
        "sleep_study_date",
        "ahi_documented",
    }
    assert cannot_determine.evidence_map["ahi_documented"][0].text == "AHI not documented"
    assert cannot_determine.policy_trust_level == "demo"
    assert any("Policy trust remains DEMO" in warning for warning in cannot_determine.warnings)


def test_documented_reviewer_export_command_writes_inspectable_missing_info_artifact(tmp_path: Path, capsys):
    output_path = tmp_path / "pa-copilot-reviewer-demo.json"

    exit_code = main(
        [
            "export-report",
            "--demo-case",
            "CPAP-02-borderline",
            "--output",
            str(output_path),
            "--with-letter",
            "--letter-type",
            "missing_info_request",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(output_path) in captured.out

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "CANNOT_DETERMINE"
    assert payload["submission_readiness"] is False
    assert payload["blockers"]["not_documented"]
    assert payload["audit_trail"]["note_hash"]
    assert payload["audit_trail"]["requirements_checked"] == [
        "osa_diagnosis",
        "sleep_study_date",
        "ahi_documented",
    ]
    assert payload["letter"]["metadata"]["draft_blocked"] is False
    assert payload["letter"]["metadata"]["contains_missing_documentation"] is True
    assert "Missing Documentation (Checklist):" in payload["letter"]["text"]
    assert "does not guarantee payer approval" in payload["letter"]["text"]
