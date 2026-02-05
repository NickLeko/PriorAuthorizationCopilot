# Prior Authorization Readiness Copilot (Flagship)

## Overview
Administrative decision-support system that evaluates PA readiness, identifies missing requirements,
and drafts payer-aligned justification letters.

## Problem
Prior authorizations fail due to incomplete documentation, unclear medical necessity language,
and payer-specific rules — not clinical quality.

## Solution
Rules-based readiness evaluation + (optional) drafting layer with full auditability.

## What This System Does
- Evaluates whether required payer criteria are documented and met
- Flags missing documentation vs documented-but-not-met thresholds
- Drafts editable payer-aligned letters
- Preserves clinician control + audit trail

## What This System Does NOT Do
- Predict approval/denial likelihood
- Provide medical advice
- Override payer policy
- Auto-submit or auto-escalate requests

---

## Semantics Contract (Locked)
These definitions are **invariants** used across:
- UI banners
- audit JSON exports
- test suite labels

### Requirement Result Status
- `MET` = required element is documented and meets threshold
- `NOT_MET` = documented but below threshold / wrong category
- `NOT_DOCUMENTED` = not found in note (missing)

### Overall Status
- `READY`  
  All required criteria are **documented and met**.  
  `submission_readiness = true`

- `CANNOT_DETERMINE`  
  One or more required criteria are **not documented**.  
  `submission_readiness = false`

- `NOT_READY`  
  All required criteria are documented, but one or more are **not met**.  
  `submission_readiness = false`

### Synthetic Test Labels
- `complete` => `READY`
- `incomplete` => `NOT_READY` or `CANNOT_DETERMINE`

`borderline` is intentionally not used unless explicitly reintroduced with a written rule.

---

## Architecture
Rules engine (deterministic) + optional write-only drafting layer.

## Evaluation
Synthetic cases, rule coverage, extraction robustness, invariant checks.

## Status
Flagship project — under active development.
