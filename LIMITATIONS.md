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


## v2.6.0 bounds and evidence

Release validation is **1461 passed, 10 xfailed**. Corpus remains 52/52; owner
visible dev is 27/27 and own pairs are 102/102, all with zero false pending.
Exp-002/003 remain 64/69 and 74/74 with zero false pending. Earlier expanded
exp-001 cases retain two unsafe passes. These finite regressions are not clinical
validation; all ten strict xfails remain, including the disputed negated-strength
False expectation (implementation requires review, not a normal observed score).

Exp-004 recognizes supported reported-use verbs including “Took”, dose/frequency
and duration-first ordering within one complete listed-drug course plus explicit
response. The grammar still enumerates verbs and schedules. Pronouns, combinations,
formulation, unusual modifiers and longitudinal course attribution can be missed.
Days floor to weeks, months use a four-week lower bound, and number words stop
at twelve. Full class-name expansion remains rejected after unsafe unrelated
therapy passes. Unresolved eligible drug context may over-trigger review.

[engine/data/cpb0236_drugs_v1.json](engine/data/cpb0236_drugs_v1.json) remains
owner-approved reviewed data for local use, unchanged at 26 entries. **ATC codes require human verification against WHO ATC before any external claim.**
Approval does not certify transcriptions, aliases, route or formulation.

Typed motor/action/muscle grades and tendon-reflex grades require explicit
named-root linkage. No muscle-to-root mapping is inferred. Patient/history
attribution or an unperformed/refused exam in the sentence disqualifies both
new and legacy motor/reflex evidence. Qualified-only evidence is NOT_DOCUMENTED;
conflicting normal/abnormal objective evidence elsewhere requires review. This
fix followed an owner-held-out safety failure missed by our original tests.
The guard has a finite vocabulary and may conservatively exclude an objective
finding when the same sentence’s qualifier describes another event. General
provenance, laterality, pain/effort attribution and wider context remain limited.

Calendar-valid new date formats require directly adjoining completed-study
context; English month names and US numeric conventions do not infer locale or
recency. Legacy year-first same-sentence borrowing remains unsafe. Full AHI/RDI
names include British spelling; their safeguards do not generally repair all
legacy abbreviations or measurement contexts. Neither/nor, unrelated legacy
therapy and cross-sentence episodes/response/copy-forward remain open. Incorrect
attestations can still produce READY; CPAP demo trust independently blocks
submission readiness for borrowed-date proposals.

The owner reports a separate never-visible 27-case held-out set with different
wording: exact 10→24/27, zero false PENDING_VERIFICATION. This differs from the
visible dev result (11→27/27) and leaves three exact-status misses. No held-out
case was read or rerun here. A prior held-out set supplied the safety-defect
feedback used for iteration 5; no universal safety or clinical generalization
claim follows. See [v2.6.0](docs/releases/v2.6.0.md) and
[exp-004](autoloop/exp-004/REPORT.md).


## Objective-exam laterality qualification

All objective-exam recognition routes use the same literal opposite-side
radiculopathy mention check. An opposite-side mention can require review even
when it is negated or historical, or another diagnosis side also appears. This
is conservative notation consistency, not temporal or negation interpretation.
The check does not expand anatomical vocabulary or infer omitted laterality or
root relationships. Unsided and bilateral examination handling remains as before;
existing recognition and inline-check limitations still apply.
