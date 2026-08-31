# Safety And Scope

## Product Boundary

This repo determines whether a request appears administratively ready under narrow, versioned payer rules.

It does not:

- make clinical recommendations
- determine medical necessity
- predict approval
- recommend utilization management strategy
- submit requests autonomously
- contact payers or patients

## Why Bundled Synthetic Data

Bundled synthetic inputs keep the demonstrated workflow:

- safe to inspect and test without checked-in PHI
- easy to test repeatedly
- reviewable without including PHI in checked-in fixtures
- honest about its current maturity

Free-form input is not screened for PHI. Do not submit real patient information.

## Refusal-First Behavior

The most important safety behavior is explicit refusal when documentation is missing.

If any required item is not documented, the result must be `CANNOT_DETERMINE`.

That avoids:

- hidden inference
- false precision
- accidental overclaiming

Revision note, June 9, 2026:

The system is designed to prefer under-extraction and missingness, but that is not a guarantee that over-extraction can never occur. Negated therapy, future-planned therapy, and therapy-duration-to-symptom-duration leakage were identified as false-positive extraction edge cases and patched with deterministic context filters plus regression tests.

## Drift Monitoring Boundary

Policy drift monitoring exists to support governance.

It does:

- snapshot configured sources
- normalize content
- validate snapshot structure and recompute stored-content hashes
- detect changes
- flag review-required situations
- track successful checks separately from content snapshot time and flag stale monitoring state
- reject malformed drift-log state and preserve recorded drift as unresolved until governance state is explicitly reset

It does not:

- rewrite rules
- change readiness outcomes automatically
- claim the monitored source is fully production-governed

## Rulebook Promotion Boundary

The rulebook registry documents a promotion convention and keeps governance metadata separate from runtime behavior. Runtime rules are loaded from configurable file paths; the registry does not enforce human approval before those files change.

It does:

- keep reviewed and active rule snapshots visible
- make release-to-release diffs inspectable
- document the intended human-review and promotion convention

It does not:

- auto-promote draft or reviewed rule snapshots
- auto-sync runtime rules from drift signals
- replace human policy review
- enforce that a human approved the configured runtime files

## Human Review In A Real Workflow

In a real workflow, this kind of tool would sit before submission as an administrative quality gate.

Human reviewers would still own:

- chart review
- policy interpretation
- edge-case escalation
- final submission decisions

## Honest Disclaimer

This repo is a local deterministic demo, not a production healthcare deployment.
