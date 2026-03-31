# Case Study
## Prior Authorization Readiness Copilot

## Summary

This repo demonstrates a narrow approach to prior authorization readiness review:

- deterministic extraction
- rules-first evaluation
- explicit refusal when documentation is missing
- deterministic write-only drafting
- auditability over automation

The current repo does not use an LLM.

## Problem Framing

The repo focuses on administrative readiness, not clinical appropriateness and not approval prediction.

## Design Choices

- Missing documentation stays missing
- `CANNOT_DETERMINE` is a first-class outcome
- Requirement logic is explicit and versioned
- Drafting is downstream of evaluated results
- Governance artifacts are part of the repo, not hidden elsewhere

## What The Repo Proves

- The overall status mapping is explicit and testable
- The extractor returns evidence spans when it captures supporting text
- Drafting stays within the evaluated result set
- Policy monitoring artifacts can be inspected without changing rules automatically

## Limits

- Synthetic cases only
- Limited payer and procedure coverage
- Regex-based extraction with narrow phrase support
- No production integration

## Possible Extensions

- Expand coverage with provenance updates and regression tests
- Add production integration layers outside this repo
- Evaluate optional LLM-assisted text formatting only if the scope changes and the contracts are updated
