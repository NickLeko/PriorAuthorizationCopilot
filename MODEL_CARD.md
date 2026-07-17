# Model Card

Project: Prior Authorization Readiness Copilot  
Version: 1.2

Changelog: 1.2 — Adds distinct human-review status semantics, enforces no-note letter inputs and dosing checks, unifies artifact metric keys, redacts checked-in notes, corrects lumbar-MRI provenance, aligns synthetic-input and checklist claims, and records the OSA/imaging extraction changes.

## Current Repo

- Deterministic administrative readiness review
- Deterministic write-only letter drafting
- No LLM implementation
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
- Runtime trust remains `demo` for supported procedures because provenance is still curated offline
- No production integration

## Possible Extensions

- Expand rule coverage with provenance updates and tests
- Add production integration layers outside this repo
- Evaluate optional LLM-assisted text formatting behind strict contracts if the scope ever changes
