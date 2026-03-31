# Product Brief
## Prior Authorization Readiness Copilot

## Current Repo

This repo implements a deterministic prior authorization readiness review for synthetic cases. It does not use an LLM.

## Product Question

Is this request administratively ready to submit as documented, and if not, which required elements are missing or below threshold?

## In Scope

- Deterministic extraction from note text
- Rules-first evaluation
- Explicit missingness handling
- Deterministic letter drafting downstream of evaluation
- Audit output
- Local demo UI

## Out of Scope

- Clinical decision support
- Approval prediction
- Autonomous submission or appeals
- Runtime policy interpretation
- Production deployment claims

## Decision Semantics

- `READY`: all required criteria are documented and met
- `NOT_READY`: all required criteria are documented, but one or more do not meet threshold
- `CANNOT_DETERMINE`: one or more required criteria are not documented

## Constraints

- Deterministic behavior only
- No LLM in the current repo
- Synthetic inputs only
- Human review required for any output use

## Current Proof

- Versioned rules in YAML
- Documented extraction behavior in [EXTRACTION_CONTRACT.md](/Users/nicholasleko/projects/PriorAuthorizationCopilot/EXTRACTION_CONTRACT.md)
- Pytest coverage for core behaviors
- Streamlit demo for inspection

## Possible Extensions

- More payer and procedure coverage
- Production integration layers
- Optional LLM-assisted text formatting behind separate contracts and tests
