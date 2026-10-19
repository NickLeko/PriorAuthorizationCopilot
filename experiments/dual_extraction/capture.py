"""Explicit, sequential OpenAI capture only; analysis stays in the offline runner."""

from __future__ import annotations

import argparse
import inspect
import json
import math
import os
import re
import signal
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from .baseline import case_inputs
from .recorded import IDENTIFIER_PATTERN
from .recordings import RawAttemptManifest
from .runner import DIRECTORY, load_frozen_baseline

ROOT = DIRECTORY.resolve().parents[1]
RUNS = DIRECTORY.resolve() / "runs"
PROMPT_VERSION = "pa-extraction-bare-v1"
ASSET_HASHES = {
    "PROTOCOL.md": "e25ebf2f2892ec6a90d11a29fdd91f8537e4031dc3747dfb9f2e33ab1b8af45d",
    "cases-v1.json": "07007451442b173df5cda18da4ed708cedc27d5ba8a6fdd2ea6e3db15e66dc15",
    "prompt-v1.md": "05ce0b890b68de6d0fd9547c2bfd7aa009c3197d1e35c3e6d3335394e7f6d7e1",
}
# Verified 2026-10-19 against the official model pages and GPT-6 guide.
# Explicit profiles only: no guessed dated snapshots or parameter substitution.
PROFILES = {
    "gpt-6-luna": "none",
    "gpt-6.1-sol": "medium",
}
EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")


class CaptureError(ValueError):
    """Payload-free local diagnostic safe to display."""


def now():
    return datetime.now(UTC).isoformat()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def write_json(path, value):
    """Atomic checkpoints; an interruption leaves the previous complete roster."""
    temporary = path.with_suffix(".tmp")
    with temporary.open("wb") as stream:
        stream.write(json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def plan(args):
    if args.model not in PROFILES:
        raise CaptureError("Unsupported model profile; supported: " + ", ".join(PROFILES))
    effort = args.reasoning_effort or PROFILES[args.model]
    if effort not in EFFORTS or (args.model == "gpt-6.1-sol" and effort == "none"):
        raise CaptureError("Unsupported reasoning effort for selected model; no parameter substitution is permitted.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.run_id):
        raise CaptureError("run-id must be 1–64 ASCII letters, digits, underscores or hyphens.")
    if not 1 <= args.max_output_tokens <= 32768 or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise CaptureError("Require 1–32768 max-output-tokens and a finite positive timeout.")
    assets = {name: (DIRECTORY / "pilot" / name).read_bytes() for name in ASSET_HASHES}
    if any(sha256(assets[name]).hexdigest() != digest for name, digest in ASSET_HASHES.items()):
        raise CaptureError("Frozen pilot assets changed.")
    roster = json.loads(assets["cases-v1.json"])
    frozen = load_frozen_baseline()
    if roster["baseline_sha256"] != sha256((DIRECTORY / "artifacts/regex-v2.7.0.jsonl").read_bytes()).hexdigest():
        raise CaptureError("Frozen baseline changed.")
    originals = {row["case_id"]: row["note"] for row in case_inputs(ROOT)}
    baseline_notes = {row["case_id"]: row["note_text"] for row in frozen[1:]}
    cases = []
    for item in roster["cases"]:
        note = originals[item["case_id"]]
        if note != baseline_notes[item["case_id"]] or sha256(note.encode("utf-8")).hexdigest() != item["note_sha256"]:
            raise CaptureError("Original note identity mismatch.")
        cases.append(dict(case_id=item["case_id"], note=note, note_sha256=item["note_sha256"]))
    if len(cases) != 15 or len({case["case_id"] for case in cases}) != 15:
        raise CaptureError("Expected the frozen 15-case roster.")
    if args.case:
        cases = [case for case in cases if case["case_id"] == args.case]
        if not cases:
            raise CaptureError("case must be an exact frozen roster case ID.")
    directory = RUNS / args.run_id
    if RUNS.is_symlink() or not directory.resolve().is_relative_to(RUNS) or directory.exists():
        raise CaptureError("Run directory exists or is unsafe; captures cannot be overwritten or resumed.")
    parent = directory.parent
    while not parent.exists():
        parent = parent.parent
    if not parent.is_dir() or not os.access(parent, os.W_OK):
        raise CaptureError("Run directory parent is not writable.")
    settings = dict(
        model=args.model,
        store=False,
        tools=[],
        tool_choice="none",
        stream=False,
        background=False,
        service_tier="default",
        truncation="disabled",
        text={"format": {"type": "text"}},
        max_output_tokens=args.max_output_tokens,
        reasoning={"effort": effort},
    )
    if effort == "none":
        settings.update(temperature=0, top_p=1)
    prompt = assets["prompt-v1.md"].decode("utf-8")
    # Conservative byte-based allowance, not a tokenizer or a quoted bill.
    # Allowances exceed documented standard rates, including cache writes.
    sizes = [len(prompt.encode("utf-8")) + len(case["note"].encode("utf-8")) + 1024 for case in cases]
    input_rate, output_rate = (0.15, 0.60) if args.model == "gpt-6-luna" else (3, 12)
    cost = (sum(sizes) * input_rate + len(cases) * args.max_output_tokens * output_rate) / 1_000_000
    return (
        cases,
        prompt,
        settings,
        directory,
        dict(
            model=args.model,
            remaining_cases=len(cases),
            case_ids=[case["case_id"] for case in cases],
            note_sha256=[case["note_sha256"] for case in cases],
            input_token_allowances=sizes,
            request_utf8_bytes=[len(json_bytes(settings | {"input": messages(prompt, case["note"])})) for case in cases],
            max_output_tokens_per_case=args.max_output_tokens,
            conservative_estimated_cost_usd=round(cost, 6),
            estimate_basis=f"UTF-8 input bytes + 1024/case; ${input_rate} input/${output_rate} output per 1M; standard tier; estimate only",
            manifest_path=str(directory / "manifest.json"),
            audit_path=str(directory / "capture.json"),
            response_paths=[str(directory / f"{index:02d}/response.txt") for index in range(1, len(cases) + 1)],
            settings=settings,
        ),
    )


def messages(prompt, note):
    return [{"role": "developer", "content": prompt}, {"role": "user", "content": note}]


def make_client(settings, timeout):
    key = os.environ.get("OPENAI_API_KEY")
    if not key or not key.strip():
        raise CaptureError("OPENAI_API_KEY is required for execution.")
    try:
        import openai

        # Pin endpoint and disable ambient provider configuration and HTTP retries.
        client = openai.OpenAI(api_key=key, base_url="https://api.openai.com/v1", max_retries=0, timeout=timeout)
        parameters = inspect.signature(client.responses.create).parameters
        if not (set(settings) | {"input"}) <= set(parameters):
            client.close()
            raise CaptureError("Required Responses API settings are unavailable in the SDK.")
        return client, openai.__version__
    except CaptureError:
        raise
    except Exception:
        raise CaptureError("Install the optional requirements-capture.txt; required OpenAI SDK functionality is unavailable.") from None


def capture(cases, prompt, settings, directory, estimate, client, sdk_version, timeout, *, population="actual_model_study"):
    """No retries or resume. Tests explicitly use the simulated population."""
    directory.parent.mkdir(parents=True, exist_ok=True)
    directory.mkdir(mode=0o700)  # Exclusive claim before any invocation.
    manifest = dict(
        schema_version=2,
        notice="Offline response attempts; provenance is declared per population.",
        population=population,
        selected_attempted_case_ids=[case["case_id"] for case in cases],
        attempts=[],
    )
    audit = dict(
        population=population,
        provider="openai",
        endpoint="https://api.openai.com/v1/responses",
        sdk_version=sdk_version,
        envelope_representation="SDK model_dump(mode=json); not raw HTTP wire bytes",
        requested_model=settings["model"],
        prompt_version=PROMPT_VERSION,
        asset_sha256=ASSET_HASHES,
        settings=settings,
        timeout_seconds=timeout,
        sdk_max_retries=0,
        estimate=estimate,
        started_at=now(),
        attempts=[],
    )
    for index, case in enumerate(cases, 1):
        folder = directory / f"{index:02d}"
        folder.mkdir()
        # Empty storage marker is never represented as provider-generated text.
        (folder / "no-response.txt").write_bytes(b"")
        attempt_id = "attempt-" + uuid4().hex
        manifest["attempts"].append(
            dict(
                case_id=case["case_id"],
                attempt_id=attempt_id,
                path=f"{index:02d}/no-response.txt",
                note_sha256=case["note_sha256"],
                stored_sha256=sha256(b"").hexdigest(),
                provider_id="openai",
                outcome="extraction_failure",
                recording=dict(
                    source="openai-responses",
                    model_id=settings["model"],
                    prompt_version=PROMPT_VERSION,
                    response_id=None,
                    origin="actual_model_response",
                ),
            )
        )
        audit["attempts"].append(dict(case_id=case["case_id"], attempt_id=attempt_id, status="not_invoked"))

    def checkpoint():
        RawAttemptManifest.model_validate(manifest, strict=True)
        write_json(directory / "capture.json", audit)
        write_json(directory / "manifest.json", manifest)

    checkpoint()  # All selected identities survive a provider failure or process exit.
    interrupted = False
    try:
        for index, (case, ref, event) in enumerate(zip(cases, manifest["attempts"], audit["attempts"], strict=True), 1):
            event.update(status="invoking", started_at=now())
            checkpoint()
            folder = directory / f"{index:02d}"
            try:
                response = client.responses.create(**settings, input=messages(prompt, case["note"]))
                if response is None:
                    event["status"] = "missing_provider_response"
                    break
                envelope = response.model_dump(mode="json")
                write_json(folder / "provider.json", envelope)
                event.update(
                    envelope_path=f"{index:02d}/provider.json",
                    envelope_sha256=sha256((folder / "provider.json").read_bytes()).hexdigest(),
                    response_id=response.id,
                    request_id=getattr(response, "_request_id", None),
                    returned_model=response.model,
                    provider_status=response.status,
                    usage=envelope.get("usage"),
                    incomplete_details=envelope.get("incomplete_details"),
                )
                if isinstance(response.id, str) and re.fullmatch(IDENTIFIER_PATTERN, response.id):
                    ref["recording"]["response_id"] = response.id
                if isinstance(response.model, str) and re.fullmatch(IDENTIFIER_PATTERN, response.model):
                    ref["recording"]["model_id"] = response.model
                parts = [part for item in envelope.get("output", []) if item.get("type") == "message" for part in item.get("content", [])]
                texts = [part["text"] for part in parts if part.get("type") == "output_text"]
                # Never concatenate parts or repair a refusal into extraction JSON.
                for number, text in enumerate(texts, 1):
                    (folder / f"part-{number:02d}.txt").write_bytes(text.encode("utf-8"))
                event["text_parts"] = [
                    dict(path=f"{index:02d}/part-{number:02d}.txt", sha256=sha256(text.encode("utf-8")).hexdigest())
                    for number, text in enumerate(texts, 1)
                ]
                if len(texts) == 1:
                    body = texts[0].encode("utf-8")
                    (folder / "response.txt").write_bytes(body)
                    ref.update(path=f"{index:02d}/response.txt", stored_sha256=sha256(body).hexdigest())
                event["status"] = "unusable_provider_output"
                if any(part.get("type") == "refusal" for part in parts):
                    event["status"] = "refusal"
                elif response.status == "incomplete":
                    event["status"] = "incomplete"
                elif response.status == "failed":
                    event["status"] = "provider_failed"
                    break
                elif response.status == "completed" and len(parts) == len(texts) == 1 and ref["recording"]["response_id"]:
                    ref["outcome"] = "response"
                    event["status"] = "response"
            except KeyboardInterrupt:
                event["status"] = "interrupted_unknown_provider_outcome"
                interrupted = True
                break
            except Exception as exc:
                # Error strings/bodies/headers may contain credentials; never log them.
                event.update(status="provider_or_capture_failure", error_type=type(exc).__name__)
                status = getattr(exc, "status_code", None)
                if isinstance(status, int):
                    event["http_status"] = status
                request_id = getattr(exc, "request_id", None)
                if isinstance(request_id, str) and re.fullmatch(IDENTIFIER_PATTERN, request_id):
                    event["request_id"] = request_id
                break  # Includes quota, billing, timeout, access and unsupported settings.
            finally:
                event["finished_at"] = now()
                checkpoint()
    except KeyboardInterrupt:
        interrupted = True
    finally:
        audit.update(finished_at=now(), interrupted=interrupted)
        checkpoint()
    return 130 if interrupted else 0 if all(ref["outcome"] == "response" for ref in manifest["attempts"]) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--case")
    selection.add_argument("--all", action="store_true")
    authorization = parser.add_mutually_exclusive_group()
    authorization.add_argument("--dry-run", action="store_true")
    authorization.add_argument("--execute", action="store_true")
    parser.add_argument("--model", default=os.environ.get("PA_CAPTURE_MODEL", "gpt-6-luna"))
    parser.add_argument("--reasoning-effort", choices=EFFORTS, default=os.environ.get("PA_CAPTURE_REASONING_EFFORT"))
    parser.add_argument("--run-id", default="pilot-v1")
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    client = None
    previous_handler = None
    try:
        cases, prompt, settings, directory, estimate = plan(args)
        print(json.dumps(estimate, indent=2), flush=True)
        if not args.execute:
            print("Dry run: no network calls or run files; SDK and provider access are checked only at execution.")
            return 0
        if not (args.case or args.all):
            raise CaptureError("Execution requires --case CASE_ID or --all and --execute.")
        client, sdk_version = make_client(settings, args.timeout)

        def terminate(signum, frame):
            raise KeyboardInterrupt

        previous_handler = signal.signal(signal.SIGTERM, terminate)
        result = capture(cases, prompt, settings, directory, estimate, client, sdk_version, args.timeout)
        print(f"Capture stopped; offline manifest: {directory / 'manifest.json'}", flush=True)
        return result
    except CaptureError as exc:
        print(str(exc))
        return 1
    except (ValueError, OSError):
        # Fixed messages from our validation only; never echo arbitrary SDK errors.
        print("Capture configuration/storage error; check model profile, assets, selection, credentials, SDK and unused run-id.")
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        if previous_handler is not None:
            signal.signal(signal.SIGTERM, previous_handler)
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
