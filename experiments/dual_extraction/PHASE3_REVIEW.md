# Phase 3 independent review handoff

Phase 3 resolves competing-citation visibility and stored-recording integrity,
then runs frozen regex-only, recorded-only and dual proposals through the existing
service. Every bundled recording is **hand-authored synthetic, not produced by a
real LLM**. This phase makes no clinical accuracy claim.

## Identity and scope

- Approved Phase 2 base: `a32bb8a3a4764eff4b5fb0f8abdcad8248a81928`.
- Branch: `codex/dual-extraction-phase3`.
- Isolated checkout: `/private/tmp/pa-copilot-dual-extraction-phase3`.
- Disagreement citation fix: `16b0ef82b74d3b59a32fe2a980df1d071ac15702`.
- Recording integrity fix: `ddca0afb6b7f6c8bce7012cd5817aa7bde0fe6c6`.
- Runner, fixtures and report: `d8e9024aa10ee95e8bd3cbea8d36d93ddd530884`.
- This evidence handoff is committed afterward. Its final SHA and post-push clean
  status are supplied in the delivery message; resolve the pushed tip with
  `git rev-parse origin/codex/dual-extraction-phase3`.

The approved remote Phase 2 reference and clean starting state were verified
before creating this branch from that exact SHA. The main checkout and prior
phase worktrees remain separate. No production source, extraction algorithm,
clinical vocabulary, policy, verification, governance, entry point, dependency,
archive or historical production golden changed. No merge, release, deployment,
provider client, credentials or live call is part of Phase 3.

## Review findings resolved

The exact synthetic reproduction gives regex eight weeks from an NSAID passage
and the recorded proposal three weeks from a gabapentin passage. Before the fix,
the dual result was NEEDS_REVIEW but hid the competing passage. Five new citation
checks failed against Phase 2, including this exact example; one already passed.
After the fix, state/value disagreements interleave regex/recorded citations,
deduplicate exact `(start,end,text)` spans, then retain at most ten. Per-span roles
and both original proposals remain available. Competing passages explicitly do
not represent one shared interpretation.

Complete sources permit an exact deduplicated combined count. If either source
was truncated, the complete combined count stays unknown, with an explicit
diagnostic and observed unique count. The canonical projection omits invented
total metadata and preserves the existing contract. Experimental consumers must
read the unknown-count diagnostic. Agreed captures retain existing regex
citations; linked lumbar duration/response captures cannot be assembled from
different proposals. Existing review-state propagation keeps its prior
representative evidence; full originals remain available separately.

Stored proposals now pass a read-only replay boundary: strict manifest/schema,
unique case and `(source,response_id)` identities, pinned stored-byte checksum,
exact note binding, complete source/model/prompt/response metadata equality,
strict proposal revalidation, and normalized recording-content hash equality
against both the record and manifest. No failed hash is silently replaced.
Missing files, malformed content and integrity/identity/note failures have
separate fixed codes; errors contain no note text or raw payload. Duplicate
identities invalidate an ambiguous manifest. Hashes trust the reviewed manifest;
they are not provider authentication or signatures.

## Runner and first report

The runner verifies and reads the existing 177-case frozen baseline, loads each
available recording once and reconciles once. All three modes reuse those same
captures through the validated callable seam. Scoped evaluations use one request,
one frozen policy, one bundle and `2026-09-01T00:00:00Z`. Regex-only full normalized
results must match the frozen results. A context change aborts publication.
No attestations/corrections are supplied and no results enter production archives.

None of the three Phase 2 fixture notes exactly matches the frozen corpus. They
remain unchanged. Four explicitly selected frozen notes therefore have new,
hand-authored synthetic recordings; no outputs fill the other coverage gaps.

| Coverage | Cases |
| --- | ---: |
| Eligible frozen synthetic notes | 177 |
| Supported policy scope | 148 |
| Incomplete scope / unsupported scope | 29 / 0 |
| Valid hand-authored recordings | 4 |
| Without recordings (all absent manifest entries) | 173 |
| Rejected recordings / missing files | 0 / 0 |
| Full three-mode comparisons | 3 |
| Extraction-only comparison | 1 |
| Comparison failures | 0 |
| Known shared-error demonstration | 1 |

Missing recordings never become clinical MISSING facts. No payer/procedure is
invented for the unscoped note. All twelve fact keys preserve exact types, states,
values and citations in each compared proposal. Every evaluated requirement
remains UNVERIFIED and every submission-readiness result is false.

| Structural metric | Numerator / denominator | Percent |
| --- | ---: | ---: |
| Value agreement, both-captured pairs | 15 / 17 | 88.2353% |
| State disagreement, valid fact pairs | 0 / 48 | 0% |
| Retained citation-set disagreement, including empty sets | 3 / 48 | 6.25% |
| Retained citation-order disagreement | 3 / 48 | 6.25% |
| Dual NEEDS_REVIEW | 2 / 48 | 4.1667% |
| Invalid available recorded responses, excluding absent/missing | 0 / 4 | 0% |
| Requirements with any mode status difference | 1 / 11 | 9.0909% |

These rates include deliberate adversarial examples. They describe structural
comparisons only, without independent correctness labels or population inference.
Zero-denominator rates are null. Incomplete citations remain marked incomplete.

The [three-mode example](artifacts/phase3/three-mode-example.json) has regex
PENDING_VERIFICATION, recorded-only NOT_READY and dual NEEDS_REVIEW. Its manual
three-week proposal intentionally cites eight-week text to exercise disagreement.
The [shared-error example](artifacts/phase3/correlated-error-example.json) uses the
actual frozen neither/nor regex limitation. Both sources agree on an unsupported
affirmative diagnosis; reconciliation says AGREED_CAPTURE and retains true, while
`clinical_verification=false` and all three results remain PENDING_VERIFICATION.
This is a labeled demonstration, not an independently held-out clinical evaluation.

See the [summary](artifacts/phase3/summary.md),
[complete machine-readable report](artifacts/phase3/comparisons.json), and
[protocol](PHASE3.md) for full fields and exact denominator definitions.

## Verification and reproduction

- Approved Phase 2 entry checks: 478 passed.
- Exact citation reproduction before fix: five failures, one pass; after fix plus
  existing reconciliation checks: 111 passed.
- Integrity checks plus existing recorded-adapter checks: 76 passed. Integrity and
  runner red logs document absent-module collection failures, not behavioral red tests.
- All new Phase 3 checks: 30 passed (6 citation, 13 integrity, 11 runner).
- Final combined focused suite: 508 passed in 7.25 seconds.
- Full regression: 2,189 passed, nine expected failures in 44.41 seconds.
- Ruff lint passed; all 99 Python files already formatted; whitespace check passed.
- Runner repeated results and explicit write/check match; baseline and Phase 2
  example checks match.
- Fixed-clock production artifact/golden regeneration: all 27 tracked files are
  byte-identical before/after and to approved Phase 2. This includes the artifacts
  README that is preserved alongside generated files.
- Frozen 177-case baseline is byte-identical to approved Phase 2, SHA-256
  `af9a1805c42df33e2985542a7b85307262dfa0fe8ab33cfcbf7f69d2ece46728`.
- Tests forbid regex recapture, recorded adapter recapture and archive writes;
  they assert four loads/four reconciliations and unchanged source bytes.
- Tampered baseline, changed context, unknown/duplicate identities, changed content,
  missing/malformed recordings and zero coverage have explicit tested outcomes.

With the project environment active, reproduce from this checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider test/test_extraction_*.py test/test_recorded_extraction.py test/test_disagreement_citations.py test/test_recording_integrity.py test/test_offline_experiment.py
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
python -m ruff check .
python -m ruff format --check .
python -m experiments.dual_extraction.runner --check
python -m experiments.dual_extraction.baseline --check
python -m experiments.dual_extraction.examples --check
```

Production regeneration was invoked through
`scripts.generate_artifacts.main(utc_now_provider=lambda: ACCEPTANCE_GOVERNANCE_NOW)`
and `scripts.generate_golden_outputs.main` with the same provider, then every
protected file was compared byte-for-byte with its approved Git version.
[Verification JSON](artifacts/phase3-verification.json) records all 27 hashes,
implementation identities, baseline hash, tests, coverage and metrics. The complete
changed-file inventory below includes the preserved test and check logs.
Trailing line whitespace emitted by pytest is trimmed in packaged logs; test
content and outcomes are unchanged.

## Complete changed-file inventory

| File | Purpose |
| --- | --- |
| `experiments/dual_extraction/PHASE2.md` | Update current reconciliation and runner documentation; historical Phase 2 review preserved |
| `experiments/dual_extraction/PHASE3.md` | Protocol, reproduction commands, failure taxonomy, metrics, limitations and next study |
| `experiments/dual_extraction/PHASE3_REVIEW.md` | Independent review handoff, complete inventory and verification evidence |
| `experiments/dual_extraction/README.md` | Link the explicitly invoked Phase 3 runner |
| `experiments/dual_extraction/artifacts/phase2-reconciliation-example.json` | Explicitly regenerate experimental example for structural-v2 provenance fields |
| `experiments/dual_extraction/artifacts/phase3-artifact-checks.txt` | Runner, frozen baseline and Phase 2 example checks; production artifact comparison evidence |
| `experiments/dual_extraction/artifacts/phase3-citations-green.txt` | 111 passing citation/reconciliation checks after the fix |
| `experiments/dual_extraction/artifacts/phase3-citations-red.txt` | Exact regression reproduction before fix: five failures and one pass |
| `experiments/dual_extraction/artifacts/phase3-entry-tests.txt` | 478 approved Phase 2 focused checks before changes |
| `experiments/dual_extraction/artifacts/phase3-focused-tests.txt` | 508 passing final experimental focused checks |
| `experiments/dual_extraction/artifacts/phase3-full-tests.txt` | Full suite: 2,189 passed and nine expected failures |
| `experiments/dual_extraction/artifacts/phase3-integrity-green.txt` | 76 passing integrity/recorded-adapter checks |
| `experiments/dual_extraction/artifacts/phase3-integrity-red.txt` | Test-first collection failure before recording loader existed |
| `experiments/dual_extraction/artifacts/phase3-quality.txt` | Ruff lint, 99-file format check and whitespace check |
| `experiments/dual_extraction/artifacts/phase3-runner-green.txt` | 30 passing new citation, integrity and runner tests |
| `experiments/dual_extraction/artifacts/phase3-runner-red.txt` | Test-first collection failure before runner existed |
| `experiments/dual_extraction/artifacts/phase3-verification.json` | Machine-readable verification, production file hashes, coverage and rate denominators |
| `experiments/dual_extraction/artifacts/phase3/comparisons.json` | Complete normalized 177-case coverage and comparison report |
| `experiments/dual_extraction/artifacts/phase3/correlated-error-example.json` | Known shared-error case with all three unverified service outputs |
| `experiments/dual_extraction/artifacts/phase3/summary.md` | Human-readable coverage, denominators, outcomes and limits |
| `experiments/dual_extraction/artifacts/phase3/three-mode-example.json` | MRI duration-conflict case with full three-mode service outputs |
| `experiments/dual_extraction/errors.py` | Fixed payload-free integrity, manifest, baseline and evaluation failure codes |
| `experiments/dual_extraction/fixtures/phase3/manifest.json` | Four explicit case bindings with pinned identity, note, file and content hashes |
| `experiments/dual_extraction/fixtures/phase3/recordings/cpap-unicode.json` | Hand-authored synthetic Unicode CPAP recording; no real model |
| `experiments/dual_extraction/fixtures/phase3/recordings/lumbar-duration-conflict.json` | Hand-authored synthetic three-versus-eight-week conflict; no real model |
| `experiments/dual_extraction/fixtures/phase3/recordings/shared-error-neither-nor.json` | Hand-authored synthetic unsupported affirmative diagnosis; no real model |
| `experiments/dual_extraction/fixtures/phase3/recordings/therapy-extraction-only.json` | Hand-authored synthetic unscoped therapy recording; no real model |
| `experiments/dual_extraction/reconcile.py` | Deterministic competing citations, truthful unknown totals and per-span source roles |
| `experiments/dual_extraction/recordings.py` | Strict read-only recording manifest and replay integrity boundary |
| `experiments/dual_extraction/runner.py` | Offline frozen-capture reuse, three service modes, coverage, metrics and write/check CLI |
| `test/test_disagreement_citations.py` | Exact adversary, state/value disagreements, ordering, deduplication, cap/count and agreed behavior |
| `test/test_offline_experiment.py` | Reproducibility, mode reuse, no recapture/archives, failures, coverage, governance and artifact checks |
| `test/test_recording_integrity.py` | Tampering, note/identity swaps, duplicates, strict parsing, missing files and immutable reload |

## Limitations, questions and next step

There are no blocking unresolved Phase 3 design questions. Study choices remain:
which real model/prompt/parameters to freeze; how to sample synthetic notes; and
who will independently label and adjudicate correctness. This implementation
intentionally accepts only hand-authored origin metadata and has no provider
integration. Four curated recordings with 17 both-captured fact pairs cannot
support clinical accuracy or generalization claims. Many of the 48 compared
cells are both missing; denominators remain explicit.

The manifest is a trusted local input, not an authenticated source. Citation
checks establish exact note quotation, not semantic support or the correct
patient/course. Numeric flags are advisory and can flag legitimate normalization.
Canonical retained-count metadata cannot express an unknown complete total, so
experimental diagnostics carry that distinction. Review-state propagation still
uses representative evidence as documented. The fixed historical governance clock
is for reproducibility and makes no current-policy freshness claim. Artifact
publication validates all input before writing but is not transactional against
filesystem failure.

The recommended next step is a separately approved synthetic actual-model study:

1. Freeze a sampling plan and reserve the known shared-error/adversarial cases as
   separately labeled strata; specify coverage for all 12 existing keys and four
   pathways, including missingness and citation truncation.
2. Choose and version the provider/model, prompt/schema and generation parameters;
   explicitly extend the origin contract for real captured responses.
3. Add a separately invoked synthetic-only capture step that stores one actual
   response per case with exact note/recording identities, full provider provenance
   and pinned hashes; keep capture separate from offline comparison.
4. Run these same deterministic comparisons against those recordings, retaining
   failures and missing coverage. Keep extraction states, verification, policy,
   governance and production behavior unchanged.
5. Obtain independent reviewed labels and adjudication before any correctness,
   precision/recall or promotion decision. Repeated agreement alone is insufficient.

No part of that live-model study has been started in Phase 3.
