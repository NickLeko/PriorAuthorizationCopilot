# Reviewer Guide

This guide is for healthcare AI product, operations, and technical reviewers who want to understand what this repo does, run a deterministic demo, and inspect the evidence trail.

## One-Screen Summary

Prior Authorization Readiness Copilot is a synthetic, local-only demo of administrative prior authorization readiness review.

It checks whether narrow documentation requirements are present and threshold-compliant for a small set of versioned demo rules. It does not authorize care, predict approval or denial, determine medical necessity, provide medical advice, submit anything to a payer, process PHI, or integrate with real payer systems.

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

Synthetic-only scope is intentional. There is no PHI handling path, patient database, payer submission channel, or external API dependency.

## What Evidence Does It Map?

`engine/extract.py` maps only the supported fact fields needed by the current rulebook:

- conservative therapy duration in weeks
- symptom duration in weeks
- neurologic red flags explicitly addressed
- prior imaging result category
- knee mechanical symptoms explicitly addressed
- OSA documentation
- sleep study date presence
- AHI/RDI value presence

The extractor returns both `facts` and an `evidence_map`. Evidence spans include character offsets and copied note text snippets. Missing information stays missing; the code does not infer undocumented facts.

The extraction contract is documented in `EXTRACTION_CONTRACT.md`.

## What Does It Flag As Missing Or Insufficient?

The rulebook in `rules/payer_rules.yaml` defines required fields and thresholds for the supported payer/procedure pairs.

Requirement statuses mean:

- `MET`: the required field was documented and met the demo-rule threshold.
- `NOT_MET`: the field was documented but failed a threshold, such as 5 weeks documented where 6 weeks are required.
- `NOT_DOCUMENTED`: the field was missing or not explicit enough for deterministic extraction.

Overall statuses are frozen in `engine/evaluate.py`:

- any `NOT_DOCUMENTED` requirement forces `CANNOT_DETERMINE`
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

`READY` is only a demo-rule documentation status. It is not an authorization decision.

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

Letter drafting has an additional safety boundary in `LETTER_DRAFTING_CONTRACT.md`: it can generate only from already evaluated results and evidence snippets, and it must block prohibited clinical or approval language.

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
