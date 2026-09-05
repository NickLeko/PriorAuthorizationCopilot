# Reviewer Guide

This guide is for healthcare product, operations, and technical reviewers who want to understand what this repo does, run a deterministic demo, and inspect the evidence trail.

## One-Screen Summary

Prior Authorization Readiness Copilot is a local administrative prior-authorization readiness demo designed and demonstrated with bundled synthetic data.

It checks whether narrow documentation requirements are present and threshold-compliant for a small set of versioned rules. The Aetna `MRI_LUMBAR` path demonstrates one clause-level mapping to official [CPB 0236](https://www.aetna.com/cpb/medical/data/200_299/0236.html), _Magnetic Resonance Imaging (MRI) and Computed Tomography (CT) of the Spine_; the source was last reviewed April 9, 2026 and accessed August 22, 2026. Every other pathway remains synthetic/demo. It does not authorize care, predict approval or denial, determine medical necessity, provide medical advice, submit anything to a payer, or integrate with real payer systems. Free-form input text is not screened for PHI, so do not submit real patient information.

## Quick Reviewer Path

From a fresh clone, enter the repo and run:

```bash
make install PYTHON=python3.12
make reviewer-demo
make acceptance
```

What this runs:

- `make install PYTHON=python3.12`: creates `.venv` and installs pinned local dependencies.
- `make reviewer-demo`: prints repo status, lists demo cases, evaluates three representative cases, and exports one missing-information artifact to `/tmp/pa-copilot-reviewer-demo.json`.
- `make acceptance`: checks stable golden snapshots for representative evaluation and governance outputs.

For full local verification, run:

```bash
make verify
```

## What Input Does The Tool Inspect?

The evaluation input is a `PARequest` with:

- payer
- procedure code
- diagnosis codes
- site of care
- ordering specialty
- synthetic note text

The bundled examples live in `inputs/synthetic_cases.json`. The request schema lives in `engine/schemas.py`.

The bundled examples are synthetic, but free-form note text is not screened; do not submit real patient information. Core evaluation is fully offline and has no patient database or payer submission channel. The optional drift-monitoring feature performs live HTTP fetches against configured payer URLs.

## What Evidence Does It Map?

`engine/extract.py` maps only the supported fact fields needed by the current rulebook:

- conservative therapy duration in weeks
- CPB 0236 qualifying conservative-therapy duration and explicit non-response
- back pain with radiculopathy
- objective motor/reflex change in an explicit nerve-root distribution
- symptom duration in weeks
- neurologic red flags explicitly addressed
- prior imaging result category
- knee mechanical symptoms explicitly addressed
- OSA documentation
- sleep study date presence
- AHI/RDI value presence

The extractor returns both internal candidate-derived facts and an `evidence_map`. Evidence spans include character offsets and copied note text snippets. Fields remain missing when no supported affirmative or explicit-missingness pattern matches. Within the explicitly tested phrase families, ambiguous, contradictory, or uncertain candidates route to human review. This narrow regex behavior is not a general clinical-language, coreference, or negation guarantee. Public facts use `null` for review-required values; requirement statuses and evidence preserve the distinction.

The extraction contract is documented in `EXTRACTION_CONTRACT.md`.

For the verified lumbar branch, CPB 0236 Footnote 1 identifies moderate activity, analgesics, NSAIDs/anti-inflammatory medication, and muscle relaxants. It does not explicitly require every modality or a particular combination. The prototype accepts a documented qualifying modality only when duration and response resolve to one unambiguous supported modality candidate. Explicit contrast clauses, conflicting candidates, and unsupported cross-modality linkage require review; this is not a general treatment-episode model.

## What Does It Flag As Missing Or Insufficient?

The rulebook in `rules/payer_rules.yaml` defines required fields and thresholds for the supported payer/procedure pairs.

Requirement statuses mean:

- `MET`: the required field was documented and met the configured-rule threshold.
- `NOT_MET`: the field was documented but failed a threshold, such as 5 weeks documented where 6 weeks are required.
- `NOT_DOCUMENTED`: the field was missing or not explicit enough for deterministic extraction.
- `NEEDS_REVIEW`: the field was documented, but its value was ambiguous, contradictory, uncertain, or could not be evaluated safely; this is not a threshold failure.

Overall statuses are frozen in `engine/evaluate.py`:

- any `NOT_DOCUMENTED` requirement forces `CANNOT_DETERMINE`
- otherwise any `NEEDS_REVIEW` requirement forces `NEEDS_REVIEW`
- otherwise any `NOT_MET` requirement forces `NOT_READY`
- all `MET` requirements return `PENDING_VERIFICATION` until every fact is `HUMAN_VERIFIED`, then `READY`

Concrete examples:

- `MRI-01-complete` -> `PENDING_VERIFICATION`
- `MRI-08-edge-below-threshold` -> `NOT_READY`
- `CPAP-02-borderline` -> `CANNOT_DETERMINE`

The bundled labeled fixture currently reports 52/52 exact overall statuses, 0 false `READY` results among 52 expected non-`READY` cases, 12 `NEEDS_REVIEW` results (23.1%), and 42 combined abstentions (80.8%). These are fixture-scoped regression results, not estimates of behavior on external or real-world notes.

## What Does The Output Mean?

The output is an administrative readiness artifact for a synthetic demo case. Inspect:

- `overall_status`
- `submission_readiness`
- `results[]`
- `blockers`
- `facts`
- `evidence_map`
- `audit_trail`
- optional `letter`

Checked-in examples are in `docs/artifacts`:

- `docs/artifacts/MRI-01-complete.json`
- `docs/artifacts/MRI-08-edge-below-threshold.json`
- `docs/artifacts/CPAP-02-borderline.json`

`audit_trail` contains rule version, active rulebook release, note hash, facts extracted, evidence map, requirements checked, blockers, warnings, and invariant errors. Volatile values are normalized in checked-in artifacts so diffs stay reviewable.

## What Does The Output Not Mean?

The output does not mean:

- payer approval
- payer denial
- approval likelihood
- clinical appropriateness
- medical necessity
- diagnosis or treatment advice
- autonomous submission readiness for a real payer workflow
- production compliance readiness

`READY` requires every requirement fact HUMAN_VERIFIED as well as every operator MET. Without those attestations, all-MET proposals return PENDING_VERIFICATION. Even on the verified lumbar pathway, READY is not an authorization or medical-necessity decision. Reviewer identity is self-reported in this local demo.

`submission_readiness` is stricter: it can be true only when the documentation status is `READY` and the policy source, monitoring state, and active rulebook are verified and current. A demo or stale pathway can preserve `overall_status=READY` for inspectability while returning `submission_readiness=false`.

## Where Does Human Review Enter?

Human review remains required at every real-world boundary:

- before interpreting payer policy
- before trusting a monitored policy source after drift or staleness
- before changing, promoting, or deploying rules
- before using documentation in a real prior authorization submission
- before any production workflow involving PHI, payer connectivity, audit operations, auth, or user permissions

In this repo, human-review boundaries are visible in:

- `docs/safety_and_scope.md`
- `FAILURE_MODES.md`
- `rulebook/manifest.yaml`
- `engine/rulebook.py`
- `engine/policy_monitor.py`
- `docs/artifacts/rulebook_status.json`
- `docs/artifacts/drift_status.json`

## Where Do Refusal And Edge Cases Appear?

Refusal-first behavior appears as `CANNOT_DETERMINE`, not as a thrown exception.

Examples:

- `CPAP-02-borderline` is missing a specific sleep study date and numeric AHI/RDI value, so it returns `CANNOT_DETERMINE`.
- `MRI-KNEE-03-cannot-determine` is missing explicit mechanical symptom documentation, so it returns `CANNOT_DETERMINE`.

Documented-but-insufficient behavior appears as `NOT_READY`.

Example:

- `MRI-08-edge-below-threshold` documents symptom and therapy duration, but both are below threshold.

Letter drafting receives a dedicated structured input containing no raw note field: request metadata, requirement results, evidence snippets, hints, counts, and policy trust. Supplied result reasons are rendered as structured evaluation output and are not independently fact-checked; the draft applies an enumerated, case-insensitive phrase check plus configured dosing-pattern checks. Diagnosis-code sanitation is minimal: trim, uppercase, and removal of spaces and `%` only.

## What Makes The Behavior Deterministic Or Auditable?

Determinism and auditability are tied to concrete repo files:

- `engine/extract.py`: regex-based deterministic extraction, no LLM path.
- `engine/evaluate.py`: frozen readiness semantics.
- `rules/payer_rules.yaml`: versioned rule requirements.
- `rules/provenance.yaml`: curated provenance metadata.
- `rulebook/manifest.yaml`: reviewed and active rulebook snapshots.
- `engine/acceptance.py`: output normalization for stable golden snapshots.
- `test/golden`: representative expected evaluation and governance outputs.
- `test/test_acceptance_snapshots.py`: exact snapshot regression checks.
- `docs/artifacts`: checked-in outputs generated by `scripts/generate_artifacts`.

The audit trail stores note hash, original-note evidence spans and per-fact verification records. Span offsets and text are exact source slices, including Unicode; their presence does not prove semantic support. This is not a production record system.

For the verified pathway, the inspectable chain is `official source → validated normalized snapshot/hash → requirement-to-clause mapping → structured rule → extracted evidence → deterministic evaluation`. Malformed or self-inconsistent snapshots, malformed drift logs, materially future timestamps, missing or stale successful-check data, unresolved drift, URL/hash mismatch, or incomplete verification metadata downgrade only the affected payer/procedure to demo trust.

## What Would Be Needed Before A Real Enterprise Workflow?

This repo intentionally does not implement these pieces. Before becoming an enterprise workflow, it would need at least:

- real payer policy ingestion and review operations
- payer-specific policy governance and approval workflows
- PHI handling, security controls, retention policy, and access control
- human-in-the-loop review UX and escalation paths
- integration with EHR, document management, payer portals, or clearinghouses
- monitoring, incident response, audit log retention, and release management
- clinical, compliance, legal, and operational validation
- plan-specific benefit and coverage handling

Those are out of scope here. The current repo is meant to demonstrate a narrow, reviewable workflow-readiness core, not a deployed healthcare platform.
