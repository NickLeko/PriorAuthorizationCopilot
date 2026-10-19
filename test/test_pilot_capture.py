"""Mocked capture only: no inference, real credentials or provider access."""

import argparse
import json
import signal
import sys
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from experiments.dual_extraction import capture, runner
from experiments.dual_extraction.recordings import load_manifest

CASE = "EXTRACTION_CONTRACT.md#unicode"
VALID = (runner.DIRECTORY / "fixtures/actual-model-boundary/valid.json").read_text()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(capture, "RUNS", tmp_path / "runs")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PA_CAPTURE_MODEL", raising=False)
    monkeypatch.delenv("PA_CAPTURE_REASONING_EFFORT", raising=False)
    return argparse.Namespace(model="gpt-6-luna", reasoning_effort=None, run_id="mocked", max_output_tokens=8192, timeout=120, case=CASE)


def response(text=VALID, *, status="completed", content=None, model="gpt-6-luna", response_id="resp_mocked"):
    envelope = dict(
        id=response_id,
        object="response",
        created_at=123,
        model=model,
        status=status,
        output=[
            dict(
                type="message",
                role="assistant",
                status="completed",
                id="msg_mock",
                content=content or [dict(type="output_text", text=text)],
            )
        ],
        usage=dict(input_tokens=99, output_tokens=20, total_tokens=119),
        incomplete_details={"reason": "max_output_tokens"} if status == "incomplete" else None,
    )
    return SimpleNamespace(**envelope, _request_id="req_mocked", model_dump=lambda **kwargs: envelope)


def run(args, reply=..., *, population="simulated_actual_model_capture", before=None):
    cases, prompt, settings, directory, estimate = capture.plan(args)
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if before:
            before(directory, len(calls))
        if isinstance(reply, BaseException):
            raise reply
        return reply if reply is not ... else response(response_id=f"resp_mocked_{len(calls)}")

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    result = capture.capture(cases, prompt, settings, directory, estimate, client, "mocked", args.timeout, population=population)
    return result, directory, calls


def test_default_and_dry_run_never_create_client_or_network(setup, monkeypatch, capsys):
    client = Mock(side_effect=AssertionError("Network forbidden"))
    monkeypatch.setattr(capture, "make_client", client)
    assert capture.main([]) == 0
    assert capture.main(["--dry-run", "--all"]) == 0
    assert capture.main(["--case", CASE]) == 0
    assert client.call_count == 0
    assert not capture.RUNS.exists()
    assert '"remaining_cases": 15' in capsys.readouterr().out


def test_missing_key_and_explicit_selection_prevent_execution(setup, capsys):
    assert capture.main(["--execute", "--case", CASE]) == 1
    assert "OPENAI_API_KEY is required" in capsys.readouterr().out
    assert capture.main(["--execute"]) == 1
    assert "requires --case" in capsys.readouterr().out
    assert not capture.RUNS.exists()


def test_model_reasoning_configuration_and_supported_combinations(setup, monkeypatch, capsys):
    assert capture.plan(setup)[2]["reasoning"] == {"effort": "none"}
    setup.reasoning_effort = "low"
    settings = capture.plan(setup)[2]
    assert settings["reasoning"] == {"effort": "low"}
    assert "temperature" not in settings and "top_p" not in settings
    setup.model = "gpt-6.1-sol"
    setup.reasoning_effort = "none"
    with pytest.raises(capture.CaptureError, match="Unsupported reasoning"):
        capture.plan(setup)
    setup.reasoning_effort = None
    assert capture.plan(setup)[2]["reasoning"] == {"effort": "medium"}
    monkeypatch.setenv("PA_CAPTURE_MODEL", "gpt-6-luna")
    monkeypatch.setenv("PA_CAPTURE_REASONING_EFFORT", "low")
    assert capture.main(["--dry-run"]) == 0
    assert '"effort": "low"' in capsys.readouterr().out
    assert capture.main(["--dry-run", "--model", "gpt-6-luna", "--reasoning-effort", "none"]) == 0
    assert '"effort": "none"' in capsys.readouterr().out


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "gpt-6.1-sol-2026-10-01"),
        ("run_id", "../escape"),
        ("max_output_tokens", 0),
        ("timeout", float("nan")),
        ("case", "unknown"),
    ],
)
def test_configuration_rejected_before_network(setup, field, value):
    setattr(setup, field, value)
    with pytest.raises(capture.CaptureError):
        capture.plan(setup)
    assert not capture.RUNS.exists()


def test_exact_unicode_note_prompt_and_separate_pinned_provider_metadata(setup):
    def before(directory, count):
        manifest = load_manifest(directory / "manifest.json")
        audit = json.loads((directory / "capture.json").read_bytes())
        assert manifest.attempts[0].attempt_id == audit["attempts"][0]["attempt_id"]
        assert audit["attempts"][0]["status"] == "invoking"
        assert manifest.attempts[0].outcome == "extraction_failure"

    text = "  ```json\r\n{broken: 😀İ}\r\n```  "
    result, directory, calls = run(setup, response(text, model="returned-model"), before=before)
    assert result == 0  # Capture success does not imply JSON validity.
    original = next(item["note"] for item in capture.case_inputs(capture.ROOT) if item["case_id"] == CASE)
    assert calls[0]["input"] == [
        dict(role="developer", content=(runner.DIRECTORY / "pilot/prompt-v1.md").read_bytes().decode("utf-8")),
        dict(role="user", content=original),
    ]
    assert "İ" in original
    assert calls[0]["store"] is False and calls[0]["tools"] == []
    assert calls[0]["reasoning"] == {"effort": "none"}
    assert calls[0]["temperature"] == 0 and calls[0]["top_p"] == 1
    manifest = load_manifest(directory / "manifest.json")
    ref = manifest.attempts[0]
    assert (directory / ref.path).read_bytes() == text.encode("utf-8")
    assert ref.stored_sha256 == sha256(text.encode("utf-8")).hexdigest()
    assert ref.recording.model_id == "returned-model"
    assert ref.recording.response_id == "resp_mocked"
    assert ref.recording.origin == "actual_model_response"
    assert ref.provider_id == "openai"
    assert manifest.population == "simulated_actual_model_capture"
    audit = json.loads((directory / "capture.json").read_bytes())
    event = audit["attempts"][0]
    assert audit["requested_model"] == "gpt-6-luna"
    assert event["returned_model"] == "returned-model"
    assert event["request_id"] == "req_mocked"
    assert event["usage"]["total_tokens"] == 119
    assert event["started_at"] <= event["finished_at"]
    assert event["envelope_sha256"] == sha256((directory / event["envelope_path"]).read_bytes()).hexdigest()
    assert "not raw HTTP wire bytes" in audit["envelope_representation"]
    assert json.loads((directory / event["envelope_path"]).read_bytes())["output"][0]["content"][0]["text"] == text


def test_complete_frozen_roster_and_existing_runner_accepts_manifest(setup):
    setup.case = None
    result, directory, calls = run(setup)
    expected = json.loads((runner.DIRECTORY / "pilot/cases-v1.json").read_bytes())["cases"]
    manifest = load_manifest(directory / "manifest.json")
    assert result == 0 and len(calls) == 15
    assert manifest.selected_attempted_case_ids == [case["case_id"] for case in expected]
    assert len({ref.attempt_id for ref in manifest.attempts}) == 15
    report = runner.build_report(manifest_path=directory / "manifest.json")
    assert report["response_accounting"]["actual_model"]["attempted_cases"] == 0
    assert report["response_accounting"]["synthetic_raw_demonstration"]["attempted_cases"] == 15
    assert report["coverage"]["successful_three_mode_cases"] >= 1
    assert runner.main(["--write", "--manifest", str(directory / "manifest.json"), "--output-dir", str(directory / "analysis")]) == 0


def test_actual_population_is_distinct_from_mocked_demonstration(setup):
    # Only temporary test storage uses the production population to verify routing.
    result, directory, _ = run(setup, population="actual_model_study")
    assert result == 0
    manifest = load_manifest(directory / "manifest.json")
    assert manifest.population == "actual_model_study"
    report = runner.build_report(manifest_path=directory / "manifest.json")
    assert report["response_accounting"]["actual_model"]["attempted_cases"] == 1
    assert report["response_accounting"]["synthetic_raw_demonstration"]["attempted_cases"] == 0


@pytest.mark.parametrize("failure", [RuntimeError("secret-provider-message"), TimeoutError("secret-timeout"), KeyboardInterrupt()])
def test_provider_failure_interrupt_and_remaining_roster_are_preserved(setup, failure):
    setup.case = None
    result, directory, calls = run(setup, failure)
    assert result == (130 if isinstance(failure, KeyboardInterrupt) else 1)
    assert len(calls) == 1
    manifest = load_manifest(directory / "manifest.json")
    assert len(manifest.attempts) == len(manifest.selected_attempted_case_ids) == 15
    assert all(ref.outcome == "extraction_failure" for ref in manifest.attempts)
    audit = json.loads((directory / "capture.json").read_bytes())
    assert all(event["status"] == "not_invoked" for event in audit["attempts"][1:])
    assert "secret-" not in (directory / "capture.json").read_text()
    assert all((directory / ref.path).exists() for ref in manifest.attempts)


@pytest.mark.parametrize("kind", ["refusal", "incomplete", "multipart", "empty", "missing"])
def test_unusable_outputs_are_retained_without_concatenation_or_regeneration(setup, kind):
    content = [dict(type="output_text", text="first"), dict(type="output_text", text="second")]
    reply = response(content=content)
    if kind == "refusal":
        reply = response(content=[dict(type="refusal", refusal="declined")])
    elif kind == "incomplete":
        reply = response("{partial", status="incomplete")
    elif kind == "empty":
        reply = response(content=[dict(type="other")])
    elif kind == "missing":
        reply = None
    result, directory, calls = run(setup, reply)
    assert result == 1 and len(calls) == 1
    manifest = load_manifest(directory / "manifest.json")
    assert manifest.attempts[0].outcome == "extraction_failure"
    if kind == "multipart":
        assert (directory / "01/part-01.txt").read_bytes() == b"first"
        assert (directory / "01/part-02.txt").read_bytes() == b"second"
        assert not (directory / "01/response.txt").exists()
    elif kind == "incomplete":
        assert (directory / "01/response.txt").read_bytes() == b"{partial"


def test_duplicate_capture_cannot_overwrite_or_resume(setup):
    _, directory, _ = run(setup)
    before = {path: path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    with pytest.raises(capture.CaptureError, match="overwritten or resumed"):
        run(setup)
    assert before == {path: path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def test_interrupt_after_success_keeps_success_and_remaining_failures(setup):
    setup.case = None

    def interrupt(directory, count):
        if count == 2:
            raise KeyboardInterrupt

    result, directory, calls = run(setup, before=interrupt)
    assert result == 130 and len(calls) == 2
    manifest = load_manifest(directory / "manifest.json")
    assert manifest.attempts[0].outcome == "response"
    assert all(ref.outcome == "extraction_failure" for ref in manifest.attempts[1:])
    audit = json.loads((directory / "capture.json").read_bytes())
    assert audit["attempts"][1]["status"] == "interrupted_unknown_provider_outcome"
    assert all(event["status"] == "not_invoked" for event in audit["attempts"][2:])


def test_failed_provider_envelope_stops_roster(setup):
    setup.case = None
    result, directory, calls = run(setup, response(status="failed"))
    assert result == 1 and len(calls) == 1
    assert json.loads((directory / "capture.json").read_bytes())["attempts"][0]["status"] == "provider_failed"


def test_unavailable_sdk_settings_do_not_generate(setup, monkeypatch):
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda model, input: None), close=Mock())
    monkeypatch.setenv("OPENAI_API_KEY", "mock-only-never-real")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **kwargs: client))
    with pytest.raises(capture.CaptureError, match="settings are unavailable"):
        capture.make_client(capture.plan(setup)[2], 120)
    client.close.assert_called_once()


def test_missing_sdk_fails_clearly_without_creating_run(setup, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "mock-only-never-real")
    monkeypatch.setitem(sys.modules, "openai", None)
    assert capture.main(["--execute", "--case", CASE]) == 1
    assert "SDK functionality is unavailable" in capsys.readouterr().out
    assert not capture.RUNS.exists()


def test_real_sdk_request_contract_with_mock_transport_and_no_retries(setup, monkeypatch):
    openai = pytest.importorskip("openai")
    httpx = pytest.importorskip("httpx2")
    monkeypatch.setenv("OPENAI_API_KEY", "mock-only-never-real")
    actual_constructor = openai.OpenAI
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            429, json={"error": {"message": "mock-only-never-real", "code": "insufficient_quota"}}, headers={"x-request-id": "req_quota"}
        )

    def constructor(**kwargs):
        assert kwargs["max_retries"] == 0
        assert kwargs["base_url"] == "https://api.openai.com/v1"
        return actual_constructor(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    monkeypatch.setattr(openai, "OpenAI", constructor)
    assert capture.main(["--execute", "--all"]) == 1
    assert len(requests) == 1  # 429 must not retry or advance to another note.
    assert requests[0]["model"] == "gpt-6-luna"
    assert requests[0]["store"] is False
    directory = capture.RUNS / "pilot-v1"
    assert all(b"mock-only-never-real" not in path.read_bytes() for path in directory.rglob("*") if path.is_file())
    assert len(load_manifest(directory / "manifest.json").attempts) == 15


def test_real_sdk_success_preserves_output_text_with_mock_transport(setup, monkeypatch):
    openai = pytest.importorskip("openai")
    httpx = pytest.importorskip("httpx2")
    monkeypatch.setenv("OPENAI_API_KEY", "mock-only-never-real")
    constructor = openai.OpenAI
    text = "\r\n" + VALID + "\n  "
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=response(text).model_dump(), headers={"x-request-id": "req_sdk_success"})

    monkeypatch.setattr(
        openai, "OpenAI", lambda **kwargs: constructor(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    )
    cases, prompt, settings, directory, estimate = capture.plan(setup)
    client, version = capture.make_client(settings, setup.timeout)
    try:
        assert (
            capture.capture(
                cases, prompt, settings, directory, estimate, client, version, setup.timeout, population="simulated_actual_model_capture"
            )
            == 0
        )
    finally:
        client.close()
    ref = load_manifest(directory / "manifest.json").attempts[0]
    assert len(requests) == 1
    assert (directory / ref.path).read_bytes() == text.encode("utf-8")
    event = json.loads((directory / "capture.json").read_bytes())["attempts"][0]
    assert event["request_id"] == "req_sdk_success"
    assert event["returned_model"] == "gpt-6-luna"
    assert event["usage"]["total_tokens"] == 119


def test_sigterm_uses_interrupt_handler_and_restores_it(setup, monkeypatch):
    previous = signal.getsignal(signal.SIGTERM)
    client = SimpleNamespace(close=Mock())
    monkeypatch.setattr(capture, "make_client", lambda *args: (client, "mocked"))

    def interrupted(*args):
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

    monkeypatch.setattr(capture, "capture", interrupted)
    assert capture.main(["--execute", "--case", CASE]) == 130
    assert signal.getsignal(signal.SIGTERM) == previous
    client.close.assert_called_once()
