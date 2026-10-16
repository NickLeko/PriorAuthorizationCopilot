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

## Iteration 3 — calendar-valid study dates with direct study linkage

General rule before implementation: accept calendar-valid US numeric, dotted
year-first, and English full/abbreviated month dates in either written ordering,
including ordinal days. New date forms require a directly adjoining completed
sleep-test cue, not merely a date elsewhere in the same sentence. Retain
non-patient, planned/cancelled, missingness, uncertainty and question guards.
This is syntax/calendar validation, with no new clock, recency or date inference.
Own paraphrases use HST/polysomnogram/home-sleep-test vocabulary, November,
February and September, day-first/ordinal/dotted/hyphen forms not in dev.

Result: dev **26/27 exact**, 0 false pending; own cumulative **52/52**
(16 positives / 36 negatives). All 4 new date positives and 10 negatives pass.
Corpus 52/52; exp-002/003 full reports unchanged. make test **1353 passed,
10 xfailed**. Calendar validation uses datetime.strptime only, never a clock.
Legacy year-first date behavior is preserved; newly accepted formats require
direct study linkage. No data-table addition and no safety failure observed.

## Iteration 4 — named AHI/RDI measurements

General rule before implementation: apnea-hypopnea index and respiratory
disturbance index are full-name aliases for documented AHI/RDI, including
space/hyphen variants and British apnoea/hypopnoea spelling. Accept explicit
numeric values with ordinary value predicates; do not infer a value from a
bare name, comparison, other vital sign, plan, negation or non-patient report.
Missingness uses the same sentence scope as abbreviated indices. Keep existing
uncertainty/review handling. Do not expand to unrelated indices such as REI.
Own pairs emphasize respiratory-disturbance / British terminology and value
predicates absent from dev; all use different dates and index values.

Result: dev **27/27 exact**, including all requirement statuses; 0 false
pending. Own cumulative **68/68** (20 positives / 48 negatives), with the final
4 full-name positives and 12 negatives correct. Corpus 52/52; exp-002 64/69
and exp-003 74/74 unchanged. make test **1369 passed, 10 xfailed in 36.96s**;
make lint green (76 Python files). No table additions or observed safety failures.

## Final common-input replay

final_audit.py baseline/current loads the two changed modules from main into
an isolated process, or uses current sources, before importing the unchanged
public scorer. This is a retrospective comparison on all 68 independent pairs,
not the prospective before-fix evidence above: own 33/68 → 68/68 exact,
0/20 → 20/20 passing positives, zero false pending both times. Dev is 11/27 →
27/27, zero false pending both times. All 52 corpus proposals, source spans,
public states and input/fact-set/verification fingerprints are identical.
At that checkpoint four iterations sufficed for the visible check. The owner
subsequently requested iteration 5 after discovering the safety defect below.
No held-out input was accessed; a perfect visible check is not held-out evidence.

## Iteration 5 — source attribution and exam performance

Origin: the owner found a false PENDING_VERIFICATION in held-out evaluation
after iteration 4; our own tests did not find it. The owner supplied the failure
class, not the held-out dataset. The earlier visible gates missed this defect.

Hypothesis: typed grades and legacy strength/reflex findings bypass source and
exam-performance qualifiers, particularly across a semicolon. General rule
(before implementation): a motor/reflex finding attributed in its sentence to
the patient or history (per patient, patient reports/states, self-reported,
by history), or accompanied by an unperformed exam (deferred, not performed,
not examined, unable to assess, limited by refusal), supplies no objective
evidence. Apply one sentence-wide guard to typed, legacy slash/word strength
and descriptive reflex/weakness paths. A qualified source alone is
NOT_DOCUMENTED; a conflicting objective finding in a different sentence is
NEEDS_REVIEW. An agreeing objective finding remains usable. Ordinary objective
exams, including on-exam/examination-shows language, retain their behavior.

Before changing extraction, authored iteration-5.json: 10 positives / 24
negatives. These cover both qualifier positions, semicolons, decimal and word
grades, numeric/descriptive reflexes, legacy objective-weakness wording,
conflicting and agreeing sources, and sentence isolation. Target exam vocabulary
includes soleus, hip/plantar flexion, Achilles/ankle/knee jerks and right-sided
roots, rather than copying dev sentences. Dev remains unchanged.

Before-fix evidence on 8199ea2: new batch 19/34 exact, **13 false pending**;
all own 87/102. Corpus 52/52, dev 27/27, exp-002 64/69 and exp-003 74/74
still had zero false pending. The safety harness intentionally rejects that
existing baseline once the new cases expose it; this is not a green candidate.
Paired tests: 30 failed / 106 passed before the repair. Inputs and expected
facts/statuses remain identical between before and after.

Implementation: one final objective-candidate guard covers all finding routes,
with whole-sentence scope across semicolons and decimal scores. Qualified-only
sources are discarded, including purported normal grades. When another objective
candidate contradicts normal/abnormal status, preserve both sentence citations
and require review. An agreeing objective source remains valid. A qualified word
grade is recognized for conflict detection even if surrounding attribution
prevents the existing passing route’s full-sentence match; this does not broaden
passing word-grade extraction. No drug-table change or label dispute.

Final iteration-5 gates: new batch **34/34** (10 positives / 24 negatives),
all own **102/102** (30 positives / 72 negatives), dev **27/27** including every
requirement status, corpus **52/52**, exp-002 **64/69** and exp-003 **74/74**
with full frozen reports unchanged. Zero false PENDING_VERIFICATION on every
set and every authored negative. Always-CANNOT_DETERMINE canary is 18/34 on the
new batch and 51/102 on all own cases; its zero false pending alone is not recall.
Paired/requirement tests: **136 passed**; make test: **1437 passed, 10 xfailed
in 38.47s**. Make lint passes (77 Python files). The additional requirement-level
checks distinguish NOT_DOCUMENTED/MISSING from NEEDS_REVIEW and verify literal
citations for conflicting evidence. No candidate safety failure or reversion;
the known pre-fix owner defect is repaired. Scope and corpus fingerprint audit
are retained separately from the original four-iteration historical audits.
The actual held-out dataset was not accessed or rerun here; no held-out passing
result is claimed. This iteration used the owner’s feedback and is development.
