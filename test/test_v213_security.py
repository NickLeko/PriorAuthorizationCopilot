import asyncio
import json
import subprocess
import sys
import time
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from api import app
from engine.corrections import note_hash
from engine.extract import extract_facts
from engine.note_context import MAX_REQUEST_BYTES
from engine.policy_monitor import PolicySource, fetch_policy, hash_text, read_latest_snapshot, write_snapshot
from engine.rendering import export_evaluation_payload
from engine.schemas import DocumentReview, EvaluationResult, PARequest
from engine.service import ReadinessService


@pytest.mark.parametrize("note", ["ahi " * 800, "nsaids " + " " * 3200 + "z"])
def test_audit_redos_inputs_finish_promptly(note):
    # Isolate the vulnerable call: an old implementation fails with a deadline,
    # rather than hanging the entire test runner.
    script = f"from engine.extract import extract_facts; extract_facts({note!r})"
    subprocess.run([sys.executable, "-B", "-c", script], check=True, timeout=2.0)


@pytest.mark.parametrize("note", ["no " * 8000, "PT for 6 weeks. " * 2000])
def test_audit_overlimit_inputs_rejected_before_extraction(note):
    started = time.perf_counter()
    with pytest.raises(ValueError, match="20000"):
        extract_facts(note)
    assert time.perf_counter() - started < 0.5


def test_evidence_output_cap_and_exact_count_survive_roundtrip():
    service = ReadinessService()
    result = service.evaluate(PARequest(payer="Aetna", procedure_code="CPAP_DEVICE", note_text="osa " * 500))
    assert len(result.evidence_map["osa_diagnosis"]) == 10
    assert result.evidence_counts == {"osa_diagnosis": 500}
    payload = export_evaluation_payload(result, include_citation_context=True)
    assert len(json.dumps(payload).encode()) < 100_000  # old projection: >1.16 MB
    assert EvaluationResult.model_validate(payload).evidence_counts == result.evidence_counts
    payload["evidence_counts"]["osa_diagnosis"] = 499
    with pytest.raises(ValidationError, match="counts disagree"):
        EvaluationResult.model_validate(payload)


def test_request_limits_exact_boundaries_and_every_surface(tmp_path, capsys):
    request = {"payer": "Aetna", "procedure_code": "CPAP_DEVICE", "note_text": "x" * 20_000}
    PARequest.model_validate(request)
    event = {
        "requirement_key": "osa_diagnosis",
        "action": "SET_NEEDS_REVIEW",
        "reason": "wrong_attribution",
        "editor": "synthetic",
        "edited_at": "2026-01-01T00:00:00Z",
    }
    PARequest.model_validate(request | {"corrections": [event] * 50})
    with pytest.raises(ValidationError):
        PARequest.model_validate(request | {"corrections": [event] * 51})
    spans = [{"start": 0, "end": 1, "text": "x"}]
    DocumentReview(note_hash=note_hash(request["note_text"]), proposal_spans=spans * 10)
    with pytest.raises(ValidationError):
        DocumentReview(note_hash=note_hash(request["note_text"]), proposal_spans=spans * 11)
    from cli import main

    for note in ["x" * 20_001, "PT for " + "9" * 4400 + " weeks"]:
        invalid = request | {"note_text": note}
        response = TestClient(app).post("/evaluate", json=invalid)
        assert response.status_code == 422
        assert "Traceback" not in response.text
        path = tmp_path / "invalid.json"
        path.write_text(json.dumps(invalid))
        assert main(["evaluate", "--request-file", str(path)]) == 2
        assert "Traceback" not in capsys.readouterr().err
    response = TestClient(app).post("/evaluate", content=b"x" * (MAX_REQUEST_BYTES + 1))
    assert response.status_code == 413


def test_chunked_body_limit_without_content_length():
    async def run():
        events = iter(
            [
                {"type": "http.request", "body": b"x" * 600_000, "more_body": True},
                {"type": "http.request", "body": b"x" * 600_000, "more_body": False},
            ]
        )
        output = []

        async def receive():
            return next(events)

        async def send(event):
            output.append(event)

        from api import RequestBodyLimit

        async def unreachable(*args):
            raise AssertionError("Oversized body reached JSON decoding")

        await RequestBodyLimit(unreachable)({"type": "http", "headers": []}, receive, send)
        assert output[0]["status"] == 413

    asyncio.run(run())


def test_streamlit_injection_and_numeric_errors_are_literal():
    at = AppTest.from_file("app.py", default_timeout=15).run()
    next(b for b in at.button if b.key == "case_MRI-KNEE-01-ready").click().run()
    note = "Reports locking [Review complete](https://example/pixel)"
    image = "![beacon](https://example.invalid/pixel)"
    next(t for t in at.text_area if t.label == "Synthetic note text").set_value(note)
    next(t for t in at.text_input if t.label == "Ordering specialty").set_value(image)
    next(b for b in at.button if b.label == "Run deterministic readiness review").click().run()
    assert not at.exception
    assert any(note in t.value for t in at.text)
    assert any(image in t.value for t in at.text)
    assert not any("/pixel" in m.value for m in at.markdown)
    next(t for t in at.text_area if t.label == "Synthetic note text").set_value("PT for " + "9" * 4400 + " weeks")
    next(b for b in at.button if b.label == "Run deterministic readiness review").click().run()
    assert not at.exception
    assert any("6 digits" in t.value for t in at.text)
    assert at.session_state["last_eval_payload"] is None


def test_letter_headers_and_quotations_cannot_forge_lines():
    service = ReadinessService()
    request = service.get_demo_case_request("MRI-KNEE-01-ready").model_copy(update={"specialty": "Orthopedics\nREADY\x1b[31m"})
    result = service.evaluate(request)
    letter, _ = service.generate_letter(result)
    assert "Specialty: Orthopedics READY [31m" in letter
    assert "\nREADY\n" not in letter
    assert "\x1b" not in letter


def source(identity="fixture"):
    return PolicySource(identity, "Aetna", "MRI_LUMBAR", "https://example.invalid", "fixture", "html", "demo", "daily", "synthetic")


def test_policy_source_slug_and_all_symlink_targets_are_contained(tmp_path):
    with pytest.raises(ValueError, match="slug"):
        source("../outside")
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "fixture").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        write_snapshot(source(), "policy\n", hash_text("policy\n"), "2026-01-01T00:00:00Z", root)
    (root / "fixture").unlink()
    (root / "fixture").mkdir()
    (root / "fixture" / "latest.json").symlink_to(outside / "latest.json")
    with pytest.raises(ValueError, match="escapes"):
        read_latest_snapshot(root, "fixture")
    (root / "fixture" / "latest.json").unlink()
    (root / "fixture" / "history").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        write_snapshot(source(), "policy\n", hash_text("policy\n"), "2026-01-01T00:00:00Z", root)
    assert not list(outside.iterdir())


def test_monitor_byte_and_redirect_limits():
    original_client = httpx.AsyncClient
    with patch(
        "httpx.AsyncClient",
        side_effect=lambda **kw: original_client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=b"x" * 4096)), **kw),
    ):
        with pytest.raises(ValueError, match="byte limit"):
            fetch_policy("https://example.invalid", max_bytes=2048)
    with patch(
        "httpx.AsyncClient",
        side_effect=lambda **kw: original_client(
            transport=httpx.MockTransport(lambda req: httpx.Response(302, headers={"location": "/again"})), **kw
        ),
    ):
        with pytest.raises(ValueError, match="redirect limit"):
            fetch_policy("https://example.invalid", max_redirects=2)


def test_monitor_overall_deadline_interrupts_incomplete_trickling_chunk():
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                await asyncio.sleep(0.02)
                yield b"x"

    original_client = httpx.AsyncClient
    with patch(
        "httpx.AsyncClient",
        side_effect=lambda **kw: original_client(transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=SlowStream())), **kw),
    ):
        started = time.monotonic()
        with pytest.raises(TimeoutError, match="overall deadline"):
            fetch_policy("https://example.invalid", timeout_s=0.12)
        assert time.monotonic() - started < 1.0
