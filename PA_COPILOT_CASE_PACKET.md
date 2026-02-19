# Prior Authorization Copilot  
## Governance-First AI for Administrative Readiness

Author: Nicholas Leko  
Role Target: AI Product Manager (Healthcare)

---

# 1. Problem Framing

Prior Authorization (PA) is a high-friction administrative process involving:

- CPT/ICD validation
- Insurance eligibility confirmation
- Medical necessity documentation
- Policy compliance checks
- Manual intake and review cycles

Common failure modes:

- Missing documentation
- Incorrect coding
- Policy mismatches
- Delayed submission due to incomplete packets
- Rework loops between provider and payer

Operational consequences:

- Increased time-to-treatment
- Staff burnout
- High administrative overhead
- Avoidable denials

---

# 2. Product Objective

Build a governance-first AI Copilot that:

- Evaluates administrative readiness (NOT medical necessity)
- Identifies missing documentation
- Flags policy conflicts
- Drafts structured readiness summaries
- Reduces rework before submission

Non-Goals:

- No autonomous submission
- No clinical judgment
- No medical decision-making
- No policy override

Design Principle:
Administrative completeness > automation rate  
Safety > speed

---

# 3. Workflow Integration (Conceptual SMART on FHIR)

Launch:

1. User opens patient chart
2. SMART app launches
3. Scoped OAuth token issued
4. Copilot retrieves required FHIR resources

Required Resources:

- Patient
- Coverage
- Condition (ICD)
- Procedure / ServiceRequest (CPT)
- Observation / DiagnosticReport
- DocumentReference (notes)

Data Handling:

- Structured data prioritized
- Narrative used only as supplemental evidence
- No raw PHI logged
- All logs hashed + redacted

Write-Back:

- Structured draft only
- Human confirmation required
- No auto-submission

Fail-Closed Policy:
If required structured data missing → NOT_READY or REFUSAL

---

# 4. Evaluation System

Primary Metrics:

- Administrative readiness accuracy
- Blocking issue precision
- Refusal correctness
- Override rate
- Time-to-decision delta

Safety Metrics:

- False READY rate (critical)
- Policy drift detection
- Invariant violations
- PHI leakage incidents (must be zero)

Decision Policy:

READY  
NOT_READY  
REFUSAL  

Auto-ready prohibited in v1.

Human-in-the-loop required for all submissions.

Rollout Strategy:

Shadow Mode → Assisted Mode → Limited Auto Draft → Expanded Use

---

# 5. Risk Register (Top 5)

1. False READY leading to denial
   → Strict structured validation + fail-closed logic

2. PHI leakage in logs
   → Hash-only storage + redaction layer

3. Policy drift
   → Version-locked policy + drift gating tests

4. Over-trust by staff
   → Explicit draft labeling + override tracking

5. Incomplete EHR data
   → Resource validation + incomplete context flag

---

# 6. Operational Impact Model

Projected Improvements (Shadow Mode Baseline Required):

- Reduced intake rework
- Reduced documentation back-and-forth
- Lower denial due to missing info
- Staff time saved per submission
- Improved SLA adherence

Optimization is measured on:
Rework reduction + throughput gain  
NOT on raw automation rate

---

# 7. Why This Demonstrates AI PM Readiness

This project shows ability to:

- Scope AI safely in regulated healthcare context
- Design evaluation systems beyond “accuracy”
- Anticipate integration + compliance constraints
- Define non-goals to prevent unsafe scope creep
- Translate workflow into deterministic decision logic
- Build governance before optimization

This is a productization exercise — not a model demo.

---

# 8. If Extended to Production

Next Steps:

- Real SMART on FHIR integration
- Marketplace approval pathway
- Pilot with defined success gates
- Drift monitoring dashboard
- Override analytics review
- Security audit + BAA readiness

---

# Summary

Prior Authorization Copilot is a governance-first administrative AI system designed to reduce workflow friction while preserving safety, auditability, and compliance.

It demonstrates how AI can be deployed responsibly in healthcare without overreaching into clinical autonomy.