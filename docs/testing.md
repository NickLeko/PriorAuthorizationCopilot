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

- the bundled synthetic evaluation suite checks coarse `complete` versus `incomplete` fixture expectations
- acceptance snapshots lock representative exact outputs for evaluation and governance surfaces

## Commands

Run the full suite:

```bash
pytest -q
```

Run the acceptance snapshots only:

```bash
pytest -q test/test_acceptance_snapshots.py
```

Run the Streamlit sanity tests only:

```bash
pytest -q test/test_streamlit_app.py
```

Run lint:

```bash
ruff check .
```

Regenerate stable artifacts:

```bash
python3 -m scripts.generate_artifacts
```

Regenerate golden snapshots intentionally after a reviewed product change:

```bash
python3 -m scripts.generate_golden_outputs
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
- contradictory evidence precedence for red-flag extraction
- governance snapshot drift and rulebook integrity

That is more useful here than adding a large quantity of low-value tests.

## What Is Not Tested

- real payer integrations
- browser automation
- authentication flows
- production deployment behavior

Those are out of scope for this repo.
