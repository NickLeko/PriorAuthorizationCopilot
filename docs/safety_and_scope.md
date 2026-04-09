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

## Why Synthetic-Only Data

Synthetic-only inputs keep the repo:

- safe to share in interviews and portfolios
- easy to test repeatedly
- free from PHI handling claims
- honest about its current maturity

## Refusal-First Behavior

The most important safety behavior is explicit refusal when documentation is missing.

If any required item is not documented, the result must be `CANNOT_DETERMINE`.

That avoids:

- hidden inference
- false precision
- accidental overclaiming

## Drift Monitoring Boundary

Policy drift monitoring exists to support governance.

It does:

- snapshot configured sources
- normalize content
- detect changes
- flag review-required situations
- flag stale monitoring baselines when checks have aged past their configured cadence

It does not:

- rewrite rules
- change readiness outcomes automatically
- claim the monitored source is fully production-governed

## Rulebook Promotion Boundary

The rulebook registry exists to separate governance from runtime behavior.

It does:

- keep reviewed and active rule snapshots visible
- make release-to-release diffs inspectable
- require human promotion of runtime rule changes

It does not:

- auto-promote draft or reviewed rule snapshots
- auto-sync runtime rules from drift signals
- replace human policy review

## Human Review In A Real Workflow

In a real workflow, this kind of tool would sit before submission as an administrative quality gate.

Human reviewers would still own:

- chart review
- policy interpretation
- edge-case escalation
- final submission decisions

## Honest Disclaimer

This repo is an enterprise-shaped demo artifact, not a production healthcare deployment.
