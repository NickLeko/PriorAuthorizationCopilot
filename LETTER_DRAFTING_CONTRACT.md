# Letter Drafting Contract v1.2

Project: Prior Authorization Readiness Copilot  
Scope: Write-only letter drafting (no extraction, no evaluation, no state mutation)  
Primary goal: Produce payer-facing administrative documentation from supplied request metadata, deterministic outputs, and captured evidence snippets.
Current repo status: deterministic letter drafting only; no LLM implementation

**Status:** Versioned current behavior  
Any change should update this contract, tests, and versioning.

---

## 1) Implemented Input And Template Boundaries

The standard templates are designed to:

- Use ONLY the typed `LetterDraftInput` boundary:
  - `LetterRequestMetadata` fields (payer, procedure_code, site_of_care, specialty, dx_codes); this type has no `note_text` field and rejects extra fields
  - structured `results[]` (status, reason, evidence hint, evidence_snippets)
  - structured counts (met_count, not_met_count, not_documented_count, needs_review_count)
  - `policy_trust_level`
- not intentionally:
  - infer undocumented facts
  - re-interpret clinical meaning
  - change requirement statuses
  - change overall readiness status
  - predict approval likelihood or “chance of approval”
  - recommend treatment, diagnosis, tests, or clinical actions
  - independently validate factual assertions in caller-supplied structured reasons
- consistently:
  - include “does not guarantee payer approval” language in summary framing
  - keep evidence snippets short (<= 25 whitespace-delimited words) and copied from supplied snippets

---

## 2) Inputs (Required)

### 2.1 Required Inputs
- `LetterDraftInput.request` (`LetterRequestMetadata`):
  - payer (string)
  - procedure_code (string)
  - site_of_care (string)
  - specialty (string)
  - dx_codes (list[string], minimally normalized by trimming, uppercasing, and removing spaces and `%`; there is no ICD-catalog or general unsafe-character validation)
- `LetterDraftInput`:
  - met_count, not_met_count, not_documented_count, needs_review_count
  - results[]:
    - key, label, status, reason
    - evidence (hint; optional)
    - evidence_snippets[] (list of strings; may be empty)
- `letter_type` (string):
  - `submission_cover_letter`
  - `missing_info_request`
  - `appeal_template`
- `LetterDraftInput.policy_trust_level` (string):
  - `demo`
  - `verified`

### 2.2 Forbidden Inputs
- raw clinical note text; the typed public drafting boundary has no note field and rejects extra fields
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
- Overall Status line: READY | PENDING_VERIFICATION | NOT_READY | CANNOT_DETERMINE | NEEDS_REVIEW
- Summary section (administrative framing only)
- Requirements section: each requirement shows status + reason + evidence
- Missing Documentation checklist:
  - emitted when at least one `NOT_DOCUMENTED` result exists
  - a `missing_info_request` with zero missing results omits the section by design
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
- letter_hash_sha256_16 (short audit linkage; exported artifacts may also include full letter text)

---

## 4) Status-conditioned Behavior

### 4.1 READY
- Requires all supplied requirement facts HUMAN_VERIFIED as well as all operators MET. The service checks proposal fingerprints before constructing this input; the write-only renderer trusts its supplied structured results.
- Allowed framing: “administrative submission readiness”
- Must NOT imply approval or clinical appropriateness

### 4.1a PENDING_VERIFICATION
- All operators MET with any fact UNVERIFIED must render PENDING_VERIFICATION.
- State that extraction is a drafting aid and human verification is still required; do not assert readiness for submission.

### 4.2 NOT_READY
- Must highlight NOT_MET requirements
- Must not blame missing documentation
- Must not propose clinical changes; may reference documentation thresholds via existing reasons/hints only

### 4.3 CANNOT_DETERMINE
- Must emphasize missing documentation (NOT_DOCUMENTED)
- Must include Missing Documentation checklist
- Must not imply criteria failure

### 4.4 NEEDS_REVIEW
- Must identify documented results that could not be evaluated against configured categories
- Must state that the disposition is not an adjudicated criteria failure
- Must not describe `NEEDS_REVIEW` requirements as threshold failures

---

## 5) Enumerated Prohibited-Phrase Check

After composing a draft, the implementation performs a case-insensitive substring check for the following configured phrases outside the `Dx codes:` header line. A detected phrase returns `DRAFT_BLOCKED`:
- “clinical diagnosis”
- “new diagnosis”
- “diagnosed with”
- “dx”
- “impression”
- “assessment”
- “hx”
- “history”
- “treatment”
- “medically necessary” (unless explicitly sanctioned by policy module; default: prohibited)
- “meets medical necessity”
- “medical necessity determination”
- “recommended”
- “should start”
- “should take”
- “high risk”
- “risk score”
- “probability of approval”
- “approval is expected”
- “approval likely”
- “likely to be approved”
- “will be approved”
- “guaranteed approval”
- “authorization approved”
- “payer will authorize”
- “clinically indicated” (default: prohibited)
- dosing patterns consisting of a number adjacent to `mg`, `mcg`, `g`, `mL`, `units`, `IU`, `tablets`, or `capsules`, or the frequency forms `daily`, `BID`, `TID`, `QID`, `q#h`, `every N hours`, or `N times per day`

Administrative references to already supplied Dx codes or requirement labels such as "diagnosis documented" are allowed when they are copied from request fields, rule labels, or evidence snippets.

Known limitation: this is an enumerated substring and dosing-pattern check, not a semantic classifier or comprehensive guarantee. Clinical, approval, or dosing-language variants outside the configured checks may pass through when present in caller-supplied result text.

---

## 6) Evidence Rules (Critical)

For each requirement:
- MUST include:
  - Evidence snippet(s) OR “No supporting snippet available.”
- Evidence snippet(s) are:
  - sourced from `evidence_snippets` only
  - trimmed and truncated to at most 25 whitespace-delimited words
  - rejoined with normalized spaces when truncated
- Requirement reasons are copied from the supplied structured evaluation and are not independently checked against evidence snippets; evidence snippets themselves are copied and truncated as described above.

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

- Current version: 1.2
- Any behavioral modification requires:
  - updating this contract
  - updating/adding tests
  - bumping letter_version
