# Testing

## Test Philosophy

This repo favors high-signal deterministic tests over broad but shallow coverage.

The most important things to protect are:

- frozen readiness semantics
- deterministic extraction behavior
- refusal-first behavior for missing documentation
- evidence mapping and auditability
- supported-scope boundaries
- API and CLI surfaces sharing the same core workflow

The main fixture/output regression layers are:

- the bundled labeled fixture suite checks exact expected overall statuses for every included case and reports fixture-scoped false-READY, exact-status, and abstention metrics; these are regression metrics, not estimates of real-world clinical-language performance
- acceptance snapshots lock representative exact outputs for evaluation and governance surfaces

`TestExtractionContractAlignment` is the executable specification for every numbered
extraction/verification guarantee and every published exact example. Known wrong
examples use strict xfails driven solely by contract JSON; resolved examples pass
normally. The negated-strength False expectation remains disputed: the engine
returns review rather than treating a denied score as an observed normal finding.
The suite also exercises Unicode citation integrity, reviewer metadata,
attestation binding, status precedence and governance gates.
Cross-surface tests compare identical Streamlit, API and CLI requests before and
after verification. A long-lived API test promotes a changed rule bundle without
restarting the service. The historical v1.5 migration retained its 287 earlier
cases with intentional status and snapshot expectation updates. Governance tests
explicitly attest facts before checking their independent submission gate, so
PENDING cannot mask those checks.

Current bundled-fixture snapshot: 52 labeled synthetic cases; 52/52 exact overall statuses; 0 false `READY` results among 52 expected non-`READY` cases; 12 `NEEDS_REVIEW` results (23.1%); and 42 combined `NEEDS_REVIEW`/`CANNOT_DETERMINE` abstentions (80.8%).

Archive and replay tests separately cover immutable policy content, append-only storage, corruption detection, type compatibility, each differential category, correct denominators, preserved refusals, resolved refusals, and fresh verification. See `test/test_policy_replay.py`. Its cases are separate from the main labeled fixture corpus.

## Pre-demo live policy check

Before a live demo, check the live source in two steps (use the project virtualenv):

1. Run `python -m engine.policy_monitor --check` (read-only). Confirm `status` is `OK` and `new_hash == old_hash`.
2. Only after that confirmation, run `python -m engine.policy_monitor --check --write` to record the successful check time.

If step 1 shows a hash change or does not confirm an unchanged `OK` result, do not write; treat it as human policy review. A detected change does not automatically update rules or restore trust.

## Commands

After setup, prefer the Make targets. They use `.venv/bin/python` when the local virtualenv exists:

```bash
make reviewer-demo
make test
make lint
make acceptance
make smoke-ui
```

Run the documentation and artifact-path regressions:

```bash
.venv/bin/python -m pytest -q test/test_reviewer_docs.py test/test_artifact_generation.py
```

Run the full suite:

```bash
.venv/bin/python -m pytest -q
```

Run the acceptance snapshots only:

```bash
.venv/bin/python -m pytest -q test/test_acceptance_snapshots.py
```

Run the Streamlit sanity tests only:

```bash
.venv/bin/python -m pytest -q test/test_streamlit_app.py
```

Run lint:

```bash
.venv/bin/python -m ruff check .
```

Freshness-dependent tests and historical acceptance fixtures use a shared UTC instant, `2026-09-01T00:00:00Z`. Runtime service checks retain the real clock. Boundary tests exercise the exact window, elapsed window, future timestamps, and combined governance errors separately.

Regenerate historical artifacts and golden snapshots intentionally after a reviewed product change, using the same clock as CI:

```bash
.venv/bin/python - <<'PY'
from engine.acceptance import ACCEPTANCE_GOVERNANCE_NOW
from scripts.generate_artifacts import main as artifacts
from scripts.generate_golden_outputs import main as goldens
clock = lambda: ACCEPTANCE_GOVERNANCE_NOW
artifacts(utc_now_provider=clock)
goldens(utc_now_provider=clock)
PY
```

Ordinary generator module commands use the real clock and describe current governance state; they are not a way to refresh a monitored source.

## Manual release step (owner)

CI tests the code, not the running deployment. After every release tag, the
hosting owner must complete these checks before calling the live release verified:

Every push to `main`, including docs-only pushes, requires an owner reboot:
this host updates files in place and reruns `app.py` without restarting the
process, which can leave engine modules from different loads alive together.

1. In the Streamlit Community Cloud **My apps** dashboard, inspect the app's
   repository/branch/entry-file label and deployment configuration. Confirm
   repository `NickLeko/PriorAuthorizationCopilot`, branch `main`, and main file
   `app.py` at the repository root. Check **Manage app** logs for the source
   revision; it must include the tagged main commit.
2. Redeploy from current `main` after every tag, then reboot the deployed app.
   A reboot alone is not evidence that the source revision changed. If the
   existing app does not fetch current main, use **Create app → Yup, I have an
   app** to deploy anew with the repository, branch and file above. Verify the
   new deployment before replacing the existing demo link. See the official
   [deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
   and [hosting controls and logs](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app).
3. Open a fresh browser session, acknowledge any displayed governance gate, and
   load `MRI-01-complete`. It must return `PENDING_VERIFICATION` without an
   exception. In **Audit and Export**, inspect **Raw evaluation payload** or
   download the JSON artifact. Its `engine_version` must match the release tag
   without the `v` prefix (for `v2.7.0`, expect `2.7.0`).
4. In a fresh session, load the same lumbar MRI case to establish request scope,
   replace its note with the exact synthetic note below, and run the review.
   Expect `NEEDS_REVIEW`, no exception, and **“but significant improvement in
   pain”** in the verification and original/effective correction citation
   context. Confirm this export's engine version also matches the tag. Record
   the deployed revision, exported version, both statuses and citation check;
   a version mismatch means the release is not yet verified.

```text
Low back pain with right leg radiculopathy. NSAIDs for 8 weeks with no improvement in sleep but significant improvement in pain. Ankle dorsiflexion strength 4/5 in the right L5 distribution.
```

## What Is Covered

- extraction contracts and determinism
- rule loader validation
- provenance and policy trust behavior
- policy drift normalization and snapshot handling
- rulebook validation and release diffs
- policy snapshots, append-only decision storage, and deterministic non-destructive replay
- letter drafting contracts
- shared service behavior
- API endpoints
- CLI workflows
- artifact generation
- reviewer quick path documentation and inspectable export behavior
- acceptance snapshots for representative evaluation and governance outputs
- Streamlit AppTest sanity coverage
- bundled synthetic regression cases

## Regression Cases

The bundled synthetic case set intentionally includes:

- all-MET proposal cases
- seven formerly automated READY cases now expect PENDING_VERIFICATION; a separate golden fixture covers fully human-verified READY
- documented-but-not-ready cases
- cannot-determine cases
- threshold edge cases
- unsupported or incomplete evidence patterns
- new procedure coverage for cervical MRI
- non-spine knee MRI coverage
- contradictory evidence abstention for relevant diagnosis, finding, and symptom facts
- adversarial subject, uncertainty, future-state, negation, and duration-anchoring cases
- explicit operator semantics and empty-requirement fail-closed behavior
- CPB 0236 modality, duration, and treatment-response cases, including contrast-clause linkage failures and tested order variants
- governance snapshot drift, structural validation, recomputed content hashes, future-time rejection, and successful-check freshness

That is more useful here than adding a large quantity of low-value tests.

Zero READY in the unverified fixture is now a structural property, not a measure
of extraction accuracy. NEEDS_REVIEW/CANNOT_DETERMINE abstention metrics retain
their prior definition; pending verification is counted separately.

## What Is Not Tested

- real payer integrations
- browser automation
- authentication flows
- production deployment behavior

Those are out of scope for this repo.


The v2.1 reproductions live in `test/test_v210_safety.py`. Run
`python -m scripts.benchmark_evaluation` on Python 3.12 for one cold and one warm
MRI evaluation with YAML-load and rulebook-computation counts. Full-suite elapsed
time comes from `python -m pytest -q`; timing is observational, not a pass/fail
threshold. The [release report](releases/v2.1.0.md) includes before/after results.


## Extraction regression coverage after the v2.1.3 migration check

The one-release v2.1.2 differential harness and frozen copies were retired in a
separate H1(a) commit after the intentional review-trigger change. Before
retirement, `python -m pytest -q -s test/test_v213_differential.py` compared
52 corpus cases, 20 independent regressions, 600 seeded generated notes and
24 denial-heavy generated notes: **696 compared, 0 differences**. The comparison
covered facts, states, exact spans, citation context, requirement results and
statuses. This migration check does not define future extraction behavior.

Keep the ordinary corpus, independent regressions and security tests as ongoing
coverage. `test/test_h1_review_triggers.py` checks selected same-sentence
persistence, copied-forward and template checkbox cues; hard-coded baseline
facts/spans for three unchanged controls; and three correct-value strict xfails
for next-line improvement, contralateral attribution and cross-sentence
copy-forward. The 20 independent note inputs remain unchanged; v2.3 corrects
only case 17's date labels and citation expectation with owner approval, and
case 18's intact-reflex assertions now pass. Resolved markers were removed. Run:

```bash
python -m pytest -q test/test_h1_review_triggers.py test/test_v210_independent.py test/test_v210_safety.py
```

H1(a)'s five F1 extraction timing probes use 19,999-character AHI, whitespace-heavy
NSAID, and repeated no/denies/without inputs. Python 3.13 medians of three warm
calls were each below 100 ms. These finite probes do not establish general
clinical-language correctness. All failure classes remain open; see
`EXTRACTION_CONTRACT.md` and `FAILURE_MODES.md` for the remaining risks.


## v2.6.0 release validation and open expectations

Fresh `make test`: **1461 passed, 10 xfailed**. `make lint` must pass as well.
The exp-004 suite contributes 1437 passing tests; 24 new executable contract
examples bring the release to 1461. The 67 existing contract examples, including
all four known-failure objects, remain unchanged from f1412a6; there are 91 total.
Only the two hardcoded version assertions change among existing test files.
Record schema stays 2.0.0. No extraction logic or data changes in release prep.

Four contract xfails remain: neither/nor, same-sentence borrowed dates, unrelated
headache therapy and the disputed negated-strength False label. The latter
returns NEEDS_REVIEW, not a normal observed score. Six others cover two
cross-sentence temporality checks, generic analgesic duration, next-line
improvement, contralateral attribution and a copy-forward header in another
sentence. The generic duration fact differs from the CPB-specific course facts.
Exp-004’s owner-authorized leading-verb contract correction already existed at
the release base; release prep changes no existing label or strict marker.

Use the unchanged public `autoloop/score.py` on corpus, unchanged owner dev,
all own cases and all exp-002/003 inputs. Expected final scores: 52/52, 27/27,
102/102, 64/69 and 74/74; zero false pending and zero automated READY throughout.
All 72 exp-004 negatives, 117 exp-002/003 negatives and 13 owner dev traps are
nonpassing. Own pairs include 30 positives, with 34 additional requirement-level
checks for missing versus review states and source citations. Development dev
improves 11→27/27; the original 68 own pairs improve retrospectively 33→68/68.
The final 34 source/performance pairs improve prospectively 19→34/34 with false
pending 13→0. Do not combine these into an invented common main baseline for
all 102 own cases. Canary exact is 9/27 dev, 51/102 own and 30/52 corpus; zero
false pending alone says nothing about positive recall.

The owner reports a separate 27-case never-visible held-out set with different
wording: 10→24/27 exact, zero false PENDING_VERIFICATION. A safety defect on a
prior held-out set—patient-reported/deferred exam treated as objective—was fixed
before release. No held-out cases were read, incorporated or rerun here; only
failure-class feedback was supplied for that repair. The visible dev file stays
committed unchanged as the owner dev check, not held-out data. Three held-out
exact-status misses remain. Earlier expanded exp-001 unsafe counterexamples and
all historical release measurements remain documented.

[engine/data/cpb0236_drugs_v1.json](../engine/data/cpb0236_drugs_v1.json) remains
owner-approved reviewed data for local use, with 26 unchanged entries. **ATC codes require human verification against WHO ATC before any external claim.**
Approval does not independently certify transcriptions or aliases.

The [generation command](releases/v2.6.0-generation-command.txt) captures all
actual writes at the shared acceptance instant 2026-09-01T00:00:00Z and restores
all outputs before stopping on any governance or non-version change. Only
engine/app version 2.5.0 → 2.6.0 is permitted; runtime clocks and monitor state
must not change. See [release notes](releases/v2.6.0.md),
[generation audit](releases/v2.6.0-generation-audit.md),
[scope audit](releases/v2.6.0-scope-audit.json) and
[documentation drift audit](releases/v2.6.0-doc-audit.md).


## v2.7.0 release-candidate validation

Fresh `make test`: **1681 passed, 9 xfailed**. `make lint` includes Ruff lint and
format checks. All 91 contract examples and their four known-failure objects
remain unchanged. The laterality module contains 219 passing cases, including
normal/abnormal notation parity, source-order, mirroring, exact citation and
stale-attestation regressions. The formerly xfailed explicit contralateral H1(a)
case is an ordinary passing test. No other expectation is relabeled.

The v2.6.0 section above records historical results. Current remaining xfails
cover four contract examples, two cross-sentence temporality cases, generic
analgesic duration, next-line response and cross-sentence copy-forward.

Use the [v2.7.0 generation command](releases/v2.7.0-generation-command.txt) with
`utc_now_provider=lambda: ACCEPTANCE_GOVERNANCE_NOW` at 2026-09-01T00:00:00Z.
The guard permits only engine/app metadata 2.6.0 → 2.7.0, restoring prior writes
and stopping on any other difference. `PA_RELEASE_STAGE=verify` requires every
regenerated output to be identical. Live source requests are prohibited by this
command. This is local snapshot/provenance consistency, not a current remote
policy check or deployment verification. No monitoring timestamp is refreshed.
See the [release notes](releases/v2.7.0.md) and audit evidence linked there.
