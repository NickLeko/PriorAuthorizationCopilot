import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from conftest import GOVERNANCE_NOW
from verification_helpers import attest

from engine.config import load_app_config
from engine.service import ReadinessService


def snapshot_service(tmp_path, checked_at):
    config = load_app_config()
    snapshot = json.loads((config.snapshot_root / "aetna_mri_lumbar/latest.json").read_text())
    snapshot["fetched_at_utc"] = checked_at.isoformat()
    snapshot["last_checked_utc"] = checked_at.isoformat()
    directory = tmp_path / "aetna_mri_lumbar"
    directory.mkdir()
    (directory / "latest.json").write_text(json.dumps(snapshot))
    return ReadinessService(config.model_copy(update={"snapshot_root": tmp_path}), utc_now_provider=lambda: GOVERNANCE_NOW)


@pytest.mark.parametrize("offset,expected", [(-1, "CURRENT"), (0, "CURRENT"), (1, "STALE")])
def test_monthly_freshness_strict_boundary(tmp_path, offset, expected):
    service = snapshot_service(tmp_path, GOVERNANCE_NOW - timedelta(days=35, seconds=offset))
    report = service.get_drift_status()
    assert report.sources[0].freshness_status == expected
    assert report.any_review_required is (expected == "STALE")
    result = service.evaluate(attest(service.evaluate(service.get_demo_case_request("MRI-01-complete"))))
    assert result.overall_status == "READY"
    assert result.submission_readiness is (expected == "CURRENT")


def test_future_snapshot_rejected_relative_to_fixed_clock(tmp_path):
    service = snapshot_service(tmp_path, GOVERNANCE_NOW + timedelta(seconds=301))
    report = service.get_drift_status()
    assert report.sources[0].status == "INVALID_SNAPSHOT"
    assert report.sources[0].freshness_status == "INVALID"
    assert "future timestamp" in report.sources[0].review_reason
    result = service.evaluate(attest(service.evaluate(service.get_demo_case_request("MRI-01-complete"))))
    assert result.overall_status == "READY"
    assert result.submission_readiness is False


def test_stale_snapshot_and_malformed_log_report_both_reasons(tmp_path):
    service = snapshot_service(tmp_path, GOVERNANCE_NOW - timedelta(days=35, seconds=1))
    (tmp_path / "drift_log.jsonl").write_text("not-json\n")
    report = service.get_drift_status()
    source = report.sources[0]
    assert source.status == "INVALID_DRIFT_LOG"
    assert source.freshness_status == "STALE"
    assert "not valid JSON" in source.review_reason
    assert "Last successful policy check exceeds" in source.review_reason
    assert report.any_review_required
    result = service.evaluate(attest(service.evaluate(service.get_demo_case_request("MRI-01-complete"))))
    assert result.policy_trust_level == "demo"
    assert result.submission_readiness is False


def test_default_clock_is_real_outside_pytest():
    before = datetime.now(timezone.utc)
    # A separate process has no conftest injection and uses the runtime default.
    output = subprocess.check_output(
        [
            sys.executable,
            "-B",
            "-c",
            "from engine.service import ReadinessService; print(ReadinessService()._utc_now().isoformat())",
        ],
        text=True,
    )
    after = datetime.now(timezone.utc)
    actual = datetime.fromisoformat(output.strip())
    assert before <= actual <= after
