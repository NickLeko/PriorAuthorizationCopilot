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
