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
