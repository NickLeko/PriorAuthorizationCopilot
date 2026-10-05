import json
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from engine.extract import extract_facts
from engine.fact_contracts import (
    FACT_CONTRACTS,
    DatePresence,
    FactContract,
    FactContractError,
    check_policy_compatibility,
    get_fact_contract,
    validate_fact_value,
)
from engine.schemas import REVIEW_REQUIRED_FACT

POLICY_FILES = [Path("rules/payer_rules.yaml"), *sorted(Path("rulebook/releases").glob("*/payer_rules.yaml"))]
PATHWAYS = {"MRI_LUMBAR", "MRI_CERVICAL", "MRI_KNEE", "CPAP_DEVICE"}


def requirements_from(path):
    rules = yaml.safe_load(path.read_text())
    for payer in rules["payers"].values():
        for procedure, policy in payer["procedures"].items():
            assert procedure in PATHWAYS
            yield from policy["required"]


def test_registry_covers_every_current_and_historical_requirement():
    keys = {requirement["key"] for path in POLICY_FILES for requirement in requirements_from(path)}
    assert keys == set(FACT_CONTRACTS)
    assert set(extract_facts("")[0]) == keys
    assert len(keys) == 12


@pytest.mark.parametrize("path", POLICY_FILES, ids=str)
def test_every_policy_is_contract_compatible(path):
    check_policy_compatibility(requirements_from(path))


def test_registry_and_contracts_are_immutable():
    with pytest.raises(TypeError):
        FACT_CONTRACTS["new_key"] = FactContract("new_key", "boolean")
    with pytest.raises(FrozenInstanceError):
        get_fact_contract("symptom_duration_weeks").unit = "months"


def test_missing_contract_is_an_error():
    with pytest.raises(FactContractError, match="missing_fact_contract"):
        get_fact_contract("unknown_requirement")
    with pytest.raises(FactContractError, match="missing_fact_contract"):
        check_policy_compatibility([{"key": "unknown_requirement", "label": "Unknown", "type": "boolean", "operator": "documented"}])


@pytest.mark.parametrize("kind", ["boolean", "duration_weeks", "numeric", "enum", "date_presence"])
def test_state_permissions_are_separate_from_captured_scalars(kind):
    unit = "weeks" if kind == "duration_weeks" else "dimensionless" if kind == "numeric" else None
    vocabulary = ("normal",) if kind == "enum" else ()
    contract = FactContract("test", kind, unit=unit, captured_values=vocabulary)
    assert contract.permitted_states == ("CAPTURED", "MISSING", "NEEDS_REVIEW")
    assert FactContract("test", kind, unit, vocabulary, False, False).permitted_states == ("CAPTURED",)
    for state_value in (None, REVIEW_REQUIRED_FACT):
        with pytest.raises(FactContractError):
            validate_fact_value(contract, state_value)


@pytest.mark.parametrize("value", [True, False])
def test_boolean_accepts_exact_booleans(value):
    assert validate_fact_value(get_fact_contract("osa_diagnosis"), value) is value


@pytest.mark.parametrize("value", ["true", "false", "True", 0, 1, 1.0, {}, [], None])
def test_boolean_rejects_coercion(value):
    with pytest.raises(FactContractError, match="expected_boolean"):
        validate_fact_value(get_fact_contract("osa_diagnosis"), value)


@pytest.mark.parametrize("value", [0, 1, 5, 6, 8, 100])
def test_weeks_accept_nonnegative_integers_even_below_policy_minimum(value):
    assert validate_fact_value(get_fact_contract("symptom_duration_weeks"), value) is value


@pytest.mark.parametrize("value", [True, False, "6", "6 weeks", 6.0, 6.5, float("nan"), float("inf"), -float("inf"), None])
def test_weeks_reject_noninteger_representations(value):
    with pytest.raises(FactContractError, match="expected_integer_weeks"):
        validate_fact_value(get_fact_contract("symptom_duration_weeks"), value)


def test_weeks_reject_negative_values():
    with pytest.raises(FactContractError, match="negative_weeks"):
        validate_fact_value(get_fact_contract("symptom_duration_weeks"), -1)


@pytest.mark.parametrize("value", [0, 1, -1, 1.25, -0.25, 10**400])
def test_numeric_preserves_finite_numeric_representation(value):
    # No existing pathway has a generic numeric fact. Exercise the declared kind
    # with a synthetic dimensionless contract, not a new registry requirement.
    contract = FactContract("numeric_test", "numeric", unit="dimensionless")
    assert validate_fact_value(contract, value) is value


@pytest.mark.parametrize("value", [True, False, "1", "1.25", None, {}, []])
def test_numeric_rejects_nonnumbers(value):
    with pytest.raises(FactContractError, match="expected_number"):
        validate_fact_value(FactContract("numeric_test", "numeric", unit="dimensionless"), value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_numeric_rejects_nonfinite_values(value):
    with pytest.raises(FactContractError, match="nonfinite_number"):
        validate_fact_value(FactContract("numeric_test", "numeric", unit="dimensionless"), value)


@pytest.mark.parametrize("value", ["none", "normal", "negative", "inconclusive", "abnormal", "unrecognized"])
def test_imaging_vocabulary_includes_failing_and_unrecognized_categories(value):
    assert validate_fact_value(get_fact_contract("prior_imaging_result"), value) is value


@pytest.mark.parametrize("value", ["edema", "NORMAL", " normal", "normal ", "", "missing", "needs_review", None, True, 1])
def test_enum_rejects_unknown_members_without_normalization(value):
    with pytest.raises(FactContractError):
        validate_fact_value(get_fact_contract("prior_imaging_result"), value)


@pytest.mark.parametrize("value", [True, False, DatePresence(True), DatePresence(False), DatePresence(True, "2024-02-29")])
def test_date_presence_accepts_boolean_and_optional_date(value):
    assert validate_fact_value(get_fact_contract("sleep_study_date"), value) is value


@pytest.mark.parametrize("value", ["true", "false", "2024-02-29", 0, 1, None, {"value": True}, DatePresence(1)])
def test_date_presence_rejects_coercion(value):
    with pytest.raises(FactContractError, match="expected_date_presence_boolean"):
        validate_fact_value(get_fact_contract("sleep_study_date"), value)


@pytest.mark.parametrize("detail", ["20240229", "2024-2-29", "2024/02/29", " 2024-02-29", "2024-02-29T00:00:00Z", date(2024, 2, 29), True])
def test_date_detail_requires_exact_iso_calendar_string(detail):
    with pytest.raises(FactContractError, match="expected_iso_date"):
        validate_fact_value(get_fact_contract("sleep_study_date"), DatePresence(True, detail))


@pytest.mark.parametrize("detail", ["2023-02-29", "2024-02-30", "2024-13-01", "2024-00-01", "0000-01-01"])
def test_date_detail_rejects_invalid_calendar_dates(detail):
    with pytest.raises(FactContractError, match="invalid_iso_date"):
        validate_fact_value(get_fact_contract("sleep_study_date"), DatePresence(True, detail))


def test_date_detail_requires_positive_presence():
    with pytest.raises(FactContractError, match="date_detail_requires_positive_presence"):
        validate_fact_value(get_fact_contract("sleep_study_date"), DatePresence(False, "2024-02-29"))


@pytest.mark.parametrize("detail", ["1900-01-01", "2099-01-01"])
def test_date_detail_has_no_recency_or_ordering_gate(detail):
    value = DatePresence(True, detail)
    assert validate_fact_value(get_fact_contract("sleep_study_date"), value) is value


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fact_kind": "duration_weeks", "unit": "months"},
        {"fact_kind": "numeric"},
        {"fact_kind": "boolean", "unit": "weeks"},
        {"fact_kind": "date_presence", "unit": "days"},
        {"fact_kind": "enum"},
        {"fact_kind": "enum", "captured_values": ("normal", "normal")},
        {"fact_kind": "boolean", "captured_values": ("true",)},
        {"fact_kind": "boolean", "permits_missing": "true"},
    ],
)
def test_contract_declarations_reject_invalid_units_and_vocabularies(kwargs):
    with pytest.raises(ValueError):
        FactContract("test", **kwargs)


@pytest.mark.parametrize(
    "requirement",
    [
        {"key": "symptom_duration_weeks", "type": "boolean", "operator": "documented"},
        {"key": "osa_diagnosis", "type": "number", "operator": "minimum", "min": 1},
        {"key": "sleep_study_date", "type": "number", "operator": "minimum", "min": 1},
        {"key": "prior_imaging_result", "type": "enum", "operator": "one_of", "allowed": ["edema"]},
        {"key": "prior_imaging_result", "type": "enum", "operator": "one_of", "allowed": [" normal "]},
    ],
)
def test_policy_contract_mismatches_fail(requirement):
    with pytest.raises(FactContractError):
        check_policy_compatibility([requirement | {"label": "Test"}])


def test_operator_type_checks_reuse_existing_schema_validator():
    with pytest.raises(ValidationError, match="incompatible"):
        check_policy_compatibility([{"key": "osa_diagnosis", "label": "Test", "type": "boolean", "operator": "minimum", "min": 1}])


def corpus_conformance_report():
    cases = json.loads(Path("inputs/synthetic_cases.json").read_text())
    captured = missing = needs_review = 0
    failures = []
    for case in cases:
        facts, _ = extract_facts(case["note_text"])
        for key, value in facts.items():
            contract = get_fact_contract(key)
            if value is None:
                missing += 1
                assert contract.permits_missing
            elif value == REVIEW_REQUIRED_FACT:
                needs_review += 1
                assert contract.permits_needs_review
            else:
                captured += 1
                try:
                    validate_fact_value(contract, value)
                except FactContractError as exc:
                    failures.append({"case_id": case["id"], "requirement_key": key, "emitted_value": value, "reason": exc.reason})
    return {"cases": len(cases), "captured": captured, "missing": missing, "needs_review": needs_review, "nonconforming": failures}


def test_read_only_corpus_conformance():
    corpus = Path("inputs/synthetic_cases.json")
    before = corpus.read_bytes()
    report = corpus_conformance_report()
    assert report["cases"] == 52
    assert report["captured"] + report["missing"] + report["needs_review"] == 52 * 12
    assert corpus.read_bytes() == before
    assert not report["nonconforming"], json.dumps(report, indent=2)
