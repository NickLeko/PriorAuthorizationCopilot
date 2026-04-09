import json
from pathlib import Path

from engine.acceptance import (
    DEFAULT_ACCEPTANCE_CASE_IDS,
    build_acceptance_evaluation_payload,
    build_acceptance_governance_payloads,
)
from engine.service import ReadinessService

GOLDEN_ROOT = Path("test/golden")


def test_acceptance_evaluation_snapshots_match_goldens():
    service = ReadinessService()

    for case_id in DEFAULT_ACCEPTANCE_CASE_IDS:
        expected = json.loads((GOLDEN_ROOT / "evaluations" / f"{case_id}.json").read_text(encoding="utf-8"))
        actual = build_acceptance_evaluation_payload(service, case_id)
        assert actual == expected


def test_acceptance_governance_snapshots_match_goldens():
    service = ReadinessService()
    expected_payloads = {
        "drift_status": json.loads((GOLDEN_ROOT / "governance" / "drift_status.json").read_text(encoding="utf-8")),
        "rulebook_status": json.loads((GOLDEN_ROOT / "governance" / "rulebook_status.json").read_text(encoding="utf-8")),
        "rulebook_diff_reviewed_vs_active": json.loads(
            (GOLDEN_ROOT / "governance" / "rulebook_diff_reviewed_vs_active.json").read_text(encoding="utf-8")
        ),
    }

    actual_payloads = build_acceptance_governance_payloads(service)
    assert actual_payloads == expected_payloads
