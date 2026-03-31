# Design Rationale Notes

This file records design assumptions for the demo. It is not a record of live user research, deployment feedback, or stakeholder approval.

## Intended Reviewers

- Prior authorization coordinators
- Utilization management reviewers
- Compliance and audit reviewers
- Engineering interviewers evaluating scope discipline

## Design Decisions

### Refusal

Missing required documentation returns `CANNOT_DETERMINE` instead of a guessed answer.

### Evidence Spans

When extraction captures supporting text, the UI shows the span so a reviewer can inspect what the rule engine used.

### Policy Trust Signaling

Rules and provenance are shown explicitly so reviewers can tell whether a pathway is demo-only or tied to monitored policy sources.

### Write-Only Drafting

Letter drafting is downstream of evaluated results and cannot change statuses or add new facts.

## Current Repo Boundary

- Deterministic implementation
- No LLM implementation
- Synthetic inputs only
- No production claims

## Possible Extensions

- Structured user research
- Production workflow instrumentation
- Broader rule coverage and integration work outside this repo
