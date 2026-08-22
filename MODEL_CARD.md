# Model Card

Project: Prior Authorization Readiness Copilot  
Version: 1.3.1

Changelog: 1.3.1 — Distinguishes recognized normal and specific negative imaging findings from inconclusive or unrecognized findings, makes implicit legacy booleans conservative, and adds a compact evidence-to-decision UI trace. Version 1.3 introduced local-context extraction, explicit operators, fail-closed evaluation, qualified rule identity, stronger provenance checks, scoped drift gates, and explicit documentation metrics.

## Current Repo

- Deterministic administrative readiness review
- Deterministic write-only letter drafting
- No LLM implementation
- Verified provenance is limited to the supported Aetna CPB 0236 lumbar-radiculopathy branch; all other pathways remain synthetic/demo
- All bundled data is synthetic; input is not screened and must not contain real PHI, with screening remaining the operator's responsibility

## Intended Use

- Local demo and offline review of synthetic prior authorization cases
- Review of missing documentation versus documented threshold failures
- Inspection of audit artifacts and deterministic decision logic

## Out of Scope

- Clinical decision support
- Approval prediction
- Autonomous submission or appeals
- Runtime policy interpretation
- Production PHI workflows

## Inputs

- Payer
- Procedure code
- Diagnosis codes
- Site of care
- Specialty
- Free-form note text; unscreened and restricted to synthetic data by operator policy

## Outputs

- Requirement-level `MET`, `NOT_MET`, `NOT_DOCUMENTED`, and `NEEDS_REVIEW`
- Overall `READY`, `NOT_READY`, `CANNOT_DETERMINE`, or `NEEDS_REVIEW`
- Blocking issues
- Deterministic write-only letter draft
- Audit JSON

## Safety Boundaries

- Missing information stays missing
- Any `NOT_DOCUMENTED` result forces `CANNOT_DETERMINE`
- With no missing result, any `NEEDS_REVIEW` result forces the human-review disposition instead of a threshold failure
- Policy drift does not update rules automatically
- Drafting cannot override evaluated statuses

## Evaluation

The repo includes pytest coverage for extraction, evaluation, drafting, rule loading, and policy-monitor helpers. All bundled evaluation cases are synthetic.

## Known Limits

- Narrow rule coverage
- Regex-based extraction with limited phrase support
- `MRI_LUMBAR` is monitored for drift; `MRI_CERVICAL`, `MRI_KNEE`, and `CPAP_DEVICE` are supported in rules but not monitored for drift
- `MRI_LUMBAR` receives `verified` trust only for the implemented Aetna CPB 0236 radiculopathy branch while its scoped source hash and freshness checks remain valid; all other procedures remain `demo`
- CPB 0236 does not explicitly prescribe a required combination of its listed conservative-therapy modalities; the prototype accepts a qualifying documented modality and does not sum shorter sequential courses without explicit overall duration
- No production integration

## Possible Extensions

- Expand rule coverage with provenance updates and tests
- Add production integration layers outside this repo
- Evaluate optional LLM-assisted text formatting behind strict contracts if the scope ever changes
