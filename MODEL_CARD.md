# Model Card — Prior Authorization Readiness Copilot

**Version:** 1.1  
**Last Updated:** February 2026  
**Author:** Nicholas Leko  
**Status:** Feature-complete (Frozen)  
**License:** MIT  

---

## 1. System Overview

The Prior Authorization Readiness Copilot is a **deterministic administrative decision-support system** designed to assess whether a prior authorization (PA) request is **documentation-ready** for submission according to payer-specific criteria.

The system:
- evaluates documentation completeness and threshold compliance,
- explicitly distinguishes missing information from documented failures,
- refuses to determine readiness when required information is absent,
- optionally generates **write-only administrative justification letters** grounded in evaluated results.

In the current public release (v1.1), all evaluation and drafting behavior is **fully deterministic**.  
An optional LLM-based drafting layer is **architecturally supported but intentionally disabled** to preserve reproducibility, auditability, and safety.

This system is **not predictive**, **not clinical**, and **not autonomous**.

---

## 2. Intended Use

### Intended Users
- Prior authorization coordinators
- Utilization management teams
- Revenue cycle operations staff
- Clinicians (review-only)

### Intended Use Cases
- Pre-submission administrative readiness review
- Identification of missing or insufficient documentation
- Preparation of payer-aligned administrative justification letters
- Audit and governance review of PA preparation logic

The system is intended for **offline evaluation, demonstration, or shadow-mode use**.  
It is not intended for unsupervised or production-autonomous operation.

---

## 3. Explicit Non-Uses (Out of Scope)

The system must **not** be used to:
- Predict approval or denial likelihood
- Make medical necessity determinations
- Provide clinical advice or recommendations
- Override, reinterpret, or negotiate payer policy
- Automatically submit, escalate, or appeal requests
- Optimize approval rates or payer outcomes
- Auto-update rules in response to policy changes

Any use outside these bounds is unsupported and unsafe.

---

## 4. System Architecture & Components

### Deterministic Core
- Context-gated, rules-based extraction of documentation signals
- Payer-specific requirement evaluation
- Explicit missingness handling
- Invariant-based readiness determination

### Write-only Drafting Layer
- Generates administrative justification letters
- Inputs:
  - evaluated requirement results
  - evidence snippets
  - policy trust level
- Outputs:
  - editable letter text
  - machine-readable letter metadata
- Deterministic in v1.1
- Cannot alter facts, statuses, or readiness outcomes

### Human Oversight
- All outputs require human review
- No autonomous action or state mutation
- Refusal (`CANNOT_DETERMINE`) is a first-class outcome

---

## 5. Policy Drift & Model Validity

Payer policy is an **external dependency** that may change independently of system code or rules.

Silent policy drift represents a critical model validity risk in administrative automation.

### Drift Detection
- Official policy sources are snapshotted as normalized text
- Content hashes are computed and compared over time
- Detected changes produce:
  - a new snapshot artifact
  - a unified diff
  - an append-only drift log entry

### Governance Constraints
- Rules are **never auto-updated**
- Policy meaning is **never inferred**
- LLMs are **not used** for policy interpretation
- Drift detection **only triggers human review**

### Runtime Impact
When policy drift is detected:
- the UI surfaces a **REVIEW_REQUIRED** status
- evaluations are gated behind explicit user acknowledgment
- outputs are marked as potentially stale

Model validity is therefore **conditional on confirmed policy alignment**.

---

## 6. Inputs & Outputs (Actual)

### Inputs
- Payer identifier
- Procedure code
- Diagnosis codes (sanitized)
- Site of care
- Ordering specialty
- Clinical note text (synthetic or de-identified)

> Note: Payer policy documents are **not parsed or interpreted at runtime**.  
> Rules are curated offline, versioned, and explicitly governed.

### Outputs
- Requirement-level results:
  - `MET`
  - `NOT_MET`
  - `NOT_DOCUMENTED`
- Overall readiness status:
  - `READY`
  - `NOT_READY`
  - `CANNOT_DETERMINE`
- Blocking issue checklist
- Optional write-only justification letter
- Audit JSON with evidence spans, invariants, and policy trust metadata

---

## 7. Decision Logic & Invariants

### Requirement Status Semantics
- `MET`: documented and meets payer threshold
- `NOT_MET`: documented but does not meet threshold
- `NOT_DOCUMENTED`: required element missing

### Overall Readiness Mapping (Frozen)
- Any `NOT_DOCUMENTED` ⇒ `CANNOT_DETERMINE`
- Any `NOT_MET` (with no missing items) ⇒ `NOT_READY`
- No blockers ⇒ `READY`

Invariant violations are explicitly surfaced and logged.

These semantics are enforced consistently across:
- UI banners
- letter drafting
- audit exports
- automated tests

---

## 8. Evaluation & Testing

### Test Strategy
- Synthetic PA cases with realistic fake PHI
- Deterministic expected outcomes
- Negative-path coverage (missing documentation)
- Invariant enforcement tests
- Letter safety tests (no clinical or predictive language)
- Policy drift gating tests

### Metrics Tracked
- Readiness classification correctness (synthetic)
- Missing documentation detection accuracy
- Invariant compliance rate
- Evidence snippet coverage

### Metrics Explicitly Excluded
- Approval rate
- Predictive accuracy
- Automation rate
- Throughput optimization

---

## 9. Observed Failure Modes & Mitigations

### Observed Risks
- Ambiguous documentation leading to refusal
- User over-trust in generated letter text
- Misinterpretation of demo rules as verified policy
- Policy drift invalidating curated rules

### Mitigations Implemented
- Conservative extraction rules
- Explicit refusal semantics (`CANNOT_DETERMINE`)
- Deterministic, write-only drafting constraints
- Policy trust level surfaced in UI and letters
- Policy drift monitoring with explicit gating
- No silent defaults or inference

---

## 10. Human-in-the-Loop Requirements

- All outputs require human review before use
- Letters are editable and non-authoritative
- The system cannot proceed when required data is missing
- Policy updates require explicit human review and rule changes
- Audit records must be accessible for every run

Human oversight is **mandatory and non-bypassable**.

---

## 11. Ethical & Governance Considerations

- The system must not pressure clinicians to fabricate documentation
- Outputs must not be treated as authoritative decisions
- Use must be transparent, explainable, and auditable
- The system must not be used for performance evaluation or enforcement
- Silent behavioral changes are prohibited

---

## 12. Change Management & Versioning

- Current version: **v1.1 (feature-complete)**
- Any change requires:
  - explicit contract update,
  - test coverage,
  - version bump,
  - model card revision.

No silent behavioral changes are permitted.

---

## Summary Statement

The Prior Authorization Readiness Copilot is a **constrained, deterministic, human-supervised administrative decision-support system**.

It is designed to:
- **refuse when uncertain**,  
- **fail loudly when assumptions are violated**, and  
- preserve auditability and governance across policy, logic, and outputs.

The system prioritizes **safety, transparency, and post-deploy validity** over automation or prediction, demonstrating a defensible approach to AI-assisted workflows in regulated healthcare environments.
