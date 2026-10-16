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
