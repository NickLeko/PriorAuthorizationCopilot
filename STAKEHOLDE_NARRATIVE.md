# Stakeholder Engagement Narrative

**Project:** Prior Authorization Readiness Copilot  
**Purpose:** Document user-centered design decisions and iteration based on stakeholder feedback  
**Status:** Simulated workflow analysis (not deployed with real users)

---

## Overview

This document captures the **stakeholder thinking** behind key design decisions in the PA Readiness Copilot.

While this system was not deployed in a live clinical environment, the design choices reflect **anticipated user needs** based on:
- Prior authorization workflow analysis
- Medical device support experience (understanding operational constraints)
- Payer-provider interaction patterns (from payer operations background)

---

## Target Stakeholders

### Primary Users
**Prior Authorization Coordinators**
- **Need:** Clear, actionable checklists when documentation is incomplete
- **Pain point:** Black-box "not ready" outputs don't tell them *what's missing*
- **Workflow constraint:** Average 15 minutes per PA case; no time to debug vague system outputs

**Utilization Management Teams**
- **Need:** Audit trails for payer disputes and internal compliance review
- **Pain point:** Inability to explain *why* a PA was submitted or rejected
- **Workflow constraint:** Must produce evidence for payer appeals and quality audits

**Revenue Cycle Leadership**
- **Need:** Measurable ROI (time saved, denial reduction)
- **Pain point:** Unquantified "efficiency improvements" don't justify software spend
- **Workflow constraint:** Budget decisions require hard cost/benefit analysis

---

### Secondary Stakeholders
**Compliance/Audit Teams**
- **Need:** Provable regulatory defensibility (HIPAA, governance artifacts)
- **Pain point:** Opaque AI systems create liability risk

**Ordering Clinicians (Review-only)**
- **Need:** Understand why PA was delayed or denied
- **Pain point:** Administrative burden distracts from patient care

---

## Design Decisions Informed by Stakeholder Needs

### Decision 1: Refusal Semantics (`CANNOT_DETERMINE`)

**Stakeholder feedback (anticipated):**
> "If the system says 'ready' but I can't find the AHI value in the note, I can't submit it. The system should tell me what's missing, not guess."  
> — PA Coordinator (workflow analysis)

**Design response:**
- Implemented **explicit refusal** when required elements are not documented
- Introduced `CANNOT_DETERMINE` as a first-class outcome (not a failure state)
- Added **Missing Documentation checklist** with evidence hints

**Why this matters:**
- PA coordinators need **actionable next steps**, not confidence scores
- Refusal prevents false confidence and avoids resubmission rework
- Checklist format aligns with existing PA workflow (coordinators already use checklists)

**Alternative considered (rejected):**
- Predict "likely ready" based on partial documentation
- **Rejected because:** Introduces false positives and creates liability when submission fails

---

### Decision 2: Evidence Snippets (Explainability)

**Stakeholder feedback (anticipated):**
> "How do I know the system actually saw the PT duration? I need to verify what it's reading before I trust the output."  
> — Utilization Management Reviewer

**Design response:**
- Capture **evidence spans** from original note text for every extracted fact
- Display up to 5 supporting snippets per requirement result
- Show "No supporting snippet available" when extraction misses (transparency over fabrication)

**Why this matters:**
- Reviewers don't trust black-box outputs; they need **provenance**
- Evidence snippets enable **rapid human verification** (2-3 seconds to scan vs. re-reading entire note)
- Supports **audit trail** for payer disputes ("here's the exact text we used")

**Alternative considered (rejected):**
- Only show extracted values without source text
- **Rejected because:** Reduces trust and makes error diagnosis impossible

---

### Decision 3: Policy Trust Signaling (Demo vs. Verified)

**Stakeholder feedback (anticipated):**
> "Are these the actual payer criteria or are you making them up? I can't submit based on demo rules."  
> — Compliance Officer

**Design response:**
- Introduced **policy trust level** (`demo` vs `verified`)
- Surface trust level in:
  - UI banner
  - Letter output
  - Audit trail
- Demo rules include explicit disclaimer: *"Criteria are illustrative only. Verify against official payer policy."*

**Why this matters:**
- Prevents misuse of unverified rules in real submissions
- Supports governance requirement: **know your assumptions**
- Aligns with medical device regulatory mindset (clear labeling of limitations)

**Alternative considered (rejected):**
- Hide trust level and assume users will verify independently
- **Rejected because:** Creates liability risk and violates transparency principle

---

### Decision 4: Write-Only Letter Drafting

**Stakeholder feedback (anticipated):**
> "I need a template to save time, but I have to be able to edit it. The system can't send letters on my behalf."  
> — PA Coordinator

**Design response:**
- Letter drafting is **downstream of evaluation** (cannot change facts or statuses)
- All letters are **editable** by human before use
- Prohibited language enforcement (no clinical recommendations, no approval claims)
- Letter metadata includes hash for audit linkage (traceability without storing raw text)

**Why this matters:**
- PA coordinators want **time savings** (template generation) without losing control
- Write-only design prevents letter generator from "overriding" deterministic evaluation
- Supports compliance: human has final authority over all payer-facing content

**Alternative considered (rejected):**
- Fully autonomous letter generation + submission
- **Rejected because:** Violates human oversight principle and creates regulatory risk

---

### Decision 5: Policy Drift Monitoring + Gating

**Stakeholder feedback (anticipated):**
> "Payer policies change all the time. If the rules are stale, the system is useless—or worse, dangerous."  
> — Revenue Cycle Director

**Design response:**
- Policy sources are **versioned and snapshotted**
- Content hashes detect changes; diffs are stored for human review
- When drift is detected:
  - UI displays `REVIEW_REQUIRED` banner
  - Evaluation is gated behind explicit acknowledgment
  - Outputs are marked as "potentially stale"

**Why this matters:**
- Silent policy drift is a **critical safety risk** in PA automation
- Gating ensures users **cannot accidentally use stale rules** without acknowledgment
- Aligns with post-market surveillance mindset from medical device background

**Alternative considered (rejected):**
- Auto-update rules based on detected policy changes
- **Rejected because:** LLM interpretation of policy introduces inference risk; humans must review

---

## Iteration Example (Simulated)

### V0.1: Initial Prototype
**Behavior:**
- Extracted AHI value if present
- If AHI missing → marked requirement as `NOT_MET` (documented but failing)
- Letter output: "AHI requirement not met"

**Stakeholder reaction (anticipated):**
> "That's wrong. AHI isn't documented *at all* in this note. The system shouldn't say it's 'not met'—it should say it's *missing*."

---

### V0.2: Missingness Handling
**Behavior:**
- Distinguished `NOT_MET` (documented but below threshold) from `NOT_DOCUMENTED` (missing)
- Changed overall status logic:
  - Any `NOT_DOCUMENTED` → `CANNOT_DETERMINE`
  - No missing items + any `NOT_MET` → `NOT_READY`

**Stakeholder reaction (anticipated):**
> "Better, but what do I do now? The output says 'cannot determine' but doesn't tell me what to add."

---

### V1.0: Actionable Refusal (Current)
**Behavior:**
- Added **Missing Documentation checklist** with evidence hints
- Example output:
```
  Overall Status: CANNOT_DETERMINE

  Missing Documentation (Checklist):
  - AHI documented: Look for numeric AHI (e.g., 'AHI 22').
  - Sleep study date documented: Look for date near 'sleep study', 'PSG', or 'polysomnography'.
```

**Stakeholder reaction (anticipated):**
> "Perfect. Now I know exactly what to ask the clinician to add to the note."

---

## Cross-Functional Alignment (Simulated)

### With Engineering
**Question:** "Why can't we just use an LLM to extract everything? Regex is brittle."

**Response:**
- LLMs introduce **non-determinism** and **hallucination risk** in extraction
- PA workflows require **reproducibility** for audit and compliance
- Evidence spans from deterministic extraction provide **traceability**

**Outcome:** Agreed to deterministic extraction core + optional LLM layer for letter drafting only (write-only)

---

### With Compliance
**Question:** "What happens if the system extracts PHI and logs it?"

**Response:**
- Audit trail stores **note hash** (not raw text)
- Evidence spans are **offsets + snippets** (minimal PHI exposure)
- No raw note text is persisted in audit JSON

**Outcome:** Agreed to current audit design; compliance team approved governance artifacts

---

### With Revenue Cycle Leadership
**Question:** "What's the ROI? How do we know this saves time?"

**Response:**
- Baseline workflow: 15 min per PA case
- With system: 6 min per PA case (60% reduction)
- At 100 cases/week: 780 hours saved annually = $23,400 labor savings

**Outcome:** Approved conceptual ROI; requested pilot with time-tracking to validate

---

## Lessons Learned (Product Thinking)

### 1. Refusal Is a Feature, Not a Bug
- Early instinct: minimize refusals to maximize "automation rate"
- **Reality:** PA coordinators *want* refusal when documentation is incomplete
- **Takeaway:** Optimize for **correctness and trust**, not automation percentage

---

### 2. Provenance > Confidence Scores
- Early instinct: show confidence % for each extracted fact
- **Reality:** Reviewers don't care about 87% vs 92% confidence—they want **source text**
- **Takeaway:** Evidence snippets provide **actionable verification**, confidence scores don't

---

### 3. Governance Artifacts Are First-Class Outputs
- Early instinct: focus on feature velocity, treat documentation as afterthought
- **Reality:** Compliance teams won't approve without PRD, Model Card, failure taxonomy
- **Takeaway:** In regulated workflows, **governance docs = product**

---

### 4. Policy Drift Is an Operational Reality
- Early instinct: assume payer policies are stable
- **Reality:** Policies change quarterly; stale rules create liability
- **Takeaway:** **Monitoring and gating** are non-negotiable for production deployment

---

## Stakeholder Quotes (Simulated)

> "This system doesn't try to be smarter than me—it helps me do my job faster by catching what I might miss."  
> — PA Coordinator (workflow analysis)

> "The audit trail is exactly what we need for payer disputes. We can show *what the system saw* and *why it made the decision*."  
> — Utilization Management Director

> "I appreciate that the system says 'I don't know' when documentation is unclear. That's safer than guessing."  
> — Compliance Officer

> "The ROI case is solid, but I want to pilot this with 10 coordinators and track actual time savings before scaling."  
> — Revenue Cycle VP

---

## Next Steps (If Deploying)

### User Acceptance Testing (Simulated Plan)
1. **Pilot with 5-10 PA coordinators** (1 month)
2. **Track time per case** (before/after)
3. **Measure refusal accuracy** (are flagged missing items actually required?)
4. **Collect feedback** on UI, checklist clarity, and letter quality

### Iteration Priorities (Based on Anticipated Feedback)
1. Expand extraction patterns for common phrasing variants
2. Add payer-specific customization (BCBS criteria may differ from Aetna)
3. Integrate with EHR (reduce manual note copy/paste)
4. Build dashboard for leadership visibility (cases processed, time saved, denial reduction)

---

**Version:** 1.0  
**Last Updated:** February 2026  
**Author:** Nicholas Leko  
**Note:** This narrative reflects anticipated stakeholder needs based on workflow analysis and prior healthcare operational experience. Not based on live user deployment.
```

