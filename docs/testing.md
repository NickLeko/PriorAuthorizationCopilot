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

Two regression layers exist on purpose:

- the bundled labeled fixture suite checks exact expected overall statuses for every included case and reports fixture-scoped false-READY, exact-status, and abstention metrics; these are regression metrics, not estimates of real-world clinical-language performance
- acceptance snapshots lock representative exact outputs for evaluation and governance surfaces

Current bundled-fixture snapshot: 52 labeled synthetic cases; 52/52 exact overall statuses; 0 false `READY` results among 45 expected non-`READY` cases; 12 `NEEDS_REVIEW` results (23.1%); and 42 combined `NEEDS_REVIEW`/`CANNOT_DETERMINE` abstentions (80.8%).

## Commands

After setup, prefer the Make targets. They use `.venv/bin/python` when the local virtualenv exists:

```bash
make reviewer-demo
make verify
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

Regenerate stable artifacts:

```bash
.venv/bin/python -m scripts.generate_artifacts
```

Regenerate golden snapshots intentionally after a reviewed product change:

```bash
.venv/bin/python -m scripts.generate_golden_outputs
```

## What Is Covered

- extraction contracts and determinism
- rule loader validation
- provenance and policy trust behavior
- policy drift normalization and snapshot handling
- rulebook validation and release diffs
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

- ready cases
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

## What Is Not Tested

- real payer integrations
- browser automation
- authentication flows
- production deployment behavior

Those are out of scope for this repo.
