from pathlib import Path

from engine import rulebook
from engine.rules_loader import load_rules
from engine.service import ReadinessService


def test_rulebook_status_is_valid_and_matches_runtime():
    service = ReadinessService()

    report = service.get_rulebook_status()

    assert report.active_release_id == "2026-08-22-active-v1.0"
    assert report.runtime_rules_version == "1.0"
    assert not report.validation_errors
    active = next(item for item in report.releases if item.release_id == report.active_release_id)
    assert active.runtime_matches is True
    assert active.files.rules_path == "rulebook/releases/2026-08-22-active-v1.0/payer_rules.yaml"
    assert active.files.provenance_path == "rulebook/releases/2026-08-22-active-v1.0/provenance.yaml"


def test_rulebook_diff_highlights_new_knee_pathway():
    service = ReadinessService()

    report = service.get_rulebook_diff("2026-04-09-reviewed-v0.4", "2026-08-22-active-v1.0")

    assert report.rules_version_from == "0.4"
    assert report.rules_version_to == "1.0"
    assert report.added_procedures == ["Aetna:MRI_KNEE"]
    assert not report.removed_procedures
    assert "Aetna:MRI_KNEE" in report.changed_provenance


def test_v08_diff_is_limited_to_normal_imaging_support():
    service = ReadinessService()

    report = service.get_rulebook_diff("2026-08-21-active-v0.7", "2026-08-22-active-v0.8")

    assert report.added_procedures == []
    assert report.removed_procedures == []
    assert report.changed_procedures == ["Aetna:MRI_CERVICAL", "Aetna:MRI_KNEE", "Aetna:MRI_LUMBAR"]
    assert report.changed_provenance == []
    assert report.changed_policy_sources == []


def test_v09_diff_only_adds_negative_to_mri_imaging_rules():
    service = ReadinessService()

    report = service.get_rulebook_diff("2026-08-22-active-v0.8", "2026-08-22-active-v0.9")

    assert report.added_procedures == []
    assert report.removed_procedures == []
    assert report.changed_procedures == ["Aetna:MRI_CERVICAL", "Aetna:MRI_KNEE", "Aetna:MRI_LUMBAR"]
    assert report.changed_provenance == []
    assert report.changed_policy_sources == []

    v09_rules = load_rules("rulebook/releases/2026-08-22-active-v0.9/payer_rules.yaml")
    for procedure_code in ("MRI_CERVICAL", "MRI_KNEE", "MRI_LUMBAR"):
        requirements = v09_rules["payers"]["Aetna"]["procedures"][procedure_code]["required"]
        imaging_requirement = next(item for item in requirements if item["key"] == "prior_imaging_result")
        assert imaging_requirement["operator"] == "one_of"
        assert "negative" in imaging_requirement["allowed"]


def test_v10_diff_is_scoped_to_verified_lumbar_policy_and_cervical_boundary_wording():
    service = ReadinessService()

    report = service.get_rulebook_diff("2026-08-22-active-v0.9", "2026-08-22-active-v1.0")

    assert report.added_procedures == []
    assert report.removed_procedures == []
    assert report.changed_procedures == ["Aetna:MRI_CERVICAL", "Aetna:MRI_LUMBAR"]
    assert report.changed_provenance == ["Aetna:MRI_CERVICAL", "Aetna:MRI_LUMBAR"]
    assert report.changed_policy_sources == ["aetna_mri_lumbar"]


def test_rulebook_diff_keeps_same_procedure_code_distinct_across_payers(monkeypatch):
    from_rules = {
        "version": "1",
        "payers": {
            "Aetna": {"procedures": {"SHARED_CODE": {"required": [{"key": "a"}]}}},
            "Cigna": {"procedures": {"SHARED_CODE": {"required": [{"key": "b"}]}}},
        },
    }
    to_rules = {
        "version": "2",
        "payers": {
            "Aetna": {"procedures": {"SHARED_CODE": {"required": [{"key": "a"}]}}},
            "Cigna": {"procedures": {"SHARED_CODE": {"required": [{"key": "changed"}]}}},
        },
    }
    manifest = {
        "stages": {"draft": None, "reviewed": "from", "active": "to"},
        "releases": {"from": {"bundle": "from", "stage": "reviewed"}, "to": {"bundle": "to", "stage": "active"}},
    }

    monkeypatch.setattr(rulebook, "load_rulebook_manifest", lambda _: manifest)
    monkeypatch.setattr(
        rulebook,
        "_load_release_bundle",
        lambda _root, raw: (None, from_rules if raw["bundle"] == "from" else to_rules, {}, {"sources": []}),
    )

    report = rulebook.get_rulebook_diff(Path("."), Path("manifest.yaml"), "from", "to")

    assert report.added_procedures == []
    assert report.removed_procedures == []
    assert report.changed_procedures == ["Cigna:SHARED_CODE"]
