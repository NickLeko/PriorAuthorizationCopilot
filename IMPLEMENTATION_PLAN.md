# IMPLEMENTATION PLAN

## Current State Summary

The repo already has a credible deterministic core:

- deterministic extraction in `engine/extract.py`
- deterministic requirement evaluation in `engine/evaluate.py`
- write-only administrative letter drafting in `engine/letter_draft.py`
- versioned payer rules in `rules/payer_rules.yaml`
- partial policy drift monitoring in `engine/policy_monitor.py`
- a Streamlit demo surface in `app.py`
- a small but solid pytest suite

The repo is compact, explainable, and honest about scope. That should be preserved.

## Biggest Weaknesses

1. `app.py` currently owns too much orchestration logic.
   - Evaluation assembly, audit construction, metrics, and UI presentation are tightly coupled.
   - That makes API and CLI additions harder than they need to be.

2. Typed contracts exist, but they are not broad enough.
   - Major internal objects such as extracted facts, evidence spans, audit summaries, and supported-procedure metadata are still mostly loose dictionaries.

3. There is no interview-friendly programmatic surface.
   - The repo has a strong Streamlit demo, but no lightweight API or CLI for clean demos, curl examples, or reusable artifact generation.

4. Error handling and unsupported-scope behavior are under-surfaced.
   - The core logic is narrow by design, but unsupported procedures, malformed requests, and partial inputs should fail more explicitly and consistently.

5. Docs are useful but fragmented.
   - The repo needs a recruiter-proof top-level narrative, architecture doc, API doc, demo walkthrough, safety/scope doc, and interview talking points.

6. Testing is good for the current core but not broad enough for a v2 artifact.
   - There is little protection yet for API, CLI, structured outputs, unsupported-scope handling, or reproducible demo artifacts.

## Highest-Leverage Improvements

1. Add a small shared application layer.
   - Create a reusable evaluation service that wraps deterministic extraction, rule lookup, scoring, audit trace creation, and output shaping.
   - This should become the single source of truth used by Streamlit, API, CLI, and artifact generation.

2. Expand typed models with Pydantic.
   - Add schemas for intake requests, supported procedures, evidence spans, blockers, audit traces, status metadata, drift summaries, and exportable reports.

3. Add central config and structured logging.
   - Keep it lightweight: one config module, one logger setup, explicit paths, and deterministic defaults.

4. Add a lightweight FastAPI layer.
   - Expose health, supported procedures, readiness evaluation, demo case listing, and drift status.
   - Keep the API honest: synthetic-only, deterministic, no persistence, no autonomous action.

5. Add a simple CLI.
   - Support listing procedures, listing demo cases, evaluating a demo case, exporting a report, validating synthetic input, and checking drift artifacts.

6. Upgrade the Streamlit demo without changing the product identity.
   - Keep the current strengths: blockers, evidence mapping, auditability, and refusal-first behavior.
   - Improve the flow, labels, operator framing, and scope/limitations presentation.

7. Strengthen reusable synthetic fixtures and artifacts.
   - Add clearer demo case helpers, stable sample outputs, and a reproducible artifact-generation script.

8. Expand tests and CI only where signal is high.
   - Add regression tests for the shared service layer, API, CLI, unsupported scope, artifact generation, and key deterministic outputs.

## What Will Not Be Changed

- The repo will remain deterministic-first.
- No LLM-first architecture will be introduced.
- The core readiness semantics will stay frozen:
  - `READY`
  - `NOT_READY`
  - `CANNOT_DETERMINE`
- The repo will remain synthetic-only.
- No real payer integrations, no EHR connectivity, no claims adjudication, no medical-necessity review, no approval prediction, and no autonomous action will be added.
- No database will be added.
- The existing extraction and evaluation logic will not be rewritten unless a concrete defect appears during refactoring.
- Policy drift monitoring will remain governance-only and will not auto-edit rules.

## Smallest Structural Change With Highest ROI

The smallest high-ROI structural change is:

1. introduce a shared, typed evaluation service
2. route Streamlit through that service
3. expose the same service through FastAPI and a CLI

That yields cleaner architecture, stronger testability, better docs, and a much stronger interview story without replacing the deterministic core.

## Planned Execution Order

1. Audit and baseline verification
2. Add worklog and implementation plan
3. Add shared models, config, logging, and evaluation orchestration
4. Refactor Streamlit to consume shared outputs instead of building them inline
5. Add FastAPI endpoints with typed request/response schemas
6. Add CLI commands for core demo workflows
7. Add reusable demo fixture helpers and artifact generation
8. Expand tests for service, API, CLI, unsupported scope, and artifacts
9. Overhaul docs and interview-facing materials
10. Tighten CI and local developer commands
11. Final verification pass, simplification pass, and worklog closeout

## Scope Discipline

If a candidate improvement starts forcing broad rewrites across the repo, the narrower fallback is:

- keep the deterministic engine intact
- add adapters around it
- document limitations honestly

That is the bar for every change in this overnight pass.
