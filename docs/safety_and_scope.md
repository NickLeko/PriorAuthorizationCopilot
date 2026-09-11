# Safety And Scope

## Product Boundary

Automated extraction is a drafting aid, not a decision gate. The engine applies
narrow versioned operators to proposed facts and requires human verification of
every requirement fact before READY. All-MET proposals without those attestations
return PENDING_VERIFICATION. v1.4.0 over-trusted extraction; known negation,
temporality and attribution failures remain in v1.5.0. Source spans now guarantee
exact original-note offsets/text, not semantic support. Self-reported verification
identity does not establish that a person actually checked the record.

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
- rewrite criterion outcomes; monitoring state can downgrade policy trust and make `submission_readiness=false`
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

## Archive And Replay Boundary

Every service result includes a sealed policy snapshot. CLI `evaluate --store` persists full synthetic requests, captured facts, verification records, and results in append-only SQLite. UI/API evaluations are not automatically archived. Triggers and hashes protect the supported local workflow, but do not provide authentication, encryption, retention controls, or resistance to a privileged rewrite.

Replay uses originally captured evidence and an explicit target version. Missing and ambiguous evidence keep their refusal semantics. A relaxed policy can resolve a correct old refusal using the same evidence; that is a reason to revisit history, not to overwrite it. All replay reports require fresh human review and have `submission_readiness=false`; passing criteria produce `PENDING_VERIFICATION`. See [policy replay](policy_replay.md).

## Human Review In A Real Workflow

In a real workflow, this kind of tool would sit before submission as an administrative quality gate.

Human reviewers would still own:

- chart review
- policy interpretation
- edge-case escalation
- final submission decisions

## Honest Disclaimer

This repo is a local deterministic demo, not a production healthcare deployment.
