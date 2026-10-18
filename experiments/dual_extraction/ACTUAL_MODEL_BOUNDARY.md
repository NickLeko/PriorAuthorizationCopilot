# Final actual-model adapter boundary

Starting branch: `codex/dual-extraction-phase3-fixes`.
Exact reviewed starting SHA: `ee4c3488e74d2aafd24f10644717d0ae95e36c27`.
New branch: `codex/dual-extraction-actual-model-boundary`.
The fetched remote matched the required SHA and the isolated checkout was clean
before changes. Implementation commit: `f1d6841372d87d234e22407bf97ef280245dc1b4`.

This is a small input-boundary correction, with runtime changes in only
recorded.py, recordings.py and runner.py. It adds no provider client, service,
registry, database, dashboard, clinical rule or production integration. Every new
example is a hand-authored simulation. No live model call has been made.

## Accepted content and trusted identity

For actual-origin capture, call:

```python
recorded = adapt_recorded_response(note_text, raw_json_text, metadata=trusted_metadata)
```

The existing `RecordingMetadata` argument is strictly revalidated. It comes from
the trusted manifest, with actual_model_response origin, model, prompt, source
and response ID. Provider and attempt IDs remain on the existing manifest entry;
exact note binding and stored-byte checksum are verified before adaptation.
Actual-origin response entries lacking a valid response ID are capture identity
failures. A declared provider failure may still have no response ID.

The model body has exactly `facts` and `evidence_counts`. All twelve fact keys
remain mandatory, using existing FactContract types and extractor-emittable
values. Each cell has state/value/evidence, with existing count and citation gates.
The adapter combines validated content and trusted metadata only inside the
existing RecordedLLMProposal/accepted-content hash. It never inserts metadata
into the raw JSON, modifies its dictionary or rewrites stored bytes. File SHA-256
and normalized accepted-recording SHA-256 remain distinct identities.

The two-argument hand-authored pathway remains compatible. Existing adapted
recordings, legacy synthetic raw responses, proposal/reconciliation semantics,
and the service injection seam are unchanged. Actual-origin bodies containing
recording metadata or a note hash are rejected; the model cannot override trusted
identity. No new external recording-file version is needed: actual origin selects
the bare body, while hand-authored origin selects the legacy envelope.

UTF-8/JSON is strict: no Markdown fences, prose, duplicate keys, missing/additional
fact keys, type coercion, unsupported values, uncited captures, offset relocation,
Unicode normalization, quotation repair or retries. Offsets are exact Python
Unicode character indices, with exclusive end. Adapter rejections remain
INVALID_RESPONSE and their attempts remain in the usability denominator.

## Capture attribution and declarations

- External manifest/body identity mismatch: RECORDING_IDENTITY_FAILURE, counted
  as capture_identity_failures rather than model-output invalidity.
- Manifest note hash mismatch, or legacy envelope note mismatch:
  RECORDING_NOTE_MISMATCH, counted as note_identity_failures.
- Stored-byte mismatch remains STORED_FILE_INTEGRITY_FAILURE; path/I/O storage
  errors retain MALFORMED_STORAGE.
- Manifest-declared extraction_failure stays a capture-layer outcome. Even a file
  containing apparently valid extraction JSON does not change that declaration.
  An adversarial test demonstrates this; no provider success or failure is inferred
  from arbitrary bytes. The report explicitly says provider_outcomes_authenticated=false.

Manifest values are trusted local assertions, not cryptographic authentication or
provider verification. Preserve supporting capture logs for a future study. This
patch makes no remote identity lookup. Provider outcomes could be misdeclared by
an operator; the runner exposes the verification boundary rather than authenticating
it. Model-generated error objects cannot establish authenticated provider failures.

The invalid-response denominator remains valid + invalid model outputs; capture
identity/note/storage errors are excluded. Every selected attempt, including those
errors, provider failures and missing files, remains in end-to-end usability.
Responses received still counts integrity-verified replies entering the adapter;
a later capture identity failure can therefore appear in that count while being
excluded from model-output validity. New explicit failure counts explain the gap.

## Intentional experimental schema changes

Report schema version 3 adds:

- input_population and provider_outcomes_authenticated at the report root.
- capture_identity_failures and note_identity_failures in each raw accounting group.
- The two explicit capture-identity outcomes described above.
- An updated invalid-response population description; its formula is unchanged.

Manifest schema version 2 additionally permits simulated_actual_model_capture.
It exercises the exact actual-origin bare-content path while routing all counts
to synthetic_raw_demonstration and labeling the report as hand-authored, with no
real calls. Actual-model statistics remain zero. The prior two population values
and historical manifest hashes remain compatible. Actual_model_study is reserved
for future real captures; raw bodies on that path now require bare content.

Both existing Phase 3 reports were explicitly regenerated for these report fields.
All 177 case records, complete normalized evaluations, downstream decisions,
coverage, structural rates and numeric response-rate results in each report remain
identical to the reviewed commit. No historical raw fixture was rewritten.

## Examples and denominator evidence

[Valid bare model-style JSON](fixtures/actual-model-boundary/valid.json) and
[invalid-offset JSON](fixtures/actual-model-boundary/invalid-offset.json) are bound
to frozen notes by the [simulated capture manifest](fixtures/actual-model-boundary/manifest.json).
Both bodies contain only facts/counts; capture metadata is separate. In the Unicode
note, OSA is at Python [3,6); the rejected body supplies UTF-8 positions [4,7).
Neither file changes after adaptation. The actual-model origin is a simulated
format exercise, not a claim that these responses came from a real model.

| Population / test | Invalid-response rate | End-to-end usable-response rate |
| --- | --- | --- |
| Existing eight-attempt synthetic demonstration | 4 / 5 | 1 / 8 |
| New two-attempt bare-body simulation | 1 / 2 | 1 / 2 |
| Seven-attempt boundary regression: valid, invalid, provider, missing, identity, note, bytes | 1 / 2 | 1 / 7 |
| Real actual-model captures performed | 0 / 0, unavailable | 0 / 0, unavailable |

The seven-attempt regression proves capture failures do not inflate model-output
invalidity and do not disappear from end-to-end usability. Agreement remains
clinically unverified, and no synthetic rate is a clinical accuracy claim.

## Verification and pilot recommendation

Test-first run: 16 failures before implementation, demonstrating the unsupported
metadata keyword and incorrect attribution. Final targeted checks: 99 passed.
Focused experimental suite: 549 passed. Full regression: 2,230 passed with nine
expected failures. Ruff lint passed; all 101 Python files passed formatting.

Frozen baseline, historical examples, and both existing Phase 3 report checks pass.
All 27 protected production artifact/golden files remain byte-identical before and
after fixed-clock regeneration and versus approved Phase 2. All 22 protected
historical fixture/baseline/example files match the reviewed starting commit.
Production extraction, policies, readiness/verification semantics, fingerprints,
governance, entry points, dependency locks and archives are untouched. Tests forbid
source recapture and archive writes; comparisons remain unverified.

[Machine-readable verification](artifacts/actual-model-boundary/verification.json)
contains hashes, denominator evidence and simulated outcomes. The adjacent logs
contain failing/passing tests, full regression, quality and artifact checks. Only
pytest trailing line whitespace was trimmed when packaging evidence. The final
pushed SHA and exact-commit CI results are supplied in the delivery handoff.

The concise [pilot protocol](pilot/PROTOCOL.md), [15-case roster](pilot/cases-v1.json)
and [full proposed model prompt](pilot/prompt-v1.md) freeze the dataset, snapshot,
prompt and generation settings. They separate ordinary/challenge/known-failure
strata and prescribe one original capture per case, no repair/retry and retention
of every failure. The selected model is a proposal, not a live configuration.

No known adapter-code blocker remains after verification. Launch still requires
explicit live-call approval, provider access and a trusted capture procedure that
preserves exact content, metadata and all attempts. The roster has a negated-exclusion
challenge rather than a literal “does not deny” example; this coverage limit is
explicit in the protocol. Independent semantic labels are required for correctness
claims. No broad audit, pilot execution, merge, tag, release or deployment is part
of this patch.

Reproduce using the project environment from the repository root:

```bash
python -m experiments.dual_extraction.baseline --check
python -m experiments.dual_extraction.examples --check
python -m experiments.dual_extraction.runner --check
python -m experiments.dual_extraction.runner --manifest experiments/dual_extraction/fixtures/phase3-fixes/manifest.json --output-dir experiments/dual_extraction/artifacts/phase3-fixes/raw-attempts --check
python -m experiments.dual_extraction.runner --manifest experiments/dual_extraction/fixtures/actual-model-boundary/manifest.json --output-dir /tmp/pa-bare-simulation --write
python -m experiments.dual_extraction.runner --manifest experiments/dual_extraction/fixtures/actual-model-boundary/manifest.json --output-dir /tmp/pa-bare-simulation --check
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
python -m ruff check .
python -m ruff format --check .
```

## Complete changed-file inventory

The 25-file inventory is checked against the exact reviewed-base diff. Final
pushed SHA, clean status and CI evidence are supplied in the delivery handoff.

| File | Purpose |
| --- | --- |
| `experiments/dual_extraction/ACTUAL_MODEL_BOUNDARY.md` | Boundary contract, attribution, schema changes, verification, examples and complete inventory |
| `experiments/dual_extraction/README.md` | Link the final boundary and proposed pilot without changing historical protocols |
| `experiments/dual_extraction/artifacts/actual-model-boundary/artifact-checks.txt` | Frozen baseline, historical/current examples, both reports and protected-file checks |
| `experiments/dual_extraction/artifacts/actual-model-boundary/focused-tests.txt` | 549 passing focused experimental checks |
| `experiments/dual_extraction/artifacts/actual-model-boundary/full-tests.txt` | 2,230 passing regression tests and nine expected failures |
| `experiments/dual_extraction/artifacts/actual-model-boundary/green-tests.txt` | 99 passing adapter/attempt boundary checks |
| `experiments/dual_extraction/artifacts/actual-model-boundary/quality.txt` | Ruff lint, 101-file formatting and branch whitespace checks |
| `experiments/dual_extraction/artifacts/actual-model-boundary/red-tests.txt` | 16 failing targeted boundary/attribution tests before implementation |
| `experiments/dual_extraction/artifacts/actual-model-boundary/verification.json` | Protected hashes, invariant historical reports, simulated outcomes and denominators |
| `experiments/dual_extraction/artifacts/phase3-fixes/raw-attempts/comparisons.json` | Explicit schema-v3 accounting fields; all original case outcomes and rate values preserved |
| `experiments/dual_extraction/artifacts/phase3-fixes/raw-attempts/summary.md` | Expose separate capture/note identity counts and clarified denominator description |
| `experiments/dual_extraction/artifacts/phase3/comparisons.json` | Explicit schema-v3 population/authentication/accounting; all original results preserved |
| `experiments/dual_extraction/artifacts/phase3/summary.md` | Expose separate capture/note identity counts and clarified denominator description |
| `experiments/dual_extraction/fixtures/actual-model-boundary/invalid-offset.json` | Hand-authored bare response with invalid UTF-8-style citation offsets |
| `experiments/dual_extraction/fixtures/actual-model-boundary/manifest.json` | Clearly simulated actual-origin capture, trusted metadata and exact raw byte hashes |
| `experiments/dual_extraction/fixtures/actual-model-boundary/valid.json` | Hand-authored bare facts/counts response accepted with external metadata |
| `experiments/dual_extraction/pilot/PROTOCOL.md` | Concise fixed-model, one-shot, synthetic-only pilot proposal and execution prerequisites |
| `experiments/dual_extraction/pilot/cases-v1.json` | Fifteen frozen note identities spanning four pathways and all twelve existing fact keys |
| `experiments/dual_extraction/pilot/prompt-v1.md` | Complete proposed bare-JSON extraction prompt using existing FactContracts |
| `experiments/dual_extraction/recorded.py` | Optional separately validated actual-origin metadata and strict bare content schema |
| `experiments/dual_extraction/recordings.py` | Explicit simulated actual-origin population and separate note-hash failure classification |
| `experiments/dual_extraction/runner.py` | Pass trusted metadata separately; attribute capture errors correctly; mark declared outcomes unauthenticated |
| `test/test_actual_model_boundary.py` | Bare content, strict parsing/types/citations, immutable raw bytes, attribution and unauthenticated failure declarations |
| `test/test_raw_response_attempts.py` | Update actual-origin simulation to bare content and assert capture/note attribution |
| `test/test_recorded_extraction.py` | Assert explicit note identity failure without changing legacy extraction validation |
