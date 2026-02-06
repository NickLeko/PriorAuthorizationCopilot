# Case Study — Prior Authorization Readiness Copilot

## Overview

Prior authorization (PA) denials are commonly framed as a clinical or predictive problem. In practice, most failures occur earlier: at the **administrative readiness** stage, where required documentation is missing, ambiguous, or misaligned with payer-specific criteria.

This project explores a different design approach:  
**a deterministic, refusal-first administrative decision-support system** that prioritizes auditability, transparency, and safety over prediction or automation.

---

## Context & Motivation

### The Real Problem
Through analysis of PA workflows and denial patterns, a consistent theme emerged:

> Most PA delays and denials are not caused by inappropriate care, but by incomplete or unclear documentation relative to payer rules.

Existing tools often attempt to:
- predict approval likelihood,
- optimize approval rates,
- or automate submissions.

These approaches introduce:
- opaque decision-making,
- regulatory risk,
- over-trust in generated outputs,
- and limited auditability.

### Design Hypothesis
If administrative readiness is evaluated **explicitly and deterministically**, many preventable denials can be addressed **before submission**, without prediction or autonomy.

---

## Problem Statement

**How can we help clinicians and PA teams determine whether a prior authorization request is administratively ready to submit, while remaining transparent, auditable, and safe in a regulated healthcare environment?**

---

## Design Goals

- Distinguish **missing documentation** from **documented but unmet criteria**
- Refuse to determine readiness when documentation is incomplete
- Preserve full human control
- Make every output explainable and reviewable
- Avoid predictive or autonomous behavior entirely

---

## Non-Goals (Explicit)

This system does **not**:
- predict approval or denial,
- make medical necessity determinations,
- provide clinical recommendations,
- automate submission or appeals,
- infer undocumented facts,
- optimize approval rates.

---

## System Architecture

Clinical Note
↓
Deterministic Extraction (context-gated, span-based)
↓
Rules-based Requirement Evaluation
↓
Invariant Enforcement
↓
Overall Readiness Status
↓
Optional Write-only Letter Drafting
↓
Audit Record + UI Presentation


### Key Architectural Decisions

#### 1. Rules-First, Deterministic Core
All readiness evaluation is performed using explicit, inspectable rules.  
No machine learning model is used for extraction or decision-making.

This ensures:
- reproducibility,
- predictable behavior,
- and explainability.

#### 2. Refusal as a First-Class Outcome
When required documentation is missing, the system does **not** guess.

Instead, it returns:
- `CANNOT_DETERMINE`

This prevents false confidence and forces explicit documentation review.

#### 3. Strict Invariants
Overall readiness status is derived using frozen rules:
- Any missing requirement ⇒ `CANNOT_DETERMINE`
- Any unmet requirement ⇒ `NOT_READY`
- No blockers ⇒ `READY`

Invariant violations are explicitly surfaced and logged.

---

## Write-Only Letter Drafting

Language models are used **only after** readiness evaluation and **only** to draft administrative text.

Constraints:
- No access to raw notes
- No ability to change statuses or facts
- No approval claims
- No clinical language

Each letter:
- cites evidence snippets,
- includes policy trust disclaimers when applicable,
- and is fully editable by a human reviewer.

This design intentionally limits AI authority.

---

## Explainability & Auditability

Every evaluation produces:
- extracted facts,
- evidence spans from the source note,
- requirement-level results,
- blocking issues,
- invariant checks,
- letter metadata (hash + version),
- a downloadable audit JSON.

Raw clinical note text is **never persisted**.

---

## Testing & Evaluation

### Synthetic Test Suite
- Realistic synthetic notes with fake PHI
- Known expected outcomes
- Edge cases (negation, ambiguity, noise)
- Explicit negative-path tests

### Metrics Tracked
- Readiness classification correctness (synthetic)
- Missing documentation detection
- Invariant compliance
- Evidence snippet coverage

### Metrics Explicitly Excluded
- Approval rate
- Predictive accuracy
- Automation throughput

---

## Results

- The system consistently distinguishes missing documentation from unmet criteria
- Refusal behavior prevents false readiness signals
- Generated letters are usable with minimal edits
- Audit outputs fully explain every decision path

Most importantly, the system **fails safely**.

---

## Tradeoffs & Design Decisions

### Why Not Prediction?
Approval outcomes depend on payer behavior, policy interpretation, and human review. Predictive models obscure responsibility and introduce regulatory risk.

This system instead answers a narrower, defensible question:
> “Is this request administratively ready based on documented criteria?”

### Why Determinism Over Flexibility?
In regulated workflows, predictability and explainability are more valuable than adaptability.

Deterministic behavior enables:
- trust,
- governance,
- and test-driven validation.

---

## Key Learnings

- Refusal is a feature, not a failure
- Missingness must be preserved, not filled
- Auditability increases trust more than confidence scores
- Limiting AI authority simplifies compliance
- Many healthcare “AI problems” are actually systems problems

---

## Limitations

- Rules must be curated and maintained
- The system does not learn from outcomes
- Not suitable for real-time or high-throughput automation
- Requires human review by design

These limitations are intentional.

---

## Project Status

**Feature-complete (v1.1).**  
The system is intentionally frozen to preserve clarity, safety, and portfolio signal.

Future work would require explicit contract updates and expanded testing.

---

## Conclusion

The Prior Authorization Readiness Copilot demonstrates a **safe, defensible approach to AI-assisted healthcare workflows** by prioritizing determinism, refusal, and auditability over prediction and automation.

Rather than attempting to “outsmart” payer decisions, the system focuses on ensuring requests are **administratively sound before submission**, aligning with real-world clinical, operational, and regulatory constraints.

