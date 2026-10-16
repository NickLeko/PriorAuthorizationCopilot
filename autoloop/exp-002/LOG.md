# exp-002 improvement log

Baseline `4e0c06f`: 52/52 corpus, zero false pending; canary 30/52, seven missed
passes. Tests 1123 passed / 10 xfailed. Scorer, clocks, policies and original
expectations are fixed. Cases and labels below were written before their fixes,
except additional adversarial challenges explicitly identified below.

## Iteration 1 — rejected: full non-steroidal anti-inflammatory class names

Hypothesis: Footnote 1 explicitly names non-steroidal anti-inflammatory drugs,
but the duration grammar misses the spelled-out multiword class. Three positives
use hyphenated, compact nonsteroidal and spaced class names. Eight initial near-
misses cover short duration, improvement, future plan, non-patient, denied/no
course, PT-only modality and unspecified duration. Source: fixed CPB Footnote 1,
CPB duration patterns and existing exclusion/subject handling.

Before: **0/3** positives pass; all eight negatives abstain (six exact; short and
improved notes should be NOT_READY). Candidate: add the full class to CPB therapy
context and its `no` negation pattern. Initial result: **3/3** positives pass,
**8/8** negatives exact with zero false pending; full suite **1134 passed,
10 xfailed**; corpus byte-for-byte baseline match.

**Rejected and reverted:** an additional challenge, derived from the contract's
`unrelated_therapy` failure class AFTER initial verification, substituted the
same three class spellings into courses explicitly for headaches. All three
became false PENDING_VERIFICATION. The candidate was immediately reverted to
HEAD. These challenge labels were written before testing, but after the first
candidate implementation; they are explicitly additional validation, not
misrepresented as part of the original eight negatives.

Post-revert score: **0/3** positives pass, **0/11 false pending** across original
and additional negatives. The added challenge negatives return to their prior
nonpassing state. Source diff confirms no product edit remains from this
iteration. No scorer, expected label, existing assertion or xfail was changed.

Repro inputs remain in `cases/rejected-iteration-1.json` and
`cases/rejected-iteration-1-challenge.json`. Initial before/after and challenge/
reverted scores, full-suite output and test-source snapshot are preserved in
`evidence/iteration-1-*`. Rejected positives remain visible in the final all-
authored evaluation, rather than being dropped from recall totals.

Gaming risk: the initial pairs alone would have made an unsafe vocabulary
expansion look successful. Policy-qualified modality is necessary but not
sufficient: the treatment must belong to the lumbar episode. No improvement
is claimed from this candidate. Unrestricted drug-name lists were not attempted;
the fixed source defines classes and this experiment has no repo-grounded
mapping of individual drug names to classes.

## Iteration 2 — accepted: whole-day CPB courses

Hypothesis (stated before cases/fix): a complete qualifying course recorded in
whole days can satisfy the same six-week minimum. Source: CPB Footnote 1 and
its no-improvement-after-six-weeks clause; existing CPB duration patterns only
accept numeric weeks. No drug-name mapping or clinical inference is involved.

Pairs fixed before implementation in `cases/iteration-2.json`: three positives
(42 days NSAIDs, 56 days analgesics before modality, 84 days muscle relaxants).
Ten negatives: 41 days, documented improvement, planned, non-patient, denied,
PT-only, unrelated headaches inline/semicolon, fractional and comparison forms.
Before: **0/3 positives pass**, negatives **8/10 exact and 0 false pending**;
short/improved courses abstain instead of NOT_READY.

Fix: add an anchored complete-course-and-response grammar for integer days,
only when its clause is the whole therapy sentence. It shares the existing
modality, exclusion, uncertainty, attribution and response resolver. Convert
integer days to completed weeks with floor division by seven; **41 → 5** cannot
cross the six-week boundary. Original week forms are unchanged. The isolated
statement restriction prevents the known indication/contrast borrowing exposed
by iteration 1; unsupported comparison/fraction/modified statements abstain.

After: **3/3 positives pass**, **10/10 negatives exact, zero false pending**;
41-day and improved courses now correctly return NOT_READY. Exact **8/13 →
13/13**, abstention **13/13 → 8/13**, matching expected **8/13**. No broader
abstention was introduced. Corpus remains byte-for-byte equal to baseline.
`make test`: **1136 passed, 10 xfailed**. No existing xfail marker/assertion
changed. Evidence: `evidence/iteration-2-*`; paired tests execute through the
public service in `test/test_exp002_recall.py`.

Gaming/limits: the whole-statement grammar is deliberately narrow and will miss
legitimate narrative qualifiers. It does not solve attribution or references in
other sentences, and does not repair the existing unrelated-week-course gap.
It is a general course grammar, not case-ID or exact-sentence matching. The
rejected iteration 1 cases remain in final totals, rather than being relabeled.

## Iteration 3 — accepted: whole-month CPB courses

Hypothesis (stated before cases/fix): a qualifying isolated course explicitly
recorded as two or more whole months clears the same six-week minimum. Source:
the fixed six-week policy and the existing extractor's four-week symptom-month
convention. Use **four completed weeks per month as a lower bound**, not a
calendar-date estimate; one month cannot meet six weeks.

Prewritten `cases/iteration-3.json`: three positives (2 months NSAIDs, 2 months
analgesics before modality, 3 months muscle relaxants) and ten negatives:
1 month, improvement, planned, non-patient, denied, PT-only, headaches inline/
semicolon, fraction and comparison. Current positives **0/3 pass before**;
negative statuses are recorded, including two incorrect CANNOT_DETERMINE
results for short/improved courses. The other eight already abstain correctly.

Fix: extend ONLY the isolated-course unit grammar to integer months and convert
them to four-week lower bounds in the shared duration helper. Preserve original
week parsing and iteration 2's indication/whole-sentence restriction.

After: cumulative positives **3/6 → 6/6 pass**; negatives **18/20 → 20/20 exact**,
zero false pending throughout; total **21/26 → 26/26 exact**. Abstention falls
**21/26 → 16/26**, matching expected **16/26**. One-month and improved-month
notes now return NOT_READY. `make test`: **1149 passed, 10 xfailed**. Then the
corpus is byte-for-byte baseline-equal. No existing assertion or marker changed.
Full before/after cases and scores are in `evidence/iteration-3-*`.

Gaming/limits: the conversion is intentionally a lower bound and has no start/
end-date calendar arithmetic. Fractional, ranged, comparative or annotated
month courses remain unsupported; fixed grammar is narrower than real narrative
notes. Correct threshold outcomes on these pairs do not establish general time
or episode understanding. Labels and previous paired cases were not changed.

## Iteration 4 — accepted: number words in isolated qualifying courses

Hypothesis (stated before cases/fix): writing six/eight/twelve instead of digits
does not change the six-week Footnote 1 criterion. Source: that fixed threshold,
qualifying classes, and the extractor's digit-only value regex; this is ordinary
number spelling, not drug classification or ontology lookup.

Prewritten `cases/iteration-4.json`: three positives (six weeks NSAIDs, eight
weeks before analgesics, twelve weeks muscle relaxants), eleven negatives:
five weeks, improvement, planned, non-patient, denied, PT-only, unrelated
headaches inline/semicolon, fraction, comparison and range. All three new
positives fail before implementation; negatives have zero false pending, with
short/improved cases incorrectly abstaining.

Fix: a finite one-through-twelve number-word mapping in the existing isolated
course grammar. Existing numeric-week patterns remain unchanged. The new grammar
continues to require a complete course and explicit response in one unsplit
sentence, so a numeric substring of a fraction, range or indication cannot be
selected. The shared helper retains conservative day/month conversions.

After: cumulative positives **6/9 → 9/9 pass**; negatives **29/31 → 31/31 exact**,
zero false pending throughout. Total **35/40 → 40/40 exact**; abstention
**30/40 → 25/40**, matching expected **25/40**. Five-week and improved-course
notes now correctly return NOT_READY. `make test`: **1163 passed, 10 xfailed**;
then corpus output equals baseline byte-for-byte. No existing assertion,
expected value or marker changed. Evidence: `evidence/iteration-4-*`.

Gaming/limits: the word range and complete-statement grammar are deliberately
bounded. Longer/compound numbers, comparative/ranged durations and narrative
course qualifiers remain unsupported. Mapping basic numbers is general, but
this is still a curated phrasing slice, not evidence of free-text clinical
recall. Neither rejected cases nor negative labels were removed to raise scores.

## Iteration 5 — accepted: direct named-root strength grades written with “of”

Hypothesis (stated before cases/fix): a direct objective exam in a named lumbar/
sacral root distribution, “strength 4 of 5” or “3 out of 5”, documents the same
motor deficit as existing slash notation. Source: CPB 0236's objective motor or
reflex changes in the specific root distribution; the existing strength parser
only recognizes slash grades. No subjective pain rating can substitute.

Prewritten `cases/iteration-5.json`: three positives (4 of 5, 3 out of 5,
4.5 of 5) and twelve negatives: normal strength, negated grade, question,
planned exam, non-patient, subjective report, missing/unnamed root, pain rating,
prior surgery inline/semicolon and contralateral radiculopathy. All three new
positives fail before implementation; all twelve negatives are nonpassing.
Five negatives initially have the wrong abstention status (normal strength and
four explicit ambiguity cases). All labels remain unchanged.

Fix: an anchored named-root objective-strength statement grammar. Explicit
negation, question, alternative attribution and opposite-side radiculopathy
route to review; normal 5 of 5 returns false. Other unsupported statements remain
unextracted. The first targeted run missed the decimal positive because the
legacy clause index splits decimals. The new route instead uses the existing
real-sentence index, preserving the legacy slash-notation path unchanged. The
initial failed test output is retained, not hidden. No unsafe pass occurred in
this iteration's paired tests.

After: cumulative positives **9/12 → 12/12 pass**, negatives **38/43 → 43/43
exact**, zero false pending. Total **47/55 → 55/55 exact**; abstention **40/55 →
36/55**, matching expected **36/55**. Normal strength now correctly gives
NOT_READY and four ambiguous statements NEEDS_REVIEW. `make test`: **1178 passed,
10 xfailed**; then corpus equals baseline byte-for-byte. No existing assertion
or xfail marker changed. Evidence: `evidence/iteration-5-*`.

Gaming/limits: the complete statement grammar is narrow and its special handling
of ambiguous word grades is asymmetric with legacy slash parsing. Named root,
strength and response wording form a curated slice, not general clinical
attribution. Opposite-side matching does not establish complete episode or
laterality understanding. These limitations and rejected cases remain visible.

## Final aggregate audit — no sixth iteration

The five-iteration budget is exhausted. No further product changes were made.
Retain all **69 authored cases**, including all fourteen from the rejected
iteration: **15 positives / 54 negatives**. The final 55 accepted pairs are
exact; rejected cases remain in the aggregate with their original labels.

For an additional retrospective comparison, `final_audit.py baseline` loads
only `67f1f3c:engine/extract.py` into an isolated Python process, then evaluates
through the unchanged public-service scorer. All other engine files are checked
against that commit. This does not checkout main, replace any source file, or
call extraction internals as the evaluator. Both baseline and current modes
score the identical case file. This is separate from the prospective before-fix
captures retained for each iteration.

| Metric, all 69 authored cases | Original engine | Final engine | Canary |
|---|---:|---:|---:|
| Exact | 41/69 | 64/69 | 41/69 |
| Positives passing | 0/15 | 12/15 | 0/15 |
| Negatives exact | 41/54 | 52/54 | 41/54 |
| False PENDING_VERIFICATION | 0 | 0 | 0 |
| Missed passes | 15 | 3 | 15 |
| Abstention | 100% | 72.46% | 100% |
| Expected abstention | 65.22% | 65.22% | 65.22% |

All 23 changed statuses move to their original expected value: twelve correct
PENDING_VERIFICATION, seven correct NOT_READY, four correct NEEDS_REVIEW.
No original correct status regresses; no wider abstention is used to achieve
the safety result. The remaining five exact-status misses are iteration 1's
three positive class-name variants and short/improved negative class-name
variants. The canary's zero false pending and 41/69 exact are insufficient
improvement evidence on their own.

Corpus: complete report equals frozen baseline, **52/52, zero false pending**;
canary remains **30/52**, seven missed passes. Exp-001's expanded 47-case report
also equals its original report: **45/47 exact, two pre-existing false pending**.
Those inherited gaps are unchanged, not omitted or presented as newly fixed.
The new authored negatives all remain nonpassing. No global safety guarantee
is claimed beyond the tested inputs.

Added eleven nonpassing regression checks for the rejected candidate's
negatives, preserving its original expected labels in the scorer. These guard
against reintroducing its unsafe expansion. The two unresolved exact negative
labels are not asserted as fixed or changed to CANNOT_DETERMINE. Together with
55 exact paired tests this yields **66 new regression tests**.

Final gates: **1189 passed, 10 xfailed** (`evidence/final-tests.txt`),
`make lint` passes (`evidence/final-lint.txt`). Baseline **1123 passed / 10
xfailed**. Newly passing strict xfails **0**; removed markers **0**. After those
gates, reran the complete current public-service audit. Evidence:
`final-all-cases.json`, `final-baseline-audit.json`, `final-current-audit.json`
and `final-scope-audit.json` in `evidence/`; `REPORT.md` contains the self-audit.

Scope audit: only `engine/extract.py` changes existing product files; only the
new `test/test_exp002_recall.py` adds tests. All pre-existing tests/expectations,
scorer, rules, rulebook, snapshots, inputs, goldens, artifacts, deployment/version
configuration, clocks and monitor state are unchanged. No generators, main
mutation, tags or PR were used. Existing untracked unrelated work was untouched.
No new disputes. The strength grammar is the most overfit-prone accepted fix;
all examples are authored, and the rejected unsafe candidate demonstrates why
this is evidence on bounded phrasing families rather than broad clinical recall.
