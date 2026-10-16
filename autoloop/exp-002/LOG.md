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
