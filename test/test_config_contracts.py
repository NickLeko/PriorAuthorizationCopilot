from pathlib import Path

import pytest

from engine.provenance import (
    get_provenance_entry,
    load_provenance,
    normalized_dx_codes,
    policy_trust_from_provenance,
)
from engine.rules_loader import load_rules
from engine.test_suites import run_cases


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


def test_provenance_loader_defaults_missing_file_to_empty_mapping(tmp_path: Path):
    missing_path = tmp_path / "missing_provenance.yaml"
    loaded = load_provenance(missing_path)

    assert loaded == {}
    assert get_provenance_entry(loaded, "Aetna", "MRI_LUMBAR") == {}
    assert policy_trust_from_provenance({}) == "demo"


def test_official_policy_provenance_maps_to_verified():
    provenance_data = {
        "sources": {
            "Aetna": {
                "MRI_LUMBAR": {
                    "source_type": "official_policy_web",
                    "source_name": "Aetna CPB 0157",
                }
            }
        }
    }

    entry = get_provenance_entry(provenance_data, "Aetna", "MRI_LUMBAR")

    assert entry["source_type"] == "official_policy_web"
    assert policy_trust_from_provenance(entry) == "verified"


def test_normalized_dx_codes_are_uppercase_deduped_and_sanitized():
    dx_codes = [" m54.5 ", "M54.5", "m%51.26", "", "  "]

    assert normalized_dx_codes(dx_codes) == ["M54.5", "M51.26"]


def test_bundled_synthetic_eval_cases_match_expected_labels():
    rows = run_cases("rules/payer_rules.yaml", "inputs/synthetic_cases.json")

    assert rows
    assert all(row["pass"] == "✅" for row in rows)
