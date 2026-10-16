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
Python source/test files. The +31 passed count is 29 new tests plus two resolved
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
