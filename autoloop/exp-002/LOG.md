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
