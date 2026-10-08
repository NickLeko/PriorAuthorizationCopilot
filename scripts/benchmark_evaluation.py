"""Measure one cold and one warm MRI evaluation; run pytest separately for suite time."""

from __future__ import annotations

import json
import platform
from time import perf_counter
from unittest.mock import patch

import yaml

import engine.service as service_module
from engine.service import ReadinessService


def main() -> int:
    for name in ("_load_bundle", "_parsed_manifest"):
        cache = getattr(service_module, name, None)
        if cache is not None:
            cache.cache_clear()
    service = ReadinessService()
    request = service.get_demo_case_request("MRI-01-complete")
    rows = []
    for temperature in ("cold", "warm"):
        with (
            patch("yaml.safe_load", wraps=yaml.safe_load) as loads,
            patch("engine.service.get_rulebook_status", wraps=service_module.get_rulebook_status) as status,
        ):
            start = perf_counter()
            service.evaluate(request)
            elapsed = perf_counter() - start
        rows.append(
            {
                "cache": temperature,
                "seconds": elapsed,
                "yaml_loads": loads.call_count,
                "rulebook_status_computations": status.call_count,
            }
        )
    print(json.dumps({"python": platform.python_version(), "case": "MRI-01-complete", "evaluations": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
