# Reviewer Guide

This guide is for healthcare AI product, operations, and technical reviewers who want to understand what this repo does, run a deterministic demo, and inspect the evidence trail.

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

The extractor returns both `facts` and an `evidence_map`. Evidence spans include character offsets and copied note text snippets. Fields remain missing when no supported affirmative or explicit-missingness pattern matches; this narrow regex behavior is not a general clinical-language or negation guarantee.

The extraction contract is documented in `EXTRACTION_CONTRACT.md`.

For the verified lumbar branch, CPB 0236 Footnote 1 identifies moderate activity, analgesics, NSAIDs/anti-inflammatory medication, and muscle relaxants. It does not explicitly require every modality or a particular combination. The prototype accepts a documented qualifying modality, selects the longest individually documented qualifying duration, and does not sum shorter sequential courses unless an overall duration is explicit. Lack of improvement is extracted and evaluated separately from duration.

## What Does It Flag As Missing Or Insufficient?

The rulebook in `rules/payer_rules.yaml` defines required fields and thresholds for the supported payer/procedure pairs.

Requirement statuses mean:

- `MET`: the required field was documented and met the configured-rule threshold.
- `NOT_MET`: the field was documented but failed a threshold, such as 5 weeks documented where 6 weeks are required.
- `NOT_DOCUMENTED`: the field was missing or not explicit enough for deterministic extraction.
- `NEEDS_REVIEW`: the field was documented, but its value could not be evaluated against the configured categories; this is not a threshold failure.

Overall statuses are frozen in `engine/evaluate.py`:

- any `NOT_DOCUMENTED` requirement forces `CANNOT_DETERMINE`
- otherwise any `NEEDS_REVIEW` requirement forces `NEEDS_REVIEW`
- otherwise any `NOT_MET` requirement forces `NOT_READY`
- only all `MET` requirements return `READY`

Concrete examples:

- `MRI-01-complete` -> `READY`
- `MRI-08-edge-below-threshold` -> `NOT_READY`
- `CPAP-02-borderline` -> `CANNOT_DETERMINE`

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

`READY` is only a configured-rule documentation status. Even on the verified lumbar pathway, it is not an authorization or medical-necessity decision.

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
- `docs/artifacts`: checked-in reviewer-facing outputs generated by `scripts/generate_artifacts`.

The audit trail stores note hash and evidence spans rather than claiming a production record system.

For the verified pathway, the inspectable chain is `official source → policy metadata/hash → requirement-to-clause mapping → structured rule → extracted evidence → deterministic evaluation`. Missing or stale baseline data, drift, URL/hash mismatch, or incomplete verification metadata downgrades only the affected payer/procedure to demo trust.

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
