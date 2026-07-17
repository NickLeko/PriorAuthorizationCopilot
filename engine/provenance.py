from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from .schemas import PARequest, PolicyTrustLevel

PROVENANCE_STRING_FIELDS = {
    "source_type",
    "source_name",
    "status",
    "source_url",
    "rule_source_label",
    "last_reviewed",
    "rule_last_updated",
    "monitored_source_id",
    "notes",
}


def load_provenance(path: str | Path) -> Dict[str, Any]:
    provenance_path = Path(path)
    if not provenance_path.exists():
        return {}

    with provenance_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ValueError("Invalid provenance file: expected a top-level mapping.")

    sources = data.get("sources", {})
    if sources is None:
        data["sources"] = {}
        return data

    if not isinstance(sources, dict):
        raise ValueError("Invalid provenance file: 'sources' must be a mapping.")

    for payer, payer_entries in sources.items():
        if not isinstance(payer_entries, dict):
            raise ValueError(f"Invalid provenance file: '{payer}' entries must be a mapping.")
        for procedure_code, entry in payer_entries.items():
            if not isinstance(entry, dict):
                raise ValueError(f"Invalid provenance file: '{payer}.{procedure_code}' must be a mapping.")
            for field_name, value in entry.items():
                if field_name in PROVENANCE_STRING_FIELDS and value is not None:
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(
                            f"Invalid provenance file: '{payer}.{procedure_code}.{field_name}' must be a non-empty string."
                        )

    return data


def get_provenance_entry(provenance_data: Dict[str, Any], payer: str, procedure_code: str) -> Dict[str, Any]:
    sources = provenance_data.get("sources", {}) or {}
    payer_entries = sources.get(payer, {})
    if not isinstance(payer_entries, dict):
        return {}

    entry = payer_entries.get(procedure_code, {})
    if not isinstance(entry, dict):
        return {}

    return dict(entry)


def policy_trust_from_provenance(entry: Dict[str, Any]) -> PolicyTrustLevel:
    source_type = str(entry.get("source_type", "")).strip().lower()
    if source_type in {"policy_document", "official_policy_web"}:
        return "verified"
    return "demo"


def normalized_dx_codes(dx_codes: list[str]) -> list[str]:
    request = PARequest(
        payer="placeholder",
        procedure_code="placeholder",
        dx_codes=dx_codes,
        site_of_care="outpatient",
        specialty="unknown",
        note_text="",
    )
    cleaned: list[str] = []
    seen: set[str] = set()
    for code in request.dx_codes:
        normalized = code.strip().upper().replace(" ", "").replace("%", "")
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)
    return cleaned
