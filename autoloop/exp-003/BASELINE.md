# exp-003 baseline

Base: main v2.4.0, `3413381`. Branch: `autoloop/exp-003`.
The scorer `autoloop/score.py` is reused unchanged through ReadinessService,
without attestations, corrections, clock changes, or generators.

| Metric | Baseline system | Always-CANNOT_DETERMINE canary |
|---|---:|---:|
| Corpus exact status | 52/52 | 30/52 |
| False PENDING_VERIFICATION | 0 | 0 |
| Missed passes | 0 | 7 |
| Abstention | 42/52 (80.7692%) | 52/52 (100%) |
| Expected abstention | 42/52 (80.7692%) | 42/52 (80.7692%) |
| Automated READY | 0 | 0 |

Corpus SHA-256: `6064495e3233138fcf78e16bc9471b4ef182679c07de0bcf012b699a53611671`.
Raw evidence: `evidence/baseline-corpus.json`, `evidence/baseline-tests.txt`.
Commands: `.venv/bin/python autoloop/score.py`; `make test`.
Baseline suite: **1202 passed, 10 xfailed in 35.76s**.

The saturated corpus cannot establish recall improvement; prospective paired
inputs will measure recall against this engine and the same canary.
All authored exp-003 cases and all 69 exp-002 cases will be scored every gate.
Exp-002 documents two inherited false passes on exp-001's historical expanded
set; these are not evidence of universal safety and are not relabeled here.

Placement preflight: `ReadinessService._bundle_snapshot` enumerates runtime
rules/provenance/policy_sources, the rulebook manifest, and explicitly referenced
release files. `engine/data/cpb0236_drugs_v1.json` is outside that list. The table
will not be added to governance inputs. Baseline bundle digest and normalized
governance projections are frozen separately for comparison after each change.
No existing golden/artifact will be rewritten; existing acceptance tests must pass.

Pre-existing untracked `soccer-practice-arena/` is left untouched.

Expanded 74-case baseline was replayed retrospectively from both original
modules at `3413381`, before service imports, with the unchanged scorer. It
scores 49/74 exact, misses all 11 positives, and has one false pending on a
new mixed class/drug challenge. The always-abstain canary is 49/74 with zero
false pending. See `evidence/baseline-audit.json`; this expanded replay does not
replace the prospective 67-case pre-fix evidence. The final revision must
remove that false pass as well as passing every new negative.
