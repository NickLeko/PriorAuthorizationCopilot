# First actual-model pilot capture

The opt-in CLI is `python -m experiments.dual_extraction.capture`. Development
and verification use mocked calls only. Live execution requires the user's
explicit authorization, `OPENAI_API_KEY`, a supported SDK and provider access.
There is no production integration or local-model backend.

This execution configuration supersedes only the **proposed** model/settings in
[PROTOCOL.md](PROTOCOL.md). That historical proposal, [prompt-v1.md](prompt-v1.md),
the [15-case roster](cases-v1.json), original notes, frozen regex captures and
offline runner remain unchanged. The CLI verifies their hashes and compares each
original note to its frozen note before preparing any request. Only the exact
developer prompt and original note enter the request, without labels or baseline
outputs. Prompt version remains `pa-extraction-bare-v1`.

## Model and frozen settings

Default: **`gpt-6-luna`, `reasoning.effort="none"`**, output budget 8192 tokens per
case, `temperature=0`, `top_p=1`. Choose a model with `--model` or
`PA_CAPTURE_MODEL`; choose effort with `--reasoning-effort` or
`PA_CAPTURE_REASONING_EFFORT`. CLI options take precedence. Supported Luna efforts
are `none`, `low`, `medium`, `high`, `xhigh`, `max`. The optional `gpt-6.1-sol`
profile defaults to `medium` and rejects `none`. No dated Luna snapshot is assumed.
Unknown models or unsupported combinations fail locally. These are two explicit
OpenAI configurations, not a provider framework.

For non-`none` reasoning, the request omits `temperature` and `top_p` because they
are unsupported. Every run freezes and records the resulting exact request
settings. All profiles use Responses, `store=false`, `tools=[]`,
`tool_choice="none"`, plain text output, `stream=false`, `background=false`,
`service_tier="default"`, `truncation="disabled"`, and no response continuation.
`--max-output-tokens` (1–32768) and `--timeout` (seconds, default 120) are
configurable. The output budget includes reasoning tokens when enabled.

Verified against official documentation on 2026-10-19:

- [GPT-6 Luna identifier and supported reasoning efforts](https://developers.openai.com/api/docs/models/gpt-6-luna).
- [GPT-6 parameter compatibility](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra).
- [GPT-6.1 Sol identifier and reasoning efforts](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
- [Standard pricing](https://developers.openai.com/api/docs/changelog): Luna $0.10 input / $0.50 output per million tokens; Sol $2 / $10.

The CLI prints the selected model/settings, remaining case count, note hashes,
proposed paths, serialized request sizes, and a conservative cost estimate before
execution. Input allowance uses UTF-8 byte length plus 1024 tokens per request;
output allowance uses the full selected budget. Pricing allowances of $0.15/$0.60
for Luna and $3/$12 for Sol per million tokens exceed standard rates, including
cache-write input pricing. This is an estimate, not a billing guarantee. Frozen
parameters do not guarantee deterministic generation. Preserved original responses
make offline replay reproducible; aliases may change over time.

## Setup and commands

From the repository root, activate the project's Python environment and install
the optional official SDK (production dependencies are unchanged):

```bash
source .venv/bin/activate
python -m pip install -r experiments/dual_extraction/requirements-capture.txt
```

Dry run: no SDK client, credentials, network calls or output files are required.
Provider access and SDK functionality cannot be verified offline. The command
without flags is also a dry run.

```bash
python -m experiments.dual_extraction.capture --dry-run --all --model gpt-6-luna --reasoning-effort none --run-id luna-pilot-v1
```

After explicit live-call authorization, set the key in the current shell using
hidden input. In the project's default zsh shell:

```zsh
read -rs 'OPENAI_API_KEY?OpenAI API key: '
export OPENAI_API_KEY
```

Do not put the value in command arguments, source files, shell history, a manifest
or a committed environment file. Clear it when finished with `unset OPENAI_API_KEY`.

One selected case:

```bash
python -m experiments.dual_extraction.capture --case 'inputs/synthetic_cases.json#CPAP-01-complete' --model gpt-6-luna --reasoning-effort none --run-id luna-one-v1 --execute
```

Complete frozen roster:

```bash
python -m experiments.dual_extraction.capture --all --model gpt-6-luna --reasoning-effort none --run-id luna-pilot-v1 --execute
```

These are alternative initial captures. Do not capture one case and then recapture
it as part of the full pilot. Run IDs are exclusive: an existing directory is
rejected, never overwritten or automatically resumed. Choosing a new ID explicitly
creates a separate run; it must not be used to hide a previous failed attempt.

Analyze with the **existing** offline runner, including after a failed capture:

```bash
python -m experiments.dual_extraction.runner --write --manifest experiments/dual_extraction/runs/luna-pilot-v1/manifest.json --output-dir experiments/dual_extraction/runs/luna-pilot-v1/analysis
```

## Preservation and failure accounting

All generated files live under the explicitly gitignored
`experiments/dual_extraction/runs/<run-id>/`. The run directory is claimed
exclusively before any invocation. `manifest.json` is an existing version-2
`actual_model_study` manifest, not a second runner format. Its metadata records
provider, case/attempt identity, note hash, returned model, response ID when
available, origin, prompt version, response file path and SHA-256. Before a
provider response exists, the manifest uses the requested model and null response
ID; the audit distinguishes the requested and returned identity.

`capture.json` records exact request settings, requested/returned IDs, SDK version,
asset hashes, provider request IDs, UTC timestamps, status and usage. The selected
roster and all attempt identities are checkpointed before the first request; each
invocation is checkpointed before sending. A failed or interrupted run keeps every
selected case in the manifest. Unreached cases remain explicit extraction-failure
entries with audit state `not_invoked`; they are **not evidence of API calls**.
The existing runner's attempted-case denominator therefore conservatively covers
the entire selected roster; use the audit log for actual invocation counts.

Each case directory retains `provider.json`: a serialization of the SDK-exposed
response envelope, **not raw HTTP wire bytes**. Its SHA-256 is in the audit log.
One output text part is saved byte-for-byte as UTF-8 `response.txt` and pinned by
the manifest. Every output text part is also preserved separately and pinned in
the audit; multiple parts are never concatenated. Refusals, incomplete responses,
missing responses and multipart outputs remain extraction failures with their
available envelope/text retained. `no-response.txt` is an empty storage marker,
never a fabricated model response. Invalid JSON, Markdown fences, whitespace,
Unicode and offsets are preserved without repair. Only the existing adapter
decides model-output validity during offline analysis.

SDK automatic retries are zero. Requests are sequential, with at most one
generation per selected case. Every provider exception (including quota, billing,
access, unsupported parameters and timeout) stops the run; failed provider response
status also stops it. Exception messages, bodies and arbitrary headers are not
logged because they can contain credentials. Fixed exception class, HTTP status
and provider request ID are retained when available. SIGINT/SIGTERM preserve the
accounting and return 130; an uncatchable kill can leave `invoking` as an unknown
provider outcome. Never retry that attempt automatically. Normal exit is 0 for
captured single-part completed responses and 1 for capture/configuration failure;
captured invalid JSON can still exit 0.

Provider outcomes remain declared, not authenticated; all clinical evaluations
remain unverified. No independent clinical accuracy labels are added.

## Mocked verification

```bash
python -m pytest -q test/test_pilot_capture.py
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m experiments.dual_extraction.baseline --check
```

`test_real_sdk_success_preserves_output_text_with_mock_transport` runs the official
SDK against an in-process mocked HTTP response, captures one frozen Unicode case,
and verifies exact response bytes, token usage and provider IDs. The full-roster
test captures 15 mocked responses and invokes the existing runner successfully.
Mocked run data uses `simulated_actual_model_capture`, keeping it out of measured
actual-model results. Temporary tests separately verify the production manifest
population. The real-SDK transport tests require the optional SDK; CI installs it.
No live API request is part of development or verification.
