# Autoloop baseline — exp-001

Starting commit: `5ac2cd8c110aec8c904a5e2577d5661fc970d1b1` (v2.2.0).
Branch: `autoloop/exp-001`; local commits only. No product code changes.

Commands:

```text
.venv/bin/python autoloop/score.py > autoloop/baseline-score.json
make test
1072 passed, 14 xfailed in 36.34s
```

Complete scoreboard output, including all per-case results and both full
confusion matrices: [baseline-score.json](baseline-score.json).
The scorer calls `ReadinessService.evaluate(PARequest.model_validate(...))`,
the same service path as `cli.py evaluate --request-file`. No extraction
internals, attestations, corrections, fixed governance clock, or case-ID branches
are used. `--cases` accepts either supported JSON container format; paths must
remain inside this repository to honor this experiment's access restriction.
Invalid cases fail the run instead of being dropped.

Input: `inputs/synthetic_cases.json`, 52 cases.
SHA-256: `6064495e3233138fcf78e16bc9471b4ef182679c07de0bcf012b699a53611671`.

| Metric | System | Always CANNOT_DETERMINE canary |
| --- | ---: | ---: |
| Exact-status correct | 52/52 (100%) | 30/52 (57.6923%) |
| False PENDING_VERIFICATION | 0 | 0 |
| Missed passes | 0 | 7 |
| Abstention | 42/52 (80.7692%) | 52/52 (100%) |
| Expected abstention | 42/52 (80.7692%) | 42/52 (80.7692%) |
| Automated READY | 0 | 0 |
| False READY | 0 | 0 |

Confusion matrices: expected rows, actual columns. R = READY,
P = PENDING_VERIFICATION, N = NOT_READY, C = CANNOT_DETERMINE,
V = NEEDS_REVIEW, U = UNKNOWN.

| System | R | P | N | C | V | U |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| R | 0 | 0 | 0 | 0 | 0 | 0 |
| P | 0 | 7 | 0 | 0 | 0 | 0 |
| N | 0 | 0 | 3 | 0 | 0 | 0 |
| C | 0 | 0 | 0 | 30 | 0 | 0 |
| V | 0 | 0 | 0 | 0 | 12 | 0 |
| U | 0 | 0 | 0 | 0 | 0 | 0 |

| Canary | R | P | N | C | V | U |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| R | 0 | 0 | 0 | 0 | 0 | 0 |
| P | 0 | 0 | 0 | 7 | 0 | 0 |
| N | 0 | 0 | 0 | 3 | 0 | 0 |
| C | 0 | 0 | 0 | 30 | 0 | 0 |
| V | 0 | 0 | 0 | 12 | 0 | 0 |
| U | 0 | 0 | 0 | 0 | 0 | 0 |

Evaluation caveats:

- Zero false passes alone proves no improvement: the canary also scores zero.
- The bundled corpus is already perfect on exact status. It cannot demonstrate
  additional improvement; fresh regressions and unchanged old expectations matter.
- `make test` pins governance freshness to the existing acceptance date
  (2026-09-01); the scoreboard uses the real service clock. Overall statuses
  match, but governance trust and artifact outputs can depend on freshness.
- Score arithmetic was independently checked with a four-case mixed vector:
  two false pending statuses, one missed pass, 25% exact accuracy, 50% abstention.
- Existing untracked `soccer-practice-arena/` is outside this experiment and left
  unchanged. No external files or external policy sources were inspected.
