# exp-003 — reviewed drug-class vocabulary and bounded recall

Base: main v2.4.0, `3413381c275a1d5b69ae56a1f0be106c258c4925`. Branch: `autoloop/exp-003`.
One required therapy-table iteration completed, with an unsafe candidate reverted
and a safer revision retained. Optional motor/reflex and sleep-study families
were not attempted. Safety work on course linkage took priority.

## Fix and its boundaries

CPB 0236 Footnote 1 supplies the qualifying therapy classes, while notes often
name a drug. `engine/data/cpb0236_drugs_v1.json` contains 26 minimal records:
15 NSAIDs, 8 muscle relaxants, and 3 analgesics. Generic names and familiar US
brand aliases are literal vocabulary; code does not infer their classes from
clinical use or drug-name patterns. A standard-library loader validates the
record schema, unique literal names, substance-code shape, class agreement,
and allowed ATC prefixes. M03B and M03C are permitted; all M03A neuromuscular
blocker entries are rejected. A non-listed drug never supplies qualifying
therapy, even if used for back pain or assigned a qualifying ATC elsewhere.

The data file begins with the required WHO-transcription / human-review notice.
No completed human review is claimed. WHO pages were consulted while preparing
the artifact; evaluation uses no network, ontology service, LLM, or NLP library.
The table is the only new lookup data. Some familiar aliases are historical US
brands; their inclusion does not claim current marketing availability.

A listed name can occupy only the class-token position in exp-002's isolated
whole-course grammar: an optional completion marker, one named drug, explicit
whole days/weeks/months, and an explicit response introduced by “with”; the
reverse duration-first form is also supported. Duration conversion and all
shared response, future/planned, non-patient, negation, uncertainty, and linkage
checks remain in force. Original note text and citation offsets are preserved.
No clinical appropriateness, prescription adherence, formulation, or indication
is inferred from drug membership. Extra formulation/combination/indication text
cannot satisfy this whole-course grammar. Named drug identities stay distinct
when resolving competing courses; merely sharing a class does not merge them.

The revision additionally records unresolved listed-drug mentions. If another
course candidate exists, an eligible unresolved mention requires review rather
than disappearing or donating its duration/response. Explicit planned, negated,
and non-patient mentions still undergo the existing exclusions. Alone, incomplete
drug statements remain missing evidence. This guard also applies alongside
legacy class-keyword courses.

The frozen direct-import allowlist initially rejected a new helper module
(`iteration-1-initial-suite.txt`: 1 failed, 1268 passed, 10 xfailed). The
standard-library vocabulary loader now lives in the existing `note_context`
module, alongside literal note contexts. No assertion or import allowlist was
changed; no dynamic import or dependency-check bypass was added to product code.

## Prospective pairs and rejected hypothesis

`cases/iteration-1.json` froze **8 positives and 59 negatives before the first
product change**. All 8 positives abstained on main. Negatives span every drug
class and include short courses, improvement, plans, non-patients, negation,
unrelated indications before/within/after courses, missing linkage, conflicts,
uncertainty, fractions/ranges/comparisons, topical formulations, combinations,
substring collisions, absent objective findings, unlisted back-pain drugs,
rocuronium, and botulinum toxin. The unchanged public scorer produced 49/67
exact before and 67/67 after the initial candidate, with zero false pending.
The initial suite subsequently passed 1278 tests with 10 existing xfails.

**Rejected hypothesis: recognizing only complete drug courses is sufficient to
preserve course linkage.** Code review motivated `cases/iteration-1-challenge.json`
(3 additional positives and 4 negative challenges, written before the safety
revision). The initial candidate produced **four false PENDING_VERIFICATION**
results when a complete course coexisted with another incomplete drug statement.
Both changed product modules were immediately restored byte-for-byte from main;
`iteration-1-challenge-reverted-score.json` and `iteration-1-reverted-corpus.json`
record the reversion. The unused data artifact remained. Rejected source is
preserved as `rejected-incomplete-linkage-*.py.txt`; none of that unsafe behavior
is accepted as a final result.

The main engine itself falsely passes one mixed class/drug challenge; the other
three negative challenges abstain. This inherited false pass is included in the
expanded baseline metrics, not excluded or relabeled. The safer revision uses
the unresolved-context guard above. It passes the four challenges and the three
additional positives, all original pairs, all 69 exp-002 cases without changing
their results, and the frozen corpus. Challenge positives confirm coverage on
other listed drugs; they already passed the first candidate. Their misses on
main were measured retrospectively. No optional recall family or failed
reproduction is claimed.

`test/test_exp003_recall.py` runs all 74 public-service pairs, verifies literal
citation offsets, expected facts where specified, unverified requirements,
non-submission readiness, and nonpassing negatives. Nine additional tests check
table size, its exclusion from the governance bundle, and rejection of outside
ATC groups or code/class disagreement. Tests use in-memory corrupt table data;
the versioned table is never rewritten by a test.

## Metrics against baseline and canary

`autoloop/score.py` is unchanged. Main is replayed in an isolated process by
loading both changed modules from git into memory before service imports; no
checkout replacement or clock patch is used by the audit. The prospective
67-case score remains separately preserved. Expanded metrics use the same
74 inputs for baseline, final, and always-CANNOT_DETERMINE canary.

| Dataset / metric | Main baseline | Final | Canary |
|---|---:|---:|---:|
| Corpus exact status | 52/52 | 52/52 | 30/52 |
| Corpus false PENDING_VERIFICATION | 0 | 0 | 0 |
| Corpus missed passes | 0 | 0 | 7 |
| Corpus abstention / expected | 80.77% / 80.77% | 80.77% / 80.77% | 100% / 80.77% |
| Expanded authored exact | 49/74 (66.22%) | 74/74 (100%) | 49/74 (66.22%) |
| Expanded authored false PENDING_VERIFICATION | 1 | 0 | 0 |
| Expanded authored missed passes | 11 | 0 | 11 |
| Expanded authored abstention / expected | 98.65% / 77.03% | 77.03% / 77.03% | 100% / 77.03% |
| Exp-002 exact / false pending | 64/69 / 0 | 64/69 / 0 | 41/69 / 0 |

Expanded positives: **0/11 → 11/11** passing. Expanded negatives:
**49/63 → 63/63** exact, with **zero final false pending**. Exact accuracy gains
25 cases / 33.78 percentage points against both main and the canary. No final
automated READY is produced. No previously correct authored status regresses.
The canary's zero false pending while missing every positive shows why safety
alone cannot establish recall. The saturated corpus cannot establish recall
gain either. Full confusion matrices and case statuses appear in
`evidence/baseline-audit.json` and `evidence/final-audit.json`.

Exp-002's report documents two additional pre-existing false passes in exp-001's
historical expanded set. Those original files and labels are untouched; this
experiment does not claim to fix those inherited open failure classes or prove
safety over arbitrary prose. The executable gates cover the frozen corpus,
all 69 exp-002 cases (including its rejected inputs), and every exp-003 authored
case. All **117 authored negatives across exp-002 and exp-003** are nonpassing
on the final engine. Historic exp-001 gaps are disclosed rather than silently
counted as safe.

## Validation and scope

Baseline: **1202 passed, 10 xfailed**. Final: **1285 passed, 10 xfailed**
in 36.34 seconds (74 pairs + 9 integrity tests added). Full output is in
`evidence/iteration-1-revised-suite.txt`. `make lint` passes; its output is in
`evidence/final-lint.txt`. No existing markers or assertions were changed.

The table is outside the explicit file list used by `_bundle_snapshot`. Bundle
digest `1e3dea24499fa5619e8862e53c75ed3596d7e94812314c995f7508a44353d0ef` and normalized drift/rulebook
projections are baseline-identical. All 52 corpus proposals have identical
facts, evidence, input/fact-set fingerprints, and requirement verification
fingerprints. Existing acceptance/golden/artifact tests pass against unchanged
committed content. New drug notes correctly receive their own new proposals.

Only `engine/extract.py` and `engine/note_context.py` change existing product
files. Added files are the one versioned table, one new test module, and this
experiment's records. `evidence/scope-audit.json` verifies main/scorer/protected
content preservation. No existing eval inputs, expected labels, policy/rules,
rulebook, snapshots, goldens, artifacts, clocks, or monitor state were changed.
Neither generator was run. No tags or PR were created. The sole push target is
`origin autoloop/exp-003`. The pre-existing `soccer-practice-arena/` is untouched.

## Honest self-audit

The **isolated whole-course grammar is the most overfit-prone change**. Its
fixed word order and small response vocabulary closely match the authored
phrasing slice. It deliberately misses common dose/frequency prose, explicit
lumbar indication modifiers, and many otherwise valid narratives. The
unresolved-drug-context guard is broad and may cause unnecessary review when a
listed drug elsewhere is irrelevant. Conversely, indication or planned status
expressed in separate sentences without a drug mention may escape these local
guards. No general coreference or clinical episode model exists.

Every example was authored during development; none is held out. The first
candidate's four false passes show that a green corpus and many initial pairs
were insufficient. The source and failing evidence remain available. ATC
prefix validation checks eligibility, not the factual correctness of a
transcription or brand mapping: human review is still required. Drug names can
have multiple route-specific codes; the narrow grammar rejects explicit topical
or combination wording but cannot resolve unspecified formulations. These are
bounds on the result, not evidence of broad clinical language understanding.

## Complete drug table for human review

**ATC codes were transcribed from WHO ATC and need human review. Brand aliases (including familiar historical US brands) and class assignments also need human review. No completed human review is claimed.**

Version: 1. SHA-256: `ae6bc85fc2f923c10a652efe76a1f5316ba2eb8c1807abf4bad73660408b4812`.
Source: WHO Collaborating Centre ATC/DDD Index 2026 (pages updated 2026-01-20), consulted 2026-10-16. US generic spellings retained; WHO spellings appear as aliases where needed.

Scope: Single-ingredient systemic names only; combinations and explicit topical formulations are not inferred. M01A NSAIDs; M03B central and M03C direct muscle relaxants; N02 analgesics. M03A neuromuscular blockers excluded. Membership does not establish indication, duration, response, or appropriateness.

| Generic name | Aliases / common US brands | WHO ATC code | Footnote 1 class |
|---|---|---|---|
| ibuprofen | Advil, Motrin | M01AE01 | NSAIDs |
| naproxen | Aleve, Naprosyn | M01AE02 | NSAIDs |
| ketoprofen | Orudis | M01AE03 | NSAIDs |
| fenoprofen | Nalfon | M01AE04 | NSAIDs |
| flurbiprofen | Ansaid | M01AE09 | NSAIDs |
| oxaprozin | Daypro | M01AE12 | NSAIDs |
| indomethacin | indometacin, Indocin | M01AB01 | NSAIDs |
| sulindac | Clinoril | M01AB02 | NSAIDs |
| tolmetin | Tolectin | M01AB03 | NSAIDs |
| diclofenac | Cataflam | M01AB05 | NSAIDs |
| etodolac | Lodine | M01AB08 | NSAIDs |
| ketorolac | Toradol | M01AB15 | NSAIDs |
| piroxicam | Feldene | M01AC01 | NSAIDs |
| meloxicam | Mobic | M01AC06 | NSAIDs |
| celecoxib | Celebrex | M01AH01 | NSAIDs |
| baclofen | Lioresal | M03BX01 | muscle relaxants |
| tizanidine | Zanaflex | M03BX02 | muscle relaxants |
| cyclobenzaprine | Flexeril, Amrix | M03BX08 | muscle relaxants |
| carisoprodol | Soma | M03BA02 | muscle relaxants |
| methocarbamol | Robaxin | M03BA03 | muscle relaxants |
| chlorzoxazone | Parafon Forte | M03BB03 | muscle relaxants |
| orphenadrine | Norflex | M03BC01 | muscle relaxants |
| dantrolene | Dantrium | M03CA01 | muscle relaxants |
| acetaminophen | paracetamol, Tylenol | N02BE01 | analgesics |
| tramadol | Ultram | N02AX02 | analgesics |
| tapentadol | Nucynta | N02AX06 | analgesics |

WHO source pages used for transcription (all codes in the table are covered):

- [WHO ATC M01AB](https://atcddd.fhi.no/atc_ddd_index/?code=M01AB&showdescription=no)
- [WHO ATC M01AE](https://atcddd.fhi.no/atc_ddd_index/?code=M01AE&showdescription=no)
- [WHO ATC M01AC](https://atcddd.fhi.no/atc_ddd_index/?code=M01AC&showdescription=no)
- [WHO ATC M01AH](https://atcddd.fhi.no/atc_ddd_index/?code=M01AH&showdescription=no)
- [WHO ATC M03BX](https://atcddd.fhi.no/atc_ddd_index/?code=M03BX&showdescription=no)
- [WHO ATC M03BA](https://atcddd.fhi.no/atc_ddd_index/?code=M03BA&showdescription=no)
- [WHO ATC M03BB](https://atcddd.fhi.no/atc_ddd_index/?code=M03BB&showdescription=no)
- [WHO ATC M03BC](https://atcddd.fhi.no/atc_ddd_index/?code=M03BC&showdescription=no)
- [WHO ATC M03CA](https://atcddd.fhi.no/atc_ddd_index/?code=M03CA&showdescription=no)
- [WHO ATC N02BE](https://atcddd.fhi.no/atc_ddd_index/?code=N02BE&showdescription=no)
- [WHO ATC N02AX](https://atcddd.fhi.no/atc_ddd_index/?code=N02AX&showdescription=no)
