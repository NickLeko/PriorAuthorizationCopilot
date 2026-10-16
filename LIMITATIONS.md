# Limitations

Typed corrections do not improve extraction; a SET_VALUE quotation is limited to 300 characters per span, with multiple spans allowed. See the canonical [correction limits](docs/safety_and_scope.md#correction-limits).

Extraction remains a drafting aid. Negation, temporality and attribution errors
remain: `has neither low back pain nor radiculopathy` can still return True,
and an unrelated visit date in the same sentence can supply a false study date.
The previously documented does/do/did-not-have and cross-sentence date examples
are fixed in v2.3.0; their broader failure classes are not solved. See
[extraction guarantees](EXTRACTION_CONTRACT.md).

## Scope Limits

- only a small number of procedures are supported
- payer coverage is intentionally narrow
- supported sites of care are constrained

## Extraction Limits

- extraction is pattern-based, not language-model-based
- unusual phrasing can remain unparsed
- the system prefers missingness over aggressive inference
- revision note, June 9, 2026: over-extraction edge cases have been identified and patched, including negated therapy, future-planned therapy, and therapy-duration leakage into symptom duration; regression tests now cover those cases
- revision note, August 31, 2026: tested subject-attribution, future/hypothetical, uncertainty/question, cross-therapy, and contradictory-candidate forms fail closed; general coreference, longitudinal episode resolution, and untested language remain unsupported

## Governance Limits

- drift monitoring is partial
- only configured sources are monitored
- rules are still curated offline

## Product Limits

- opt-in CLI persistence in a local append-only SQLite decision/policy archive; ordinary UI/API evaluations are not automatically saved
- archive records retain full requests and verification metadata, but have no encryption, access control, or production retention/deletion workflow
- triggers and hashes protect the supported workflow, not against a privileged database/schema rewrite
- replay uses only originally captured evidence and explicit target policy snapshots; it does not re-extract old notes, collect missing evidence, or make a case automatically READY
- no authentication
- no user management
- no deployment packaging beyond local/demo use

## Healthcare Limits

- not validated for real-world clinical or administrative operations
- not suitable for real PHI workflows as currently packaged
- not a substitute for payer policy review or human chart review


## v2.5.0 bounds and evidence

Five accepted exp-001 fixes handle auxiliary-verb negation, linked reflex
qualifiers, intact reflexes, explicitly negated numeric strength and study-date
association across sentences. A denied numeric score now requires review; the
old strict-xfail expectation of False remains disputed and unchanged.

The reflex grammar has a small predicate vocabulary and a 160-character
lookback. Unusual legitimate wording may be missed. Requiring date/study context
in one sentence does not resolve two events within that sentence and can miss
genuine cross-sentence links. Neither/nor negation, unrelated therapy,
cross-sentence temporality/response/copy-forward and laterality remain open.
Incorrect attestations can still produce false READY from unsupported proposals;
CPAP demo trust independently keeps submission_readiness=false.

The four accepted exp-002 fixes cover isolated qualifying courses in whole days,
whole months and number words one through twelve, plus direct named-root strength
grades written “of” / “out of”. Days floor to completed weeks; months use a
four-week lower bound, not calendar inference. Complete course/response grammar
misses legitimate narrative qualifiers; the new strength route's review handling
does not repair the legacy slash-route laterality/attribution gap. Full class-name
expansion was reverted after unsafe headache-therapy passes.

Exp-003 adds listed drug names through the same narrow course-sentence grammar;
a leading verb such as 'Took' remains unrecognized. Eligible unresolved listed-drug
context alongside another course now requires review, which can over-trigger.
[engine/data/cpb0236_drugs_v1.json](engine/data/cpb0236_drugs_v1.json) is
owner-approved reviewed data for local use. **ATC codes require human verification
against WHO ATC before any external claim.** Approval does not certify each
transcription or alias; route/formulation ambiguity and its human-review notice remain.

Validation: **1301 passed, 10 xfailed**, corpus 52/52 with zero false pending,
45/45 original authored cases, and two false pending results in the expanded 47.
These finite regressions are not clinical validation. See the
[exp-001 report](autoloop/REPORT.md). Exp-002's 69 authored cases improve 41/69 →
64/69 exact with zero false pending across 54 negatives, but retain three missed
passes and two wrong negative abstentions.

Exp-003 improves 49/74 → 74/74 development statuses with zero final false
pending across 63 negatives; its unsafe first candidate was reverted. The owner
reports zero false pending on three held-out sets, exact 23→25/41, 15→15/36
and 14→15/34. Those cases were not inspected or rerun during release prep. See
[v2.5.0](docs/releases/v2.5.0.md) and the [exp-003 report](autoloop/exp-003/REPORT.md).
