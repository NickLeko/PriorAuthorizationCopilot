# MARATHON PASS PLAN

## Current Starting Point

The repo already has a solid deterministic backbone and shared product surface:

- deterministic extraction, evaluation, blocker detection, and letter drafting
- FastAPI, CLI, and Streamlit surfaces over a shared service layer
- typed schemas, central config, and structured logging
- synthetic demo cases, reproducible artifacts, and growing regression coverage
- provenance metadata and a governance-only drift surface
- three supported procedures:
  - `MRI_LUMBAR`
  - `MRI_CERVICAL`
  - `CPAP_DEVICE`

The repo does not need a redesign. The remaining gains are mostly product depth, governance clarity, and behavior lock-in.

## Chosen Work Items

### 1. Add one narrow non-spine deterministic pathway if it stays defensible

Target candidate:
- `MRI_KNEE`

Acceptance bar:
- no fuzzy medical-necessity logic
- no broad orthopedic abstraction
- one additional extractor field at most
- clear documented blocker and cannot-determine behavior
- synthetic fixtures, tests, artifacts, and docs all updated

Fallback:
- if the rule contract becomes vague, skip the new procedure and deepen scenario coverage for the existing three procedures instead

### 2. Introduce a lightweight versioned rulebook and promotion workflow

Planned shape:
- a small governance artifact for `draft`, `reviewed`, and `active`
- validation and diff utilities
- rulebook version metadata surfaced in outputs where useful
- explicit human-review promotion steps in docs

### 3. Deepen offline drift reporting instead of widening to weak new sources

Planned direction:
- richer source metadata and stale-review visibility
- markdown and JSON drift report artifacts
- comparison of monitored snapshots against active rule assumptions when practical

### 4. Add golden outputs and acceptance checks

Planned coverage:
- representative ready, not-ready, and cannot-determine cases
- rulebook and drift artifact integrity
- cheap deterministic acceptance command wired into local workflow

### 5. Tighten local ergonomics and recruiter-facing docs

Planned direction:
- one-command high-signal verify and acceptance flows
- refreshed docs tied to the new procedure, rulebook, and governance story
- sharper interview narrative for the v1, v2, v3 progression

## Skipped Or Deprioritized Work Items

- no LLM layer
- no database
- no auth
- no Docker or deployment stack
- no broad second wave of procedures unless the first new one is clearly rigorous
- no live payer scraping requirement
- no automatic rule promotion or rule mutation from drift monitoring
- no large UI redesign that mainly changes aesthetics without improving clarity

## Dependency Order

1. Confirm current repo state and add this plan and worklog section
2. Implement the non-spine procedure only if the rule contract survives review
3. Build the rulebook/promotion workflow around the updated rule set
4. Improve drift artifacts and governance reporting
5. Add golden outputs and acceptance-style tests
6. Tighten ergonomics, docs, and interview materials
7. Run Ruff, full tests, artifact generation, smoke checks, and a simplification pass

## Stop Criteria

Stop when one of these becomes true:

- the backlog above is substantially complete
- the next remaining work is mostly cosmetic or platform theater
- the next remaining work would widen claims faster than it improves rigor
- the repo reaches a point where additional changes add more explanation burden than credibility

## Decision Rules For The Marathon Pass

- Prefer one rigorous non-spine procedure over multiple shallow ones.
- Prefer governance depth over procedure count once product scope becomes harder to defend.
- Prefer offline, inspectable artifacts over network-dependent demos.
- Prefer regression lock-in over additional optional features.
- If an idea feels impressive but hard to explain in two minutes, skip it.
