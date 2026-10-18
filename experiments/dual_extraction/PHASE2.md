# Phase 2: recorded proposals and structural reconciliation

This offline package accepts **hand-authored synthetic recordings only**. The
fixtures are not outputs of a real model, prompts are not implemented, and no
provider, credentials, network call, production mode switch,
or production archive write is present. The offline comparison runner is described
in [Phase 3](PHASE3.md). `model_id: synthetic-no-model` and
`origin: hand_authored_synthetic` make that provenance explicit.

## Citation entry gate

Every `CAPTURED` fact in `ExtractionProposal` must have at least one retained
valid citation. This applies to all 12 existing keys, including captured false
values. Exact Unicode character offsets and original text are checked by the
existing validators. Counts cannot stand in for quotations. The existing
`MISSING` and `NEEDS_REVIEW` evidence semantics are unchanged. Production service
validation is unchanged; the additional gate is in the experimental contract.

## Recorded-response protocol

`adapt_recorded_response(note_text, payload)` accepts a JSON string or dictionary
of JSON data and returns a `RecordedLLMProposal` containing recording metadata,
the normalized recording SHA-256, and the validated `ExtractionProposal`.

The response has this structure (the real fixtures include all 12 keys):

```json
{
  "recording": {
    "source": "recorded-llm:synthetic",
    "model_id": "synthetic-no-model",
    "prompt_version": "synthetic-schema-v1",
    "response_id": "synthetic-example",
    "origin": "hand_authored_synthetic"
  },
  "note_sha256": "<SHA-256 of the exact original note>",
  "facts": {
    "osa_diagnosis": {
      "state": "CAPTURED",
      "value": true,
      "evidence": [{"start": 0, "end": 3, "text": "OSA"}]
    }
  },
  "evidence_counts": {}
}
```

Each fact must explicitly supply its state, value, and evidence list. Non-captured
values must be null. Captured values use the existing **extractor** vocabulary,
not reviewer vocabulary or policy passing values. Evidence is never repaired,
re-located, or silently truncated. Each list has at most ten retained citations;
declared original totals must satisfy the existing capped-count structure.
Empty evidence lists are represented by absent keys in the legacy evidence map.

Unknown fields/keys, wrong types, duplicate JSON keys, nonfinite JSON numbers,
incorrect note hashes, invented spans, and missing citations fail explicitly.
Python model objects are not raw JSON recordings and are rejected, including
objects constructed through validation-bypassing Pydantic methods.

Failures raise payload-free `ExperimentFailure` codes:

| Code | Meaning |
| --- | --- |
| `INVALID_RECORDED_RESPONSE` | Malformed or invalid recording; no proposal returned |
| `RECORDED_EXTRACTION_FAILURE` | The recording contains an explicit error; no proposal returned |
| `INVALID_PROPOSAL` | Reconciliation input failed revalidation or is not a proposal |
| `NOTE_MISMATCH` | The two proposals refer to different exact note strings |

These errors never become `MISSING`. Adapter/reconciler code does not log notes,
quotations, raw responses, or validation payloads. Diagnostics are fixed codes;
normal exceptions suppress raw validation causes. Experiment records deliberately
retain synthetic note/citation contents for inspection and are not log messages.

Source/model/prompt/response identifiers and recording hashes stay in experimental
records, outside clinical facts, policy inputs, and production fingerprints.
Identifiers and hashes preserve declared provenance; they do not authenticate a
provider, reviewer, or clinical claim. This version's origin literal must be
explicitly extended before accepting genuine model-generated recordings.

## Reconciliation

`reconcile(regex_proposal, recorded_llm_proposal)` accepts already-captured sources,
revalidates both, requires the exact same note, and returns a `ReconciliationRecord`.
It never calls an extractor, service, model, or archive. The input roles are regex
and recorded LLM; their actual source identities remain in the preserved inputs.

| Input states/values | Disposition | Reason |
| --- | --- | --- |
| Both captured, exact same type/value | CAPTURED | `AGREED_CAPTURE` |
| Both missing | MISSING | `BOTH_MISSING` |
| Captured versus missing | NEEDS_REVIEW | `STATE_DISAGREEMENT` |
| Conflicting captured values | NEEDS_REVIEW | `VALUE_DISAGREEMENT` |
| Either needs review | NEEDS_REVIEW | `REVIEW_REQUIRED` |
| Invalid proposal or extraction failure | Explicit exception | No dual proposal |

Every fact has separate state, value, retained-citation-set, citation-order, and
total-count comparisons. `values_agree=null` means values were not compared because
both states were not captured. Equal retained sets are not a complete citation
comparison if either source was truncated; the record explicitly says so.

Phase 3's review follow-up uses an interleaved, exact-span-deduplicated combination
for state/value disagreements, retaining passages from both sources before the
existing ten-span cap. Per-span provenance and both originals remain in the
record. If either combined source is truncated, the complete combined total is
unknown; the canonical proposal contains retained spans without a fabricated
total, and experimental diagnostics explain the limitation. For agreed captures,
regex citations remain unchanged. No truncated source totals are summed.
Citation differences do not override scalar agreement.

For the lumbar therapy pair, dual values can both be captured only when both
inputs captured both matching values. Both retained citation lists then come from
the regex proposal. Complementary fields from different inputs cannot create a
joint capture; a disagreement/review leaves at least one field unresolved. This
preserves source-level pairing, not proof of semantic episode/course linkage in
either original source. Per-fact dispositions still follow the table exactly.

`clinical_verification` is always false. Agreement is not clinical truth, human
attestation, or policy approval. A test deliberately agrees on a patient OSA
proposal quoted from a relative's diagnosis; structural agreement still leaves
all service requirements unverified.

## Numeric observations

For captured integer values, fixed analysis flags report when the numeric value
does not appear literally in that source's retained quotations. This can identify
potentially implausible or unsupported numbers for investigation without a new
clinical magnitude threshold. It also flags legitimate normalization, such as
12 weeks supported by “3 months,” and may miss an implausible number that is
quoted verbatim. It changes no value, state, policy status, or vocabulary. Broader
clinical plausibility remains unimplemented and would need a separately approved
definition.

## Synthetic examples and checks

The three labeled [fixtures](fixtures/recorded) exercise Unicode CPAP citations,
lumbar agreement, and a deliberate duration disagreement. The latter asserts six
weeks against a quotation saying eight, to demonstrate structural validation's
limits. These are proposed test inputs, not new clinical gold labels.

The [recorded proposal example](artifacts/phase2-recorded-proposal-example.json)
and [reconciliation example](artifacts/phase2-reconciliation-example.json) expose
decoded snapshots for readability, including both originals, dual facts/states,
citations, provenance and per-fact reasons. They are experimental projections,
not production evaluation/archive records.

```bash
python -m experiments.dual_extraction.examples --check
python -m experiments.dual_extraction.examples --write
python -m experiments.dual_extraction.baseline --check
python -m pytest -q test/test_extraction_citation_gate.py test/test_recorded_extraction.py test/test_extraction_reconciliation.py test/test_extraction_examples.py
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

The explicit example command produces exactly two fixed review artifacts from
one synthetic note, capturing each source once. It has no corpus iteration,
mode execution, downstream evaluation, performance metrics, or archive writes;
the complete three-mode comparison runner is separately invoked through Phase 3.
