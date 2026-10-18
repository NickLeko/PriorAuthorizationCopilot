# Dual extraction experiment

This opt-in, offline experiment preserves the released regex extractor and the
existing service workflow. Phase 1 introduced the proposal contract and callable
seam described below. [Phase 2](PHASE2.md) adds validated hand-authored synthetic
recordings and pure structural reconciliation. There are no model calls,
credentials, three-mode comparison runner, or application mode switch.

## Frozen release behavior

The reference is v2.7.0, commit
`5d7a03f646eccd70e69bfc32f3281057b3bf6b54`. The separate
[`artifacts/regex-v2.7.0.jsonl`](artifacts/regex-v2.7.0.jsonl) contains a manifest
followed by 177 case records:

| Existing input | Cases | Service evaluations |
| --- | ---: | ---: |
| `inputs/synthetic_cases.json` | 52 | 52 |
| JSON examples in `EXTRACTION_CONTRACT.md` | 91 | 62 |
| `test/fixtures/v210_independent.json` | 20 | 20 |
| `inputs/replay/cases.json` | 14 | 14 |
| Total | 177 | 148 |

These are regression inputs, not held-out validation. The artifact records what
the release does, including known wrong proposals; it creates no clinical gold
labels and measures no semantic accuracy. Existing source labels are unchanged.
Contract examples without a procedure have extraction captures only. Replay
inputs are evaluated against the current active policy without importing their
synthetic attestation flags or performing counterfactual policy replay.

Every record includes the source identifier, exact note and SHA-256, request
metadata where declared, all 12 raw facts with Python type names, captured states,
ordered citations, offsets, truncation counts, and the downstream evaluation
where scoped. Each source runs once: scoped records reuse the service's immutable
original proposal. Only audit run IDs and wall-clock audit timestamps are
normalized. Values, snapshots, fingerprints, policy trust, and governance results
remain intact. The governance clock is the existing historical acceptance instant
`2026-09-01T00:00:00Z`; this does not refresh monitoring or change runtime clocks.

From the repository root, using the project's Python environment:

```bash
python -m experiments.dual_extraction.baseline --check
python -m experiments.dual_extraction.baseline --write
```

`--check` never writes. Regeneration requires explicit `--write`; review its diff
against the released capture. `--output` can direct a capture to a temporary file,
and `--repo-root` selects the repository input root. Production goldens and decision
archives are separate and must not be updated to accommodate experiment failures.

## Proposal contract and adapter

`proposals.ExtractionProposal` holds the original note, source identity, optional
string diagnostics, and an existing immutable `OriginalProposal`. Its validation
requires exactly the 12 existing fact keys and reuses `materialize()` for the
extractor vocabulary, state/value consistency, and exact source slices. The
Phase 2 entry gate additionally requires at least one retained valid citation
for every captured fact; missing/review evidence semantics are unchanged. The
legacy import adapter also validates raw types and offsets before JSON capture
can normalize them. This does not establish semantic support.

`extract_regex_proposal(note)` calls the unchanged extractor once.
`proposal_from_legacy(note, legacy_tuple, source=...)` captures an already obtained
result; `proposal_to_legacy(proposal)` returns fresh dictionaries and an
`EvidenceMap`. The latter explicitly restores `total_counts` from the snapshot
because its lists are already capped. Outbound adaptation revalidates the envelope
even if a caller used Pydantic's validation-bypassing model-copy methods.

Missing and review-required facts both use null in the snapshot's public value
map, distinguished by explicit states. Export restores the internal review
sentinel; captured false values remain false. Citation list order, offsets,
quotations and pre-cap counts survive both adaptation and JSON transport. Mapping
key insertion order is not part of the contract: the existing immutable snapshot
uses canonical sorted keys. Source and diagnostics never enter the snapshot or
production fingerprints.

## Injectable service boundary

The exact service type alias is:

```python
ExtractionCallable = Callable[[str], tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]]
```

`ReadinessService(extractor=...)` accepts this optional keyword-only callable. Its
input is the exact original note; its output is the existing raw fact/evidence
tuple. The evidence dictionary may be an `EvidenceMap` carrying `total_counts`.
There is no mode selection or production import of this experimental package.
With no injection the service resolves its existing imported `extract_facts` at
evaluation time, preserving existing callers and module-patch behavior. Even a
falsey callable is honored when explicitly supplied.

The same service validation, corrections, operators, attestations, fingerprints,
governance gates and result validators consume injected output. This seam does
not add caching or change service lifetime. A later offline runner must capture
each source once and provide a note-bound replay callable across modes; repeated
service evaluation alone would call its extraction dependency again.

## Checks

```bash
python -m pytest -q test/test_extraction_baseline.py test/test_extraction_proposals.py test/test_extraction_injection.py
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

The baseline and adapter tests exercise all existing input notes, including known
failures. Compatibility tests compare full evaluations with only audit identity
normalized, test human attestations and both trusted/untrusted governance, and
exercise archive reload/replay without re-extraction. Existing cross-surface and
golden tests continue to protect FastAPI, Streamlit, and CLI behavior.
