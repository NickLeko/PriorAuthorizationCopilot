# Model Card — Prior Authorization Readiness Copilot

**Version:** 0.1 (Pre-Build / Design-Time)  
**Last Updated:** February 2026  
**Author:** Nicholas Leko  
**Status:** Draft — Intent & Risk Lock-In  
**License:** MIT  

---

## Model Overview

The Prior Authorization Readiness Copilot is an **administrative decision-support system** designed to assess whether a prior authorization (PA) request is *administratively ready* for submission, identify missing or weak documentation, and assist in drafting payer-aligned justification letters.

This system is **not a predictive model** and does **not** estimate approval likelihood. Its primary function is **pre-submission readiness assessment** under explicit human control.

---

## Intended Use

The system is intended to support:

- Prior authorization teams preparing PA submissions
- Revenue cycle and utilization management staff
- Clinicians seeking clarity on administrative documentation requirements

Primary use cases include:
- Identifying missing documentation relative to payer rules
- Highlighting weak or ambiguous justification language
- Drafting editable, payer-aligned justification letters
- Improving consistency and auditability of PA preparation

The system is designed for **internal decision support** and **offline or shadow-mode evaluation** prior to any operational integration.

---

## Explicit Non-Goals (Out of Scope)

This system is **not** intended to:

- Predict prior authorization approval or denial
- Provide medical advice or clinical judgment
- Override, reinterpret, or negotiate payer policy
- Autonomously submit PA requests
- Replace human review or decision-making
- Optimize approval rates as a primary objective

Any use outside these bounds is explicitly unsupported.

---

## System Description (High-Level)

### Architecture Principles
- **Rules-first evaluation:**  
  Deterministic logic assesses administrative readiness and requirement coverage.
- **LLM-assisted drafting (write-only):**  
  Language models are used exclusively to draft justification text after readiness evaluation.
- **Human-in-the-loop by default:**  
  All outputs require human review and approval.
- **Auditability over automation:**  
  Every output must be traceable to source inputs and rule evaluations.

### Core Capabilities
- Readiness classification (e.g., ready vs missing requirements)
- Requirement gap identification
- Draft justification letter generation
- Rationale and source attribution

---

## Inputs & Outputs (Conceptual)

### Inputs
- Structured administrative data (procedure codes, diagnosis codes, payer identifiers)
- Unstructured clinical documentation
- Payer policy documents (e.g., PDFs, guidelines)

### Outputs
- Readiness status or score
- Checklist of missing or weak administrative elements
- Draft justification letter (fully editable)
- Explanation of rule evaluations and assumptions

---

## Human-in-the-Loop Requirements

- Outputs must be reviewed by a human user prior to any submission
- No automated escalation or submission is permitted
- Ambiguous or incomplete cases must default to “missing information”
- Users must be able to see *why* a requirement was flagged

Human oversight is considered **mandatory**, not optional.

---

## Anticipated Risks & Failure Modes (Pre-Build)

This section documents **expected risks prior to implementation**. These will be revised post-build.

### Known Risks
- Hallucinated policy requirements
- Over-trust in generated justification text
- Incomplete or outdated policy inputs
- Inconsistent outputs across similar cases

### Mitigations (Design-Time)
- Rules-first gating before LLM invocation
- Write-only LLM role with no decision authority
- Explicit source citation requirements
- Conservative defaults when uncertainty exists

---

## Evaluation Approach (Planned)

Quantitative performance metrics are **intentionally undefined** at this stage.

Planned evaluation includes:
- Synthetic PA cases with known administrative requirements
- Rule coverage and error analysis
- Human review of drafted justifications
- Qualitative assessment of clarity and usefulness

Predictive accuracy and approval rate optimization are explicitly deprioritized.

---

## Monitoring & Change Considerations

This v0.1 model card reflects **design intent only**.

Post-build versions will include:
- Observed failure modes
- Empirical evaluation results
- Monitoring signals
- Update and change control policies (via PCCP or equivalent)

Any material change in scope or behavior will require model card revision.

---

## Ethical & Governance Considerations

- The system must not be used to pressure clinicians into inappropriate documentation
- Outputs should not be treated as authoritative or definitive
- Use must be transparent and auditable
- The system should not be used for individual performance evaluation

---

## Summary Statement

The Prior Authorization Readiness Copilot is a **constrained, human-supervised administrative support system** designed to improve the quality and consistency of PA preparation. Its design prioritizes transparency, auditability, and safety over automation or prediction. This v0.1 model card establishes intent, boundaries, and anticipated risks prior to implementation.
