# FAILURE_MODES.md
## Failure Modes, Safety Analysis, and Mitigations

**Project:** Prior Authorization Readiness Copilot  
**Owner:** Nicholas Leko  
**Last Updated:** September 4, 2026 — v1.5.0
**Status:** Versioned current behavior. Changes should update tests and docs.

---

## 1) Scope and Safety Posture

Current repo status:
- deterministic implementation
- no LLM implementation
- all bundled data is synthetic; input is not screened and must not contain real PHI, with screening remaining the operator's responsibility

Automated extraction is a **drafting aid, not a decision gate**. v1.4.0's posture over-trusted extraction. Negated diagnoses returned affirmative facts, contradicting the extraction contract as written. v1.5.0 resolves that contradiction by changing what the engine may assert rather than by making extraction match the contract. The language patterns remain unchanged, including known negation, temporality and attribution errors.

It evaluates whether payer-required administrative criteria are:
- documented and met (`MET`)
- documented but not met (`NOT_MET`)
- not documented (`NOT_DOCUMENTED`)
- documented but ambiguous, contradictory, uncertain, or not safely evaluable (`NEEDS_REVIEW`)

It then derives an overall readiness status:
- `READY`
- `PENDING_VERIFICATION`
- `NOT_READY`
- `CANNOT_DETERMINE`
- `NEEDS_REVIEW`

The system is intentionally:
- **non-predictive**
- **non-clinical**
- **non-autonomous**
- **refusal-first when missingness exists**

---

## 2) Safety-Critical Design Guarantees (Invariants)

### 2.1 Current Readiness Invariants
- Any `NOT_DOCUMENTED` ⇒ overall status **must** be `CANNOT_DETERMINE`
- Any `NEEDS_REVIEW` (and no `NOT_DOCUMENTED`) ⇒ overall status **must** be `NEEDS_REVIEW`
- Any `NOT_MET` (and no `NOT_DOCUMENTED` or `NEEDS_REVIEW`) ⇒ overall status **must** be `NOT_READY`
- No blockers and any unverified requirement fact ⇒ `PENDING_VERIFICATION`, submission readiness false
- No blockers and all requirement facts `HUMAN_VERIFIED` ⇒ `READY`
- `submission_readiness=true` additionally requires `READY`, current verified policy trust, a trustworthy active rulebook, and no unresolved or invalid governance state

Invariant violations are surfaced in:
- UI banners
- audit output
- tests (behavioral contract)

### 2.2 Source-location and verification guarantees
- Captured spans have original-note character offsets and exact source-slice text, including Unicode case expansion. This guarantees location integrity, not semantic support or complete context.
- Requirement facts default to `UNVERIFIED`. `HUMAN_VERIFIED` records reviewer/time and is bound to the exact request, rule bundle, proposal and evidence.
- A reviewer must leave unsupported facts unverified. Verification cannot edit scalars or override missing, ambiguous or failed requirements.
- Self-reported identity is not authentication. Rubber-stamping or fabricated attestations can still permit false READY; there is no production attestation store.

### 2.3 Write-only Letter Guarantee
Letter drafting:
- accepts only `LetterDraftInput`, whose typed request metadata has no `note_text` field and rejects extra fields
- cannot change requirement results or readiness status
- renders caller-supplied structured reasons without independently validating them against evidence snippets
- must include non-guarantee framing (“does not guarantee payer approval”)

### 2.4 Policy Drift Governance Guarantee
- Policy drift detection for configured monitored sources only triggers **human review**
- Rules are never auto-updated
- Policy meaning is never inferred (no LLM policy interpretation)
- UI gates evaluation if drift is detected for a monitored source (`REVIEW_REQUIRED` acknowledgement required)
- Acknowledgement permits inspection only; it does not restore verified trust or make `submission_readiness` true
- Malformed drift-log state and any recorded drift without an explicit resolution mechanism fail policy trust closed

---

## 3) Failure Mode Taxonomy

### FM-1: False READY (Unsafe Over-Trust)
**Definition:** System outputs `READY` when criteria are actually missing or failing.

**Primary causes:**
- Extraction over-reads numbers (e.g., symptom duration misread as PT duration)
- Regex false positives under noisy notes
- Rule mapping mismatch vs policy source

**Mitigations:**
- v1.5.0 blocks READY on automated extraction alone; every requirement fact needs human verification
- Conservative extraction patterns (therapy duration must be therapy-linked)
- Evidence spans attached to each extracted field
- Synthetic regression tests include noise and edge cases
- Policy drift gating to reduce stale-rule risk

**Residual risk:** Cannot be eliminated in free-text notes; requires human review.

**Revision note, June 9, 2026:** Fable 5 identified three false-positive extraction paths that could produce false `MET` determinations before this fix:
- negated therapy phrasing, such as `Patient denies completing PT x 8 weeks`, could be extracted as completed conservative therapy
- future-tense therapy phrasing, such as `Will start PT for 6 weeks next month`, could be extracted as completed conservative therapy
- therapy durations, such as `Completed PT for 6 weeks`, could leak into `symptom_duration_weeks`

These were failures in the over-extraction direction, which is the direction the safety contract is designed to minimize. The patched extractor now rejects locally negated or future-planned therapy durations and skips therapy-context durations when extracting symptom duration. Regression coverage was added for the original cases and related phrasing variants. The residual risk remains non-zero for untested free-text phrasing.

**Revision note, August 31, 2026:** Candidate resolution now also fails closed for the tested cross-therapy, non-patient attribution, future/hypothetical, uncertainty/question, and contradictory-finding phrase families. The bundled labeled fixture and direct adversarial tests include forward/reversed order and lexical variants. This is bounded deterministic coverage, not a claim of general clinical-language understanding or zero real-world false `READY` risk.

**Revision note, September 4, 2026:** The fourth audit reproduced affirmative proposals from negated diagnoses and strength, reflex qualifiers borrowed from pain, resolved findings, and unrelated therapy. These extraction errors remain. Automated all-MET cases now stop at PENDING_VERIFICATION. The borrowed sleep-study date was one case the existing design contained: v1.4.0 produced READY documentation status but submission_readiness=false under demo policy trust, as the README already allowed. This release also fixes Unicode offset corruption, long-lived service cache staleness after rule promotion, and unknown/misspelled monitoring frequencies disabling freshness enforcement. Exact contract examples and numbered guarantees are executable; finite tests cannot prove arbitrary clinical-language correctness.

---

### FM-2: False CANNOT_DETERMINE (Operational Friction)
**Definition:** System refuses (`CANNOT_DETERMINE`) even though documentation exists.

**Primary causes:**
- Under-capture of phrasing variants (“weakness absent”, “bowel/bladder intact”)
- Date formats not recognized for sleep study
- Imaging results described indirectly

**Mitigations:**
- Expand deterministic extraction patterns over time with tests
- Treat “imaging performed but unclear” as documented `inconclusive`
- Evidence snippets shown so humans can override with documentation edits

**Residual risk:** Some note styles remain unsupported; that’s acceptable given refusal-first posture.

---

### FM-3: Misclassification Between NOT_MET, NOT_DOCUMENTED, And NEEDS_REVIEW
**Definition:** System marks a requirement as failing (`NOT_MET`) when it is actually missing or unevaluable, or otherwise confuses the three states.

**Primary causes:**
- Ambiguous phrasing (e.g., “trialed PT” with no duration)
- Implicit documentation without thresholds

**Mitigations:**
- Hard separation: failed thresholds use `NOT_MET`, missing values use `NOT_DOCUMENTED`, and ambiguous, contradictory, uncertain, or otherwise unsafe-to-resolve values use `NEEDS_REVIEW`
- “duration not specified” ⇒ `NOT_DOCUMENTED`
- Rule reasons explicitly instruct what must be documented

---

### FM-4: Evidence Snippet Coverage Gaps
**Definition:** A requirement status is correct, but evidence snippet is missing.

**Primary causes:**
- Span capture misses the exact triggering substring
- Multi-sentence contexts

**Mitigations:**
- Evidence map stores spans from extraction layer
- UI shows “No supporting snippet available” (never invents evidence)
- Tests validate snippet presence for key pathways

**Residual risk:** Evidence gaps reduce reviewer trust; requires iterative pattern tuning.

---

### FM-5: Policy Drift (Stale Rules)
**Definition:** Payer changes policy; rules remain old; system produces outdated decisions.

**Primary causes:**
- External policy update
- Plan-specific variation not captured by general bulletin

**Mitigations:**
- Snapshot + hash drift detection
- Snapshot structure, source identity, timestamp, stored-content hash, and drift-log validation
- Diff artifact generation
- Append-only drift log
- UI `REVIEW_REQUIRED` gate

**Residual risk:** Drift between checks; mitigated by check frequency + governance.

---

### FM-6: Over-Trust in Generated Letter Text
**Definition:** User treats letter as authoritative or submits without review.

**Primary causes:**
- Automation bias
- Letter phrasing too strong

**Mitigations:**
- Deterministic drafting and prohibited-language constraints
- Explicit “does not guarantee payer approval” line
- No clinical recommendations; no prediction language
- Audit linkage via hash (traceability)

**Residual risk:** Human behavior; mitigated through UI framing and governance policies.

---

### FM-7: Misuse Outside Intended Scope
**Definition:** Used for real PHI, autonomous submission, or clinical decisioning.

**Mitigations:**
- Explicit non-goals in README, MODEL_CARD, and safety docs
- Runtime evaluation records retain the full request, including note text, and runtime exports serialize it; checked-in repository artifacts replace full `note_text` values with a short hash and `[redacted for repository]`
- Audit and export payloads include the request, note hash, facts, evidence spans, provenance, requirements, blockers, warnings, and metrics
- “Administrative decision support only” banner in UI

---

## 4) Monitoring & Kill Switches (Operational Controls)

- **Bundled synthetic eval mismatch in the UI** ⇒ local evaluation disabled
- **Pytest failure in CI** ⇒ treat as a regression
- **Policy drift detected for a monitored source** ⇒ evaluation gated behind acknowledgment
- **Invariant violation detected** ⇒ surfaced in UI + audit; treat as a build defect

---

## 5) Change Control

Any change to:
- extraction patterns
- requirement semantics
- overall readiness invariants
- letter drafting constraints
- drift gating behavior

requires:
- updated tests
- version bump
- updated docs (README, model card, safety docs, and this file as needed)

---
