# Letter Drafting Contract v1.0 (Frozen)

Project: Prior Authorization Readiness Copilot  
Scope: Write-only letter drafting (no extraction, no evaluation, no state mutation)  
Inputs: requirement_results + evidence_map + policy_snapshot metadata  
Outputs: letter_text + letter_metadata (no PHI beyond what is already in the note spans provided)  
LLM Role: Formatting + explanation only (no new facts)

THIS CONTRACT IS FROZEN.
Any change requires: contract update, new or updated tests, explicit version bump.

---

## 1. Purpose

Generate a payer-facing justification/cover letter that:
- Reflects the deterministic requirement outcomes
- Cites only provided evidence spans
- Clearly identifies missing documentation when present
- Never implies approval likelihood or clinical judgment

The letter must be defensible, auditable, and consistent with the rules engine.

---

## 2. Hard Constraints (Non-Negotiable)

The letter generator MUST:
- Use ONLY facts present in `requirement_results`, `facts`, and `evidence_map` spans
- NEVER invent details (no hallucinations)
- NEVER infer missing documentation
- NEVER change any statuses (READY / NOT_READY / CANNOT_DETERMINE)
- NEVER recommend treatment, diagnose, or suggest clinical conclusions
- NEVER claim the payer will approve
- NEVER include raw full note text (only short quoted snippets already provided as spans)

If any required input is missing or inconsistent, output must include a `DRAFT_BLOCKED` section with reasons.

---

## 3. Inputs (Required)

### 3.1 Core Inputs
- overall_status: READY | NOT_READY | CANNOT_DETERMINE
- requirements: list of requirement_result objects:
  - requirement_id
  - display_name
  - status: MET | NOT_MET | NOT_DOCUMENTED
  - reason: short deterministic reason string from rules layer
  - what_to_look_for_hint: string (optional)
  - evidence_fields: list of field_names referenced
- evidence_map: map[field_name] -> evidence_record:
  - field_name
  - status: MET | NOT_MET | NOT_DOCUMENTED
  - spans[]: { start, end, text, type: supporting | missingness }
- policy_snapshot:
  - payer
  - procedure_code / procedure_name
  - site_of_care
  - specialty (if applicable)
  - rules_version
  - policy_trust_level: demo | verified
- patient_identifiers (optional, only if provided explicitly in allowed inputs):
  - patient_name (or initials), DOB (optional)
  - ordering_provider (optional)

### 3.2 Forbidden Inputs
- Raw full clinical note text
- Any external payer policy text not contained in `policy_snapshot` (unless explicitly provided as allowed excerpt)

---

## 4. Output (Required)

### 4.1 Letter Text
A single plain-text or markdown letter with:
- Header block (payer, procedure, site, date, optional identifiers)
- Summary section (what is being requested + current readiness status)
- Requirements section (bullet list or table-like bullets)
- Evidence section (only short snippets from spans, grouped per requirement)
- Missing Documentation section (only if any NOT_DOCUMENTED)
- Closing statement (administrative readiness framing, no promises)

### 4.2 Letter Metadata (Machine-Readable)
Return alongside text:
- letter_version: 1.0
- generated_timestamp
- overall_status (echo)
- included_requirements: ids
- cited_spans_count
- contains_missing_documentation: bool
- draft_blocked: bool
- draft_blocked_reasons: list (if blocked)

---

## 5. Style Rules

The letter MUST:
- Be administrative and professional
- Avoid clinical recommendations or subjective language
- Use “documentation indicates…” and “record reflects…” phrasing
- Avoid “medically necessary” unless the rules engine explicitly tags that phrase as allowed
- Keep evidence quotes short (<= 25 words per snippet)
- Prefer bullet lists for requirements to reduce ambiguity

---

## 6. Status-Conditioned Behavior

### 6.1 If overall_status = READY
- State that documentation appears complete for administrative submission
- List all requirements as MET with supporting snippets
- Do NOT claim approval, only readiness

### 6.2 If overall_status = NOT_READY
- Clearly identify which requirements are NOT_MET
- Include evidence supporting NOT_MET (e.g., “duration 4 weeks” when threshold is 6)
- Suggest “additional documentation or time course may be needed” ONLY if the rules engine provides a neutral hint
- Do not prescribe actions beyond documentation

### 6.3 If overall_status = CANNOT_DETERMINE
- Emphasize missing documentation (NOT_DOCUMENTED)
- Include missingness snippets where available (type=missingness)
- Provide a clean checklist of missing items using `what_to_look_for_hint`
- Do not imply the patient fails criteria—only that documentation is incomplete

---

## 7. Evidence Citation Rules (Critical)

- Every factual claim MUST map to:
  - a requirement_result field, OR
  - a facts field, OR
  - an evidence span text
- Every requirement row MUST include at least one of:
  - supporting evidence snippet, OR
  - missingness snippet, OR
  - “No supporting snippet available” (only allowed when extraction has no spans)
- Never cite anything outside spans
- Never paraphrase a fact that is not explicitly present

---

## 8. Invariant Checks (Must Run Before Drafting)

The letter generator MUST validate:
- overall_status is consistent with requirement statuses (your frozen invariants)
- evidence_map contains records for each referenced field_name
- any NOT_DOCUMENTED requirement has either:
  - missingness span(s), OR
  - an explicit “not documented” reason from rules layer

If any check fails:
- Set draft_blocked = true
- Output a short DRAFT_BLOCKED section instead of a letter

---

## 9. Test Suite Requirements

Add synthetic tests that assert:
- READY letter contains no “missing documentation” section
- CANNOT_DETERMINE letter includes a missing checklist
- NOT_READY letter highlights NOT_MET items and does not use “cannot determine”
- No letter contains claims not backed by spans
- Evidence snippet length cap enforced
- DRAFT_BLOCKED triggers on missing evidence_map records

---

## 10. Versioning

Current version: 1.0  
Any change requires tests + version bump (1.1, 1.2, ...)

---
