from engine.service import ReadinessService


def test_rulebook_status_is_valid_and_matches_runtime():
    service = ReadinessService()

    report = service.get_rulebook_status()

    assert report.active_release_id == "2026-07-17-active-v0.6"
    assert report.runtime_rules_version == "0.6"
    assert not report.validation_errors
    active = next(item for item in report.releases if item.release_id == report.active_release_id)
    assert active.runtime_matches is True
    assert active.files.rules_path == "rulebook/releases/2026-07-17-active-v0.6/payer_rules.yaml"
    assert active.files.provenance_path == "rulebook/releases/2026-07-17-active-v0.6/provenance.yaml"


def test_rulebook_diff_highlights_new_knee_pathway():
    service = ReadinessService()

    report = service.get_rulebook_diff("2026-04-09-reviewed-v0.4", "2026-07-17-active-v0.6")

    assert report.rules_version_from == "0.4"
    assert report.rules_version_to == "0.6"
    assert report.added_procedures == ["MRI_KNEE"]
    assert not report.removed_procedures
    assert "MRI_KNEE" in report.changed_provenance
