# Letter Drafting Contract v1.1 (Frozen)

Project: Prior Authorization Readiness Copilot  
Scope: Write-only letter drafting (no extraction, no evaluation, no state mutation)  
Primary goal: Produce payer-facing administrative documentation that is strictly grounded in deterministic outputs + captured evidence snippets.

**Status:** FROZEN  
Any change requires: contract update + tests + explicit version bump.

---

## 1) Non-Negotiable Boundaries

The letter generator MUST:

- Use ONLY:
  - `PARequest` fields (payer, procedure_code, site_of_care, specialty, dx_codes)
  - `ReadinessReport.results[]` (status, reason, evidence hint, evidence_snippets)
  - `ReadinessReport` counts (met_count, not_met_count, not_documented_count)
  - `policy_trust_level` provided by caller
- NEVER:
  - infer undocumented facts
  - re-interpret clinical meaning
  - change requirement statuses
  - change overall readiness status
  - predict approval likelihood or “chance of approval”
  - recommend treatment, diagnosis, tests, or clinical actions
  - add facts not explicitly supported by evidence snippets
- ALWAYS:
  - include “does not guarantee payer approval” language in summary framing
  - keep evidence snippets short (<= 25 words) and verbatim

---

## 2) Inputs (Required)

### 2.1 Required Inputs
- `PARequest`:
  - payer (string)
  - procedure_code (string)
  - site_of_care (string)
  - specialty (string)
  - dx_codes (list[string], sanitized)
- `ReadinessReport`:
  - met_count, not_met_count, not_documented_count
  - results[]:
    - key, label, status, reason
    - evidence (hint; optional)
    - evidence_snippets[] (list of strings; may be empty)
- `letter_type` (string):
  - `submission_cover_letter`
  - `missing_info_request`
  - `appeal_template`
- `policy_trust_level` (string):
  - `demo`
  - `verified`

### 2.2 Forbidden Inputs
- raw clinical note text
- external policy text (unless explicitly included as allowed excerpts)
- model outputs from any upstream LLM extraction

---

## 3) Outputs (Required)

### 3.1 Letter Text
Letter must include:
- header: payer, procedure, site, specialty, generated timestamp, dx codes (if any)
- policy trust line:
  - if `demo`: MUST include DEMO disclaimer line in header
  - if `verified`: MAY include a verified provenance line
- Overall Status line: READY | NOT_READY | CANNOT_DETERMINE
- Summary section (administrative framing only)
- Requirements section: each requirement shows status + reason + evidence
- Missing Documentation checklist:
  - REQUIRED when overall status is CANNOT_DETERMINE OR letter_type is missing_info_request
  - built from evidence hints where present

### 3.2 Letter Metadata (Machine-readable)
Must return metadata including:
- letter_version
- generated_timestamp_utc
- overall_status
- letter_type
- policy_trust_level
- cited_snippets_count
- contains_missing_documentation
- draft_blocked + reasons
- letter_hash_sha256_16 (audit linkage without storing full letter text)

---

## 4) Status-conditioned Behavior

### 4.1 READY
- Allowed framing: “administrative submission readiness”
- Must NOT imply approval or clinical appropriateness

### 4.2 NOT_READY
- Must highlight NOT_MET requirements
- Must not blame missing documentation
- Must not propose clinical changes; may reference documentation thresholds via existing reasons/hints only

### 4.3 CANNOT_DETERMINE
- Must emphasize missing documentation (NOT_DOCUMENTED)
- Must include Missing Documentation checklist
- Must not imply criteria failure

---

## 5) Prohibited Language (Hard Block)

The letter must not contain:
- “diagnosis”
- “treatment”
- “medically necessary” (unless explicitly sanctioned by policy module; default: prohibited)
- “recommended”
- “should start”
- “should take”
- “high risk”
- “risk score”
- “probability of approval”
- “will be approved”
- “guaranteed approval”
- “clinically indicated” (default: prohibited)
- any dosing instructions

---

## 6) Evidence Rules (Critical)

For each requirement:
- MUST include:
  - Evidence snippet(s) OR “No supporting snippet available.”
- Evidence snippet(s) must be:
  - verbatim
  - short (<= 25 words)
  - sourced from `evidence_snippets` only
- The letter must never paraphrase a fact that is not explicitly present in evidence snippets.

---

## 7) Draft Blocking Rules

If any of the following are true, letter generation must return `DRAFT_BLOCKED`:
- invalid letter_type or policy_trust_level
- missing payer or procedure_code
- empty requirements list
- requirement results contain invalid statuses
- result counts do not match computed totals from results list

---

## 8) Versioning

- Current version: 1.1
- Any modification requires:
  - updating this contract
  - updating/adding tests
  - bumping letter_version
