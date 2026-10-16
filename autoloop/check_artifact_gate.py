"""Read-only preflight of drift JSON produced by both Makefile generators.

One differing committed output is sufficient to trigger the experiment stop rule.
This does not invoke either generator or write to a golden/artifact directory.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.acceptance import normalize_drift_payload  # noqa: E402
from engine.service import ReadinessService  # noqa: E402


def differences(expected, actual, path=""):
    if isinstance(expected, dict) and isinstance(actual, dict):
        return [
            difference
            for key in sorted(expected.keys() | actual.keys())
            for difference in differences(expected.get(key), actual.get(key), f"{path}/{key}")
        ]
    if isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual):
        return [difference for index, pair in enumerate(zip(expected, actual)) for difference in differences(*pair, f"{path}/{index}")]
    return [] if expected == actual else [{"path": path, "committed": expected, "would_generate": actual}]


def check():
    service = ReadinessService()
    actual = normalize_drift_payload(service.get_drift_status().model_dump(mode="json"))
    checks = []
    for relative in ("test/golden/governance/drift_status.json", "docs/artifacts/drift_status.json"):
        expected = json.loads((ROOT / relative).read_text())
        checks.append({"file": relative, "differences": differences(expected, actual)})
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "public drift projection, real default clock; no generation or committed-file writes",
        "stop_required": any(item["differences"] for item in checks),
        "checks": checks,
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
