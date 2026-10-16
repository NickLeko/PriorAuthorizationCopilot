# exp-004 — general recall grammar checked against owner dev data

Base: main v2.5.0, `89a1500`. Work: `autoloop/exp-004`.
Four iterations completed. Final owner dev: **27/27 exact**, including all
requirement statuses, with **zero false PENDING_VERIFICATION**. Independent
paraphrases: **68/68**, including **20 positives and 48 negatives**. Corpus
remains **52/52**. No held-out input was accessed or evaluated.

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

Motor grammar includes anatomical/action cues such as iliopsoas, tibialis
anterior, gastrocnemius and plantar flexion; the new pairs also cover Achilles,
ankle and knee jerks. It does not contain a muscle-to-root lookup. Signed endpoint
grades are reviewed rather than silently treated as ordinary grades. Reflex
normal/abnormal wording can dispute a grade; high grades without explicit
abnormality wording require review. Legacy unmodified-strength behavior and its
existing gaps remain, rather than rewriting old contracts.

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

All 48 new negatives, 117 exp-002/003 negatives and 13 owner traps are nonpassing
at the final gate. No automated READY is produced. The saturated 52-case corpus
cannot establish recall gain; unchanged proposals/fingerprints establish only
non-regression on those inputs. Historical exp-001 counterexamples remain in
prior reports and are not silently relabeled or claimed fixed.

## Baseline, final and canary

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

No observed false PENDING_VERIFICATION required a safety reversion in this run.
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
this experiment's records and `test/test_exp004_recall.py`. The scope audit checks
the first commit/dev hash, four immutable pair hashes, absence of runtime dev-ID
references, unchanged main and table, all 66 other contract objects, pre-existing
test files, scorer, policies/rules, rulebook, snapshots, inputs, goldens,
artifacts, deployment settings, clocks and monitor state. Neither generator was
run. No main update, tag or PR operation occurred. Only autoloop/exp-004 is the
push target. Pre-existing soccer-practice-arena/ is untouched.

Final validation: **1369 passed, 10 xfailed in 36.96s**; `make lint` green
(76 Python files). All ten pre-existing strict xfails remain; no marker was
removed. New tests account for exactly 68 passing cases over the 1301 baseline.
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
root-distribution language. It cannot establish that a score was objectively
measured rather than quoted from subjective history in arbitrary prose. Existing
legacy strength attribution/laterality paths retain their gaps. New date formats
use US numeric conventions and English month parsing, not locale inference;
legacy year-first calendar/association weaknesses are not generally repaired.
Full-name index safeguards do not establish equivalent safety for all legacy
abbreviations or measurement contexts.

The owner dev check was used adaptively, so **27/27 is development performance**.
All own pairs were authored during development, not independently held out.
The separate owner held-out set remains untouched. Its result is still needed
to assess whether these gains transfer to other wording; no improvement on that
set, real clinical accuracy, or universal safety is claimed here.
