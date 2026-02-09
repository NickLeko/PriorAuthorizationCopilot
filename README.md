# Prior Authorization Readiness Copilot (Flagship)

## Overview
The Prior Authorization Readiness Copilot is an **administrative decision-support system** that evaluates whether a prior authorization (PA) request is **documentation-ready** according to payer-specific criteria.

It deterministically assesses documentation completeness and threshold compliance, explicitly surfaces missing information, and generates **write-only, payer-facing justification letters** grounded in captured evidence.

This system is intentionally **not predictive, not clinical, and not autonomous**.

> **Note:** In the current public demo (v1.1), letter drafting is **deterministic and template-based**.  
> An optional LLM-based drafting layer is architecturally supported but intentionally **not enabled** to preserve reproducibility, auditability, and safety.

---

## Design Philosophy
This project optimizes for **safety, auditability, and long-term maintainability** over automation or predictive performance.

Where uncertainty exists, the system explicitly **refuses to decide**.


---


## Failure Modes & Safety Guarantees
This system’s behavior is governed by explicit, test-backed safety contracts.

Key properties:
- refusal-first behavior when documentation is missing,
- frozen readiness invariants (`READY`, `NOT_READY`, `CANNOT_DETERMINE`),
- deterministic extraction with evidence spans,
- write-only letter drafting with prohibited-language constraints,
- policy drift detection with human review gating.

All known failure modes, mitigations, and residual risks are documented in:

➡️ **[`FAILURE_MODES.md`](./FAILURE_MODES.md)**

This file serves as the authoritative reference for system safety, governance, and change control.


---


## Problem
Prior authorization denials are most commonly caused by:
- missing or ambiguous documentation,
- misalignment with payer-specific administrative criteria,
- unclear justification language.

These failures are **administrative**, not clinical.

Most tools attempt to “optimize approval” using opaque models. This system instead prioritizes **determinism, explicit missingness handling, and failure transparency**.

---

## Solution
A **rules-first, deterministic pipeline** that:

1. Extracts structured facts from clinical notes using context-gated rules
2. Evaluates payer-defined requirements with explicit missingness handling
3. Enforces invariant-based readiness semantics
4. Optionally generates **write-only** justification letters grounded strictly in evaluated results and evidence snippets
5. Produces a complete audit trail suitable for review and governance

---

## Policy Drift & Post-Deploy Governance

Payer policies are external dependencies that change over time.  
Silent policy drift is one of the highest-risk failure modes in prior authorization automation.

This system explicitly treats payer policy as a **versioned, monitored input**, not a static assumption.

### Drift Detection (Deterministic)
- Official policy sources are snapshotted as normalized text
- Content hashes are computed and compared over time
- Any change produces:
  - a stored snapshot
  - a unified diff artifact
  - an append-only drift log entry

### Governance Guarantees
- **Rules are never auto-updated**
- **Policy meaning is never inferred**
- **LLMs are not used for policy interpretation**
- Drift detection **only triggers human review**

### UI Trust Gating
When policy drift is detected:
- the UI surfaces a **REVIEW_REQUIRED** state
- evaluation is gated behind explicit user acknowledgment
- outputs are marked as potentially stale

This ensures the system **fails loudly and safely** rather than silently producing outdated decisions.

Policy updates require:
- human review
- rule and test updates
- explicit recommitment of governance artifacts

---

## What This System Does
- Determines whether payer-required criteria are:
  - documented and met,
  - documented but not met,
  - or not documented
- Differentiates **missing documentation** from **documented failures**
- Refuses to determine readiness when documentation is incomplete
- Drafts payer-aligned administrative letters (submission, missing-info request, appeal templates)
- Preserves full human control and review at all times
- Emits an auditable, test-locked JSON record for every run

---

## What This System Does NOT Do
- Predict approval or denial likelihood
- Make clinical judgments or recommendations
- Infer undocumented facts
- Override payer policy
- Auto-submit, auto-appeal, or auto-escalate requests
- Use LLMs for extraction, evaluation, or decision-making
- Auto-update rules in response to policy changes

---

## Core Semantics Contract (Frozen)

These definitions are **invariants** enforced across:
- UI banners
- letter generation
- audit exports
- automated tests

### Requirement Result Status
- `MET`  
  Required element is explicitly documented **and meets** the payer threshold

- `NOT_MET`  
  Required element is documented but **does not meet** the threshold

- `NOT_DOCUMENTED`  
  Required element is **not present** in the note

### Overall Readiness Status
- `READY`  
  All required criteria are documented and met  
  `submission_readiness = true`

- `CANNOT_DETERMINE`  
  One or more required criteria are not documented  
  `submission_readiness = false`

- `NOT_READY`  
  All required criteria are documented, but one or more are not met  
  `submission_readiness = false`

### Invariant Rules
- Any `NOT_DOCUMENTED` ⇒ overall status **must** be `CANNOT_DETERMINE`
- Any `NOT_MET` (with no missing items) ⇒ overall status **must** be `NOT_READY`
- No blockers ⇒ overall status **must** be `READY`

Invariant violations are explicitly surfaced in the UI and audit trail.

---

## Letter Drafting (Write-only by Design)

The letter generator is a **pure formatting layer**.

### Inputs
- evaluated requirement results
- evidence snippets
- policy trust level

### Outputs
- payer-facing administrative letters
- machine-readable letter metadata

In v1.1, drafting is **deterministic and template-based**.

The drafting layer:
- cannot change requirement statuses
- cannot infer facts
- cannot predict approval
- cannot introduce new information

Policy trust level is explicitly surfaced:
- `demo` → illustrative rules disclaimer is injected
- `verified` → provenance-confirmed framing

---

## Audit & Governance
Every run produces a downloadable audit record containing:
- run metadata and timestamps
- short note hash (no raw PHI)
- payer, procedure, site, specialty
- rules version and policy trust level
- policy drift status at time of evaluation
- extracted facts
- evidence spans
- requirement results
- overall readiness status
- blocking issues
- invariant violations (if any)
- letter artifact metadata (hash + version, not raw text)

Policy snapshots and drift logs are treated as **first-class governance artifacts** and are committed for reproducibility.

See FAILURE_MODES.md for explicit failure taxonomy and mitigations.

This design supports:
- reproducibility
- reviewability
- governance
- regression testing

---

## Evaluation & Testing
- Synthetic test suite with realistic fake PHI
- Deterministic expected outcomes
- Explicit negative-path tests (e.g., `CANNOT_DETERMINE`)
- Invariant enforcement tests
- Letter safety tests (no clinical language, no approval claims)

Tests are treated as **behavioral contracts**, not examples.

---

## Architecture Summary

Clinical Note  
↓  
Deterministic Extraction (context-gated, span-based)  
↓  
Requirement Evaluation (rules-first)  
↓  
Invariant Enforcement  
↓  
Overall Readiness Status  
↓  
Optional Write-only Letter Drafting  
↓  
Audit Record + UI Presentation  
↓  
**Policy Drift Monitor (out-of-band governance)**

---

## Project Status
**Flagship project — feature-complete (v1.1).**

The system is intentionally frozen at this stage to preserve:
- clarity of scope,
- regulatory defensibility,
- and portfolio signal.

Future changes require explicit contract updates, governance review, and test coverage.
