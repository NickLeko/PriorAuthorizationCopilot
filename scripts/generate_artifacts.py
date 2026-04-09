from __future__ import annotations

from engine.rendering import (
    export_evaluation_payload,
    render_drift_markdown,
    render_rulebook_diff_markdown,
    write_json_artifact,
)
from engine.service import ReadinessService

DEFAULT_CASE_IDS = [
    "MRI-01-complete",
    "MRI-08-edge-below-threshold",
    "MRI-CERV-01-ready",
    "MRI-KNEE-01-ready",
    "CPAP-02-borderline",
]


def main() -> int:
    service = ReadinessService()
    artifact_dir = service.config.docs_artifacts_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    drift_report = service.get_drift_status()
    supported_procedures = service.list_supported_procedures()
    demo_cases = service.list_demo_case_summaries()
    rulebook_status = service.get_rulebook_status()
    default_rulebook_diff = service.get_rulebook_diff("2026-04-09-reviewed-v0.4", "2026-04-09-active-v0.5")

    for case_id in DEFAULT_CASE_IDS:
        request = service.get_demo_case_request(case_id)
        evaluation = service.evaluate(request)
        letter_text, letter_meta = service.generate_letter(evaluation)
        write_json_artifact(
            export_evaluation_payload(evaluation, letter_text=letter_text, letter_meta=letter_meta),
            artifact_dir / f"{case_id}.json",
        )

    write_json_artifact(
        drift_report.model_dump(mode="json"),
        artifact_dir / "drift_status.json",
    )
    (artifact_dir / "drift_report.md").write_text(render_drift_markdown(drift_report), encoding="utf-8")
    write_json_artifact(
        [item.model_dump(mode="json") for item in supported_procedures],
        artifact_dir / "supported_procedures.json",
    )
    write_json_artifact(
        [item.model_dump(mode="json") for item in demo_cases],
        artifact_dir / "demo_cases.json",
    )
    write_json_artifact(
        [item.model_dump(mode="json") for item in demo_cases if item.showcase.get("featured")],
        artifact_dir / "featured_demo_cases.json",
    )
    write_json_artifact(
        service.get_status().model_dump(mode="json"),
        artifact_dir / "status.json",
    )
    write_json_artifact(
        rulebook_status.model_dump(mode="json"),
        artifact_dir / "rulebook_status.json",
    )
    write_json_artifact(
        default_rulebook_diff.model_dump(mode="json"),
        artifact_dir / "rulebook_diff_reviewed_vs_active.json",
    )
    (artifact_dir / "rulebook_diff_reviewed_vs_active.md").write_text(
        render_rulebook_diff_markdown(default_rulebook_diff),
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
