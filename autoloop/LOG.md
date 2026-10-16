# Autonomous experiment log

## Phase 1 — evaluator frozen

Baseline committed as `7ade3e8`, then printed before continuing. No product
code changed. See [BASELINE.md](BASELINE.md) and
[baseline-score.json](baseline-score.json). The hard safety count is false
PENDING_VERIFICATION, separately from automated READY and missed passes.
The always-abstain canary achieves zero false passes without solving the task.

## Pre-loop artifact gate — required stop

Hypothesis, stated before testing: current-clock artifact generation already
changes committed governance projections because the successful policy check
is dated 2026-08-31 and the acceptance tests use 2026-09-01.

Minimal read-only reproduction:

```text
.venv/bin/python autoloop/check_artifact_gate.py
```

This constructs `ReadinessService()` with its unmodified runtime clock,
projects `get_drift_status()` through the exact `normalize_drift_payload`
function used by both generators, and compares parsed committed JSON. It does
not invoke the generators or write to either protected output directory. One
differing generator output suffices to prove the stop condition; this is not
an exhaustive enumeration of all affected outputs.

Result recorded in [artifact-gate.json](artifact-gate.json), at
2026-10-15 20:51:57 America/Los_Angeles (2026-10-16 03:51:57 UTC):

| Field | Committed | Default generation would produce |
| --- | --- | --- |
| any_review_required | false | true |
| sources[0].freshness_status | CURRENT | STALE |
| sources[0].review_reason | null | Last successful policy check exceeds the configured monthly monitoring window. |
| stale_source_count | 0 | 1 |

Both `test/golden/governance/drift_status.json` and
`docs/artifacts/drift_status.json` have those four differences. Sources:
`engine/acceptance.py`, `engine/service.py`,
`scripts/generate_golden_outputs.py`, `scripts/generate_artifacts.py`,
`test/conftest.py`, and the fixed policy snapshot metadata.

Applicable hard rule: "If make goldens or make artifacts would change committed
files, stop and log why instead of regenerating."

Disposition: stopped before iteration 1. No product defect hypothesis was tested
or fixed; no product regression test or xfail marker was changed. The freshness
difference is existing clock-dependent behavior, not a newly introduced defect.
Neither generator was run. No clock override or policy update was made to bypass
the stop. Zero of five allowed improvement iterations consumed.

## Closure verification

- Re-ran the unchanged scoreboard: [final-score.json](final-score.json) is
  byte-for-byte identical to the baseline. All metric deltas are zero.
- Exercised the actual `--cases` command on both a top-level list and an object
  with a `cases` list, using temporary files inside this repository. Both
  evaluated one minimal CPAP note through the public service with no READY.
- Rechecked score arithmetic with a mixed four-case status vector containing
  two false pending results and one missed pass.
- Re-ran `make test`; complete output is in [final-test.txt](final-test.txt).
- No rejected product hypotheses, disputes, reverted gaming attempts, or newly
  passing xfails. No policy, corpus, existing assertions, goldens, deployment
  configuration, main-branch reference, or tags changed. No push performed.

# Phase 2 — resumed under revised stop rule

The user replaced the artifact-generation stop rule. Phase 1 is frozen and was
not repeated. Neither Makefile generator is run. Existing fixed-clock acceptance
tests are authoritative; any candidate causing an existing test failure is
reverted. Runtime clock, monitoring state and fixed policy target stay unchanged.
The earlier stop above remains the historical record.

## Iteration 1 — confirmed diagnosis defect; fix rejected by regression gate

Hypothesis (stated before testing): `_finding_is_negated` does not recognize
`does/do/did not have` immediately before back pain or radiculopathy, causing a
false affirmative under the CPB 0236 requirement for persistent back pain with
radiculopathy. Sources: `engine/extract.py`, `EXTRACTION_CONTRACT.md`'s
`negation_first` strict xfail, the negation limitation in `LIMITATIONS.md` and
`FAILURE_MODES.md`, and the fixed policy's pain-plus-objective-findings clause.

Repro: [rejected-diagnosis-cases.json](rejected-diagnosis-cases.json), nine notes:
six denied criteria, two affirmative controls, one conflicting denial/affirmation.
Every expected status was fixed before testing. The temporary pytest repro is
retained verbatim in `evidence/iteration-1-repro-test.py.txt` (its original JSON
path has since been moved to the descriptive filename above).

Attempted fix: added the missing auxiliary-verb phrase to the existing bounded
negation regex. Targeted tests became 76 passed / 5 xfailed; the previously strict
`negation_first` assertion passed unchanged. Fresh cases changed from 2/9 exact,
7 false pending, 0% abstention to 9/9 exact, 0 false pending, 11.1111% abstention
(expected 11.1111%). Corpus results remained 52/52, zero false pending, zero
missed passes, 42/52 abstention.

**Rejected and reverted**: full `make test` returned **2 failed, 1080 passed,
13 xfailed**, because two existing tests explicitly assert the erroneous True:

- `test/test_corrections.py::test_failing_correction_and_original_negation_error`
- `test/test_service.py::test_complete_lumbar_proposals_require_every_human_verification`
  (the negated-diagnosis parameter)

These assertions conflict with the correct-value contract xfail. This is a
**dispute**, not permission to edit them. Product edit and xfail-marker removal
were both reverted. The unaccepted repro test is retained as evidence rather
than adding failing tests to the regression gate. No existing expected status,
case, assertion or marker remains changed by this iteration.

After revert: **1072 passed, 14 xfailed**. Then the frozen scoreboard was run:
52/52 exact, zero false pending, zero missed passes, 42/52 abstention. Rejected
repros return to 2/9 exact and seven false pending, matching their pre-fix state.
No increase from the pre-iteration state occurred. Detailed before/attempted/
reverted outputs are in `evidence/iteration-1-*`.

Metric-gaming audit: the attempt corrected explicit denial rather than broadly
abstaining; its small abstention increase matched an exact-accuracy gain. No
improvement is claimed because the existing-test gate rejected the fix.

## Iteration 2 — accepted: reflex descriptors borrowed from unrelated attributes

Hypothesis (stated before testing): any abnormal adjective in a reflex-containing
clause is treated as a reflex finding, even when it describes pain or sensation.
Sources: `_finding_is_negated`/objective collection in `engine/extract.py`, the
`reflex_attribution` contract xfail, FM-1's borrowed reflex qualifiers, and the
fixed CPB 0236 requirement for objective motor or reflex change (not pain relief
or sensory change alone).

Minimal repro: `Low back pain with radiculopathy. Right L5 distribution: reflexes
assessed, pain decreased. NSAIDs for 8 weeks with minimal improvement.` Expected
CANNOT_DETERMINE because no objective motor/reflex change is documented; before
was PENDING_VERIFICATION. `autoloop/regression_cases.json` gained 14 fixed-label
notes, covering both adjective orders, pain/sensation, explicit abnormal and
normal reflex controls, and a contradictory repeated finding.

Fix: require descriptors to link grammatically to a reflex noun, with copular
forms and bounded elliptical repeat findings; another subject cannot bridge the
link. Existing same-clause uncertainty, attribution and contradiction handling
is retained. This is regex/standard library only. Both normal and abnormal
adjectives receive the same linkage check.

Evidence (`evidence/iteration-2-*`): new pytest cases **6 failed / 8 passed before**,
then all 14 pass. Cumulative repro scoreboard **8/14 → 14/14 exact**;
**5 → 0 false pending**; **0 → 0 missed passes**;
**7.1429% → 50% abstention**, expected **50%**. The increase corresponds to six
corrected results, not broader refusal without accuracy gain. One bad normal
pain attribution previously produced NOT_READY rather than a false pending.

Removed only the strict marker for the existing `reflex_attribution` example
(`test_G01_exact_examples_and_determinism`): its unchanged expected null fact
and CANNOT_DETERMINE status now pass. The example/expectations were not edited.

Gate: **1087 passed, 13 xfailed**, no existing failure. Then the frozen corpus
scoreboard was run: byte-for-byte identical to baseline (**52/52 exact, zero
false pending, zero missed passes, 42/52 abstention**). Targeted lint passed.

Metric-gaming/limits: a small explicit predicate vocabulary and a 160-character
lookback bound recognition; unusual legitimate reflex wording can still be
missed. The rule is not a general syntax parser or a solution to attribution.
No claim of held-out generalization is made.

## Iteration 3 — accepted: intact reflexes incorrectly treated as missing

Hypothesis (stated before testing): the normal-reflex vocabulary lacks `intact`,
so explicit intact reflexes cannot produce a normal finding. Source: the existing
strict `independent_18_intact_reflexes` xfail, normal-reflex extraction code,
FM-2's under-capture class, and CPB 0236's objective motor/reflex-change criterion.
An intact reflex alone does not satisfy a change requirement, so a complete
otherwise qualifying note should be NOT_READY rather than missing/indeterminate.

Minimal repro: `Low back pain with radiculopathy. Right L5 distribution: reflexes
intact. NSAIDs for 8 weeks with minimal improvement.` Before CANNOT_DETERMINE;
expected NOT_READY. Seven new fixed-label cases were appended without altering
any previous case: intact before/after reflex wording, a different root,
uncertainty, contradictory repeat, unrelated intact sensation, and abnormal
reflexes alongside intact sensation.

Fix: add `intact` to the normal-reflex vocabulary and the existing predicate
link grammar. It retains iteration 2's subject linkage and the existing
uncertainty and contradiction handlers.

Evidence (`evidence/iteration-3-*`): **5 failed / 16 passed before**, all 21 pass
after. Cumulative repro score **16/21 → 21/21 exact**, false pending **0 → 0**,
missed passes **0 → 0**, abstention **13/21 → 10/21**, expected **10/21**. This fixes
wrong abstention and a missed contradiction, without expanding the passing set.

Removed only the strict marker on existing independent case 18. Its entire
unchanged expected-fact mapping, requirement statuses, NOT_READY status and
submission_readiness=false now pass.

Gate: **1095 passed, 12 xfailed**. Then the corpus scoreboard remained byte-for-
byte identical to baseline. Targeted lint/format checks passed after formatting
the simplified marker expression.

Metric-gaming/limits: this is a lexical extension justified by the existing
correct-value test; it does not infer intact strength or reflexes from unrelated
sensation, and does not claim general normal-exam recognition. Its test source
is known rather than held out.

## Iteration 4 — accepted: negated numeric strength treated as observed score

Hypothesis (stated before testing): numeric strength candidates are compared
with 5 even when explicitly negated. Sources: the strength loop in
`engine/extract.py`, `negated_strength` in the contract/strict xfails,
FM-1 negated-strength limitation, and the policy's requirement for objective
motor/reflex evidence. A denied score is not an observed score.

Minimal repro: `Low back pain with radiculopathy. Right L5 distribution:
dorsiflexion strength not 4/5. NSAIDs for 8 weeks with minimal improvement.`
Expected NEEDS_REVIEW; before PENDING_VERIFICATION. Eight fixed-label cases
were appended, including negated normal strength, prefix/suffix negation,
affirmative deficit/normal controls, and unrelated sensory-loss negation.

Fix: use the existing bounded negation helper plus an immediate `not` prefix
for strength-score candidates, and route them to the existing review state
before numeric threshold evaluation. This avoids inferring either normal or
abnormal strength from a denied number.

**Dispute left unchanged:** the existing `negated_strength` xfail asserts a
False fact / NOT_READY for `not 4/5`. A negated 4/5 does not establish normal
strength (it could be 3/5 or 5/5); review is the justified bounded result. Its
expected value and strict marker remain untouched, and it remains xfailed.

Evidence (`evidence/iteration-4-*`): **5 failed / 24 passed before**, all 29 pass
after. Cumulative repro score **24/29 → 29/29 exact**, false pending **4 → 0**,
missed passes **0 → 0**, abstention **10/29 → 15/29**, expected **15/29**. The
increase addresses five exact-status errors and preserves passing controls.

Gate: **1103 passed, 12 xfailed**. Then the frozen corpus scoreboard was run:
byte-for-byte identical to baseline. Targeted lint and format checks passed.
No additional existing marker was removed by this fix.

Metric-gaming/limits: narrowly refusing to interpret a negated number is policy-
justified, but it is still an abstention increase on these repros and must not be
advertised alone as improvement. Exact expected status improves for every new
negated-score case. This does not handle every negation form, replacement score,
or attribution of a numeric score to a different examination.

## Iteration 5 — confirmed date-association defect; fix rejected by regression gate

Hypothesis (stated before testing): the sleep-study date extractor borrows an
unrelated appointment date across sentence boundaries within its 80-character
window. Sources: date collection in `engine/extract.py`, the `borrowed_date`
contract xfails, FM-1/FM-2 date-association limitations, and the fixed CPAP rule's
requirement for dated sleep-study evidence.

Repro: [rejected-date-cases.json](rejected-date-cases.json), seven fixed-label
notes. Minimal negative: `OSA. Visit date 2024-05-18. Sleep study date not
recorded. AHI 22.` Expected CANNOT_DETERMINE, before PENDING_VERIFICATION.
Controls include genuine study dates in both orders and a cancelled study.
A genuinely dated study after a separate appointment also exposes a wrong
citation even when the status already passes. The temporary pytest repro is
retained in `evidence/iteration-5-repro-test.py.txt`.

Attempted fix: require the sleep-study context in the date's own sentence via
the existing indexed context helper; preserve existing exclusion/future checks.
The two correct-value borrowed-date strict markers were temporarily removed
when their unchanged assertions passed.

Evidence (`evidence/iteration-5-*`): **4 failed / 3 passed before**, all seven
pass after. Exact status **4/7 → 7/7**, false pending **3 → 0**, missed passes
**0 → 0**, abstention **1/7 → 4/7**, expected **4/7**. The fourth corrected test
checks the date citation. Corpus results stayed unchanged.

**Rejected and reverted:** `make test` returned **3 failed, 1109 passed,
10 xfailed**, with existing assertions retaining the borrowed-date behavior:

- `test_archive_invariants.py::test_borrowed_date_verified_ready_without_submission_readiness_roundtrips`
- `test_corrections.py::test_borrowed_date_can_be_withdrawn_without_fixing_extraction`
- `test_v210_independent.py::test_independent_correct_values_and_states`
  (independent case 17, whose frozen expected sleep_study_date is True and
  expected overall is PENDING_VERIFICATION despite its explicitly missing date)

This is a second **dispute** between known-error fixtures and correct-value
contract xfails. Their assertions and fixture remain unchanged. The product
candidate and both temporary xfail-marker removals were restored to the
iteration 4 commit. The unaccepted repro test is retained as evidence rather
than installed as a failing regression test. The citation-only strict xfail
also remains unchanged.

After revert: **1103 passed, 12 xfailed**. Then the frozen corpus scoreboard
was run: byte-for-byte equal to baseline. Date repro status score returns to
4/7 exact, three false pending; diagnosis repros still match their pre-attempt
statuses (2/9 exact, seven false pending). Neither set was silently dropped.
All five allowed improvement iterations have now been consumed.

Metric-gaming/limits: sentence association is a bounded heuristic; it would
still miss genuine cross-sentence dates and does not solve attribution of
multiple events within one sentence. It was not accepted, and no improvement
is claimed for it.

## Phase 2 closure

Final tests: **1103 passed, 12 xfailed**. Baseline: **1072 passed, 14 xfailed**.
The +31 passed tests comprise 29 new parametrized regression cases and two
previously strict xfails. The negated-strength xfail remains disputed and failing.

The corpus results and canary remain exactly frozen. Accepted regression cases
score 29/29, zero false pending, zero missed passes, 15/29 abstention (expected
15/29). To avoid selecting only successful fixes, all **45** authored cases
(including both rejected candidates) are retained and scored in
`all-authored-cases.json` / `all-authored-score.json`: **35/45 exact**, **10 false
pending**, **zero missed passes**, **16/45 abstention** (expected **20/45**).
Those ten remaining false pending results are the rejected diagnosis/date
cases; their statuses did not worsen from their respective pre-attempt states.
These are authored regressions, not held-out validation.

Protected-path diff audit passed. All assertions in the two modified existing
test files were compared by AST with the starting commit and are identical;
only the two resolved marker selections changed. Phase 1 and first-stop JSON,
scoreboard code, baseline, and original final-test evidence remain byte-for-byte
unchanged. No generator, clock override, monitoring-state change, policy edit,
original corpus edit, golden/artifact edit, push, tag or main change occurred.
