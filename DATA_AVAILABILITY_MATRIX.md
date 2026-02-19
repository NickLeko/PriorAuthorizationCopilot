# Prior Authorization Copilot  
## Data Availability & Fallback Matrix

**Purpose:**  
Define required data elements for readiness evaluation, their source, and fallback logic if unavailable.

---

# 1. Core Administrative Data

| Data Element | FHIR Resource | Required? | If Missing | Risk Level |
|--------------|--------------|----------|-----------|------------|
| Insurance Plan | Coverage | Yes | NOT_READY | High |
| CPT/Procedure Code | Procedure / ServiceRequest | Yes | NOT_READY | High |
| ICD Diagnosis Code | Condition | Yes | NOT_READY | High |
| Ordering Provider | Practitioner | Yes | REFUSAL | Medium |

---

# 2. Clinical Support Data

| Data Element | FHIR Resource | Required? | If Missing | Risk Level |
|--------------|--------------|----------|-----------|------------|
| Recent Progress Note | DocumentReference | Conditional | Flag as missing evidence | High |
| Imaging Report | Observation / DiagnosticReport | Conditional | NOT_READY if policy requires | High |
| Lab Results | Observation | Conditional | Flag insufficient support | Medium |
| Prior Treatment History | Condition / Procedure | Conditional | Add caution tag | Medium |

---

# 3. Policy-Derived Requirements

| Policy Requirement | Data Source | Enforcement |
|--------------------|------------|------------|
| Age restrictions | Patient | Deterministic validation |
| Step therapy requirement | MedicationRequest | Conditional rule |
| Documentation window (e.g., within 6 months) | Observation date | Temporal validation |
| Site-of-care restriction | Encounter | Context validation |

---

# 4. Evaluation Guardrails

Copilot MUST:

- Validate presence of required structured codes
- Validate recency constraints
- Validate documentation existence
- Fail closed if required policy-linked data missing

Copilot MUST NOT:

- Infer missing structured codes from narrative alone
- Assume compliance without structured evidence
- Override payer policy

---

# 5. Data Freshness Rules

| Data Type | Acceptable Recency | Enforcement |
|-----------|-------------------|------------|
| Imaging | ≤ 6 months | NOT_READY if expired |
| Labs | ≤ 3 months (policy-dependent) | NOT_READY |
| Clinical Note | ≤ 30 days (if required) | Flag |

---

# 6. Data Quality Failure Modes

| Failure Mode | Example | Mitigation |
|--------------|---------|------------|
| Incorrect CPT code | Wrong modifier | Human confirmation required |
| Outdated diagnosis | Historical resolved condition | Date validation |
| Missing structured data but present in note | Narrative-only documentation | REFUSAL or manual review |
| Duplicate encounter data | Multiple entries | Deduplication logic |

---

# 7. Structured vs Narrative Handling

Structured data is always primary.

Narrative text:

- Used only for supplemental evidence
- Never sole source for deterministic decision
- Extracted with traceable snippet references
- Logged via hash only

---

# 8. Refusal Triggers

Copilot must refuse if:

- No CPT or ICD present
- Insurance plan not identifiable
- Policy version not loaded
- EHR data retrieval incomplete
- Conflicting structured data detected

---

# 9. Human Escalation Rules

Escalate to human review when:

- Confidence threshold below defined limit
- Policy rule partially satisfied
- Structured/narrative mismatch
- High-cost procedure category
- Pediatric or high-risk case

---

# 10. Design Philosophy

The Copilot evaluates readiness, not medical necessity.

If required structured evidence is missing, it fails closed.

Administrative completeness > automation rate.

Safety > speed.