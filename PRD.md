# Product Requirements Document (PRD)
## Prior Authorization Readiness Copilot

**Author:** Nicholas Leko  
**Status:** Feature-complete (v1.1)  
**Last Updated:** February 2026  
**Project Type:** Flagship Administrative Decision-Support System  

---

## 1. Problem Statement

Prior authorization (PA) requests are frequently delayed or denied not due to inappropriate care, but because of **incomplete, ambiguous, or misaligned administrative documentation** relative to payer-specific criteria.

These failures result in:
- delays to patient care,
- increased administrative burden,
- avoidable rework and resubmissions,
- friction between providers and payers.

The core problem is **administrative readiness**, not clinical decision-making or approval prediction.

---

## 2. Target Users & Stakeholders

### Primary Users
- Prior authorization coordinators
- Utilization management teams
- Revenue cycle operations staff

### Secondary Stakeholders
- Ordering clinicians (review-only)
- Compliance and audit teams
- Operations leadership

This system is **not patient-facing**, **not payer-facing**, and **not autonomous**.

---

## 3. Goals & Non-Goals

### Goals
- Determine whether a PA request is **administratively ready** for submission
- Explicitly identify **missing documentation** vs **documented but unmet criteria**
- Reduce preventable denials caused by documentation gaps
- Preserve full human control, transparency, and auditability
- Provide clear, reproducible explanations for every output
- Fail loudly and safely when assumptions are violated

### Non-Goals (Explicit)
- Predict approval or denial likelihood
- Make medical necessity determinations
- Provide clinical recommendations
- Override, reinterpret, or negotiate payer policy
- Automate submission, escalation, or appeals
- Optimize for approval rates or automation metrics
- Auto-update rules in response to policy changes

---

## 4. Product Scope

### In Scope
- Deterministic extraction of documentation signals from clinical notes
- Rules-first evaluation of payer-specific requirements
- Explicit missingness handling (`NOT_DOCUMENTED`)
- Invariant-based readiness determination
- Write-only drafting of administrative justification letters  
  *(deterministic in v1.1; LLM-based drafting architecturally supported but intentionally disabled in the public demo)*
- Policy provenance surfacing and trust signaling
- Policy drift detection and governance gating
- Full audit trail with evidence spans
- Synthetic test suite and offline evaluation

### Out of Scope
- Real-time EHR integration
- Direct payer communication
- Automated appeals or submissions
- Machine learning–driven decisioning
- Continuous learning or model retraining
- Live clinical workflows
- Autonomous system behavior

---

## 5. Decision Being Supported

**Decision:**  
> “Is this prior authorization request administratively ready to submit as documented, and if not, what specific administrative elements are missing or below threshold?”

The system supports **pre-submission review only**.

It does not answer:
- whether the procedure is appropriate,
- whether it should be approved,
- or what clinical action should be taken.

---

## 6. System Inputs

### Structured Inputs
- Payer identifier
- Procedure code
- Diagnosis codes (sanitized)
- Site of care
- Ordering specialty

### Unstructured Inputs
- Clinical note text (synthetic or de-identified)

> Note: Payer policy documents are **not parsed or interpreted at runtime**.  
> Rules are curated offline, versioned, and governed explicitly.

---

## 7. System Outputs

### Primary Outputs
- **Requirement-level results**
  - `MET`
  - `NOT_MET`
  - `NOT_DOCUMENTED`
- **Overall readiness status**
  - `READY`
  - `NOT_READY`
  - `CANNOT_DETERMINE`
- **Blocking issues**
  - Explicit list of missing or unmet requirements

### Secondary Outputs
- **Administrative justification letters** (write-only)
  - Submission cover letters
  - Missing information requests
  - Appeal templates
- **Audit JSON**
  - Facts extracted
  - Evidence spans
  - Rules evaluated
  - Invariant checks
  - Policy trust level
  - Letter artifact metadata (hash + version)

The system does **not** output:
- approval probability,
- denial risk,
- confidence scores,
- clinical interpretation.

---

## 8. Core Semantics & Invariants (Frozen)

### Requirement Status
- `MET`: documented and meets payer threshold
- `NOT_MET`: documented but does not meet threshold
- `NOT_DOCUMENTED`: required element not present

### Overall Status
- `READY`: all required criteria documented and met
- `CANNOT_DETERMINE`: one or more required criteria not documented
- `NOT_READY`: all criteria documented, but one or more not met

### Invariant Rules
- Any `NOT_DOCUMENTED` ⇒ overall must be `CANNOT_DETERMINE`
- Any `NOT_MET` (with no missing items) ⇒ overall must be `NOT_READY`
- No blockers ⇒ overall must be `READY`

Invariant violations are explicitly surfaced and logged.

---

## 9. Policy Drift & Governance Requirements

### Problem
Payer policies are external dependencies that change over time.  
Silent policy drift can invalidate otherwise correct rules.

### Requirements
- Policy sources must be explicitly registered and versioned
- Normalized policy content must be snapshotted
- Content hashes must be compared over time
- Any change must produce:
  - a snapshot artifact,
  - a diff artifact,
  - an append-only drift log entry

### Explicit Non-Behavior
- Rules must **never** auto-update
- Policy meaning must **never** be inferred
- LLMs must **not** be used for policy interpretation

### Runtime UX Requirements
When drift is detected:
- UI must surface `REVIEW_REQUIRED`
- Evaluation must be gated behind explicit acknowledgment
- Outputs must be labeled as potentially stale

---

## 10. Architecture Principles

- **Rules-first, deterministic evaluation**
- **Governance before automation**
- **Write-only drafting layer**
- **LLM use architecturally constrained**
- **No hidden state or learning**
- **Failure-safe defaults**
  - ambiguity → refusal (`CANNOT_DETERMINE`)
- **Evidence-linked explanations**
- **Test-locked behavior**

---

## 11. Success Metrics

### Primary Metrics (Tracked)
- Correct readiness classification on synthetic cases
- Correct detection of missing vs unmet requirements
- Invariant compliance rate
- Evidence snippet coverage
- Policy drift detection accuracy

### Secondary Metrics (Qualitative)
- Reviewer clarity and trust
- Ease of correcting missing documentation
- Consistency across similar cases

### Explicitly Excluded Metrics
- Approval rate
- Denial prediction accuracy
- Automation percentage
- Throughput optimization

---

## 12. Evaluation Plan

### Offline Evaluation
- Synthetic PA cases with known ground truth
- Edge-case and negation handling tests
- Negative-path tests (`CANNOT_DETERMINE`)
- Invariant enforcement tests
- Policy drift gating tests

### Review Mode
- Human inspection of audit outputs
- Comparison against expected rule behavior
- Letter review for prohibited language

No live automation or production deployment is planned.

---

## 13. Constraints & Guardrails

- Determinism preferred over flexibility
- No inference beyond explicit documentation
- No silent defaults or gap-filling
- Latency tolerance is minutes, not seconds
- All behavior must be testable and auditable
- Governance artifacts are first-class outputs

---

## 14. Risks & Mitigations (Governance Reference)

All material risks, failure modes, mitigations, and residual limitations for this system are formally documented and versioned in the **Failure Modes & Safety Contract**:

➡️ **[`FAILURE_MODES.md`](./FAILURE_MODES.md)**

That document is the **authoritative source** for:
- known and expected failure modes,
- why those failures occur,
- which mitigations exist inside vs. outside the system,
- what risks are explicitly accepted,
- and what behaviors are prohibited.



### Summary (Non-Exhaustive)

This PRD intentionally does **not** restate the full safety analysis to avoid duplication and drift. At a high level, the system addresses the following risk categories:

| Risk Category | Mitigation Strategy |
|----|----|
| Hallucinated or inferred facts | Deterministic, evidence-backed extraction only |
| Over-trust in generated artifacts | Write-only drafting with prohibited-language enforcement |
| Policy drift invalidating rules | Snapshotting, diffing, and explicit UI gating |
| Scope creep into prediction or autonomy | Frozen contracts and explicit non-goals |
| Misuse of demo rules | Policy trust level surfaced in UI, letters, and audit |

Any change to system risk posture or mitigation strategy **must** be reflected in `FAILURE_MODES.md` and accompanied by:
- updated or new tests,
- contract review,
- and an explicit version bump.


---

## 15. Stopping Criteria

The system is considered complete when:
- Invariants hold across all tests
- Missing documentation reliably triggers refusal
- Letters are grounded, editable, and non-authoritative
- Policy drift is detectable and review-gated
- No feature depends on probabilistic inference

**Status:** All criteria satisfied in v1.1.

---

## Summary

The Prior Authorization Readiness Copilot is a **governance-first administrative decision-support system**.

It deliberately chooses:
- refusal over guesswork,
- determinism over optimization,
- and transparency over automation.

This PRD reflects a consciously constrained product designed for **regulated healthcare environments**, where correctness, explainability, and post-deploy validity matter more than speed or scale.
