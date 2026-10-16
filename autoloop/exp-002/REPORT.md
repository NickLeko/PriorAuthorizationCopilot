# exp-002 — bounded recall experiment

Base: main v2.3.0, `67f1f3ccaf1ccdbd74b8c4b3a58620ae3c08209a`.
Work: `autoloop/exp-002`; five iterations, four accepted and one rejected.
The original public-service scoreboard is unchanged. No automated READY is
produced. The final engine improves recall on the authored pairs without adding
false PENDING_VERIFICATION on the corpus or any authored negative.

## Confirmed defects fixed

All paired inputs and expected labels were written before the relevant fix.
Each positive failed before implementation. The same parametrized public-service
test, `test/test_exp002_recall.py::test_exp002_pair`, executes both sides,
asserts exact statuses/facts, checks evidence offsets and requires unverified
facts and no submission readiness. Per-case statuses and confusion matrices
are retained in `evidence/iteration-N-before-score.json` and `*-after-score.json`.

| Iteration | Policy-derived family and narrow fix | Positive regression IDs | Negative coverage | Full suite after iteration |
|---|---|---|---|---|
| 2 | Complete qualifying courses in whole days; floor completed days / 7 | `days_threshold`, `days_before_modality`, `days_relaxant` | 10: short, improved, planned, non-patient, denied, PT-only, unrelated indication inline/semicolon, fraction, comparison | 1136 passed / 10 xfailed |
| 3 | Complete qualifying courses in whole months; four-week lower bound per month | `months_nsaid`, `months_before_modality`, `months_relaxant` | 10, including one month below six weeks and substantial improvement | 1149 passed / 10 xfailed |
| 4 | Number words one through twelve in that isolated course grammar | `words_threshold`, `words_before_modality`, `words_relaxant` | 11, including five weeks, improvement, fractional/comparative/ranged language and unrelated therapy | 1163 passed / 10 xfailed |
| 5 | Direct named-root objective strength written “4 of 5” / “3 out of 5”, including decimal scores | `exam_of`, `exam_out_of`, `exam_decimal` | 12: normal, negated, questioned, planned, non-patient, subjective, missing/unnamed root, pain rating, alternative attribution inline/semicolon, opposite side | 1178 passed / 10 xfailed |

Sources: unchanged `rules/payer_rules.yaml` lumbar requirements and
`policy_snapshots/aetna_mri_lumbar/latest.json` CPB 0236. The policy requires
objective motor/reflex changes in a specific root distribution and no improvement
after six weeks of qualifying conservative therapy. Footnote 1 defines the
qualifying classes. Day conversion is exact for completed weeks; month conversion
is a conservative duration bound, not an inferred calendar date. The new grammar
requires an isolated complete course/response statement, avoiding indication
modifiers and split-clause borrowing. Original numeric-week extraction is kept.

Iteration 5 initially missed its decimal positive because legacy clauses split
decimal points. The failed output is preserved. Its new notation path uses the
existing real-sentence index; the legacy slash-notation route is unchanged.
Negation/uncertainty/alternative attribution and opposite-side findings require
review, while explicit normal strength fails the objective-finding requirement.

## Rejected hypothesis and remaining misses

Iteration 1 tested full non-steroidal anti-inflammatory class names explicitly
listed in Footnote 1. Its three positives reproduced the recall defect. The
initial expansion passed three positives and eight negatives, the suite and the
corpus. Additional challenges derived from the contract's `unrelated_therapy`
failure class then produced **three false PENDING_VERIFICATION** for courses
explicitly for headaches. The candidate was immediately reverted. No improvement
from that candidate is included in the accepted result.

Those three challenges were added after the initial implementation, before
testing them; they are additional validation, not claimed as original pre-fix
pairs. All fourteen iteration-1 inputs remain in the final evaluation with their
original labels. The three positives still abstain; its short and improved
negative cases still abstain instead of NOT_READY. No hypothesis was rejected
for failure to reproduce. Individual drug-name mapping was not attempted because
the available fixed source defines classes rather than an auditable drug list.

The eleven rejected-candidate negatives also remain executable as safety
regressions in `test_exp002_rejected_candidate_stays_nonpassing`. That test
asserts nonpassing and a non-MET requirement. It deliberately does not pretend
the two unresolved exact-status misses are fixed; the scoreboard exposes both.

## Metrics and canary

The final all-authored set contains **69 cases: 15 positives and 54 negatives**.
It includes 51 original near-miss negatives and three later attribution
challenges. Accepted iterations contribute 12 positives and 43 negatives,
all **55/55 exact**. Including the rejection, positives are **12/15 passing**
and negatives **52/54 exact**, with **0/54 false PENDING_VERIFICATION**.

| Dataset / metric | Original engine | Final engine | Always-CANNOT_DETERMINE canary |
|---|---:|---:|---:|
| Corpus exact | 52/52 | 52/52 | 30/52 |
| Corpus false PENDING_VERIFICATION | 0 | 0 | 0 |
| Corpus missed passes | 0 | 0 | 7 |
| Corpus abstention / expected | 80.77% / 80.77% | 80.77% / 80.77% | 100% / 80.77% |
| All authored exact | 41/69 (59.42%) | 64/69 (92.75%) | 41/69 (59.42%) |
| All authored false PENDING_VERIFICATION | 0 | 0 | 0 |
| All authored missed passes | 15 | 3 | 15 |
| All authored abstention / expected | 100% / 65.22% | 72.46% / 65.22% | 100% / 65.22% |

The authored-set exact gain is **23 cases / 33.33 percentage points**, both
against baseline and against the canary. Twelve CANNOT_DETERMINE results become
correct PENDING_VERIFICATION, seven become correct NOT_READY, and four become
correct NEEDS_REVIEW. No previously correct authored status regresses.
Abstention decreases 27.54 points while exact accuracy improves. Zero false
pending alone proves little: the canary achieves it while missing every pass.
The unchanged corpus cannot establish recall improvement either.

`final_audit.py baseline` loads the original extractor from git into an isolated
Python process before importing the unchanged public-service scorer. Other
engine files are asserted unchanged; no checkout or on-disk replacement occurs.
`final_audit.py current` evaluates the same 69 inputs. Full reports, source hashes,
case hash, confusion matrices and remaining mismatches are in
`evidence/final-baseline-audit.json` and `evidence/final-current-audit.json`.
This final baseline replay is explicitly retrospective; the per-iteration
before-fix evidence was captured prospectively.

The exp-001 expanded 47-case report is also identical for original and final
engines: **45/47 exact, two pre-existing false PENDING_VERIFICATION**. These are
the documented inherited gaps, not new exp-002 negatives or newly introduced
passes. This experiment does not claim universal safety or to resolve them.

## Tests, disputes and scope

Baseline: **1123 passed, 10 xfailed**. Final: **1189 passed, 10 xfailed**.
The 66 new regressions comprise 55 exact paired tests plus eleven safety tests
for rejected-candidate negatives. Newly passing strict xfails: **0**; markers
removed: **0**. `make test` and `make lint` pass. Final raw outputs are
`evidence/final-tests.txt` and `evidence/final-lint.txt`.

No existing test assertion, expected status, eval case or fixture was changed.
No new disputes were raised; unresolved cases remain recorded as misses.
Only `engine/extract.py` changes product code; new tests and experiment records
provide the evidence. Scorer, policies, rulebook, inputs, goldens, artifacts,
deployment configuration, version, clocks and policy-monitor state are unchanged.
No generators, tag operations, PR creation or main mutation were used. The
pre-existing untracked `soccer-practice-arena/` directory was left alone.

## Honest self-audit

The **direct named-root strength grammar is the most overfit-prone fix**. Its
whole-statement form and named-root requirement closely bound the authored
phrasing slice; the three positives do not establish robust interpretation of
arbitrary exam prose. It does, however, recognize a general numeric notation
rather than IDs, fixture names or exact sentences, and twelve adversarial
near-misses constrain the change. Its new review handling is asymmetric with
legacy slash notation and leaves existing attribution limitations intact.

The isolated-course grammar is also intentionally narrow. Requiring “with” and
an explicit response omits many valid narrative notes; number words stop at
twelve, and month values are lower bounds. These restrictions trade recall for
evidence and do not establish episode understanding across sentences. Duration
families share one mechanism, so the four accepted iterations are not four
independent demonstrations of generalization.

All examples are authored during development, not held out. The unsafe class
expansion showed that initial pairs and an unchanged corpus can both miss a
real false pass. Keeping its rejected inputs, unsafe intermediate evidence and
remaining misses prevents selective reporting. Safety gates here establish
non-regression on tested inputs, not a guarantee over unseen clinical notes.
