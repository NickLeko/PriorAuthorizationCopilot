# Prior Authorization Readiness Copilot

This self-directed prototype demonstrates deterministic prior-authorization documentation review, human verification, and policy-change replay. It uses synthetic cases and narrow rules; it does not authorize care or predict payer approval.

## Three Design Decisions

### 1. Missing evidence, failed criteria, and ambiguity need different outcomes

A missing sleep-study date requires more documentation (`CANNOT_DETERMINE`). A captured duration below a rule's minimum fails that criterion (`NOT_READY`). Conflicting or unrecognized captured evidence requires interpretation (`NEEDS_REVIEW`). Combining them would hide what a reviewer needs to do next. Missing evidence takes precedence over ambiguity, which takes precedence over a failed criterion.

### 2. Plausible extraction and exact citations still require human verification

Automated extraction is a drafting aid, not a decision gate. Regex proposals can misread negation, resolved findings, or unrelated evidence even when their citations exactly match the original note. All passing operators therefore produce `PENDING_VERIFICATION` until every requirement fact is explicitly `HUMAN_VERIFIED`. Only then can the result become `READY`; policy trust independently controls submission readiness.

The trace is `source span → proposed fact → rule/operator → requirement result → human verification → overall status`. Reviewer identity is self-reported. See the [extraction and verification contract](EXTRACTION_CONTRACT.md) for executable examples of known errors and the [v1.5.0 release](docs/releases/v1.5.0.md) for why the gate changed while language extraction remained unchanged.

### 3. Policy changes require replay without rewriting history

Every service evaluation records an immutable policy snapshot with an identifier, effective date, and content hash. Here, “immutable” policy snapshots and rule releases mean content-hashed, version-fixed records, not enforced tamper resistance. For legacy runtime rules, the date is the local rule-update date, not a claimed payer effective date. The CLI can explicitly archive decisions in append-only SQLite and replay their captured evidence under another version. A report distinguishes outcome flips, newly undeterminable or review-required cases, unchanged outcomes with changed reasoning, resolved refusals, and unchanged cases.

A correctly refused case can become determinable when a new policy removes an evidence requirement. That is a reason to revisit an archive; it does not make the original refusal wrong. Replay never overwrites the original decision, invents missing evidence, or transfers human attestations. All-met replays remain `PENDING_VERIFICATION` and require fresh human review.

Read the [policy versioning and replay contract](docs/policy_replay.md), inspect the [synthetic replay summary](docs/artifacts/policy_replay_summary.json), or follow the [five-minute walkthrough](docs/demo_walkthrough.md). Its 14 hand-authored synthetic cases across three synthetic policy versions were constructed to exercise the differential categories; their counts demonstrate the mechanism, not the prevalence of real policy-change outcomes.

One `Aetna:MRI_LUMBAR` pathway demonstrates official-policy provenance for a limited CPB 0236 branch. Cervical MRI, knee MRI, CPAP, and the replay policy revisions remain synthetic demonstrations. This is a portfolio artifact, not a production payer integration or clinical decision system.

![Prior Authorization Readiness Copilot showing a CANNOT_DETERMINE result with explicit missing-documentation blockers](assets/readme/prior-auth-readiness-demo.png)

_Current app, captured September 11, 2026: synthetic CPAP case `CPAP-02-borderline`, with the 52-case regression suite and explicit missing-documentation refusal. These fixture checks do not estimate extraction accuracy on clinical notes._

## Read This First

This is a synthetic workflow-readiness demo, not a payer or clinical deployment.

- Bundled inputs are synthetic, and free-form input is intended for synthetic demo text; input text is not screened, so do not submit real patient information.
- Outputs are administrative readiness signals under narrow versioned rules. One lumbar-MRI pathway is mapped to an official Aetna policy; the remaining pathways are synthetic demonstrations.
- `READY` means every requirement's proposed fact is `HUMAN_VERIFIED` and every operator is `MET`. It is never an authorization or medical-necessity determination.
- `PENDING_VERIFICATION` means every operator is `MET`, but at least one fact is `UNVERIFIED`; submission readiness is always false. `MET` alone is a result over a proposed scalar, not proof of source support.
- `NOT_READY` means captured evidence is evaluable, but fails a configured operator (a minimum, allowed category, or required affirmation).
- `CANNOT_DETERMINE` means required documentation is missing or not explicit enough.
- `NEEDS_REVIEW` means documentation was found but at least one result was ambiguous, contradictory, or not safely evaluable; it is not an adjudicated threshold failure.
- `submission_readiness=true` additionally requires current verified policy provenance, a trusted active rulebook, and no unresolved drift. A documentation result may remain `READY` while submission readiness is false.
- No output means payer approval, denial prediction, medical necessity, clinical appropriateness, or medical advice.

## Quick Reviewer Path

From a fresh clone, enter the repo and run:

```bash
make install PYTHON=python3.12
make reviewer-demo
make acceptance
```

The `make reviewer-demo` target runs a deterministic local path through:

- service status and supported scope
- bundled synthetic demo cases
- one `PENDING_VERIFICATION` case: `MRI-01-complete`
- one documented threshold failure: `MRI-08-edge-below-threshold`
- one refusal-first missing-information case: `CPAP-02-borderline`
- one exported JSON artifact at `/tmp/pa-copilot-reviewer-demo.json`

The target does not run replay. Continue with the separate replay demonstration (the output directory must not already exist):

```bash
.venv/bin/python -m scripts.replay_demo --output-dir /tmp/pa-replay-run
```

This generates an archive and reports for 14 hand-authored synthetic cases across three synthetic policy versions, constructed to distinguish the differential categories, not estimate real-world prevalence. For a no-setup review, use the [five-minute walkthrough](docs/demo_walkthrough.md) and checked-in artifacts:

- [docs/artifacts/MRI-01-complete.json](docs/artifacts/MRI-01-complete.json)
- [docs/artifacts/MRI-08-edge-below-threshold.json](docs/artifacts/MRI-08-edge-below-threshold.json)
- [docs/artifacts/CPAP-02-borderline.json](docs/artifacts/CPAP-02-borderline.json)

For a guided review of inputs, evidence mapping, missing-information flags, output meaning, human review, governance, and enterprise gaps, start with [docs/reviewer_guide.md](docs/reviewer_guide.md).

## What This Repo Does

- proposes a narrow set of facts from demo note text using deterministic patterns
- evaluates those facts against versioned payer requirements
- returns requirement-level reasoning, blocker summaries, evidence mapping, and audit trace data
- exposes the same workflow through Streamlit, FastAPI, and a CLI
- monitors configured sources for drift without rewriting criteria; stale or invalid governance can lower policy trust and block submission readiness
- embeds policy snapshots in every service evaluation; explicitly archives and replays decisions through the CLI

## What This Repo Does Not Do

- no approval prediction
- no clinical decision support
- no claims adjudication
- no medical-necessity review
- no autonomous submission or outreach
- no real payer integrations
- no production or compliance claims

## How The Readiness Logic Works

At a high level:

1. A bundled synthetic or user-entered demo request enters through Streamlit, FastAPI, CLI, or artifact generation.
2. `engine/extract.py` deterministically proposes facts and captures source spans from note text; proposals can be wrong.
3. `rules/payer_rules.yaml` defines which facts are required for each supported payer/procedure pair.
4. `engine/evaluate.py` applies frozen status semantics:
   - any `NOT_DOCUMENTED` requirement forces `CANNOT_DETERMINE`
   - otherwise any `NEEDS_REVIEW` requirement forces `NEEDS_REVIEW`
   - otherwise any `NOT_MET` requirement forces `NOT_READY`
   - all `MET` requirements with any unverified fact return `PENDING_VERIFICATION`
   - only all `MET` requirements with all facts `HUMAN_VERIFIED` return `READY`
5. `engine/service.py` assembles blockers, proposed facts, evidence maps, provenance, warnings, a sealed policy snapshot, audit trace data, and standard output payloads.
6. `evaluate --store` appends the result to a local archive. `replay` evaluates captured facts against an explicit target snapshot and produces a separate report; ordinary UI/API evaluations are not automatically archived.

The engine records human attestations; it cannot prove a person reviewed the note. Reviewer identity is self-reported, with no authentication or tamper-resistant attestation store. A real workflow would still require policy interpretation, chart review, escalation handling, final submission decisions, PHI controls, auth, audit operations, and payer integration layers.

In Streamlit, inspect the original note and each proposal, enter your reviewer name, check the facts you actually verified, and select **Record human verification**. In FastAPI, repeat `POST /evaluate` with the same request and `fact_verifications` keyed by requirement. Each record contains `state: "HUMAN_VERIFIED"`, `reviewer`, timezone-aware `verified_at`, and the result's `verification_fingerprint` as `fingerprint`. In CLI, use `evaluate --request-file request.json --json`, or add `--verifications-file attestations.json` to a demo evaluation. Unverified is the default everywhere. Changed notes, request scope or rule bundles invalidate old attestations; verification cannot edit a proposed value or override a failed requirement. See [docs/api.md](docs/api.md) for the payload.

## Why Deterministic First

This problem is intentionally narrow. Deterministic logic is the right backbone because it is:

- explainable requirement by requirement
- explicit about rule operators and fail-closed status semantics
- auditable with stable evidence references
- safe to refuse when documentation is missing
- testable with synthetic fixtures and regression cases
- payer-qualified in rule identity and procedure-scoped in policy trust
- versioned through sealed policy snapshots and a file-based rulebook release convention with provenance and drift signals
- reproducible through adversarial extraction tests and generated artifacts

`CANNOT_DETERMINE` is a feature here, not a failure mode.

The bundled labeled fixture currently contains 52 synthetic cases. Its regression snapshot is 52/52 exact overall statuses, 0 false `READY` results among 52 expected non-`READY` cases, 12 `NEEDS_REVIEW` results (23.1%), and 42 combined `NEEDS_REVIEW`/`CANNOT_DETERMINE` abstentions (80.8%). Seven cases now await human verification. Zero automated READY is a structural consequence of the verification gate, not evidence of extraction accuracy. These figures describe only the checked-in fixture; they are not estimates of performance on clinical notes or external data.

## Current Supported Scope

| Payer | Procedure | Policy trust | Drift monitored |
| --- | --- | --- | --- |
| Aetna | `MRI_LUMBAR` | Verified for one CPB 0236 radiculopathy branch | Yes |
| Aetna | `MRI_CERVICAL` | Synthetic/demo | No |
| Aetna | `MRI_KNEE` | Synthetic/demo | No |
| Aetna | `CPAP_DEVICE` | Synthetic/demo | No |

`MRI_LUMBAR` implements only the persistent back pain with radiculopathy alternative in official [Aetna Clinical Policy Bulletin 0236](https://www.aetna.com/cpb/medical/data/200_299/0236.html), _Magnetic Resonance Imaging (MRI) and Computed Tomography (CT) of the Spine_. The source was last reviewed April 9, 2026 and accessed August 22, 2026. The implemented branch requires back pain with radiculopathy, objective motor/reflex findings in an explicit nerve-root distribution, at least six weeks of qualifying conservative therapy, and explicit lack of improvement. Other CPB 0236 indications are not modeled.

Footnote 1 identifies moderate activity, analgesics, NSAIDs/anti-inflammatory medication, and muscle relaxants as conservative-therapy modalities, but it does not explicitly say that every modality, a specific combination, or only one modality is required. The prototype interprets a documented qualifying modality as sufficient evidence of therapy type. For a duration and response to satisfy the implemented branch together, they must resolve to one unambiguous supported modality candidate; contrast clauses, conflicting candidates, and unsupported cross-modality linkage route to review. This is a bounded deterministic interpretation, not quoted Aetna policy language or general episode resolution.

The verified provenance chain is `official source → validated normalized snapshot/hash → requirement-to-clause mapping → structured rule → extracted evidence → deterministic evaluation`. Snapshot structure, source identity, stored content, recomputed hash, timestamps, freshness, and unresolved drift are checked before trust can remain verified. Invalid state downgrades only the affected payer/procedure to demo and forces `submission_readiness=false`; this is still local prototype governance, not production policy management.

Bundled inputs remain synthetic; free-form input is not screened and must not contain real patient information. Policy drift monitoring is governance-only and does not automatically update rules. The rulebook registry tracks reviewed and active snapshots separately from runtime drift monitoring.

## Architecture At A Glance

- `engine/extract.py`: deterministic extraction
- `engine/evaluate.py`: requirement evaluation and frozen status semantics
- `engine/letter_draft.py`: write-only administrative letter drafting
- `engine/service.py`: shared orchestration for UI, API, CLI, and artifacts
- `engine/policy_monitor.py`: governance-only drift detection and snapshot handling
- `engine/rulebook.py`: versioned rulebook validation and diffing
- `engine/policies.py`: canonical policy snapshots and captured-fact type compatibility
- `engine/decision_store.py`: append-only local SQLite archive
- `engine/replay.py`: non-destructive comparison using archived evidence
- `engine/acceptance.py`: golden-output normalization for acceptance checks
- `app.py`: Streamlit operator demo
- `api.py`: FastAPI surface
- `cli.py`: local demo and export workflows

More detail: [docs/architecture.md](docs/architecture.md)

## Local Setup

Python version used in this repo: `3.12.x` (`.python-version` pins `3.12.3`).

```bash
make install PYTHON=python3.12
make test
make lint
make acceptance
make smoke-ui
make verify
make run
```

If you prefer direct commands:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q test/test_acceptance_snapshots.py
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q test/test_streamlit_app.py
.venv/bin/python -m scripts.generate_artifacts
.venv/bin/python -m scripts.generate_golden_outputs
.venv/bin/python -m streamlit run app.py
```

## FastAPI

Run locally:

```bash
make api
```

Direct equivalent: `.venv/bin/python -m uvicorn api:app --reload`

Example calls:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/supported-procedures
curl http://127.0.0.1:8000/demo-cases
curl -X POST http://127.0.0.1:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "payer": "Aetna",
    "procedure_code": "MRI_LUMBAR",
    "dx_codes": ["M54.16"],
    "site_of_care": "outpatient",
    "specialty": "Orthopedics",
    "note_text": "Low back pain with right leg radiculopathy. NSAIDs for 8 weeks with minimal improvement. Objective motor exam in the right L5 distribution: ankle dorsiflexion strength 4/5."
  }'
```

Full API notes: [docs/api.md](docs/api.md)

## CLI

Evaluation and export commands below share the service used by the UI/API. Archiving, explicit policy selection, and replay are CLI capabilities; see [policy versioning and replay](docs/policy_replay.md) for commands. The archive is an opt-in local SQLite file containing full requests, proposed facts, verification records, policy snapshots, and results. It has no authenticated reviewer ledger, multi-user workflow, encryption, or production retention controls. SQLite triggers prevent supported updates/deletes/replacements, and hashes detect corruption; a privileged filesystem owner can rewrite the database and schema.

```bash
.venv/bin/python cli.py status
.venv/bin/python cli.py list-procedures
.venv/bin/python cli.py list-demo-cases
.venv/bin/python cli.py evaluate --demo-case MRI-01-complete
.venv/bin/python cli.py evaluate --demo-case MRI-CERV-01-ready
.venv/bin/python cli.py evaluate --demo-case MRI-KNEE-01-ready
.venv/bin/python cli.py evaluate --demo-case CPAP-02-borderline
.venv/bin/python cli.py export-report --demo-case CPAP-02-borderline --output /tmp/pa-copilot-reviewer-demo.json --with-letter --letter-type missing_info_request
.venv/bin/python cli.py drift-status
.venv/bin/python cli.py rulebook-status
.venv/bin/python cli.py rulebook-diff --from-release 2026-04-09-reviewed-v0.4 --to-release 2026-08-22-active-v1.0
```

## Demo Artifacts

Stable sample outputs are generated under [docs/artifacts](docs/artifacts).
Volatile run IDs, timestamps, letter hashes, and freshness ages are normalized so regeneration stays reviewable.
See [docs/artifacts/README.md](docs/artifacts/README.md) for how to inspect these artifacts.

- [MRI-01-complete.json](docs/artifacts/MRI-01-complete.json)
- [MRI-08-edge-below-threshold.json](docs/artifacts/MRI-08-edge-below-threshold.json)
- [MRI-CERV-01-ready.json](docs/artifacts/MRI-CERV-01-ready.json)
- [MRI-KNEE-01-ready.json](docs/artifacts/MRI-KNEE-01-ready.json)
- [CPAP-02-borderline.json](docs/artifacts/CPAP-02-borderline.json)
- [drift_status.json](docs/artifacts/drift_status.json)
- [drift_report.md](docs/artifacts/drift_report.md)
- [featured_demo_cases.json](docs/artifacts/featured_demo_cases.json)
- [rulebook_status.json](docs/artifacts/rulebook_status.json)
- [rulebook_diff_reviewed_vs_active.json](docs/artifacts/rulebook_diff_reviewed_vs_active.json)
- [rulebook_diff_reviewed_vs_active.md](docs/artifacts/rulebook_diff_reviewed_vs_active.md)
- [status.json](docs/artifacts/status.json)
- [safety_metrics.json](docs/artifacts/safety_metrics.json)
- [policy_replay_summary.json](docs/artifacts/policy_replay_summary.json): separate replay generator, 14 constructed synthetic cases across three synthetic policy versions; category counts demonstrate distinctions, not real-world prevalence

Regenerate ordinary evaluation and governance artifacts with (the replay summary is produced separately by `scripts.replay_demo`):

```bash
.venv/bin/python -m scripts.generate_artifacts
```

Regenerate golden acceptance snapshots with:

```bash
.venv/bin/python -m scripts.generate_golden_outputs
```

## Key Docs

- [docs/policy_replay.md](docs/policy_replay.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/api.md](docs/api.md)
- [docs/demo_walkthrough.md](docs/demo_walkthrough.md)
- [docs/reviewer_guide.md](docs/reviewer_guide.md)
- [docs/testing.md](docs/testing.md)
- [docs/safety_and_scope.md](docs/safety_and_scope.md)
- [EXTRACTION_CONTRACT.md](EXTRACTION_CONTRACT.md)
- [LETTER_DRAFTING_CONTRACT.md](LETTER_DRAFTING_CONTRACT.md)
- [MODEL_CARD.md](MODEL_CARD.md)
- [FAILURE_MODES.md](FAILURE_MODES.md)
- [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md)
- [WHY_THIS_EXISTS.md](WHY_THIS_EXISTS.md)
- [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)
- [LIMITATIONS.md](LIMITATIONS.md)
- [NEXT_STEPS.md](NEXT_STEPS.md)

## Repo Quality Gates

- deterministic-only evaluation path
- synthetic fixtures only
- pytest regression coverage
- acceptance snapshots for representative product outputs
- structured outputs shared across UI, API, CLI, and exported artifacts
- explicit unsupported-scope handling
- honest scope and safety language
