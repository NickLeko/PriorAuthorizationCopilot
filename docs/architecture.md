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
8. immutable policy snapshots, opt-in decision archive, and replay

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
- proposes a narrow set of structured facts plus original-note evidence spans
- unrecognized evidence can remain missing or require review; known false proposals remain, so exact spans do not establish semantic support

### Deterministic evaluation

- `engine/evaluate.py`
- evaluates extracted facts against explicit `documented`, `equals_true`, `minimum`, and `one_of` requirement operators
- preserves frozen semantics:
  - `READY`: all requirements met and all facts HUMAN_VERIFIED
  - `PENDING_VERIFICATION`: all requirements met, with at least one unverified fact
  - `NOT_READY`: all requirements captured and evaluable, but at least one fails its configured operator
  - `CANNOT_DETERMINE`: at least one required element is not documented
  - `NEEDS_REVIEW`: no required element is missing, but at least one documented result is ambiguous, contradictory, uncertain, or cannot be safely evaluated

### Shared application service

- `engine/service.py`
- the main orchestration boundary
- validates scope
- normalizes request inputs
- calls extraction and evaluation
- computes blockers, metrics, audit trace, warnings, procedure registry metadata, and provenance summaries
- returns one standardized `EvaluationResult`

### Policy snapshots, archive, and replay

- `engine/policies.py`: seals dated policy identities and canonical criteria with a content hash; routes incompatible captured scalar types to NEEDS_REVIEW before explicit-policy evaluation/replay
- `engine/decision_store.py`: local SQLite policies/decisions tables, append-only triggers, and read-time hash validation
- `engine/replay.py`: invokes the existing evaluator on captured facts and an explicit target snapshot; produces criterion differences and category counts without modifying history
- recording is opt-in through CLI `evaluate --store`; ordinary UI/API evaluations include snapshots but do not create an archive
- replay never re-extracts notes or transfers attestations; missing and ambiguous evidence retain refusal semantics, while relaxed requirements can resolve old refusals for fresh human review
- this is not an authenticated ledger, encrypted patient record system, multi-user workflow, or production retention service; hashes do not resist a privileged rewrite

See [the replay contract](policy_replay.md) for identifiers, effective dates, category definitions, and archive limits.

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
- validates file-based rulebook snapshots retained by convention; the filesystem does not enforce release immutability
- diffs reviewed and active releases
- keys procedure identity by payer and procedure code
- keeps promotion metadata separate from runtime drift monitoring

### Governance-only drift monitoring

- `engine/policy_monitor.py`
- snapshots monitored sources
- computes diffs and drift events
- never mutates rules automatically

For the one verified pathway, provenance remains inspectable as `official source → policy metadata/hash → requirement-to-clause mapping → structured rule → extracted evidence → deterministic evaluation`. Trust and drift gates are scoped to the affected payer/procedure. `submission_readiness` can be true only when documentation resolves to `READY` and policy/rulebook trust is verified and current.

### App surfaces

- `app.py`: Streamlit operator demo
- `api.py`: FastAPI endpoints
- `cli.py`: local evaluation/export, policy registration, append-only archiving, and replay commands

## Runtime Flow

1. A request enters through Streamlit, the API, CLI, or an artifact script.
2. `engine/service.py` validates scope and normalizes the request.
3. `engine/extract.py` deterministically proposes facts and captures original-note evidence spans.
4. `engine/evaluate.py` applies rule requirements and returns requirement results.
5. `engine/service.py` validates any per-fact human attestations against proposal fingerprints, applies the verification gate, and assembles blockers, metrics, warnings, provenance and audit trace. Runtime rule bundles are reread for each evaluation; changed inputs invalidate old attestations.
6. The service embeds the selected policy snapshot in the result and audit trace; the surface renders or exports that typed result.
7. CLI `evaluate --store` explicitly archives it. Replay is a separate path from archive to evaluator to report, using the archived capture states and target policy rather than current extraction/runtime rules.

## Why This Shape Was Chosen

- It keeps the deterministic core small and explainable requirement by requirement.
- It avoids pushing product logic into the Streamlit app.
- It gives the repo reusable API and CLI surfaces plus a small opt-in SQLite archive, without adding a service mesh or hosted database.
- It supports stronger tests, stable exported artifacts, and a human-review governance story.

## What Was Intentionally Left Simple

- a local SQLite archive, with no hosted database, case-management service, or automatic UI/API persistence
- no auth
- no background workers
- no generic workflow engine
- no LLM orchestration layer

The existing archive is sufficient to demonstrate versioned history and replay within the local deterministic scope.
