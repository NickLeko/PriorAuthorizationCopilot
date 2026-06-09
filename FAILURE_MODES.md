# FAILURE_MODES.md
## Failure Modes, Safety Analysis, and Mitigations

**Project:** Prior Authorization Readiness Copilot  
**Owner:** Nicholas Leko  
**Last Updated:** June 9, 2026
**Status:** Versioned current behavior. Changes should update tests and docs.

---

## 1) Scope and Safety Posture

Current repo status:
- deterministic implementation
- no LLM implementation
- synthetic inputs only

This system is **administrative decision support** for prior authorization readiness.

It evaluates whether payer-required administrative criteria are:
- documented and met (`MET`)
- documented but not met (`NOT_MET`)
- not documented (`NOT_DOCUMENTED`)

It then derives an overall readiness status:
- `READY`
- `NOT_READY`
- `CANNOT_DETERMINE`

The system is intentionally:
- **non-predictive**
- **non-clinical**
- **non-autonomous**
- **refusal-first when missingness exists**

---

## 2) Safety-Critical Design Guarantees (Invariants)

### 2.1 Current Readiness Invariants
- Any `NOT_DOCUMENTED` ⇒ overall status **must** be `CANNOT_DETERMINE`
- Any `NOT_MET` (and no `NOT_DOCUMENTED`) ⇒ overall status **must** be `NOT_READY`
- No blockers ⇒ overall status **must** be `READY`

Invariant violations are surfaced in:
- UI banners
- audit output
- tests (behavioral contract)

### 2.2 “No Inference” Guarantee
- Extraction is deterministic and span-evidenced
- Missing documentation is preserved as `None` / `NOT_DOCUMENTED`
- No silent defaults

### 2.3 Write-only Letter Guarantee
Letter drafting:
- cannot access raw note text
- cannot change requirement results or readiness status
- cannot add facts that are not directly supported by evidence snippets
- must include non-guarantee framing (“does not guarantee payer approval”)

### 2.4 Policy Drift Governance Guarantee
- Policy drift detection for configured monitored sources only triggers **human review**
- Rules are never auto-updated
- Policy meaning is never inferred (no LLM policy interpretation)
- UI gates evaluation if drift is detected for a monitored source (`REVIEW_REQUIRED` acknowledgement required)

---

## 3) Failure Mode Taxonomy

### FM-1: False READY (Unsafe Over-Trust)
**Definition:** System outputs `READY` when criteria are actually missing or failing.

**Primary causes:**
- Extraction over-reads numbers (e.g., symptom duration misread as PT duration)
- Regex false positives under noisy notes
- Rule mapping mismatch vs policy source

**Mitigations:**
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

### FM-3: Misclassification Between NOT_MET vs NOT_DOCUMENTED
**Definition:** System marks a requirement as failing (`NOT_MET`) when it is actually missing, or vice versa.

**Primary causes:**
- Ambiguous phrasing (e.g., “trialed PT” with no duration)
- Implicit documentation without thresholds

**Mitigations:**
- Hard separation: values required for `NOT_MET`; otherwise treat as missing
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
- No persistence of raw note text
- Audit contains only note hash and spans (for synthetic/demo)
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
