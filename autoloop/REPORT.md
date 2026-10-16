# Experiment exp-001 — iterations 6 and 7 completed

Both previously rejected fixes are now accepted under the owner's narrow test-
rewrite authorization. Each iteration passed `make test` and the frozen public-
service scoreboard and is committed separately. Iteration 6: `0b1674b`; iteration
7 includes this final report. The prior report and original first-stop record
are preserved verbatim below as history.

- Final tests: **1123 passed, 8 xfailed**, versus **1103 / 12** at 962fafc.
- Corpus: **52/52 exact, zero false PENDING_VERIFICATION**, byte-for-byte baseline
  match; no corpus improvement is claimed from its saturated score.
- Frozen original 45 authored cases: **35/45 → 42/45 → 45/45 exact**, false pending
  **10 → 3 → 0** across the two resumed iterations.
- Expanded 47 cases, also counting the replacement setup errors: **35/47 →
  42/47 → 45/47 exact**, false pending **12 → 5 → 2**. The two remaining errors
  are disclosed limitations, not fixed cases hidden from evaluation.

## Per-test classification and coverage

Classifications were written in [LOG.md](LOG.md) before editing. Class **(a)**
asserts product behavior; class **(b)** uses a proposal to exercise another feature.
The fixed policy/contract sources are [payer_rules.yaml](../rules/payer_rules.yaml)
(`equals_true` lumbar diagnosis and dated-study CPAP requirements) and
[EXTRACTION_CONTRACT.md](../EXTRACTION_CONTRACT.md) (`negation_first`, `borrowed_date`,
G03–G05 on attestations/corrections and G07 on demo-policy readiness).

| Iteration / disputed test | Class | Rewrite and preserved purpose |
| --- | --- | --- |
| 6: corrections `test_failing_correction_and_original_negation_error` | **(b)** | Swap in explicit neither/nor denial, still wrongly captured True. Preserve True → False SET_VALUE, immutable original and NOT_READY. Add original-True snapshot, changed fingerprint and NOT_MET checks. Separate below-threshold correction assertion is unchanged. |
| 6: service `test_complete_lumbar_proposals_require_every_human_verification` (denied parameter) | **(b)** | Swap only the wrong-proposal input to the same neither/nor denial. Retain a correct parameter and a semantically wrong all-MET parameter, every omitted-attestation check, and fully attested READY. No body assertion changed. |
| 7: archive `test_borrowed_date_verified_ready_without_submission_readiness_roundtrips` | **(b)** | Swap to an unrelated visit date in the same sentence as the undated study. Still a wrong all-MET proposal with deliberately incorrect synthetic attestations; retain READY, demo trust, submission_readiness=false and exact SQLite round trip. Add original date-True and PENDING_VERIFICATION preconditions. |
| 7: corrections `test_borrowed_date_can_be_withdrawn_without_fixing_extraction` | **(b)** | Same same-sentence setup. Retain wrong True, actual offending-span review, SET_MISSING, immutable original and CANNOT_DETERMINE. Add effective-null, original-True snapshot and changed fingerprint checks. |
| 7: independent case 17 in `test_independent_correct_values_and_states` | **(a)** | Correct only its three labels as listed below. All generic state/fact/status assertions remain intact, and its note is unchanged. |
| 7: `test_independent_17_study_citation_correct_sentence` | **(a)** | A missing date yields null and an empty date-citation list; an undated completion statement cannot act as a date quotation. Three newly active genuine-date controls assert the exact date span and marked citation context. |

The category-(b) tests retain wrong-proposal setups rather than becoming easier
correct-note smoke tests. The two replacement inputs were scored before either
fix and remain visible in [resume-setup-cases.json](resume-setup-cases.json):
`neither low back pain nor radiculopathy` and a same-sentence unrelated visit
date. Both still produce false pending; that risk is preserved in the feature
tests and counted in the expanded set.

## Fixes and independent-case-17 label change

**Iteration 6:** re-applied exactly the rejected bounded `does/do/did not have`
negation regex alternative. Nine original diagnosis repros were added to the
collected regression suite without relabeling: **7 failed / 31 passed before**
product fix on the cumulative suite; all 38 pass after. The nine diagnosis
cases improve **2/9 → 9/9 exact, false pending 7 → 0**.

**Iteration 7:** re-applied exactly the rejected requirement that a candidate
date and study context share a sentence, using the existing indexed context
helper. Other future/exclusion logic is unchanged. Seven unchanged-label date
repros became collected regressions, including positive exact-date/context
checks: **4 failed / 41 passed before**, all 45 pass after. Date cases improve
**4/7 → 7/7 exact, false pending 3 → 0**, and the fourth failing test's incorrect
citation is corrected.

The owner-approved case-17 change is explicitly a **label change**:

| Case-17 field | Old | New |
| --- | --- | --- |
| `expected.sleep_study_date` | true | null |
| `expected_requirements.sleep_study_date` | MET | NOT_DOCUMENTED |
| `expected_overall` | PENDING_VERIFICATION | CANNOT_DETERMINE |

Rationale: the note says the study date cannot be located; its numeric date is
an appointment in another sentence. The fixed CPAP dated-study requirement and
the executable `borrowed_date` contract require missingness, with G04 deriving
CANNOT_DETERMINE. The case input and every other fixture entry/field are unchanged.
This relabel is not used as independent evidence of improvement; the frozen
45-case authored set was not relabeled and independently demonstrates both gains.

## Strict xfails and test counts

Removed in iteration 6:

- Contract `negation_first`: original False / NOT_READY assertions now pass.

Removed in iteration 7:

- Contract `borrowed_date`: original null / CANNOT_DETERMINE assertions now pass.
- `test_G07_borrowed_date_remains_contained_by_demo_submission_gate`: unchanged
  missing-date and false-submission assertions pass, including with attestations.
- `test_independent_17_study_citation_correct_sentence`: owner-rewritten assertion
  now passes. This is an expectation correction as well as a removed marker,
  unlike the three unchanged-assertion resolutions above.

The unrelated negated-strength expectation dispute and every other xfail remain
unchanged. No failed test or strict XPASS remains.

| Result | At 962fafc | After 6 | After 7 |
| --- | ---: | ---: | ---: |
| Passed | 1103 | 1113 | 1123 |
| Xfailed | 12 | 11 | 8 |
| Collected authored regression cases | 29 | 38 | 45 |

The +20 passed tests comprise 16 newly collected repros and four removed markers;
three of those markers retain their original assertions and one is owner-rewritten.
[Iteration 6 suite](evidence/iteration-6-suite.txt),
[iteration 7 suite](evidence/iteration-7-suite.txt) and targeted outputs retain
full evidence. Targeted Ruff lint/format checks pass on all modified Python files.
Raw pytest stdout retains its emitted whitespace.

## Metrics and canary

The scoreboard and all measured case inputs/labels below are unchanged across
these measurements. All missed-pass counts remain zero. Full confusion matrices,
hashes and individual cases are in the linked reports.

| Fixed set | Before 6: exact / false pending | After 6 | After 7 |
| --- | --- | --- | --- |
| Corpus (52) | 52/52 / 0 | 52/52 / 0 | 52/52 / 0 |
| Original authored (45) | 35/45 / 10 | 42/45 / 3 | 45/45 / 0 |
| Expanded authored (47) | 35/47 / 12 | 42/47 / 5 | 45/47 / 2 |

Original-45 abstention rises **16/45 → 17/45 → 20/45**, matching its expected
20/45 at completion. Expanded-47 abstention is **16/47 → 17/47 → 20/47**, with
21/47 expected. Every rise accompanies an exact-status gain. Case-by-case checks
confirm no newly false pending result at either accepted transition.

| Final set | System exact | Canary exact | System / canary false pending | System / canary missed passes |
| --- | --- | --- | --- | --- |
| Corpus 52 | 52/52 | 30/52 | 0 / 0 | 0 / 7 |
| Original 45 | 45/45 | 11/45 | 0 / 0 | 0 / 13 |
| Expanded 47 | 45/47 | 12/47 | 2 / 0 | 0 / 13 |

The canary abstains on 100% of every set. The system's corpus abstention remains
42/52, matching expected. Zero false pending alone remains weak evidence because
the canary also scores zero; exact-status gains on frozen new cases, preserved
passing controls and complete mismatch reporting support the changes.

Final reports: [corpus](evidence/iteration-7-corpus.json),
[original authored 45](evidence/iteration-7-all-authored.json),
[expanded 47](evidence/iteration-7-expanded.json),
[remaining setup errors](evidence/iteration-7-setups.json).
Before/after reports for each iteration are under `evidence/iteration-6-*` and
`evidence/iteration-7-*`; original baseline and prior reports are not overwritten.

## Self-audit and scope

No feature coverage was weakened by merely flipping a known-bug setup assertion:
correction, immutable-snapshot, fingerprint, every omitted-attestation check and
wrong-READY archive coverage remain or are strengthened. The empty citation
assertion is less demanding about positive source rendering by itself, so the
three newly active genuine-date regressions explicitly check that rendering.
Case 17's relabel and citation rewrite are transparently distinguished from
unchanged-label improvements. The narrower regex/sentence fixes still miss other
negations and event associations, including the two deliberately retained setup
errors. These authored cases are not held-out validation or proof of general
clinical-language correctness.

Scope audit against 962fafc verified every other function in the five existing
test files is unchanged; contract-test bodies/expectations are unchanged; the
fixture differs only at the three authorized case-17 labels. The baseline,
scoreboard, original 45-case input/labels and old JSON evidence are unchanged.
Rules, rulebook, policy snapshots, inputs, goldens, committed artifacts, deployment
config, clocks and monitoring state are unchanged. Neither generator was run.
Work/commits and the authorized final push are restricted to `autoloop/exp-001`;
main remains at 5ac2cd8, with no tags or PR. Pre-existing untracked
`soccer-practice-arena/` remains untouched.

---

# Iterations 1–5 report — historical record preserved verbatim

# Experiment exp-001 — resumed Phase 2 report

Completed the five-iteration bound on `autoloop/exp-001`: **three accepted fixes,
two confirmed defects with rejected fixes**. No additional product improvements
were attempted after iteration 5. Phase 1 was preserved, not repeated. The
first-stop report is preserved verbatim below as historical context.

The corpus remains **52/52 exact, zero false PENDING_VERIFICATION**, byte-for-byte
equal to baseline. Evidence of improvement comes from newly failing-then-passing
regressions, not the already-perfect corpus. Final `make test`: **1103 passed,
12 xfailed**. No push, tag, deployment change or main change occurred.

## Accepted fixes and regression evidence

All 29 new regression instances run in
`test/test_autoloop_regressions.py::test_autoloop_regression`, using the public
service and [regression_cases.json](regression_cases.json). Tests assert exact
overall status, relevant fact values, requirement status, false submission
readiness, no automated READY and literal evidence-span offsets. Expected
values were written before fixes; existing case expectations were not changed.

| Iteration | Defect and fix | Representative regression | New failures before fix | Result |
| --- | --- | --- | ---: | --- |
| 2 | Pain/sensation adjectives were borrowed as reflex findings. Require a grammatical reflex noun/descriptor link. | `reflex_unrelated_attribute_1` (`reflexes assessed, pain decreased`) | 6 | 14 cases pass; 1 old xfail now passes |
| 3 | Explicitly intact reflexes were missing. Add `intact` to normal reflex vocabulary with the same subject linkage. | `reflex_intact_1` | 5 | 7 additional cases pass; 1 old xfail now passes |
| 4 | Negated numeric strength was compared as an observed score. Route denied scores to the existing review state first. | `strength_negated_1` (`strength not 4/5`) | 5 | 8 additional cases pass; existing disputed xfail retained |

Changes are confined to deterministic regex/standard-library extraction, without
new dependencies or an architectural rewrite. The fixed policy requires
objective motor/reflex evidence; pain relief or sensation alone does not supply
that evidence. A denied number supplies neither an observed deficit nor normal
strength. Explicit intact reflexes alone do not satisfy a change requirement.

Only these existing strict markers were removed, after their unchanged
expectations passed:

- Contract `reflex_attribution`: null objective fact and CANNOT_DETERMINE.
- `independent_18_intact_reflexes`: false objective fact, NOT_MET and NOT_READY,
  together with the fixture's entire unchanged fact/requirement mapping.

Each accepted iteration passed the full suite, then ran the frozen scoreboard.
See [LOG.md](LOG.md) and `evidence/iteration-2-*`, `iteration-3-*`,
`iteration-4-*` for full before/after results.

## Rejected fixes and disputes

No hypothesis failed to reproduce. Two real defects remain because the revised
rule required reverting any fix that failed an existing test.

**Iteration 1 — diagnosis negation.** Adding `does/do/did not have` to bounded
negation recognition fixed seven new errors, including a denial/affirmation
conflict. New-case exact status rose 2/9 → 9/9 and false pending fell 7 → 0.
But two existing tests explicitly assert the known incorrect affirmative
proposal for a denied diagnosis (`test_corrections.py` and `test_service.py`).
Full suite: 2 failed, 1080 passed, 13 xfailed. The fix and temporary marker
removal were reverted; suite returned to 1072 passed, 14 xfailed.
[Reproductions](rejected-diagnosis-cases.json) and `evidence/iteration-1-*` retain
this result. Those existing assertions are disputed and unchanged.

**Iteration 5 — borrowed sleep-study date.** Requiring study context in the date's
own sentence corrected three false pending results and one wrong citation.
New-case exact status rose 4/7 → 7/7 and false pending fell 3 → 0. But existing
archive, correction and independent-case-17 tests deliberately retain the
borrowed-date value; the independent fixture expects PENDING_VERIFICATION even
though the study date is explicitly missing. Full suite: 3 failed, 1109 passed,
10 xfailed. The candidate and both temporary marker removals were reverted.
[Reproductions](rejected-date-cases.json) and `evidence/iteration-5-*` retain the
results. Their assertions/fixture are disputed and unchanged.

**Negated-strength expectation dispute.** The original `negated_strength` strict
xfail expects False / NOT_READY for `not 4/5`. That number's negation does not
establish a normal exam; the accepted fix yields NEEDS_REVIEW. The original
expected fact/status and strict marker remain untouched, so it remains xfailed.

No existing expected status, eval input, golden output or assertion was edited.
An AST comparison confirmed unchanged assertion inventories in both existing
test files whose marker selection was modified.

## Score deltas and canary comparisons

[Final corpus scoreboard](phase2-corpus-score.json) equals the
[Phase 1 baseline](baseline-score.json) byte-for-byte. Its input hash remains
`6064495e3233138fcf78e16bc9471b4ef182679c07de0bcf012b699a53611671`.
All corpus deltas from baseline are zero:

| Corpus metric | Baseline and final system | Canary | Final minus canary |
| --- | ---: | ---: | ---: |
| Exact accuracy | 52/52 (100%) | 30/52 (57.6923%) | +42.3077 percentage points |
| False PENDING_VERIFICATION | 0 | 0 | 0 |
| Missed passes | 0 | 7 | -7 |
| Abstention rate | 42/52 (80.7692%) | 52/52 (100%) | -19.2308 percentage points |
| Expected abstention rate | 42/52 (80.7692%) | 42/52 (80.7692%) | 0 |
| Automated READY | 0 | 0 | 0 |

Fresh-case scores are cumulative at each iteration, so their changing denominators
must not be interpreted as repeated measurements of one fixed corpus:

| Accepted iteration | Cumulative exact before → after | False pending before → after | Abstention before → after | Expected abstention |
| --- | --- | --- | --- | --- |
| 2 | 8/14 → 14/14 | 5 → 0 | 1/14 → 7/14 | 7/14 |
| 3 | 16/21 → 21/21 | 0 → 0 | 13/21 → 10/21 | 10/21 |
| 4 | 24/29 → 29/29 | 4 → 0 | 10/29 → 15/29 | 15/29 |

The [29-case final regression scoreboard](phase2-regression-score.json) is
29/29 exact, zero false pending, zero missed passes, 15/29 abstention (matching
expected). Its canary is 7/29 exact, zero false pending, eight missed passes,
100% abstention. The abstention increases in iterations 2 and 4 each correspond
to exact-status gains; iteration 3 reduces wrong abstention.

To avoid reporting only successful candidates, the [all-authored input](all-authored-cases.json)
and [scoreboard](all-authored-score.json) include **all 45 new cases**, including
the rejected fixes:

| All-authored metric | Final system | Canary |
| --- | ---: | ---: |
| Exact accuracy | 35/45 (77.7778%) | 11/45 (24.4444%) |
| False PENDING_VERIFICATION | **10** | 0 |
| Missed passes | 0 | 13 |
| Abstention | 16/45 (35.5556%) | 45/45 (100%) |
| Expected abstention | 20/45 (44.4444%) | 20/45 (44.4444%) |

The ten remaining false pending results are seven diagnosis and three date
cases. Both rejected case sets have exactly their original pre-attempt statuses;
none worsened. No single before-all-fixes baseline was measured on this combined
new set, so no aggregate baseline improvement is claimed for it. Full confusion
matrices and case results are retained in each JSON scoreboard.

## Tests and constraints

| Result | Original baseline | Final | Delta |
| --- | ---: | ---: | ---: |
| Passed | 1072 | 1103 | +31 |
| Xfailed | 14 | 12 | -2 |
| Existing strict xfails newly passing | 0 | 2 | +2 |
| New collected regression instances | 0 | 29 | +29 |
| Failed / strict XPASS | 0 | 0 | 0 |

[Final full-suite output](evidence/iteration-5-reverted-suite.txt) records the
post-revert result. Targeted Ruff lint/format checks passed for all modified
Python source/test files. Raw pytest evidence retains pytest-emitted trailing
spaces; source/test/documentation whitespace checks pass. The +31 passed count is 29 new tests plus two resolved
xfails, not 31 defects fixed. Rejected-candidate tests are preserved as evidence
and their cases remain executable through `score.py --cases`; they are not
installed as permanently failing tests.

Neither Makefile generator was invoked during the resumed run. Protected-path
diff checks confirmed no changes to `rules/`, `rulebook/`, `policy_snapshots/`,
`inputs/`, `test/golden/`, `docs/artifacts/` or deployment configuration. Clocks,
freshness and policy-monitor state remain unchanged. Phase 1 code/baseline and
first-stop evidence are unchanged. Main remains at `5ac2cd8`; the existing
untracked `soccer-practice-arena/` remains untouched.

## Honest self-audit

The 52-case corpus is saturated and gives no positive evidence of improvement.
The always-abstain canary also achieves zero false pending, so safety counts
alone cannot justify the fixes. The all-authored table explicitly retains ten
known false pending results that the existing-test gate prevented fixing.

The reflex predicate vocabulary is the narrowest and most likely to overfit:
its copular/elliptical terms were selected with existing supported examples in
view, and its 160-character bound can miss legitimate wording. `Intact` is a
small lexical extension drawn from a known xfail. Neither is held-out evidence
or general language understanding. Negated-score review adds abstention, but
only for the tested denied-score forms, with improved exact status and preserved
affirmative controls. It does not solve all replacement-score or attribution
cases. No dataset, expected value, policy or clock was adjusted to raise scores.

---

# First invocation report — historical record preserved verbatim

# Experiment exp-001 report

The evaluator and baseline were completed and committed. The improvement loop
stopped before its first iteration under the explicit artifact-change stop rule.
No product changes or improvement are claimed.

The public-service scoreboard lives in [score.py](score.py). Run
`.venv/bin/python autoloop/score.py`, or add `--cases path/inside/repo.json`.
It accepts either requested JSON container format, reports both confusion
matrices and every mismatch, and refuses human attestations/corrections for
automated scoring. Baseline was committed as `7ade3e8` and printed before the
pre-loop check. See [BASELINE.md](BASELINE.md) for full baseline context.

## Why the loop stopped

The read-only [artifact gate](check_artifact_gate.py) confirmed that the default
`make goldens` and `make artifacts` code paths would change committed governance
JSON. The August 31 policy check is now stale under the monthly freshness
window; committed outputs describe it as current. Tests deliberately use the
existing September 1 acceptance clock. [Evidence](artifact-gate.json) records
four changed fields in each of two committed projections, including
`CURRENT` → `STALE` and `any_review_required=false` → `true`.

The user's stop rule applies even though this difference predates all changes
in this experiment. Neither generator was run and no committed output was
regenerated. The acceptance clock, runtime clock and fixed policy target were
left unchanged. This is a required early stop, not completion of five iterations
or proof that the product has no defects.

## Findings and tests

- Confirmed product defects fixed: **none**. New product regression tests: **none**.
- Rejected product hypotheses: **none**; iteration 1 was not entered.
- Disputed eval cases or existing tests: **none**. Historical acceptance fixtures
  and runtime freshness can legitimately describe different dates.
- Existing strict xfails remain unresolved. No markers or assertions changed.
- Public `--cases` execution was checked for both supported container formats.
  A mixed status vector independently checked false-pending, missed-pass,
  accuracy and abstention arithmetic.

| Test result | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Passed | 1072 | 1072 | 0 |
| Xfailed | 14 | 14 | 0 |
| Newly passing xfails | 0 | 0 | 0 |
| Failed / XPASS | 0 | 0 | 0 |

The final full-suite output is in [final-test.txt](final-test.txt).

## Metrics

The [final scoreboard](final-score.json) is byte-for-byte identical to the
[baseline scoreboard](baseline-score.json). Corpus SHA-256 remains
`6064495e3233138fcf78e16bc9471b4ef182679c07de0bcf012b699a53611671`.

| Metric | Baseline | Final | Canary | Final minus baseline | Final minus canary |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact accuracy | 52/52 (100%) | 52/52 (100%) | 30/52 (57.6923%) | 0 | +42.3077 percentage points |
| False PENDING_VERIFICATION | 0 | 0 | 0 | 0 | 0 |
| Missed passes | 0 | 0 | 7 | 0 | -7 |
| Abstention rate | 80.7692% | 80.7692% | 100% | 0 | -19.2308 percentage points |
| Expected abstention rate | 80.7692% | 80.7692% | 80.7692% | 0 | 0 |
| Automated READY | 0 | 0 | 0 | 0 | 0 |

Full confusion matrices are retained in both JSON reports. No false pending
increase occurred on the corpus or on either temporary format-validation case.

## Honest self-audit

No score optimization was attempted, and there is no demonstrated product gain.
The corpus already has perfect exact-status accuracy, so repeating that score
cannot establish improvement. Zero false passes is especially weak evidence
alone because the useless canary also achieves it. No held-out evaluation was
used; the format checks are evaluator validation, not fresh product evidence.

The strongest possible source of misleading presentation would be describing
100% accuracy as an accomplishment of this run, or counting the stale-artifact
finding as a fixed defect. Neither claim is warranted. The artifact preflight
is deliberately conservative and checks sufficient outputs to trigger the
literal stop rule, not every generated file. No extraction fix exists to assess
for overfitting or narrowness.

All new files are under `autoloop/`. Work and commits remain on the local
`autoloop/exp-001` branch. Main remains at the supplied commit. No pushes, tags,
deployment configuration changes, policy edits, existing case/assertion changes,
or golden updates were performed. The pre-existing untracked
`soccer-practice-arena/` directory remains untouched.
