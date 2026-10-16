# exp-004 baseline

Main v2.5.0: 89a1500e1f3a0888e977ab0dde7cbfd21a26e8c7.
Required first commit: 25b10cb, only the byte-identical owner dev file.
Dev SHA-256: 4832267bc1ff0ac8f57aac1dd36961ef62ea4d3f15d9286662866a0981685389.

The unchanged autoloop/score.py evaluates the public ReadinessService without
attestations/corrections. No runtime clock or governance state is changed.

| Dataset | System exact | False pending | Always-abstain canary exact |
|---|---:|---:|---:|
| Corpus | 52/52 | 0 | 30/52 |
| Owner dev | 11/27 | 0 | 9/27 |
| All exp-002 authored (including rejected) | 64/69 | 0 | 41/69 |
| All exp-003 authored | 74/74 | 0 | 49/74 |

Dev has 14 passing labels and 13 traps. Baseline misses 12 passing cases;
two already pass (duration-first drug and abbreviated RDI). Exact requirement
mismatches are captured separately, including missing facts on nonpassing traps.
Baseline suite: 1301 passed, 10 xfailed in 36.81s.
Raw metrics/confusion matrices/governance: evidence/baseline.json.
Raw suite: evidence/baseline-tests.txt. No generators run.

Existing historical exp-001 failures remain documented in earlier reports;
this experiment does not claim universal safety. Gates include the corpus,
immutable owner dev check, all exp-002/003 cases, and every new authored pair.
