# Prior Authorization Readiness Copilot

Prior authorization often fails before medical necessity is even evaluated: missing documentation, unclear payer requirements, policy variation, rule drift, and handoff gaps between provider and payer teams.

This project is a deterministic readiness workflow that checks prior-authorization documentation against versioned payer rules before submission. It returns `READY`, `NOT_READY`, or `CANNOT_DETERMINE`, with evidence mapping, audit artifacts, and explicit refusal behavior when required information is missing.

It is a self-directed prototype, not a production payer integration or clinical decision system. The goal is to show how prior-auth workflows can be made more reviewable, auditable, and implementation-aware.

![Prior Authorization Readiness Copilot showing a CANNOT_DETERMINE result with explicit missing-documentation blockers](assets/readme/prior-auth-readiness-demo.png)

_Synthetic CPAP demo case. The workflow refuses to infer a missing sleep-study date or AHI/RDI value and surfaces both documentation gaps for review._

The separate screenshot at `docs/images/prior-auth-copilot-demo.png` is a historical UI reference from rules version `0.2` with a `2026-02-05` review date; the current checked-in state is rules version `0.5` with `2026-04-09` provenance review dates.

## Read This First

This is a synthetic workflow-readiness demo, not a payer or clinical deployment.

- Bundled inputs are synthetic, and free-form input is intended for synthetic demo text; input text is not screened, so do not submit real patient information.
- Outputs are administrative readiness signals under narrow demo rules.
- `READY` means the required demo-rule documentation was found and met threshold.
- `NOT_READY` means required documentation was found but failed a threshold.
- `CANNOT_DETERMINE` means required documentation is missing or not explicit enough.
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
- one `READY` case: `MRI-01-complete`
- one documented threshold failure: `MRI-08-edge-below-threshold`
- one refusal-first missing-information case: `CPAP-02-borderline`
- one exported JSON artifact at `/tmp/pa-copilot-reviewer-demo.json`

Then inspect the checked-in sample artifacts:

- [docs/artifacts/MRI-01-complete.json](docs/artifacts/MRI-01-complete.json)
- [docs/artifacts/MRI-08-edge-below-threshold.json](docs/artifacts/MRI-08-edge-below-threshold.json)
- [docs/artifacts/CPAP-02-borderline.json](docs/artifacts/CPAP-02-borderline.json)

For a guided review of inputs, evidence mapping, missing-information flags, output meaning, human review, governance, and enterprise gaps, start with [docs/reviewer_guide.md](docs/reviewer_guide.md).

## What This Repo Does

- extracts a narrow set of required facts from demo note text using deterministic rules
- evaluates those facts against versioned payer requirements
- returns requirement-level reasoning, blocker summaries, evidence mapping, and audit trace data
- exposes the same workflow through Streamlit, FastAPI, and a CLI
- monitors configured policy sources for drift without auto-changing rules or outcomes

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
2. `engine/extract.py` deterministically extracts only supported facts and evidence spans from note text.
3. `rules/payer_rules.yaml` defines which facts are required for each supported payer/procedure pair.
4. `engine/evaluate.py` applies frozen status semantics:
   - any `NOT_DOCUMENTED` requirement forces `CANNOT_DETERMINE`
   - otherwise any `NOT_MET` requirement forces `NOT_READY`
   - only all `MET` requirements return `READY`
5. `engine/service.py` assembles blockers, facts, evidence maps, provenance, warnings, audit trace data, and standard output payloads.

Human review remains outside the automation boundary. A real workflow would still require policy interpretation, chart review, escalation handling, final submission decisions, PHI controls, auth, audit operations, and payer integration layers that are intentionally not implemented here.

## Why Deterministic First

This problem is intentionally narrow. For a recruiter-facing and interview-defensible artifact, deterministic logic is the right backbone because it is:

- explainable requirement by requirement
- auditable with stable evidence references
- safe to refuse when documentation is missing
- testable with synthetic fixtures and regression cases

`CANNOT_DETERMINE` is a feature here, not a failure mode.

## Current Supported Scope

| Payer | Procedure | Supported in rules | Drift monitored |
| --- | --- | --- | --- |
| Aetna | `MRI_LUMBAR` | Yes | Yes |
| Aetna | `MRI_CERVICAL` | Yes | No |
| Aetna | `MRI_KNEE` | Yes | No |
| Aetna | `CPAP_DEVICE` | Yes | No |

Bundled inputs are synthetic; free-form input is not screened and must not contain real patient information. Policy drift monitoring is governance-only and does not automatically update rules. Procedure registry output now also surfaces category, rule family, rule source label, last rule update, and last reviewed metadata. A lightweight rulebook registry now tracks reviewed and active snapshots separately from runtime drift monitoring.

## Architecture At A Glance

- `engine/extract.py`: deterministic extraction
- `engine/evaluate.py`: requirement evaluation and frozen status semantics
- `engine/letter_draft.py`: write-only administrative letter drafting
- `engine/service.py`: shared orchestration for UI, API, CLI, and artifacts
- `engine/policy_monitor.py`: governance-only drift detection and snapshot handling
- `engine/rulebook.py`: versioned rulebook validation and diffing
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
    "note_text": "Low back pain with right leg radiculopathy x 8 weeks. Completed PT for 8 weeks and NSAIDs with minimal improvement. Denies bowel/bladder incontinence. No saddle anesthesia. Prior imaging: lumbar xray inconclusive. Neuro exam: mild weakness dorsiflexion 4/5."
  }'
```

Full API notes: [docs/api.md](docs/api.md)

## CLI

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
.venv/bin/python cli.py rulebook-diff --from-release 2026-04-09-reviewed-v0.4 --to-release 2026-04-09-active-v0.5
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

Regenerate demo artifacts with:

```bash
.venv/bin/python -m scripts.generate_artifacts
```

Regenerate golden acceptance snapshots with:

```bash
.venv/bin/python -m scripts.generate_golden_outputs
```

## Key Docs

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
- [INTERVIEW_TALKING_POINTS.md](INTERVIEW_TALKING_POINTS.md)

## Repo Quality Gates

- deterministic-only evaluation path
- synthetic fixtures only
- pytest regression coverage
- acceptance snapshots for representative product outputs
- structured outputs shared across UI, API, CLI, and exported artifacts
- explicit unsupported-scope handling
- honest scope and safety language
