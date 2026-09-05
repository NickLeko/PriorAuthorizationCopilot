from pathlib import Path

import pytest

from engine.provenance import (
    get_provenance_entry,
    load_provenance,
    normalized_dx_codes,
    policy_trust_from_provenance,
)
from engine.rules_loader import load_rules
from engine.schemas import RequirementDefinition
from engine.test_suites import run_cases, summarize_safety_metrics


def test_rules_loader_rejects_enum_without_allowed_values(tmp_path: Path):
    rules_path = tmp_path / "bad_rules.yaml"
    rules_path.write_text(
        """
version: 1
payers:
  Aetna:
    procedures:
      MRI_LUMBAR:
        display_name: "MRI Lumbar Spine"
        required:
          - key: prior_imaging_result
            label: "Prior imaging result"
            type: enum
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="allowed must be a non-empty list"):
        load_rules(str(rules_path))


def test_rules_loader_rejects_unknown_requirement_type(tmp_path: Path):
    rules_path = tmp_path / "bad_rules_type.yaml"
    rules_path.write_text(
        """
version: 1
payers:
  Aetna:
    procedures:
      MRI_LUMBAR:
        display_name: "MRI Lumbar Spine"
        required:
          - key: symptom_duration_weeks
            label: "Symptom duration"
            type: free_text
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="type must be one of"):
        load_rules(str(rules_path))


def test_rules_loader_rejects_operator_incompatible_with_type(tmp_path: Path):
    rules_path = tmp_path / "bad_rules_operator.yaml"
    rules_path.write_text(
        """
version: 1
payers:
  Aetna:
    procedures:
      CPAP_DEVICE:
        display_name: "CPAP"
        required:
          - key: osa_diagnosis
            label: "OSA diagnosis"
            type: boolean
            operator: minimum
            min: 1
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="incompatible with type"):
        load_rules(str(rules_path))


def test_rules_loader_rejects_invalid_metadata(tmp_path: Path):
    rules_path = tmp_path / "bad_rules_metadata.yaml"
    rules_path.write_text(
        """
version: 1
payers:
  Aetna:
    procedures:
      MRI_CERVICAL:
        display_name: "MRI Cervical Spine"
        metadata:
          category: ""
          rule_family: "spine_mri_conservative_therapy"
          summary: "Test summary"
        required:
          - key: symptom_duration_weeks
            label: "Symptom duration"
            type: number
            min: 6
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="metadata.category must be a non-empty string"):
        load_rules(str(rules_path))


def test_provenance_loader_defaults_missing_file_to_empty_mapping(tmp_path: Path):
    missing_path = tmp_path / "missing_provenance.yaml"
    loaded = load_provenance(missing_path)

    assert loaded == {}
    assert get_provenance_entry(loaded, "Aetna", "MRI_LUMBAR") == {}
    assert policy_trust_from_provenance({}) == "demo"


def test_verified_official_policy_provenance_maps_to_verified():
    provenance_data = {
        "sources": {
            "Aetna": {
                "MRI_LUMBAR": {
                    "source_type": "official_policy_web",
                    "source_name": "Aetna CPB 0236",
                    "status": "verified",
                    "source_url": "https://www.aetna.com/cpb/medical/data/200_299/0236.html",
                    "policy_identifier": "CPB 0236",
                    "policy_title": "MRI and CT of the Spine",
                    "policy_effective_date": "1998-05-06",
                    "policy_last_reviewed": "2026-04-09",
                    "accessed_date": "2026-08-22",
                    "content_hash_sha256": "a" * 64,
                    "monitored_source_id": "aetna_mri_lumbar",
                    "last_reviewed": "2026-08-22",
                    "rule_last_updated": "2026-08-22",
                    "requirement_clause_map": {"criterion": "Policy > Medical Necessity > criterion"},
                }
            }
        }
    }

    entry = get_provenance_entry(provenance_data, "Aetna", "MRI_LUMBAR")

    assert entry["source_type"] == "official_policy_web"
    assert policy_trust_from_provenance(entry, ["criterion"]) == "verified"


def test_verified_label_without_complete_clause_mapping_remains_demo():
    entry = {
        "source_type": "official_policy_web",
        "source_name": "Aetna CPB 0236",
        "status": "verified",
    }

    assert policy_trust_from_provenance(entry) == "demo"


@pytest.mark.parametrize("status", [None, "unverified", "stale", "review_required"])
def test_official_policy_source_without_verified_status_remains_demo(status):
    entry = {"source_type": "official_policy_web"}
    if status is not None:
        entry["status"] = status

    assert policy_trust_from_provenance(entry) == "demo"


@pytest.mark.parametrize(
    "rules_path",
    [
        "rules/payer_rules.yaml",
        "rulebook/releases/2026-08-22-active-v1.0/payer_rules.yaml",
    ],
)
def test_current_bundled_rules_use_explicit_requirement_operators(rules_path):
    rules = load_rules(rules_path)

    for payer in rules["payers"].values():
        for procedure in payer["procedures"].values():
            assert all(requirement.get("operator") for requirement in procedure["required"])


def test_requirement_definition_legacy_boolean_fallback_is_conservative():
    requirement = RequirementDefinition(key="legacy_flag", label="Legacy flag", type="boolean")

    assert requirement.operator == "equals_true"


def test_bundled_provenance_contains_rule_source_metadata():
    provenance = load_provenance("rules/provenance.yaml")
    entry = get_provenance_entry(provenance, "Aetna", "MRI_CERVICAL")

    assert entry["rule_source_label"] == "Human-curated summary of cervical spine MRI administrative criteria"
    assert entry["rule_last_updated"] == "2026-04-09"

    knee_entry = get_provenance_entry(provenance, "Aetna", "MRI_KNEE")
    assert knee_entry["rule_source_label"] == "Human-curated summary of knee MRI administrative documentation criteria"

    lumbar_entry = get_provenance_entry(provenance, "Aetna", "MRI_LUMBAR")
    assert lumbar_entry["status"] == "verified"
    assert lumbar_entry["policy_identifier"] == "CPB 0236"
    assert set(lumbar_entry["requirement_clause_map"]) == {
        "back_pain_with_radiculopathy",
        "objective_motor_or_reflex_change_in_root_distribution",
        "cpb_0236_conservative_therapy_weeks",
        "cpb_0236_conservative_therapy_no_improvement",
    }


def test_normalized_dx_codes_are_uppercase_deduped_and_sanitized():
    dx_codes = [" m54.5 ", "M54.5", "m%51.26", "", "  "]

    assert normalized_dx_codes(dx_codes) == ["M54.5", "M51.26"]


def test_bundled_synthetic_eval_cases_match_expected_labels():
    rows = run_cases("rules/payer_rules.yaml", "inputs/synthetic_cases.json")
    metrics = summarize_safety_metrics(rows)

    assert rows
    assert all(row["pass"] == "✅" for row in rows)
    assert all(row["expected"] for row in rows)
    assert metrics["total_labeled_cases"] == 52
    assert metrics["expected_non_ready_count"] == 52
    assert metrics["exact_overall_status_accuracy_pct"] == 100.0
    assert metrics["false_ready_count"] == 0
    assert metrics["false_ready_rate_pct"] == 0.0
    assert metrics["needs_review_count"] == 12
    assert metrics["abstention_count"] == 42
