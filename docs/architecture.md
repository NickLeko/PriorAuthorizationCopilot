# Architecture

## System Shape

This repo is a compact deterministic application, not a platform.

The architecture is intentionally split into a small number of explainable layers:

1. data and rules
2. deterministic extraction
3. deterministic evaluation
4. shared orchestration
5. output surfaces
6. rulebook governance
7. governance-only drift monitoring

## Module Boundaries

### Domain and schemas

- `engine/schemas.py`
- typed request, result, blocker, audit, drift, and supported-procedure models

### Rule and provenance loading

- `engine/rules_loader.py`
- `engine/provenance.py`
- load versioned payer rules, procedure registry metadata, and provenance metadata

### Deterministic extraction

- `engine/extract.py`
- converts note text into a narrow set of structured facts plus evidence spans
- conservative by design: missing or unclear information stays missing

### Deterministic evaluation

- `engine/evaluate.py`
- evaluates extracted facts against requirement definitions
- preserves frozen semantics:
  - `READY`: all requirements met
  - `NOT_READY`: all requirements documented, but at least one fails threshold
  - `CANNOT_DETERMINE`: at least one required element is not documented

### Shared application service

- `engine/service.py`
- the main orchestration boundary
- validates scope
- normalizes request inputs
- calls extraction and evaluation
- computes blockers, metrics, audit trace, warnings, procedure registry metadata, and provenance summaries
- returns one standardized `EvaluationResult`

### Rendering and artifacts

- `engine/rendering.py`
- converts evaluation results into stable export payloads and CLI summaries

### Acceptance harness

- `engine/acceptance.py`
- normalizes stable product outputs into golden snapshots for regression protection

### Demo case registry

- `engine/demo_cases.py`
- loads reusable synthetic fixtures used by UI, CLI, tests, and artifact generation

### Rulebook governance

- `engine/rulebook.py`
- validates versioned rulebook snapshots
- diffs reviewed and active releases
- keeps promotion metadata separate from runtime drift monitoring

### Governance-only drift monitoring

- `engine/policy_monitor.py`
- snapshots monitored sources
- computes diffs and drift events
- never mutates rules automatically

### App surfaces

- `app.py`: Streamlit operator demo
- `api.py`: FastAPI endpoints
- `cli.py`: local demo and export commands

## Runtime Flow

1. A request enters through Streamlit, the API, CLI, or an artifact script.
2. `engine/service.py` validates scope and normalizes the request.
3. `engine/extract.py` deterministically extracts facts and evidence spans.
4. `engine/evaluate.py` applies rule requirements and returns requirement results.
5. `engine/service.py` assembles blockers, metrics, warnings, procedure metadata, provenance, rulebook metadata, and audit trace.
6. The surface renders or exports the same typed result.

## Why This Shape Was Chosen

- It keeps the deterministic core small and interview-explainable.
- It avoids pushing product logic into the Streamlit app.
- It gives the repo reusable API and CLI surfaces without introducing a database or service mesh.
- It supports stronger tests, stable exported artifacts, and a human-review governance story.

## What Was Intentionally Left Simple

- no database
- no auth
- no background workers
- no generic workflow engine
- no LLM orchestration layer

Those would make the repo look larger, not stronger.
