# Prior Authorization Readiness Copilot

Deterministic prior authorization readiness review for synthetic demo cases.

This repo checks whether a request is administratively ready against versioned payer rules. It does not make clinical judgments, predict approval, assess medical necessity, or act autonomously.

## What This Repo Does

- extracts a narrow set of required facts from synthetic note text using deterministic rules
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

Synthetic inputs only. Policy drift monitoring is governance-only and does not automatically update rules. Procedure registry output now also surfaces category, rule family, rule source label, last rule update, and last reviewed metadata. A lightweight rulebook registry now tracks reviewed and active snapshots separately from runtime drift monitoring.

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
.venv/bin/python cli.py export-report --demo-case CPAP-02-borderline --output docs/artifacts/manual_export.json --with-letter
.venv/bin/python cli.py drift-status
.venv/bin/python cli.py rulebook-status
.venv/bin/python cli.py rulebook-diff --from-release 2026-04-09-reviewed-v0.4 --to-release 2026-04-09-active-v0.5
```

## Demo Artifacts

Stable sample outputs are generated under [docs/artifacts](docs/artifacts).
Volatile run IDs, timestamps, letter hashes, and freshness ages are normalized so regeneration stays reviewable.

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
