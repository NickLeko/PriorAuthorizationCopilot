# Phase 3: offline three-mode comparisons

All four bundled recordings are **hand-authored synthetic proposals, not outputs
of a real LLM**. This is a structural experiment, including deliberately wrong
proposals and a known shared error. It makes no clinical accuracy or population
performance claim. No production integration, live calls, provider credentials,
database, decision-archive writes, or application mode switches are introduced.

## Run and reproduce

From the repository root with the project environment:

```bash
python -m experiments.dual_extraction.runner --check
python -m experiments.dual_extraction.runner --write
python -m experiments.dual_extraction.baseline --check
python -m experiments.dual_extraction.examples --check
```

Writing requires explicit `--write`. `--check` computes the results and compares
without writing. Use `--manifest <path>` for a reviewed recording manifest and
`--output-dir <path>` for separate experimental artifacts. Inputs are fully loaded
and compared before artifact writing starts. Source validation/configuration
failures abort before publishing output. A filesystem I/O failure during writing
is not a transactional publication guarantee.

The default outputs are separate from production goldens and decision archives:

- [Machine-readable report](artifacts/phase3/comparisons.json).
- [Human-readable summary](artifacts/phase3/summary.md).
- [Three-mode decision-disagreement example](artifacts/phase3/three-mode-example.json).
- [Known shared-error example](artifacts/phase3/correlated-error-example.json).

For a run with no applicable example, the corresponding example file contains
JSON null, replacing any previous example rather than leaving stale results.

## Frozen inputs and honest coverage

The runner reads the existing 177-case baseline and verifies its approved SHA-256
before parsing. It reconstructs validated regex proposals from those captures;
it does not call the regex extractor or a model. The baseline's 148 scoped
evaluations retain their policy definitions and request metadata. The other 29
notes remain extraction-only eligible; payer/procedure metadata is not invented.

None of the three Phase 2 recording notes exactly matches a frozen note. Those
source fixtures are unchanged and are not silently substituted. Four deliberately
curated recordings for frozen notes are pinned by the
[Phase 3 manifest](fixtures/phase3/manifest.json):

| Frozen case | Purpose | Evaluation |
| --- | --- | --- |
| `inputs/synthetic_cases.json#MRI-01-complete` | Synthetic three-versus-eight-week conflict | Three modes |
| `EXTRACTION_CONTRACT.md#neither_nor_negation` | Known correlated/shared error | Three modes |
| `EXTRACTION_CONTRACT.md#unicode` | Unicode CPAP proposal | Three modes |
| `EXTRACTION_CONTRACT.md#therapy_weeks` | Unscoped therapy proposal | Extraction only |

The remaining 173 cases have no recording. No placeholder LLM facts are generated
for them. These four selected responses are not independent clinical labels or
held-out model results. In particular, the duration conflict deliberately cites
eight-week text for a three-week value to exercise downstream disagreement.

Coverage reports eligible cases, policy-supported/incomplete/unsupported scopes,
valid recordings, absent entries, missing files, malformed recordings, integrity
failures, successful three-mode comparisons, extraction-only comparisons, and
comparison failures. Recording-status counts partition the corpus; scope counts
are a separate dimension. Absent and missing-file recordings never become
`MISSING` clinical facts or a manufactured service evaluation.

## Review follow-up: competing citations

The exact NSAID-eight-week versus gabapentin-three-week reproduction first failed
against Phase 2. `STATE_DISAGREEMENT` and `VALUE_DISAGREEMENT` now retain available
citations from both sources in deterministic regex/LLM interleaving order, then
deduplicate exact `(start,end,text)` identities and apply the existing ten-span
cap. Interleaving ensures one source's long list does not crowd out the other.
Each retained citation has source-role attribution; full source-specific evidence
remains in both immutable original proposals.

When both inputs are complete, the deduplicated combined total can be stated
exactly. When either combined source was already truncated, the complete total
is unknown: `dual_complete_citation_count=null`, an observed unique count and cap
indicator are retained, and `COMBINED_CITATION_TOTAL_UNKNOWN` is emitted. The
canonical proposal contains capped retained spans with no invented total-count
metadata. This is compatible with the existing contract; its absent total must
not be interpreted as complete evidence by an experimental consumer.

`COMPETING_CITATIONS_NOT_A_SHARED_INTERPRETATION` explicitly warns that passages
can support competing interpretations. Source totals are never summed. Agreed
captured facts retain their original regex evidence and snapshots unchanged.
Review-state propagation keeps its prior representative-evidence behavior; both
originals are always preserved in the experimental record.

Both linked lumbar fields can be captured only when both sources captured both
matching values; both canonical lists then come from the same regex proposal.
Combining citations for unresolved review facts never creates a captured course.
No new drug interpretation or clinical rule is added by the gabapentin test.

This follow-up uses `structural-v2`. The existing small experimental Phase 2
reconciliation example was explicitly regenerated for the new comparison fields
and citation provenance. Production goldens and the 177-case baseline are unchanged.

## Review follow-up: strict recording reload

`recordings.load_manifest()` validates the explicit schema and enforces one entry
per case and unique `(source,response_id)` identities. Duplicate identities or
unknown case IDs invalidate the manifest rather than being silently skipped.

`recordings.load_recording()` reads a stored proposal once, checks its pinned file
SHA-256, strictly revalidates the proposal and citation gate, verifies exact note
identity and all source/model/prompt/response identifiers, and reconstructs the
adapter's normalized recording content to verify `recording_sha256`. It also
compares that content hash to the separately pinned manifest value. It never
restamps a failed hash or rewrites an input. Tampering remains a failure even if
a caller updates only the file checksum but leaves an inconsistent content hash.

Errors are fixed codes, without note text or raw payloads:

| Code | Treatment |
| --- | --- |
| `MISSING_RECORDING` | Separate missing-file coverage |
| `MALFORMED_RECORDING` | Rejected structure/validation |
| `RECORDING_INTEGRITY_FAILURE` | Rejected checksum/content mismatch |
| `RECORDING_IDENTITY_FAILURE` | Rejected identity mismatch; duplicates invalidate manifest |
| `RECORDING_NOTE_MISMATCH` | Rejected exact-note mismatch |
| `INVALID_RECORDING_MANIFEST` | Abort ambiguous/invalid experiment configuration |
| `INVALID_FROZEN_BASELINE` | Abort changed frozen corpus |
| `EXPERIMENT_CONTEXT_CHANGED` | Abort inconsistent policy/governance context |

Malformed syntax is distinguished from integrity failure after the file checksum:
unknown modifications fail integrity first; explicitly pinned malformed JSON fails
structure validation. Hashes bind files/content to a reviewed manifest, not to an
authenticated model provider. Editing both data and all trusted manifest hashes
defines a new input requiring review; these are not signatures.

## Comparison and evaluation

The runner loads each recorded source once and reconciles once per valid case.
Regex-only, recorded-only, and dual callables reuse those same captures and reject
any different note. Every legacy conversion passes through `ExtractionProposal`
validation. The existing service evaluates the same request and frozen policy
with the established fixed governance clock, `2026-09-01T00:00:00Z`.

Regex-only results must match the complete frozen evaluation, with only audit run
IDs/timestamps normalized. Bundle/policy changes, different cross-mode policy trust,
or changed surrounding rulebook/drift context abort the run. This does not change
production governance or refresh monitoring. No attestations or corrections are
carried into any mode, and no mode auto-verifies a fact.

Each valid case preserves all 12 source/dual facts with exact Python type names,
states, quotations, offsets, ordering, count metadata, disagreement reasons,
source and recording identities, per-citation attribution, completeness flags,
and advisory numeric observations. Scoped cases include full normalized service
results, requirement-status comparisons, overall statuses, submission readiness,
and relevant governance conditions. Unscoped cases have no invented evaluations.

Every rate includes a numerator, denominator, and population definition. Value
agreement uses only both-captured fact pairs; state/citation/review rates use all
valid fact comparisons, including empty citation sets. Invalid-response rate
includes malformed/integrity-rejected available recordings but excludes absent
entries/missing files. Downstream difference rate uses requirements in successful
three-mode cases. A zero denominator produces null, never fictitious agreement.
The shared-error demonstration is included and explicitly labeled in the totals.

## Limits and next study

Structural agreement is not semantic truth. The neither/nor note produces an
unsupported affirmative diagnosis in both regex and the hand-authored recording;
reconciliation says `AGREED_CAPTURE`, keeps the value, and still reports
`clinical_verification=false`. All three service outcomes remain
`PENDING_VERIFICATION`. This is an adversarial demonstration, not independent
clinical evaluation. Numeric literal flags are advisory and can flag valid unit
normalization; no new clinical thresholds are inferred.

The next actual-model study should first select a provider/model and versioned
prompt plus generation parameters, explicitly extend origin metadata beyond
hand-authored recordings, and add a separately invoked synthetic-only capture
step. Persist actual responses once with note identity, recording identity,
provider provenance and pinned hashes, then run the same offline comparison.
Define the sampling plan and separate shared-error demonstrations from ordinary
study strata. Independent reviewed labels and a held-out design are required
before correctness/precision/recall claims. No live-model integration is included
in this phase.
