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

### Non-Goals (Explicit)
- Predict approval or denial likelihood
- Make medical necessity determinations
- Provide clinical recommendations
- Override, reinterpret, or negotiate payer policy
- Automate submission, escalation, or appeals
- Optimize for approval rates or automation metrics

---

## 4. Product Scope

### In Scope
- Deterministic extraction of documentation signals from clinical notes
- Rules-first evaluation of payer-specific requirements
- Explicit missingness handling (`NOT_DOCUMENTED`)
- Invariant-based readiness determination
- Write-only drafting of administrative justification letters  
  *(deterministic in v1.1; LLM-based drafting architecturally supported but intentionally disabled in the public demo)*
- Full audit trail with evidence spans
- Synthetic test suite and offline evaluation

### Out of Scope
- Real-time EHR integration
- Direct payer communication
- Automated appeals or submissions
- Machine learning–driven decisioning
- Continuous learning or model retraining
- Live clinical workflows

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

> Note: Payer policy documents are **not parsed at runtime**. Rules are curated offline and versioned.

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

## 9. Architecture Principles

- **Rules-first, deterministic evaluation**
- **Write-only drafting layer (deterministic in v1.1)**
- **LLM use architecturally constrained and disabled in public demo**
- **No hidden state or learning**
- **Failure-safe defaults**
  - ambiguity → refusal (`CANNOT_DETERMINE`)
- **Evidence-linked explanations**
- **Test-locked behavior**

---

## 10. Success Metrics

### Primary Metrics (Tracked)
- Correct readiness classification on synthetic cases
- Correct detection of missing vs unmet requirements
- Invariant compliance rate
- Evidence snippet coverage

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

## 11. Evaluation Plan

### Offline Evaluation
- Synthetic PA cases with known ground truth
- Edge-case and negation handling tests
- Negative-path tests (`CANNOT_DETERMINE`)

### Review Mode
- Human inspection of audit outputs
- Comparison against expected rule behavior
- Letter review for prohibited language

No live automation or production deployment is planned.

---

## 12. Constraints & Guardrails

- Determinism preferred over flexibility
- No inference beyond explicit documentation
- No silent defaults or gap-filling
- Latency tolerance is minutes, not seconds
- All behavior must be testable and auditable

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|----|----|
| Hallucinated facts | Deterministic extraction only |
| Over-trust in generated text | Write-only drafting + disclaimers |
| Policy drift | Versioned rules + trust level |
| Scope creep into prediction | Frozen contracts + explicit non-goals |
| Misuse of demo rules | Policy trust line in letters |

---

## 14. Stopping Criteria

The system is considered complete when:
- Invariants hold across all tests
- Missing documentation reliably triggers refusal
- Letters are grounded, editable, and non
