# Refusal Is a Feature (Safety Narrative)

Project: Prior Authorization Readiness Copilot  
Purpose: Explain why “CANNOT_DETERMINE” is the correct, safer outcome when documentation is missing.

---

## 1) The Core Design Choice

This system is **administrative decision support**, not clinical judgment and not approval prediction.

It answers:
- “Is the request administratively ready based on documented criteria?”

It does NOT answer:
- “Is the procedure appropriate?”
- “Will this be approved?”
- “What should the clinician do?”

---

## 2) Why Missing Documentation Forces Refusal

Clinical notes are often incomplete or inconsistent.

If a required criterion is **not documented**, the safest output is:
- **CANNOT_DETERMINE**

Because any alternative requires guessing:
- inferring facts the note does not state
- “helpfully” assuming negatives (dangerous)
- silently filling gaps (non-auditable)

This system refuses because it is designed to be **auditable and defensible**.

---

## 3) Frozen Invariants (Safety Rails)

The system enforces:

- Any NOT_DOCUMENTED ⇒ overall must be CANNOT_DETERMINE
- Any NOT_MET (and no NOT_DOCUMENTED) ⇒ overall must be NOT_READY
- No blockers ⇒ overall must be READY

Invariant violations are surfaced explicitly (UI + audit).

---

## 4) Example: Why CANNOT_DETERMINE Is Correct

Scenario:
- Payer requires documented AHI for OSA pathway
- Note says: “AHI not stated.”

Outcome:
- Requirement AHI status = NOT_DOCUMENTED
- Overall status = CANNOT_DETERMINE
- Letter includes a Missing Documentation checklist item:
  - “Provide numeric AHI value (e.g., ‘AHI 22’).”

Key point:
- The system does not assume the patient fails criteria.
- The system does not invent AHI values.
- The system makes the missing documentation explicit.

---

## 5) Why This Improves Trust

This refusal behavior:
- prevents silent hallucinations
- enables reproducible outcomes
- supports payer-facing defensibility
- makes it easy for users to correct the record (checklist)

Refusal is a feature because it prioritizes:
- accuracy over convenience
- auditability over “smooth output”
- explicit uncertainty over fabricated certainty

---

## 6) Practical Boundary (Model Usage)

- Extraction + evaluation: deterministic (rules-first)
- Letter generation: write-only, downstream of deterministic outputs
- The letter generator cannot change statuses or infer facts

This preserves a clear separation between:
- documentation assessment
- administrative readiness
- narrative formatting
