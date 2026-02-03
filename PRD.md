# Product Requirements Document (PRD)
## Prior Authorization Readiness Copilot

**Author:** Nicholas Leko  
**Status:** Draft (Pre-Build PRD)  
**Last Updated:** February 2026  
**Project Type:** Flagship Agentic AI System

---

## 1. Problem Statement

Prior authorization (PA) requests frequently fail or are delayed not because of inappropriate care, but due to **incomplete documentation, unclear justification language, and payer-specific administrative requirements**.

These failures create:
- Delays in care
- Administrative burden for clinicians and staff
- Revenue leakage for health systems
- Friction between providers and payers

The core problem is **administrative readiness**, not clinical decision-making.

---

## 2. Target Users & Stakeholders

### Primary Users
- Hospital or clinic prior authorization teams
- Revenue cycle / utilization management staff

### Secondary Stakeholders
- Clinicians submitting PA requests
- Operations leadership
- Compliance and audit teams

This system is **not patient-facing** and **not payer-facing**.

---

## 3. Goals & Non-Goals

### Goals
- Assess whether a PA request is *administratively ready* for submission
- Identify missing or weak documentation relative to payer rules
- Reduce preventable denials caused by documentation gaps
- Preserve full human control and auditability
- Improve speed and consistency of PA preparation

### Non-Goals
- Predict payer approval or denial
- Make medical necessity determinations
- Override or reinterpret payer policy
- Automate submission or approval decisions
- Replace clinical or administrative judgment

---

## 4. Product Scope

### In Scope
- Rules-based evaluation of PA readiness
- Identification of missing or insufficient requirements
- LLM-assisted drafting of justification letters (write-only)
- Transparent rationale for every output
- Offline and synthetic-case evaluation

### Out of Scope
- Real-time EHR integration
- Automated payer communication
- Appeals automation
- Model fine-tuning or end-to-end learning systems

---

## 5. Decision Being Supported

**Decision:**  
> “Is this prior authorization request ready to submit as-is, and if not, what specific administrative elements are missing or weak?”

The system supports **pre-submission review**, not outcome prediction.

---

## 6. System Inputs

### Structured Inputs
- Procedure codes (e.g., CPT / HCPCS)
- Diagnosis codes (e.g., ICD)
- Site of care
- Payer identifier

### Unstructured Inputs
- Clinical notes
- Prior authorization policy documents (PDFs, guidelines)
- Historical PA examples (synthetic or de-identified)

---

## 7. System Outputs

- **Readiness score or status**
  - Ready
  - Missing requirements
  - High denial risk due to documentation gaps (administrative only)

- **Checklist of missing or weak elements**
  - Explicit mapping to payer requirements

- **Draft justification letter**
  - Payer-aligned
  - Fully editable
  - Traceable to source inputs

- **Rationale & audit trail**
  - What rules fired
  - What information was used
  - What assumptions (if any) were made

---

## 8. Architecture Principles

- **Rules-first evaluation**
  - Deterministic, inspectable, auditable
- **LLM as write-only assistant**
  - No autonomous decisions
  - No hidden state
- **Human-in-the-loop by design**
  - Every output requires review
- **Failure-safe defaults**
  - Ambiguity → “missing information,” not “ready”

---

## 9. Success Metrics

### Primary Metrics
- Accuracy of readiness classification on synthetic cases
- Accuracy of missing-requirement detection

### Secondary Metrics
- Time saved per PA preparation
- Consistency of outputs across similar cases
- User-reported clarity and trust

### Explicitly Deprioritized Metrics
- Approval rate
- Predictive accuracy
- End-to-end automation rate

---

## 10. Evaluation Plan

### Offline Evaluation
- Synthetic PA cases with known requirements
- Rule coverage and error analysis
- Human review of drafted justifications

### Silent Mode
- Run on historical cases without user exposure
- Compare agent output vs known outcomes (qualitative)

### Shadow Mode
- Show outputs to users without affecting submissions
- Collect feedback on usefulness and correctness

No live automation is planned in the MVP.

---

## 11. Constraints & Guardrails

- Outputs must be explainable and auditable
- The system must not hallucinate policy requirements
- Any uncertainty must be explicitly surfaced
- Latency may be minutes, not seconds
- Determinism is preferred over creativity

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|----|----|
| Hallucinated requirements | Rules-first gating, source citation |
| Over-trust in generated text | Write-only LLM, mandatory human review |
| Policy drift | Versioned policy inputs |
| Scope creep toward prediction | Explicit non-goals in PRD and model card |

---

## 13. Rollout Strategy

1. Offline testing on synthetic cases  
2. Silent mode on historical data  
3. Shadow mode with PA teams  
4. Limited internal MVP usage  

Progression is gated by **trust and clarity**, not performance metrics alone.

---

## 14. Stopping Criteria

The MVP is considered complete when:
- Readiness classification is reliable on synthetic cases
- Missing-requirement detection is consistent
- Drafted letters are usable with minimal edits
- Users understand *why* the system flags issues

Further automation is intentionally deferred.

---

## Summary

This PRD defines a **prior authorization readiness system**, not a predictive or autonomous agent. The system prioritizes transparency, auditability, and administrative correctness over speed or automation, aligning with real healthcare workflows and regulatory expectations.