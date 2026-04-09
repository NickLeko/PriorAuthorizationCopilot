# Interview Talking Points

## 30-Second Summary

This repo is a deterministic prior authorization readiness copilot for synthetic demo cases. It checks administrative readiness against narrow, versioned payer rules, returns blocker-level reasoning and evidence mapping, exposes the same workflow through Streamlit, FastAPI, and a CLI, and now includes a lightweight rulebook and governance layer. It does not make clinical judgments, predict approval, or act autonomously.

## 2-Minute Walkthrough

1. A synthetic request enters through the UI, API, or CLI.
2. The shared service validates scope and normalizes the request.
3. Deterministic extraction pulls a narrow fact set and evidence spans from note text.
4. Deterministic evaluation applies versioned payer requirements and returns `READY`, `NOT_READY`, or `CANNOT_DETERMINE`.
5. The result includes blockers, requirement-level reasoning, extracted facts, audit metadata, and a deterministic administrative letter option.
6. Separate governance surfaces track policy drift and rulebook promotion without mutating runtime logic automatically.
7. The third pass added a non-spine knee MRI pathway, versioned rulebook snapshots, stale-source reporting, and golden acceptance checks.

## Why This Matters In Healthcare Admin Workflows

- many prior auth delays are administrative documentation failures, not deep clinical disagreements
- deterministic readiness checks can reduce preventable back-and-forth before submission
- refusal-first behavior is safer than pretending certainty when documentation is incomplete
- auditable outputs matter because reviewers need to know exactly why a request is blocked

## Why Deterministic Before LLM Here

- the supported scope is intentionally narrow
- requirement semantics matter more than broad language flexibility
- deterministic outputs are easier to test, explain, diff, and govern
- the repo is meant to show disciplined product framing, not prompt theater

## Safety And Governance Rationale

- synthetic-only inputs avoid PHI and production-readiness theater
- `CANNOT_DETERMINE` is an explicit safety feature
- unsupported scope is rejected instead of guessed through
- rulebook promotion is human-driven
- drift monitoring is governance-only and never auto-updates runtime rules

## What Changed Across The Three Passes

### v1

- pulled orchestration out of the Streamlit app
- added typed service, API, CLI, artifacts, and stronger docs

### v2

- added cervical MRI
- strengthened provenance metadata and registry surfaces
- added Streamlit sanity coverage and richer artifacts

### v3

- added a non-spine knee MRI pathway with one new extractor field
- introduced reviewed vs active rulebook snapshots and release diffs
- surfaced stale drift baselines and review reasons
- added golden acceptance snapshots for representative product outputs

## Limitations

- one payer only
- four supported procedures only
- pattern-based extraction only
- one monitored policy source only
- no persistence, auth, or deployment stack
- not production-ready for real healthcare operations

## Next Real Product Steps

- add a second monitored source only with a clean offline baseline
- expand procedure coverage only when a new pathway can stay equally deterministic
- tighten the human review workflow around rulebook promotion
- add structured intake adapters before adding any storage layer

## Tradeoffs Intentionally Made

- chose explainability over broad coverage
- chose one narrow non-spine pathway over a larger procedure list
- chose a lightweight rulebook over a full workflow platform
- chose acceptance snapshots over more speculative feature work
- chose to skip Docker, auth, and databases because they would add explanation burden faster than credibility

## Top 10 Talking Points

1. The repo solves administrative readiness, not approval prediction.
2. `CANNOT_DETERMINE` is a deliberate refusal mode, not a failure.
3. Deterministic logic was chosen because the supported scope is narrow and fully defensible.
4. The same workflow powers Streamlit, FastAPI, CLI, exported artifacts, and golden acceptance snapshots.
5. The third pass added a non-spine knee MRI pathway without turning the repo into a generic imaging engine.
6. Evidence spans and structured provenance make outputs auditable instead of opaque.
7. The rulebook shows reviewed vs active rule snapshots and release diffs without pretending to be a platform.
8. Drift monitoring exists, but it is governance-only and never auto-promotes rule changes.
9. Synthetic-only data keeps the repo safe to share and easy to test.
10. The architecture stays intentionally compact: no database, no auth, no LLM layer, no fake enterprise complexity.
