"""Production regression retained from the excluded research injection tests."""

import engine.service as service_module
from engine.extract import extract_facts
from engine.schemas import PARequest
from engine.service import ReadinessService


def test_default_retains_existing_module_patch_behavior(monkeypatch):
    # Source: audit/remediation:test/test_extraction_injection.py. This check
    # exercises the ordinary service and needs no experimental injection API.
    service = ReadinessService()
    calls = []

    def recorded(note):
        calls.append(note)
        return extract_facts(note)

    monkeypatch.setattr(service_module, "extract_facts", recorded)
    service.evaluate(PARequest(payer="Aetna", procedure_code="CPAP_DEVICE", note_text="OSA"))
    assert calls == ["OSA"]
