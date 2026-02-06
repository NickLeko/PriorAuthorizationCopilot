# Extraction Contract v1.0 (Frozen)

Project: Prior Authorization Readiness Copilot  
Scope: Deterministic extraction only; context-gated; span-evidenced  
Output: (facts, evidence_map)  
Rules Version: 1.0  
Status Semantics (per requirement): MET | NOT_MET | NOT_DOCUMENTED

THIS CONTRACT IS FROZEN.
Any change requires: contract update, new or updated tests, and an explicit version bump.

---

## 1. Purpose

This document defines the authoritative extraction contract for the Prior Authorization Readiness Copilot.

Extraction characteristics:
- Deterministic
- Rules-first
- Auditable
- Context-gated
- Evidence-backed

LLMs are explicitly prohibited from participating in extraction.

---

## 2. Global Extraction Invariants

- Extraction returns (facts, evidence_map)
- Each field resolves to either:
  - a concrete value, or
  - null if not documented
- Every field MUST emit an evidence record
- No inference beyond explicit note text
- Missing documentation is preserved, never guessed
- No silent defaults

---

## 3. Field Contracts

### 3.1 Conservative Therapy Weeks

Field:
conservative_therapy_weeks: int | null

Accepted Signals (therapy context required):
- PT / physical therapy
- NSAIDs / anti-inflammatories
- Activity modification
- Home exercise program (HEP)
- Chiropractic care

Extraction Rules:
- Duration extracted ONLY if therapy context exists
- Accept weeks or months; normalize to weeks
- If multiple durations exist, the maximum duration wins
- Bare duration without therapy context → NOT_DOCUMENTED

Examples:
- "Completed PT for 8 weeks" → 8
- "Symptoms x 8 weeks" → NOT_DOCUMENTED

Evidence:
- Span(s) containing therapy context AND duration

---

### 3.2 Symptom Duration

Field:
symptom_duration_weeks: int | null

Accepted Signals:
- Any explicit duration tied to symptoms

Extraction Rules:
- Therapy context not required
- Normalize months to weeks
- Vague descriptors (e.g., "chronic", "longstanding") → NOT_DOCUMENTED

Examples:
- "Pain for 3 months" → 12
- "Chronic pain" → NOT_DOCUMENTED

Evidence:
- Duration span

---

### 3.3 Neurologic Red Flags

Field:
neuro_red_flags_documented: bool | null

Accepted Signals:
Explicit presence OR denial of:
- Weakness
- Numbness
- Bowel or bladder dysfunction
- Saddle anesthesia
- Progressive neurologic deficit

Extraction Rules:
- Explicit symptom mention required
- Meta phrases such as "no red flags documented" → NOT_DOCUMENTED
- Mixed signals → documented = true; downstream logic determines MET vs NOT_MET

Examples:
- "Denies weakness or bowel/bladder issues" → false
- "No red flags documented" → NOT_DOCUMENTED

Evidence:
- Symptom or denial span(s)

---

### 3.4 Prior Imaging Result

Field:
prior_imaging_result: abnormal | normal | inconclusive | null

Accepted Signals:
- MRI, CT, or X-ray with an explicit result descriptor

Extraction Rules:
- "Normal" imaging is treated as inconclusive (non-blocking)
- Historical imaging is allowed
- Imaging mentioned without a result → NOT_DOCUMENTED

Examples:
- "MRI lumbar spine normal" → inconclusive
- "Prior MRI reviewed" → NOT_DOCUMENTED

Evidence:
- Imaging + result span

---

### 3.5 Sleep Study Date (OSA Use Case)

Field:
sleep_study_date: date | null

Accepted Signals:
Date with nearby sleep-study context:
- Sleep study
- PSG
- Polysomnography
- HST

Extraction Rules:
- Sleep-study context must exist within a proximity window
- Scheduling or follow-up dates are ignored

Examples:
- "PSG on 3/12/2023" → 2023-03-12
- "Follow-up visit on 3/12/2023" → NOT_DOCUMENTED

Evidence:
- Contextual date span

---

### 3.6 AHI / RDI Value

Field:
ahi: float | null

Accepted Signals:
- Numeric AHI or RDI value

Extraction Rules:
- Numeric value required
- Negation-aware
- Explicit missingness (e.g., "AHI not stated") → NOT_DOCUMENTED
- Missingness evidence must be captured

Examples:
- "AHI 22.4" → 22.4
- "Elevated AHI" → NOT_DOCUMENTED

Evidence:
- Numeric span or missingness span

---

## 4. Evidence Map Contract (Required)

Every field MUST emit an evidence record.

Structure:
- field_name: string
- status: MET | NOT_MET | NOT_DOCUMENTED
- spans: list of objects containing:
  - start: integer offset
  - end: integer offset
  - text: raw note text span
  - type: supporting | missingness

Rules:
- No raw note text stored outside spans
- Missing fields may include missingness spans
- Span offsets must map to original note text

---

## 5. Non-Goals (Explicit)

The extraction layer does NOT:
- Predict approval
- Score likelihood
- Make clinical judgments
- Infer undocumented facts
- Use LLMs
- Mutate downstream state

---

## 6. Audit Requirements

Each extraction run must persist:
- rules_version: 1.0
- extraction_contract_version: 1.0
- Extracted facts
- Evidence map
- Invariant violations (if any)

---

## 7. Versioning and Change Control

Current version: 1.0

Any modification requires:
- Contract update
- New or updated tests
- Version bump (e.g., 1.1)

---

## 8. Locked Next Step

Proceed to LLM-assisted justification letter drafting with:
- Inputs: requirement statuses and evidence only
- Output: write-only text draft
- No rule overrides
- No state mutation
