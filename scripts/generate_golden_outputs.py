from __future__ import annotations

from pathlib import Path

from engine.acceptance import (
    DEFAULT_ACCEPTANCE_CASE_IDS,
    build_acceptance_evaluation_payload,
    build_acceptance_governance_payloads,
    build_corrected_acceptance_payloads,
)
from engine.rendering import write_json_artifact
from engine.service import ReadinessService

GOLDEN_ROOT = Path("test/golden")


def main(*, utc_now_provider=None) -> int:
    service = ReadinessService(utc_now_provider=utc_now_provider)
    evaluation_dir = GOLDEN_ROOT / "evaluations"
    governance_dir = GOLDEN_ROOT / "governance"

    for case_id in DEFAULT_ACCEPTANCE_CASE_IDS:
        write_json_artifact(
            build_acceptance_evaluation_payload(service, case_id),
            evaluation_dir / f"{case_id}.json",
        )

    for name, payload in build_acceptance_governance_payloads(service).items():
        write_json_artifact(payload, governance_dir / f"{name}.json")

    for name, payload in build_corrected_acceptance_payloads(service).items():
        write_json_artifact(payload, evaluation_dir / f"{name}.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
