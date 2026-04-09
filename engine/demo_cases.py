from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .config import AppConfig
from .schemas import DemoCase, PARequest


def load_demo_cases(path: str | Path) -> List[DemoCase]:
    cases_path = Path(path)
    with cases_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [DemoCase.model_validate(item) for item in payload]


def list_demo_cases(config: AppConfig) -> List[DemoCase]:
    return load_demo_cases(config.synthetic_cases_path)


def get_demo_case(case_id: str, config: AppConfig) -> DemoCase:
    for case in list_demo_cases(config):
        if case.id == case_id:
            return case
    raise KeyError(f"Demo case not found: {case_id}")


def featured_demo_cases(config: AppConfig) -> List[DemoCase]:
    featured = [case for case in list_demo_cases(config) if bool(case.showcase.get("featured"))]
    return sorted(featured, key=lambda case: int(case.showcase.get("sort_order", 999)))


def expected_overall_status_for_demo_case(case: DemoCase) -> str | None:
    expected = str(case.showcase.get("expected_overall_status") or "").strip()
    return expected or None


def demo_case_to_request(case: DemoCase) -> PARequest:
    return PARequest(
        payer=case.payer,
        procedure_code=case.procedure_code,
        dx_codes=case.dx_codes,
        site_of_care=case.site_of_care,
        specialty=case.specialty,
        note_text=case.note_text,
    )
