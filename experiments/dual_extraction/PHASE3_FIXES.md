# Phase 3 corrective patch: response attempts and complete review evidence

This patch starts from reviewed Phase 3 commit
`51b220d88a8e426a769a903734caf6acbea1edd7` on the separate branch
`codex/dual-extraction-phase3-fixes`. The fetched remote reference matched that
exact SHA and the new checkout was clean before changes. It resolves both blocking
review findings and restores the approved Phase 2 example.

All bundled responses, including the new raw examples and failure events, are
**hand-authored synthetic demonstrations, not real LLM outputs**. No provider,
credentials, live call, production integration or clinical rule is introduced.
This document supersedes the original Phase 3 protocol's response-rate definition
and representative-evidence behavior for REVIEW_REQUIRED. Historical protocol and
review evidence otherwise remain unchanged.

## Raw storage and selection boundary

Version 1 manifests still load the four already-adapted hand-authored recordings
through the existing strict replay boundary. They are descriptive fixtures and
never become measured model attempts. Their exact bytes and manifest are unchanged.

Version 2 adds only two small storage schemas: a raw attempt reference and an
explicit attempted-case manifest. It does not add a provider abstraction or a
capture client. Each attempted case has one outcome, with no retries or selection
of a favorable response. `selected_attempted_case_ids` must match the entries
exactly; dropping an unsuccessful entry while retaining its selection aborts the
run. Case IDs, attempt IDs and available source/response identities must be unique.
Unknown cases and mixed origins abort before artifact publication.

Each entry pins:

- Frozen case and exact note hash.
- Attempt ID, source, model, prompt version, response ID where available, and
  provider ID where available. A provider failure may have no response ID.
- Relative storage path and SHA-256 of the exact originally stored bytes.
- Declared outcome: response received or explicit extraction failure.

The version 2 population is either `synthetic_raw_demonstration` with
`hand_authored_synthetic` origin or `actual_model_study` with
`actual_model_response` origin. The latter is an explicitly declared offline
storage format for future recordings, not evidence that a model was called.
Actual-origin behavior is tested with an in-memory hand-authored simulation;
no committed example is labeled an actual model response. Version 1 and version 2
recordings are not mixed in one run.

After note/path/file-integrity checks, the runner calls
`adapt_recorded_response()` once for each raw response. Raw bytes are decoded
strictly as UTF-8; no JSON repair, offset conversion, fence stripping, metadata
injection, fact coercion or replacement checksum is performed. A successful
adapter result must also match the manifest's recording identity. Each mode then
reuses that one capture, as before. Invalid responses never become clinical
MISSING facts and receive no fabricated evaluation.

A declared provider/model failure preserves its original opaque failure bytes
and external identity after the same file-integrity check. It is not an adapter
request. A file declared as a response whose body contains an error object is an
adapter rejection; explicit extraction failures must be declared as such in the
trusted manifest. Raw files are never embedded in error messages or copied into
the comparison report. Synthetic note text in the existing frozen corpus remains
in its established report fields.

| Attempt outcome | Meaning |
| --- | --- |
| NOT_ATTEMPTED / ABSENT | No attempted-case entry; legacy hand-authored fixtures do not imply a model attempt |
| VALID_RESPONSE | Stored raw response passed adaptation and identity checks |
| INVALID_RESPONSE | UTF-8, JSON, schema, vocabulary, state/type, citation, offset, note or response identity rejection |
| EXTRACTION_FAILURE | Explicit manifest-declared provider/model failure with verified stored failure bytes |
| MISSING_RECORDING | Selected attempt has no stored file; it remains an attempt |
| STORED_FILE_INTEGRITY_FAILURE | Stored bytes differ from the manifest hash; adaptation is not attempted |
| MALFORMED_STORAGE | Inaccessible/out-of-scope storage or mismatched manifest note binding |
| Manifest failure | Invalid schema, roster, scope, duplicate identity or origin; abort the run |

Errors expose fixed codes only. Storage-integrity failures are separate from
model-output validity. The per-case report retains the manifest entry, population,
attempt outcome and whether adaptation was attempted even when no proposal exists.
A valid response followed by a downstream evaluation failure remains a valid
response; comparison failures and successful three-mode evaluations are separate.

## Honest denominator definitions

`response_accounting` has separate `actual_model`, `synthetic_raw_demonstration`
and `hand_authored_adapted` groups. Structural metrics stay descriptive. Adapted
hand-authored fixture failures have counts, not a measured LLM invalid-response
rate. No synthetic statistics are pooled into actual-model response metrics.

For each raw population:

- **Attempted cases:** every selected explicit attempt, including all failures.
- **Declared responses received:** entries declaring response, including files
  later missing or corrupt. This is a capture-manifest assertion, not validation.
- **Responses received:** integrity-verified raw replies on which adaptation was
  attempted, including malformed UTF-8/JSON and all other adapter rejections.
- **Invalid recorded-response rate:** adapter-rejected responses divided by
  adaptation-attempted responses (`invalid / (valid + invalid)`). Provider failures,
  missing files, integrity failures and malformed storage are excluded from this
  validity denominator because their response content could not be assessed.
- **End-to-end usable-response rate:** valid adapted responses divided by all
  selected attempts. Provider, missing-file, integrity and storage failures stay
  in this denominator. A usable extraction can still lack policy scope or fail
  downstream evaluation; successful three-mode evaluations are counted separately.
- **Not attempted:** frozen eligible cases minus selected attempts in that group.

Zero denominators produce null percentages, displayed as unavailable. The two
response rates must be read together; neither is clinical accuracy. The roster
and manifest are trusted local input. They cannot prove that an operator has not
removed an attempt from both lists or falsely declared origin. An actual study
must preserve its selected roster and capture log independently for review.

## Recomputed demonstration

The [new manifest](fixtures/phase3-fixes/manifest.json) declares eight synthetic
attempts. Seven files are present; one is deliberately absent. The changed-bytes
fixture deliberately appends a visible `TAMPERED` marker without updating its
original pinned checksum. These are authored failure cases, not repaired records.

| Synthetic raw accounting | Count |
| --- | ---: |
| Attempted cases | 8 |
| Declared responses received | 7 |
| Integrity-verified responses submitted to adaptation | 5 |
| Valid adapted responses | 1 |
| Adapter rejections | 4 |
| Provider/model extraction failures | 1 |
| Missing stored responses | 1 |
| File-integrity failures | 1 |
| Malformed storage failures | 0 |
| Not attempted in the 177-case corpus | 169 |
| Successful three-mode evaluations | 1 |

The simulated invalid-response rate is **4/5 = 80%**. The simulated end-to-end
usable-response rate is **1/8 = 12.5%**. Actual-model counts remain zero, with
both actual-model response-rate denominators **0/0** and percentages null.
This deliberately selected sample is not a model performance estimate.

Examples are [valid raw format](fixtures/phase3-fixes/valid-response.json),
[invalid Unicode byte offsets](fixtures/phase3-fixes/invalid-unicode-offset.json)
and [explicit provider failure](fixtures/phase3-fixes/provider-failure.json).
The Unicode note begins with `İ.`; OSA is at Python offsets `[3,6)` while the
invalid response uses UTF-8 byte offsets `[4,7)`. The stored bytes remain intact
and are rejected. Wrong type, uncited capture and malformed JSON supply the other
three adapter rejections.

See the [raw-attempt summary](artifacts/phase3-fixes/raw-attempts/summary.md) and
[full report](artifacts/phase3-fixes/raw-attempts/comparisons.json).
The existing four-recording [Phase 3 report](artifacts/phase3/summary.md) still
has 3 full comparisons, 1 extraction-only comparison and 173 absent recordings.
All 177 original case comparison/evaluation/decision fields and all six descriptive
structural rates match the reviewed commit exactly. The former misleading 0/4
invalid-response rate is removed; those four fixtures are now explicitly counted
as hand-authored adapted recordings with no measured LLM performance.

## Complete REVIEW_REQUIRED evidence

Whenever the dual disposition is NEEDS_REVIEW and both retained citation lists
differ, the canonical dual projection now retains both available sources. This
includes REVIEW_REQUIRED without changing its reason. Existing state/value
mismatch behavior is retained, including attribution when those reasons share an
identical span. Agreement behavior is unchanged.

Citations are deterministically interleaved, exact-span deduplicated, attributed
to regex/LLM/both, and capped at ten. If either combined source was already
truncated, its complete combined count stays unknown; no source totals are summed.
Both original proposals survive. Competing passages explicitly do not establish
one interpretation, no disagreement becomes CAPTURED, and linked lumbar fields
cannot be assembled from unrelated proposals.

The two fixed examples preserve the original REVIEW_REQUIRED reason:

- [Regex CAPTURED eight weeks; LLM NEEDS_REVIEW citing three weeks](artifacts/phase3/review-required-llm-example.json).
- [Regex NEEDS_REVIEW citing eight weeks; LLM CAPTURED three weeks](artifacts/phase3/review-required-regex-example.json).

These are hand-authored source-role reproductions. They do not claim to rerun the
production regex algorithm. Tests additionally cover already-truncated lists,
a duplicate shared span, exact cap/order and unknown complete counts. Agreement
continues to have `clinical_verification=false` and cannot grant human verification.

## Historical preservation and verification

The Phase 2 reconciliation example is restored byte-for-byte to approved Phase 2
commit `a32bb8a3a4764eff4b5fb0f8abdcad8248a81928`, SHA-256
`e96f873a00b5d2316a63d1171977be51e32da13f220818b63fffe40c48dd4479`.
The approved recorded-proposal example also remains identical. The current
[structural-v2 example](artifacts/phase3/structural-v2-reconciliation-example.json)
is separate and matches the structural-v2 example from the reviewed Phase 3 tip.
The current examples command pins the two approved historical hashes and only
writes current Phase 3 examples. The original Phase 2 generator was also run in
the untouched approved Phase 2 checkout and passed, as did Phase 1 baseline replay.

Test-first reproduction recorded **11 failures and 7 passes** before fixes:
unsupported raw manifests and hidden citations in both review roles, including
truncation. These are real behavioral failures, not absent-module collection
errors. Corrected tests cover valid adaptation, Unicode offsets, vocabulary/types,
uncited captures, malformed JSON/UTF-8, provider errors without response IDs,
missing/tampered storage, roster/identity failures, source immutability, no regex
recapture and no archive writes.

Final local verification: **532 focused tests passed; 2,213 full tests passed with
9 expected failures**. Ruff lint passed and all 100 Python files passed formatting.
Fixed-clock regeneration left all **27** protected production artifact/golden files
byte-identical before/after and versus approved Phase 2. The **177-case** frozen
regex baseline is unchanged. Historical protocols, decision archives, engine,
policies, entry points, verification and governance code are untouched.
[Machine-readable evidence](artifacts/phase3-fixes/verification.json) contains the
protected hashes and exact metric numerators/denominators. Test logs trim pytest's
trailing line whitespace without changing assertions or outcomes. Final pushed
SHA, clean status and remote CI evidence are supplied in the delivery handoff.

From the repository root with the project environment:

```bash
python -m experiments.dual_extraction.runner --check
python -m experiments.dual_extraction.runner --manifest experiments/dual_extraction/fixtures/phase3-fixes/manifest.json --output-dir experiments/dual_extraction/artifacts/phase3-fixes/raw-attempts --check
python -m experiments.dual_extraction.examples --check
python -m experiments.dual_extraction.baseline --check
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider test/test_extraction_*.py test/test_recorded_extraction.py test/test_disagreement_citations.py test/test_recording_integrity.py test/test_offline_experiment.py test/test_raw_response_attempts.py
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
python -m ruff check .
python -m ruff format --check .
```

Use explicit `--write` to regenerate current experimental outputs. No write mode
rewrites raw inputs or the approved Phase 2 examples. Output publication remains
nontransactional against a filesystem I/O failure, as documented in Phase 3.

## Remaining limits before an actual-model pilot

There are no real-model recordings in this patch. Provenance and provider errors
are manifest declarations, not authenticated provider attestations. Only exact
frozen synthetic notes are supported; one selected attempt per case is enforced.
There is no retry model, sampling/capture service or source authenticity mechanism.
The raw format is the exact body accepted by the existing strict adapter, not an
arbitrary provider SDK envelope. Unsupported wrappers are counted as rejected;
future capture must specify this contract rather than silently transform bytes.

Before a pilot, independently review this patch, freeze a selected roster and
capture protocol, choose model/prompt/parameters, and define independent semantic
labels. Offset/citation checks establish exact quotation, not semantic support or
correct course attribution. Agreement remains unverified; the known shared-error
demonstration still cannot become READY. No clinical accuracy or promotion claim
is supported. No live capture, provider integration, merge, release or deployment
has been performed.

## Implementation identity and complete changed-file inventory
- Citation fix: `742a5a6c84ee1d0e99de3d5cdd15b0a876b3ce1d`.
- Raw attempt accounting: `073b10cab63c417dd1c80c2ad9ec74b114812234`.
- Historical evidence separation: `0bb02c5b4a43d66977e42f4a7c2b18a5429c50d1`.

The final evidence commit follows these implementation commits. Its exact pushed
SHA and CI status are supplied in the delivery handoff. This 38-file inventory is
checked against the exact reviewed-base diff.

| File | Purpose |
| --- | --- |
| `experiments/dual_extraction/PHASE3_FIXES.md` | Corrective protocol, denominator definitions, review evidence, limitations and complete inventory |
| `experiments/dual_extraction/README.md` | Link to the corrective protocol while preserving historical phase documents |
| `experiments/dual_extraction/artifacts/phase2-reconciliation-example.json` | Restore exact approved Phase 2 structural-v1 bytes |
| `experiments/dual_extraction/artifacts/phase3-fixes/artifact-checks.txt` | Current and historical generator checks plus protected-file verification |
| `experiments/dual_extraction/artifacts/phase3-fixes/focused-tests.txt` | 532 passing focused tests |
| `experiments/dual_extraction/artifacts/phase3-fixes/full-tests.txt` | 2,213 passing full tests and nine expected failures |
| `experiments/dual_extraction/artifacts/phase3-fixes/quality.txt` | Ruff lint, format and full-branch whitespace evidence |
| `experiments/dual_extraction/artifacts/phase3-fixes/raw-attempts/comparisons.json` | All 177 cases, eight explicit simulated attempts, separate accounting and normalized outputs |
| `experiments/dual_extraction/artifacts/phase3-fixes/raw-attempts/correlated-error-example.json` | Explicit null: this raw sample contains no shared-error demonstration |
| `experiments/dual_extraction/artifacts/phase3-fixes/raw-attempts/summary.md` | Eight-attempt counts and precise simulated rate denominators |
| `experiments/dual_extraction/artifacts/phase3-fixes/raw-attempts/three-mode-example.json` | Valid synthetic raw response evaluated in all three modes |
| `experiments/dual_extraction/artifacts/phase3-fixes/red-tests.txt` | Test-first behavioral failures for raw-attempt accounting and review evidence |
| `experiments/dual_extraction/artifacts/phase3-fixes/verification.json` | Machine-readable tests, original-case invariance, production hashes and rate evidence |
| `experiments/dual_extraction/artifacts/phase3/comparisons.json` | Existing hand-authored comparison with schema-v2 explicit accounting; comparisons/evaluations unchanged |
| `experiments/dual_extraction/artifacts/phase3/correlated-error-example.json` | Existing shared-error result plus explicit non-attempt metadata |
| `experiments/dual_extraction/artifacts/phase3/review-required-llm-example.json` | Regex role captured eight weeks; LLM role reviews a competing three-week passage |
| `experiments/dual_extraction/artifacts/phase3/review-required-regex-example.json` | Regex role reviews eight-week passage; LLM role captured three weeks |
| `experiments/dual_extraction/artifacts/phase3/structural-v2-reconciliation-example.json` | Preserve reviewed structural-v2 example at a Phase 3 path |
| `experiments/dual_extraction/artifacts/phase3/summary.md` | Original structural results with corrected separate response accounting |
| `experiments/dual_extraction/artifacts/phase3/three-mode-example.json` | Existing duration-conflict result plus explicit non-attempt metadata |
| `experiments/dual_extraction/errors.py` | Two fixed storage failure codes without clinical payloads |
| `experiments/dual_extraction/examples.py` | Verify immutable historical hashes; generate current examples separately |
| `experiments/dual_extraction/fixtures/phase3-fixes/changed-bytes.json` | Deliberately corrupted synthetic raw bytes; original manifest checksum remains unchanged |
| `experiments/dual_extraction/fixtures/phase3-fixes/invalid-type.json` | Synthetic string instead of boolean; adapter rejection |
| `experiments/dual_extraction/fixtures/phase3-fixes/invalid-unicode-offset.json` | Synthetic UTF-8 offsets rather than Python offsets; adapter rejection |
| `experiments/dual_extraction/fixtures/phase3-fixes/malformed-response.json` | Synthetic malformed raw JSON preserved as an invalid response |
| `experiments/dual_extraction/fixtures/phase3-fixes/manifest.json` | Explicit eight-case attempted roster, external identities, outcomes and pinned file hashes |
| `experiments/dual_extraction/fixtures/phase3-fixes/provider-failure.json` | Opaque synthetic provider error; no response ID or actual provider call |
| `experiments/dual_extraction/fixtures/phase3-fixes/uncited-capture.json` | Synthetic CAPTURED without evidence; adapter rejection |
| `experiments/dual_extraction/fixtures/phase3-fixes/valid-response.json` | Hand-authored raw adapter-format response that passes validation |
| `experiments/dual_extraction/reconcile.py` | General NEEDS_REVIEW citation visibility without altering reasons or captured agreement |
| `experiments/dual_extraction/recorded.py` | Explicit actual-origin offline schema alternative; same strict fact/evidence gates |
| `experiments/dual_extraction/recordings.py` | Versioned raw manifest, attempted roster, optional failure response identity and read-only byte integrity |
| `experiments/dual_extraction/runner.py` | Adapt raw responses once, retain all failure outcomes, separate populations and validity/usability denominators |
| `test/test_disagreement_citations.py` | Both review-role regressions, truncation, duplicate provenance, caps and original preservation |
| `test/test_extraction_examples.py` | Separate current paths, historical immutability and both corrected review examples |
| `test/test_offline_experiment.py` | Replace misleading legacy validity-rate assertions with separate hand-authored counts |
| `test/test_raw_response_attempts.py` | Raw success/rejection/failure/storage/roster/privacy/reuse tests and reproducible bundled report |
