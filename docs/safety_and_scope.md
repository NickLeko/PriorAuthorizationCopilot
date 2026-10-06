# Safety And Scope

## Correction Limits

v2.0.0 permits typed reviewer corrections over retained original proposals. The limits below apply to every surface:

- Corrections are source-located: exact quotations and hashes establish location integrity, not semantic support. Human misreading of negation or borrowed qualifiers remains a risk; corrections do not establish clinical truth or coverage.
- Reviewer identity remains self-reported. The mechanism enforces self-reported timestamp ordering, not action separation, distinct reviewers, or proof of review. A single request with correction at T and attestation at T+1s can pass without backdating. Correction does not imply verification: all effective requirement facts must pass and be HUMAN_VERIFIED before READY.
- Corrected decisions are viewable, not replayable, including after RESTORE_ORIGINAL or restoration of an original value.
- Supporting dates attached to requirement facts are not checked for recency or ordering.
- SET_VALUE allows at most 3 evidence spans, each limited to 300 Python Unicode characters. Multiple spans are allowed within that count. Overlength spans are rejected, never truncated; letters retain the full exact quotation.
- Letters disclose reviewer-supplied facts and self-reported identities; audit comments do not enter letter reasoning. Structured exports retain original proposals and the full ordered correction list.

No authentication, multi-user workflow, broader procedure coverage, extraction changes, cross-policy correction replay, revision lineage, or correction metrics framework is added. Evaluation remains deterministic with no ontology, LLM or RAG in the decision path; outputs are administrative evaluations, never clinical truth or coverage decisions.

## Product Boundary

Automated extraction is a drafting aid, not a decision gate. The engine applies
narrow versioned operators to proposed facts and requires human verification of
every requirement fact before READY. All-MET proposals without those attestations
return PENDING_VERIFICATION. v1.4.0 over-trusted extraction; known negation,
temporality and attribution failures remain in v1.5.0. Source spans preserve exact original-note offsets/text.

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
