# Prior Authorization Copilot  
## Conceptual EHR Integration Architecture (SMART on FHIR)

**Status:** Conceptual Production Integration Design  
**Scope:** Defines how PA Copilot would integrate into a live EHR environment.  
**Non-Goal:** This document does NOT implement integration. It defines constraints, risks, and safety posture.

---

# 1. Integration Objective

Enable provider staff to use PA Copilot within their EHR workflow while:

- Maintaining HIPAA compliance
- Preventing PHI leakage
- Preserving auditability
- Avoiding unsafe write-back automation
- Supporting human-in-the-loop review

This design assumes SMART on FHIR integration within a certified EHR ecosystem (e.g., Epic, Cerner, Athenahealth).

---

# 2. High-Level Architecture

## 2.1 Launch Flow (SMART on FHIR)

1. User opens patient chart in EHR.
2. User launches PA Copilot via SMART on FHIR app.
3. EHR issues OAuth2 access token with scoped permissions.
4. Copilot retrieves required FHIR resources.
5. Copilot performs readiness evaluation.
6. Copilot returns structured output for user review.
7. Optional: structured draft is written back (non-authoritative).

---

# 3. Required FHIR Resources

| Resource | Purpose | Risk Surface |
|-----------|---------|--------------|
| Patient | Identity context | PHI |
| Coverage | Insurance information | PHI |
| Condition | Diagnosis codes | PHI |
| Procedure / ServiceRequest | Requested service | PHI |
| Observation | Labs/imaging | PHI |
| DocumentReference | Clinical notes | High PHI risk |
| Practitioner | Ordering provider | Moderate PHI |

**Invariant:** Copilot never modifies original clinical documentation.

---

# 4. Data Minimization Policy

Copilot retrieves ONLY:

- Structured fields necessary for readiness validation
- Clinical note excerpts relevant to medical necessity

Copilot MUST NOT:
- Store raw PHI in logs
- Persist full clinical notes
- Cache patient-level data beyond active session

All logs use:
- Hashed note identifiers
- Redacted structured fields
- No raw narrative text

---

# 5. Write-Back Strategy

Copilot may:

- Generate structured draft summary
- Populate PA intake form fields
- Generate checklist of missing documentation

Copilot MUST NOT:

- Submit PA automatically
- Modify diagnosis codes
- Modify clinical documentation
- Trigger payer-facing communication autonomously

All outputs require explicit human confirmation.

---

# 6. Human-in-the-Loop Controls

Auto-ready determination is prohibited in v1.

Copilot outputs one of:

- READY (administratively complete)
- NOT_READY (blocking issues)
- REFUSAL (insufficient context)

Human reviewer must approve any generated content before submission.

---

# 7. Fallback & Failure Modes

## 7.1 Token Expiration
→ Prompt user to re-authenticate.

## 7.2 Missing Resource
→ Trigger NOT_READY with explicit missing data list.

## 7.3 API Latency / Timeout
→ Fail closed (no inference without complete data).

## 7.4 Partial Data Availability
→ Explicitly mark evaluation as “Incomplete Data Context.”

---

# 8. Audit Logging Requirements

Each session logs:

- Timestamp
- User ID (role-based)
- Patient encounter ID (hashed)
- FHIR resources accessed
- Model version
- Policy version
- Determination result
- Blocking issues
- Invariant violations
- Write-back action (if any)

Logs must be:

- Immutable
- Tamper-evident
- Exportable for compliance review

---

# 9. Security Controls

- OAuth2 + SMART scopes
- Role-based access control
- TLS encryption in transit
- No PHI persisted outside secure environment
- Strict environment separation (dev/test/prod)
- Prompt injection detection layer (if narrative used)

---

# 10. Risk Register (Integration-Specific)

| Risk | Mitigation |
|------|------------|
| PHI leakage in logs | Structured redaction + hash-only logging |
| EHR data mismatch | Validate required resource presence before inference |
| Over-trust of draft | Explicit “Draft – Requires Review” labeling |
| Silent integration failure | Fail-closed policy |
| Policy-resource misalignment | Version-locked policy + validation tests |

---

# 11. Production Readiness Checklist

- [ ] HIPAA security review
- [ ] BAA in place
- [ ] EHR marketplace approval
- [ ] SMART scope audit
- [ ] Logging validation
- [ ] Shadow mode pilot
- [ ] Human override rate tracking
- [ ] Rollout gating approval

---

# 12. Design Principle

Copilot is a decision-support augmentation layer.

It does not:

- Replace clinical judgment
- Submit prior authorizations autonomously
- Override payer policy

It exists to reduce administrative burden while preserving safety and compliance.