# exp-004 loop log

Base: main v2.5.0, 89a1500. Branch: autoloop/exp-004.
First commit 25b10cb contains only the owner dev file, unchanged, SHA-256
4832267bc1ff0ac8f57aac1dd36961ef62ea4d3f15d9286662866a0981685389.
The dev set is a check, not a source of exact-sentence rules. Each batch below
is authored before its implementation with different target vocabulary.
No held-out input is accessed. Existing untracked soccer-practice-arena/ is untouched.

## Dispute / explicit owner exception

The v2.5 executable contract asserts that “Took ibuprofen for 6 weeks with no
improvement” is missing evidence. This conflicts with the requested general
leading-verb recall fix. The owner explicitly approved correcting only that
example's therapy facts and overall status. No other existing expectation,
assertion, fixture, marker or contract example may change. Dev labels stay fixed.

## Iteration 1 — reported drug courses

Hypothesis: class membership is available, but the isolated course grammar
omits ordinary use verbs, dosing schedules, and course-first ordering.
General rule (before implementation): one listed drug in a reported present/past
course may have an optional patient subject/use verb phrase, dose and frequency;
duration can precede or follow it. An explicit response must belong to the same
whole course. Preserve future, negation, non-patient, unrelated-indication,
uncertainty and conflicting-course guards. Do not infer unlisted drugs' classes.
Paraphrases use etodolac, Dantrium, Ultram and sulindac, and verbs/schedules not
present in dev; negatives challenge the same rule rather than copying dev notes.

Result: dev 11/27 → 18/27 exact, 0 false pending; own pairs 16/16 exact
(4 positives / 12 negatives); corpus 52/52; exp-002 64/69 and exp-003 74/74
full reports unchanged, both with 0 false pending. Initial make test caught a legacy response-resolution regression (1 failed,
1316 passed / 10 xfailed); the failed run is retained. Nested-response handling
is now restricted to recognized whole drug courses; final suite result below. The shared response recognizer now includes benefit and
without-response wording; a positive response nested inside “no meaningful
benefit” is not counted again as an affirmative benefit. No drug-table addition.
The sole owner-authorized contract correction is applied; ID/note are unchanged.

Process correction: an initial local iteration commit was made before checking
the completed full-suite output. Its premature green-count text was corrected,
and the unpublished commit is amended only after all gates pass. No next
iteration proceeds on a failing suite.

Iteration 1 final: **1317 passed, 10 xfailed**, lint on changed Python files
passes. Final scoreboard remains dev 18/27, 0 false pending; own 16/16,
corpus 52/52, exp-002/003 full reports unchanged. No safety failure observed.

## Iteration 2 — typed objective exam grades

Hypothesis: a literal “strength” prerequisite misses typed motor exams; numeric
reflex grades are also absent. General rule before implementation: bind an
explicit motor or tendon-reflex grade directly to a named lumbar/sacral root
in the same exam clause. Motor labels or lower-limb muscles/actions may identify
the scale; +/- modifiers do not erase a subnormal base score. For reflexes,
low grades document change, the ordinary grade with normal/symmetric language
is normal, and brisk grades need explicit abnormality wording. Uncertain,
negated, pain-limited, conflicting-side or alternatively attributed findings
require review. Do not infer root distributions from muscle anatomy alone.
Own vocabulary adds iliopsoas, tibialis anterior, gastrocnemius, plantar flexion,
Achilles/ankle/knee jerks, different roots and scores, outside dev's target terms.

Result: dev **24/27 exact**, 0 false pending; own cumulative **38/38**
(12 positives / 26 negatives), including all 8 motor/reflex positives and
14 near-miss negatives. Corpus 52/52; exp-002 64/69 and exp-003 74/74 unchanged.
make test **1339 passed, 10 xfailed**. The new paraphrase harness initially
compared raw review sentinels with public service scalars (which deliberately
use None plus captured_fact_states). Corrected only this experiment's new
harness to check raw facts and the public review state, retaining every authored
case, fact expectation and status. A wrong state attribute in that harness was
also corrected; both failed outputs are preserved. No baseline test changed.
No drug additions, no safety failure, no dev-label dispute in this family.
