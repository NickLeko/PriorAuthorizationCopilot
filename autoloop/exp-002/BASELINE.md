# exp-002 baseline

Start: v2.3.0, `67f1f3ccaf1ccdbd74b8c4b3a58620ae3c08209a`.
Local branch: `autoloop/exp-002`, cut from main. No product edits at baseline.
Reuse `autoloop/score.py` unchanged, through the public `ReadinessService` path;
no attestations or corrections. Clock behavior is unchanged.

Commands:

```text
.venv/bin/python autoloop/score.py
make test
1123 passed, 10 xfailed in 35.81s
```

Full results/confusion matrices: [baseline-corpus.json](evidence/baseline-corpus.json).
Full suite output: [baseline-tests.txt](evidence/baseline-tests.txt).

| Metric | System | Always CANNOT_DETERMINE canary |
| --- | ---: | ---: |
| Exact status | 52/52 (100%) | 30/52 (57.6923%) |
| False PENDING_VERIFICATION | 0 | 0 |
| Missed passes | 0 | 7 |
| Abstention | 42/52 (80.7692%) | 52/52 (100%) |
| Expected abstention | 42/52 (80.7692%) | 42/52 (80.7692%) |
| Automated READY | 0 | 0 |

Case SHA-256: `6064495e3233138fcf78e16bc9471b4ef182679c07de0bcf012b699a53611671`.
The saturated corpus cannot demonstrate recall improvement. New paired positive
and negative cases are the evidence; zero false passes alone is insufficient
because the canary also scores zero. Existing known failures in exp-001 remain
historical counterexamples, not a claim that all language is already safe.

Fixed target: CPB 0236 persistent back pain/radiculopathy with objective motor
or reflex change in a root distribution and no improvement after six weeks.
Footnote 1: moderate activity, analgesics, non-steroidal anti-inflammatory drugs,
muscle relaxants. Rules, policy snapshots, original cases/tests/assertions,
goldens/artifacts, clock state and monitoring state remain fixed. Neither
generator is to be run. Pre-existing untracked `soccer-practice-arena/` is left
untouched; no file access outside this repository is part of the experiment.
