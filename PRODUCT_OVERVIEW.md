# Product Overview

Prior Authorization Readiness Copilot is a deterministic internal-product demo for administrative prior auth readiness review.

## What It Does

- checks whether a request is administratively ready under narrow, versioned payer rules; bundled examples are synthetic
- extracts only a small supported fact set from note text
- returns requirement-level reasoning, blockers, evidence spans, and audit metadata
- exposes the same logic through Streamlit, FastAPI, CLI, exported artifacts, and acceptance snapshots

## What It Does Not Do

- no clinical judgment
- no medical-necessity review
- no approval prediction
- no autonomous action
- all bundled data is synthetic; input is not screened and must not contain real PHI, with screening remaining the operator's responsibility

## Current Scope

- payer: `Aetna`
- supported procedures:
  - `MRI_LUMBAR`
  - `MRI_CERVICAL`
  - `MRI_KNEE`
  - `CPAP_DEVICE`
- monitored policy source count: `1`
- verified policy pathway: `Aetna:MRI_LUMBAR`, limited to the supported CPB 0236 radiculopathy branch
- synthetic/demo pathways: `MRI_CERVICAL`, `MRI_KNEE`, and `CPAP_DEVICE`

## Why It Is Credible

- deterministic extraction and evaluation
- explicit rule operators and fail-closed empty/missing behavior
- evidence-to-fact-to-rule-to-result traceability
- explicit unsupported-scope handling
- refusal-first `CANNOT_DETERMINE` behavior
- payer-qualified rule identity, procedure-scoped trust, and immutable rule releases
- official-source provenance mapping and governance-only drift detection for the verified pathway
- golden output snapshots and regression tests

## Why It Is Intentionally Narrow

This repo is meant to be explainable by one person in an interview. It prioritizes rigor, auditability, and honest product boundaries over broad claims.
