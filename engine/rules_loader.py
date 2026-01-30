from __future__ import annotations
import yaml
from typing import Any, Dict


def load_rules(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "payers" not in data:
        raise ValueError("Invalid rules file: expected top-level 'payers'.")
    return data
