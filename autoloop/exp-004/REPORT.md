# exp-004 — general recall grammar checked against owner dev data

Base: main v2.5.0, `89a1500`. Work: `autoloop/exp-004`.
Five iterations completed. Final owner dev: **27/27 exact**, including all
requirement statuses, with **zero false PENDING_VERIFICATION**. Own authored
paraphrases: **102/102**, including **30 positives and 72 negatives**. Corpus
remains **52/52**. Iteration 5 repairs a defect **found by the owner’s held-out
evaluation, not by our own tests**. No held-out dataset was read or evaluated
here; the owner-provided failure class was used to develop this repair.

## Immutable owner check and approved exception

The required first commit, `25b10cb`, contains only the unchanged owner file
`dev.json`. SHA-256:
`4832267bc1ff0ac8f57aac1dd36961ef62ea4d3f15d9286662866a0981685389`.
All 27 cases, notes, requirement labels and statuses remain byte-identical.
No dev status label is disputed or edited.

One pre-existing executable contract expectation conflicted with a general
leading-verb fix: `exp003_leading_verb_missed` expected “Took ibuprofen for
6 weeks with no improvement” to remain missing. The conflict was logged and
the owner explicitly authorized that one correction. Its ID/note stay unchanged;
only therapy facts (six weeks / no improvement) and status (PENDING_VERIFICATION)
change. All other 66 contract objects, four known-failure markers, existing
pytest assertions, eval inputs, fixtures and expected statuses remain unchanged.
The exception is recorded in `evidence/final-scope-audit.json`.
Existing release prose is not a new release claim; this experiment does not
bump versions or regenerate release documentation/artifacts.

## General rules, written before implementation

Each rule was stated in plain language in `LOG.md` and the conversation before
implementation. Every input batch was authored before its fix; before/after
case hashes match. Four or more new positive paraphrases and four or more
near-miss negatives accompany each rule. Necessary policy context is shared,
but target drugs, verbs, muscles, date vocabulary and measurement constructions
extend beyond the owner check rather than copying its sentences. Product code
never loads dev data, case IDs or expected labels.

| Iteration / commit | General rule implemented | Independent batch | Exact before → after |
|---|---|---:|---:|
| 1 / `a8e25af` | A listed drug may have an optional patient/use verb phrase, dose and frequency in a whole reported course. Duration can precede/follow the drug. Explicit nonresponse/response stays linked to that course; existing safety exclusions and unresolved-course review remain. | 4 positives / 12 negatives | 8/16 → 16/16 |
| 2 / `0b63a79` | A typed motor or tendon-reflex grade directly linked to a named lumbar/sacral root is an objective exam cue. Accept lower-limb muscle/action labels and +/- subnormal motor grades. Do not infer a root from anatomy. Normal, uncertain, negated, attributed or side-conflicting findings are handled separately. | 8 positives / 14 negatives | 5/22 → 22/22 |
| 3 / `911dc17` | Calendar-valid US numeric, dotted year-first and English month-name dates, in either named-date order and with ordinal days, count only with direct sleep-test linkage. Retain planned, non-patient, missingness and uncertainty exclusions. | 4 positives / 10 negatives | 9/14 → 14/14 |
| 4 / `d23ec3a` | Full apnea-hypopnea / respiratory-disturbance index names, including whitespace/hyphen and British spelling, are AHI/RDI aliases only with explicit numeric measurements. Missing, planned, negated and non-patient values do not supply documentation. | 4 positives / 12 negatives | 11/16 → 16/16 |
| 5 / continuation of `8199ea2` | Sentence-wide patient/history attribution or an unperformed exam disqualifies a finding across typed and legacy routes. Qualified evidence alone is NOT_DOCUMENTED; conflicting normal/abnormal objective evidence elsewhere is NEEDS_REVIEW. Agreeing objective evidence remains usable. | 10 positives / 24 negatives | 19/34 → 34/34 |

Motor grammar includes anatomical/action cues such as iliopsoas, tibialis
anterior, gastrocnemius and plantar flexion; the new pairs also cover Achilles,
ankle and knee jerks. It does not contain a muscle-to-root lookup. Signed endpoint
grades are reviewed rather than silently treated as ordinary grades. Reflex
normal/abnormal wording can dispute a grade; high grades without explicit
abnormality wording require review. Iteration 5 now applies source/performance
safeguards to legacy unmodified strength and descriptive reflex findings too,
without changing any existing contract expectation in this continuation.

Therapy paraphrases use etodolac, Dantrium, Ultram and sulindac, with reported
use, doses, BID/TID/nightly/twice-a-day schedules and course-first syntax. They
challenge short/improved courses, future intent, relatives, indication modifiers,
denials, non-listed drugs, ranges, missing response, cross-course conflict,
topical wording and questions. Benefit/without-response wording is recognized;
inside a recognized whole drug course, “no meaningful benefit” is not double
counted as affirmative benefit.

Date pairs use HST/polysomnogram/home sleep test, November/February/September,
hyphenated US, dotted year-first, ordinal and day-first month forms. They test
same-sentence office-date borrowing, invalid dates/leap days, schedules,
cancellations, non-patients, missing study context, partial dates, questions and
absent OSA diagnosis. Validation uses `datetime.strptime` without reading or
changing a clock. New formats require direct event linkage; legacy year-first
association behavior is retained.

Index pairs add respiratory-disturbance and British apnoea/hypopnoea terminology,
parenthetical abbreviations, explicit value predicates and decimal values. Their
negatives include missing values, plans, denial, relatives, uncertainty, other
vitals/indices, comparisons, negative values, questions and absent OSA. REI is
not promoted to AHI/RDI. Full-name safeguards are narrower than the preserved
legacy abbreviation route; no broad semantic measurement model is claimed.

## Held-out defect and iteration 5 repair

The owner reported that a root-linked grade attributed to the patient with
an exam deferred still returned PENDING_VERIFICATION. This safety defect was
present at `8199ea2` despite dev 27/27 and all 68 earlier own cases passing.
Our tests had omitted this source/performance family; they did not discover it.

The new rule and 34 cases were written before changing extraction. Qualifiers
cover per patient, patient reports/states, self-reported, by history, deferred,
not performed, not examined, unable to assess and limited by refusal. The guard
uses a whole sentence, including semicolons and decimal grades, before resolving
all typed motor/reflex, legacy slash strength, word strength, descriptive
reflex and objective-weakness candidates. Qualifiers remove both abnormal and
normal findings as objective evidence. Word grades with surrounding qualifiers
are retained only for conflict detection; the passing word-grade grammar still
requires a full sentence match.

Qualified-only evidence yields a missing raw fact, public MISSING state and
**NOT_DOCUMENTED** requirement, without supporting objective citations. A
conflicting normal/abnormal objective finding in a separate sentence yields
**NEEDS_REVIEW**, with literal citations to both sources. Agreeing sources
allow the separately documented objective finding to support the requirement.
The 10 positives also cover on-exam/examination-shows wording and unrelated
patient reports or deferrals in separate sentences. The 24 negatives vary
qualifier wording and position across new and legacy paths; six check conflicts.
An additional requirement-level test verifies NOT_DOCUMENTED versus NEEDS_REVIEW,
public states and literal evidence, beyond overall-status checks.

| Iteration 5 check | Before (`8199ea2`) | After | Always-CANNOT_DETERMINE canary |
|---|---:|---:|---:|
| New own cases exact | 19/34 | 34/34 | 18/34 |
| New own negatives returning false PENDING_VERIFICATION | 13/24 | 0/24 | 0/24 |
| All own cases exact | 87/102 | 102/102 | 51/102 |
| Dev exact / false pending | 27/27 / 0 | 27/27 / 0 | 9/27 / 0 |

The pre-fix safety assertion deliberately fails on the reproduced existing
fault; its output is retained in `iteration-5-before-summary.txt`. Pre-fix
paired tests report 30 failed / 106 passed because both overall and requirement
checks exercise the defect. The candidate fix passes all 136 paired checks.
No expectation or authored case was changed between the before/after runs.
The five historical exp-002 mismatches remain unchanged; they are not new passes.

## Per-iteration gates

`autoloop/score.py` is unchanged and runs through public ReadinessService with
no attestations or corrections. `capture.py` records corpus, dev, all exp-002/003
inputs (including rejected exp-002 cases), every accumulated own pair and dev
requirement mismatches. Every final iteration gate has zero false pending on
all those sets. Corpus and prior authored full reports must equal baseline.

| Checkpoint | Dev exact | Dev false pending | Own cumulative exact | Full make test |
|---|---:|---:|---:|---|
| Main baseline | 11/27 | 0 | Not yet authored | 1301 passed / 10 xfailed |
| Iteration 1 final | 18/27 | 0 | 16/16 | 1317 passed / 10 xfailed |
| Iteration 2 final | 24/27 | 0 | 38/38 | 1339 passed / 10 xfailed |
| Iteration 3 final | 26/27 | 0 | 52/52 | 1353 passed / 10 xfailed |
| Iteration 4 final | 27/27 | 0 | 68/68 | 1369 passed / 10 xfailed |
| Iteration 5 final | 27/27 | 0 | 102/102 | 1437 passed / 10 xfailed |

All 72 exp-004 negatives, 117 exp-002/003 negatives and 13 owner traps are nonpassing
at the final gate. No automated READY is produced. The saturated 52-case corpus
cannot establish recall gain; unchanged proposals/fingerprints establish only
non-regression on those inputs. Historical exp-001 counterexamples remain in
prior reports and are not silently relabeled or claimed fixed.

## Main baseline and canary on the original four-iteration inputs

This historical common-input comparison covers the original 68 own cases.
Iteration 5’s 34 additional cases and prospective baseline are reported above;
main was not retrospectively scored on those additional cases. The original
68 cases, dev, corpus and exp-002/003 retain their iteration-4 final scores.

| Dataset / metric | Main baseline | Final | Always-CANNOT_DETERMINE canary |
|---|---:|---:|---:|
| Dev exact | 11/27 (40.74%) | 27/27 (100%) | 9/27 (33.33%) |
| Dev false pending | 0 | 0 | 0 |
| Dev missed positive passes | 12 | 0 | 14 |
| Dev abstention / expected | 92.59% / 33.33% | 33.33% / 33.33% | 100% / 33.33% |
| Own exact, all 68 inputs | 33/68 (48.53%) | 68/68 (100%) | 33/68 (48.53%) |
| Own false pending | 0 | 0 | 0 |
| Own missed positive passes | 20 | 0 | 20 |
| Own abstention / expected | 100% / 63.24% | 63.24% / 63.24% | 100% / 63.24% |
| Corpus exact / false pending | 52/52 / 0 | 52/52 / 0 | 30/52 / 0 |
| Exp-002 exact / false pending | 64/69 / 0 | 64/69 / 0 | 41/69 / 0 |
| Exp-003 exact / false pending | 74/74 / 0 | 74/74 / 0 | 49/74 / 0 |

Dev passing cases improve **2/14 → 14/14**; traps improve **9/13 → 13/13 exact**.
The exact-status gain is sixteen cases / 59.26 percentage points against main.
The own-set gain is 35 cases / 51.47 points. Zero false pending alone is weak
evidence: the canary also scores zero while missing every positive.

The common-input baseline for all 68 own cases is explicitly retrospective:
`final_audit.py baseline` loads original extract/note_context sources from git
into an isolated process before service imports. Current mode evaluates the
same files without replacing source on disk. Both use the unchanged scorer.
Raw confusion matrices, hashes, statuses and complete corpus proposal comparison
are in `evidence/final-baseline-audit.json` and `evidence/final-current-audit.json`.
The prospective per-iteration before-fix reports/tests remain separately saved.

## Failed intermediate work and process corrections

The four initial iterations observed no false PENDING_VERIFICATION in their
visible checks. The owner subsequently found the iteration-2 safety defect in
held-out evaluation; iteration 5 reproduces and repairs it as documented above.
A perfect dev check had not established safety on unseen wording.
A broad nested-response deduplication initially changed a frozen legacy class
course's review fact. The suite caught it; that behavior was rejected and the
change restricted to recognized whole drug courses. The first local iteration
commit was made before checking the completed suite, and its log prematurely
recorded a green count. This was corrected transparently; the unpublished commit
was amended only after all gates passed. The failed full-suite output remains
`iteration-1-initial-suite.txt`. Subsequent iterations were committed after
checking the actual green full-suite outputs.

The new paraphrase harness initially compared raw review sentinels against public
service scalar facts. The latter correctly use None plus a separate review state.
That new harness was repaired to assert raw extraction and the public state;
its mistaken state attribute was also corrected. No authored expected fact,
status, dev label, or pre-existing test assertion was changed to hide these
failures. The failed harness and suite outputs remain in evidence. These were
test-layer mistakes, not new clinical success claims.

## Drug data, scope and disputes

**Drug-table additions: none.** The approved versioned table remains byte-identical
to main, with the existing human-verification notice. No class is inferred for
unlisted drugs. No ontology service, LLM or NLP dependency is added; all changes
use regex and the standard library. Calendar/month parsing is standard-library
syntax validation, not a new clinical lookup dataset.

The only existing files changed are `engine/extract.py`, `engine/note_context.py`
and the one authorized JSON example in `EXTRACTION_CONTRACT.md`. New files are
this experiment's records, `test/test_exp004_recall.py` and
`test/test_exp004_exam_sources.py`. The original scope audit checks
the first commit/dev hash, four immutable pair hashes, absence of runtime dev-ID
references, unchanged main and table, all 66 other contract objects, pre-existing
test files, scorer, policies/rules, rulebook, snapshots, inputs, goldens,
artifacts, deployment settings, clocks and monitor state. Neither generator was
run. No main update, tag or PR operation occurred. Only autoloop/exp-004 is the
push target. Pre-existing soccer-practice-arena/ is untouched.

Iteration 5 additionally changes only `engine/extract.py` among product files.
`evidence/iteration-5-scope-audit.json` checks against `8199ea2`: unchanged dev,
every earlier authored case, all existing tests/assertions and the contract,
drug table, scorer and all other frozen tracked files. Full corpus proposals,
source spans, public states and fingerprints still match the main baseline.

Final validation: **1437 passed, 10 xfailed in 38.47s**; `make lint` green
(77 Python files). All ten pre-existing strict xfails remain; no marker was
removed. New tests account for 102 own cases and 34 requirement-level checks,
136 passing tests over the 1301 main baseline.
All 52 corpus facts, public states, literal citations, input/fact-set fingerprints
and requirement verification fingerprints match main. Governance projections
and bundle identity also match baseline. There is no new dev-status dispute;
the single approved contract conflict is the only expectation exception.

## Honest self-audit

The **reported drug-course prefix grammar is most likely to have fit the visible
dev wording rather than the full general pattern**. It now handles multiple verb
families, different drugs, doses, schedules and ordering on independent examples,
but still enumerates verbs and frequency syntax and requires a whole isolated
course with an explicit response. Pronouns, relative clauses, simultaneous drug
regimens, administration instructions, different response expressions and
longitudinal episodes can still be missed. The independent pairs reduce the
risk of literal dev matching; they do not remove selection bias from an author
who saw the dev set and implemented the grammar.

Motor/reflex recognition also uses a bounded anatomical vocabulary and explicit
root-distribution language. The owner’s held-out finding demonstrates a real
safety gap missed by our original test selection. Iteration 5 addresses the
specified source/performance phrases across typed and legacy paths, but a
finite regex vocabulary still cannot prove objective measurement in arbitrary
prose. Sentence-wide exclusion is deliberately conservative and may abstain
when a qualifier describes another event within the same sentence. Different
source paraphrases and wider document context remain unvalidated. Legacy
laterality and unrelated attribution gaps are not generally repaired. New date formats
use US numeric conventions and English month parsing, not locale inference;
legacy year-first calendar/association weaknesses are not generally repaired.
Full-name index safeguards do not establish equivalent safety for all legacy
abbreviations or measurement contexts.

The owner dev check was used adaptively, so **27/27 is development performance**.
All own pairs were authored during development, not independently held out.
No held-out dataset was accessed, but iteration 5 used owner-provided feedback
from that evaluation. The new own cases are regression/development checks, not
independent held-out evidence. A fresh owner rerun is needed to assess this
repair on the actual held-out inputs; no passing held-out score, real clinical
accuracy, or universal safety is claimed here.
