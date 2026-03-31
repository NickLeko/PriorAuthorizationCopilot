# Model Card

Project: Prior Authorization Readiness Copilot  
Version: 1.1

## Current Repo

- Deterministic administrative readiness review
- Deterministic write-only letter drafting
- No LLM implementation
- Synthetic inputs only

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
- Synthetic note text

## Outputs

- Requirement-level `MET`, `NOT_MET`, and `NOT_DOCUMENTED`
- Overall `READY`, `NOT_READY`, or `CANNOT_DETERMINE`
- Blocking issues
- Deterministic write-only letter draft
- Audit JSON

## Safety Boundaries

- Missing information stays missing
- Any `NOT_DOCUMENTED` result forces `CANNOT_DETERMINE`
- Policy drift does not update rules automatically
- Drafting cannot override evaluated statuses

## Evaluation

The repo includes pytest coverage for extraction, evaluation, drafting, rule loading, and policy-monitor helpers. All bundled evaluation cases are synthetic.

## Known Limits

- Narrow rule coverage
- Regex-based extraction with limited phrase support
- `MRI_LUMBAR` is monitored for drift; `CPAP_DEVICE` is supported in rules but not monitored for drift
- Runtime trust remains `demo` for both procedures because provenance is still curated offline
- No production integration

## Possible Extensions

- Expand rule coverage with provenance updates and tests
- Add production integration layers outside this repo
- Evaluate optional LLM-assisted text formatting behind strict contracts if the scope ever changes
