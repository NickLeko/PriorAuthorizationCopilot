from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from .schemas import LEGACY_OPERATOR_BY_TYPE

ALLOWED_REQUIREMENT_TYPES = {"number", "boolean", "enum"}
ALLOWED_REQUIREMENT_OPERATORS = {"documented", "equals_true", "minimum", "one_of"}
EXPECTED_TYPE_BY_OPERATOR = {"documented": "boolean", "equals_true": "boolean", "minimum": "number", "one_of": "enum"}


def _validate_procedure_metadata(metadata: Dict[str, Any], payer: str, procedure_code: str) -> None:
    location = f"{payer}.{procedure_code}.metadata"

    if not isinstance(metadata, dict):
        raise ValueError(f"Invalid rules file: {location} must be a mapping.")

    required_string_fields = ("category", "rule_family", "summary")
    for field_name in required_string_fields:
        value = metadata.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Invalid rules file: {location}.{field_name} must be a non-empty string.")

    supported_sites = metadata.get("supported_sites", [])
    if supported_sites is not None:
        if not isinstance(supported_sites, list):
            raise ValueError(f"Invalid rules file: {location}.supported_sites must be a list when provided.")
        if any(not isinstance(site, str) or not site.strip() for site in supported_sites):
            raise ValueError(f"Invalid rules file: {location}.supported_sites entries must be non-empty strings.")

    notes = metadata.get("notes", [])
    if notes is not None:
        if not isinstance(notes, list):
            raise ValueError(f"Invalid rules file: {location}.notes must be a list when provided.")
        if any(not isinstance(note, str) or not note.strip() for note in notes):
            raise ValueError(f"Invalid rules file: {location}.notes entries must be non-empty strings.")

    last_rule_update = metadata.get("last_rule_update")
    if last_rule_update is not None and (not isinstance(last_rule_update, str) or not last_rule_update.strip()):
        raise ValueError(f"Invalid rules file: {location}.last_rule_update must be a non-empty string when provided.")


def _validate_requirement(req: Dict[str, Any], payer: str, procedure_code: str, idx: int) -> None:
    location = f"{payer}.{procedure_code}.required[{idx}]"

    key = req.get("key")
    if not isinstance(key, str) or not key.strip():
        raise ValueError(f"Invalid rules file: {location}.key must be a non-empty string.")

    req_type = req.get("type", "boolean")
    if req_type not in ALLOWED_REQUIREMENT_TYPES:
        raise ValueError(f"Invalid rules file: {location}.type must be one of {sorted(ALLOWED_REQUIREMENT_TYPES)}.")

    operator = req.get("operator") or LEGACY_OPERATOR_BY_TYPE[req_type]
    if operator not in ALLOWED_REQUIREMENT_OPERATORS:
        raise ValueError(f"Invalid rules file: {location}.operator must be one of {sorted(ALLOWED_REQUIREMENT_OPERATORS)}.")
    if EXPECTED_TYPE_BY_OPERATOR[operator] != req_type:
        raise ValueError(f"Invalid rules file: {location}.operator '{operator}' is incompatible with type '{req_type}'.")

    label = req.get("label", key)
    if not isinstance(label, str) or not label.strip():
        raise ValueError(f"Invalid rules file: {location}.label must be a non-empty string.")

    if req_type == "number":
        if "min" not in req or not isinstance(req["min"], (int, float)):
            raise ValueError(f"Invalid rules file: {location}.min must be numeric for number requirements.")

    if req_type == "enum":
        allowed = req.get("allowed")
        if not isinstance(allowed, list) or not allowed:
            raise ValueError(f"Invalid rules file: {location}.allowed must be a non-empty list for enum requirements.")
        if any(not isinstance(value, str) or not value.strip() for value in allowed):
            raise ValueError(f"Invalid rules file: {location}.allowed must contain non-empty strings.")


def _validate_procedures(procedures: Dict[str, Any], payer: str) -> None:
    if not isinstance(procedures, dict) or not procedures:
        raise ValueError(f"Invalid rules file: {payer}.procedures must be a non-empty mapping.")

    for procedure_code, procedure in procedures.items():
        if not isinstance(procedure, dict):
            raise ValueError(f"Invalid rules file: {payer}.{procedure_code} must be a mapping.")

        display_name = procedure.get("display_name", procedure_code)
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError(f"Invalid rules file: {payer}.{procedure_code}.display_name must be a non-empty string.")

        metadata = procedure.get("metadata")
        if metadata is not None:
            _validate_procedure_metadata(metadata, payer, procedure_code)

        requirements = procedure.get("required")
        if not isinstance(requirements, list) or not requirements:
            raise ValueError(f"Invalid rules file: {payer}.{procedure_code}.required must be a non-empty list.")

        for idx, requirement in enumerate(requirements):
            if not isinstance(requirement, dict):
                raise ValueError(f"Invalid rules file: {payer}.{procedure_code}.required[{idx}] must be a mapping.")
            _validate_requirement(requirement, payer, procedure_code, idx)


def _validate_rules(data: Dict[str, Any]) -> None:
    payers = data["payers"]
    if not isinstance(payers, dict) or not payers:
        raise ValueError("Invalid rules file: 'payers' must be a non-empty mapping.")

    for payer, payer_config in payers.items():
        if not isinstance(payer_config, dict):
            raise ValueError(f"Invalid rules file: payer '{payer}' must be a mapping.")
        _validate_procedures(payer_config.get("procedures"), payer)

    policy_notes = data.get("policy_notes")
    if policy_notes is not None:
        if not isinstance(policy_notes, list):
            raise ValueError("Invalid rules file: 'policy_notes' must be a list when provided.")
        if any(not isinstance(note, str) or not note.strip() for note in policy_notes):
            raise ValueError("Invalid rules file: 'policy_notes' entries must be non-empty strings.")


def load_rules(path: str) -> Dict[str, Any]:
    rules_path = Path(path)
    if not rules_path.exists():
        raise FileNotFoundError(f"Rules file not found: {rules_path}")

    with rules_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "payers" not in data:
        raise ValueError("Invalid rules file: expected top-level 'payers'.")
    _validate_rules(data)
    return data
