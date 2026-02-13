# Operational Metrics Dashboard (Design Concept)

**Project:** Prior Authorization Readiness Copilot  
**Purpose:** Define measurable outcomes and KPI framework for operational deployment  
**Status:** Conceptual design (not production-deployed)

---

## Overview

If deployed in a live PA workflow, this system would track three categories of metrics:
1. **Model Quality Metrics** (technical performance)
2. **Operational Impact Metrics** (business outcomes)
3. **Governance Metrics** (safety and compliance)

This document demonstrates product thinking around **what to measure** and **how to measure it**.

---

## Model Quality Metrics

### Extraction Precision
**Definition:** Percentage of extracted facts that are verified as correct by human review.

**Measurement approach:**
```sql
-- Sample 100 random cases per week for human audit
SELECT 
  DATE_TRUNC('week', timestamp_utc) AS week,
  COUNT(*) AS total_facts_extracted,
  SUM(CASE WHEN human_verified = TRUE THEN 1 ELSE 0 END) AS correct_facts,
  ROUND(100.0 * correct_facts / total_facts_extracted, 1) AS precision_pct
FROM extraction_audit_log
WHERE human_verified IS NOT NULL
GROUP BY week
ORDER BY week DESC;
```

**Target:** ≥95% precision on sampled cases

---

### Evidence Snippet Coverage
**Definition:** Percentage of requirement results that include at least one supporting evidence snippet.

**Measurement approach:**
```sql
SELECT 
  payer,
  procedure_code,
  COUNT(*) AS total_requirements_evaluated,
  SUM(CASE WHEN evidence_snippets_count > 0 THEN 1 ELSE 0 END) AS with_evidence,
  ROUND(100.0 * with_evidence / total_requirements_evaluated, 1) AS coverage_pct
FROM requirement_results_log
GROUP BY payer, procedure_code
ORDER BY coverage_pct ASC;
```

**Target:** ≥90% coverage (lower coverage indicates extraction gaps)

---

### Invariant Violation Rate
**Definition:** Percentage of evaluation runs where frozen invariants are violated (system consistency check).

**Measurement approach:**
```sql
SELECT 
  DATE_TRUNC('day', timestamp_utc) AS day,
  COUNT(*) AS total_evaluations,
  SUM(CASE WHEN invariant_errors_count > 0 THEN 1 ELSE 0 END) AS violations,
  ROUND(100.0 * violations / total_evaluations, 1) AS violation_rate_pct
FROM pa_audit_log
GROUP BY day
ORDER BY day DESC;
```

**Target:** 0% (any violation is a build defect requiring immediate fix)

---

### Refusal Rate by Payer
**Definition:** Percentage of cases resulting in `CANNOT_DETERMINE` due to missing documentation.

**Measurement approach:**
```sql
SELECT 
  payer,
  COUNT(*) AS total_cases,
  SUM(CASE WHEN overall_status = 'CANNOT_DETERMINE' THEN 1 ELSE 0 END) AS refusals,
  ROUND(100.0 * refusals / total_cases, 1) AS refusal_rate_pct
FROM pa_audit_log
GROUP BY payer
ORDER BY refusal_rate_pct DESC;
```

**Expected range:** 10-30% (higher = more documentation gaps; lower may indicate under-refusal)

**Interpretation:** High refusal rates indicate either (a) poor documentation practices or (b) overly strict extraction patterns.

---

## Operational Impact Metrics

### Time Saved Per PA Case
**Definition:** Reduction in staff time spent on PA readiness review.

**Baseline (manual process):**
- Average time per PA case: **15 minutes**
  - 5 min: locate and read clinical note
  - 4 min: cross-check payer criteria
  - 3 min: identify missing elements
  - 3 min: draft request or missing-info letter

**With system:**
- Average time per PA case: **6 minutes**
  - 2 min: upload note + run evaluation
  - 2 min: review blocking items
  - 2 min: finalize letter or request additional documentation

**Time saved:** 15 min - 6 min = **9 minutes per case** (60% reduction)

**Measurement approach:**
```sql
-- Aggregate time savings across all cases
SELECT 
  DATE_TRUNC('month', timestamp_utc) AS month,
  COUNT(*) AS cases_processed,
  COUNT(*) * 9 AS total_minutes_saved,
  ROUND(COUNT(*) * 9 / 60.0, 1) AS total_hours_saved
FROM pa_audit_log
GROUP BY month
ORDER BY month DESC;
```

---

### Projected Annual Labor Savings
**Assumption:** 100 PA cases per week, 52 weeks/year

**Calculation:**
- Cases per year: 100 × 52 = **5,200 cases**
- Time saved per case: **9 minutes**
- Total time saved: 5,200 × 9 = **46,800 minutes = 780 hours**
- Hourly labor cost (PA coordinator): **$30/hour** (loaded cost with benefits)
- **Annual savings: 780 hours × $30 = $23,400**

**At scale (500 cases/week):**
- **Annual savings: $117,000**

**Measurement approach:**
Track actual staff hours before/after system deployment via time-tracking integration.

---

### Documentation Rework Reduction
**Definition:** Percentage reduction in PA cases requiring resubmission due to incomplete documentation.

**Baseline denial rate (incomplete documentation):** 25%  
**Target denial rate (with system):** 10%  
**Reduction:** 15 percentage points

**Measurement approach:**
```sql
-- Compare denial rates before/after system deployment
SELECT 
  deployment_period, -- 'before' or 'after'
  COUNT(*) AS total_submissions,
  SUM(CASE WHEN denial_reason = 'incomplete_documentation' THEN 1 ELSE 0 END) AS incomplete_denials,
  ROUND(100.0 * incomplete_denials / total_submissions, 1) AS denial_rate_pct
FROM pa_submission_outcomes
GROUP BY deployment_period;
```

**Expected impact:**
- Fewer resubmissions → faster patient care access
- Reduced staff rework → lower operational costs

---

### Missing Documentation Identification Rate
**Definition:** Percentage of cases where the system correctly identifies missing elements that would have caused denial.

**Measurement approach:**
Human review of `CANNOT_DETERMINE` cases to validate that flagged missing elements were actually required.
```sql
-- Sample 50 CANNOT_DETERMINE cases per month for validation
SELECT 
  DATE_TRUNC('month', timestamp_utc) AS month,
  COUNT(*) AS total_refusal_cases_sampled,
  SUM(CASE WHEN human_validated_missing = TRUE THEN 1 ELSE 0 END) AS correct_identifications,
  ROUND(100.0 * correct_identifications / total_refusal_cases_sampled, 1) AS identification_accuracy_pct
FROM refusal_validation_log
GROUP BY month;
```

**Target:** ≥90% accuracy (system correctly identifies what's missing)

---

## Governance Metrics

### Policy Drift Detection Rate
**Definition:** Percentage of monitored policy sources where content changes are detected.

**Measurement approach:**
```sql
-- Count drift events from append-only drift log
SELECT 
  DATE_TRUNC('month', detected_at_utc) AS month,
  COUNT(DISTINCT id) AS unique_policies_monitored,
  SUM(CASE WHEN event = 'POLICY_DRIFT_DETECTED' THEN 1 ELSE 0 END) AS drift_events,
  ROUND(100.0 * drift_events / unique_policies_monitored, 1) AS drift_rate_pct
FROM policy_drift_log
GROUP BY month
ORDER BY month DESC;
```

**Expected:** 5-10% monthly (payer policies change periodically, not constantly)

**Action trigger:** Any drift event requires human review and potential rule update.

---

### Rule Staleness Window
**Definition:** Time elapsed between policy drift detection and rule update.

**Measurement approach:**
```sql
-- Calculate lag between drift detection and rule commit
SELECT 
  id AS policy_source_id,
  detected_at_utc,
  rule_updated_at_utc,
  EXTRACT(EPOCH FROM (rule_updated_at_utc - detected_at_utc)) / 86400.0 AS lag_days
FROM policy_drift_resolution_log
WHERE rule_updated_at_utc IS NOT NULL
ORDER BY lag_days DESC;
```

**Target:** <7 days (minimize window where rules may be stale)

---

### Audit Trail Completeness
**Definition:** Percentage of evaluation runs with complete audit artifacts (no missing fields).

**Measurement approach:**
```sql
SELECT 
  COUNT(*) AS total_evaluations,
  SUM(CASE WHEN audit_complete = TRUE THEN 1 ELSE 0 END) AS complete_audits,
  ROUND(100.0 * complete_audits / total_evaluations, 1) AS completeness_pct
FROM pa_audit_log;
```

**Target:** 100% (any incomplete audit is a governance failure)

---

## Dashboard Mockup (Conceptual)

### Executive Summary View
```
┌─────────────────────────────────────────────────────────────┐
│  PA Readiness Copilot — Monthly Performance (Feb 2026)     │
├─────────────────────────────────────────────────────────────┤
│  Cases Processed:        412                                │
│  Time Saved:             62 hours                           │
│  Projected Annual ROI:   $23,400                            │
│  Refusal Rate:           18%                                │
│  Extraction Precision:   97%                                │
│  Invariant Violations:   0                                  │
│  Policy Drift Events:    1 (reviewed, rules updated)        │
└─────────────────────────────────────────────────────────────┘
```

### Detailed Metrics by Payer
```
┌──────────┬────────┬──────────┬──────────────┬─────────────┐
│  Payer   │ Cases  │ Refusal% │ Avg Time (m) │ Precision%  │
├──────────┼────────┼──────────┼──────────────┼─────────────┤
│  Aetna   │  180   │   15%    │      6.2     │    98%      │
│  BCBS    │  120   │   22%    │      6.8     │    96%      │
│  UHC     │  112   │   19%    │      5.9     │    97%      │
└──────────┴────────┴──────────┴──────────────┴─────────────┘
```

---

## Key Insights for Product Decisions

### High Refusal Rate → Documentation Workflow Improvement
If refusal rate is >30% for a specific payer:
- **Hypothesis:** Documentation templates are missing required fields
- **Action:** Work with PA coordinators to update intake forms

### Low Evidence Coverage → Extraction Pattern Gaps
If evidence snippet coverage is <85%:
- **Hypothesis:** Extraction patterns are under-capturing certain phrasing variants
- **Action:** Review cases with missing evidence and expand regex/context rules

### Policy Drift Lag → Governance Process Improvement
If rule staleness window is >14 days:
- **Hypothesis:** Rule update process is too manual or under-resourced
- **Action:** Automate policy diff review and prioritize high-volume payers

---

## Limitations & Caveats

- **No production deployment:** All metrics are **conceptual projections** based on synthetic test cases
- **Time savings estimates:** Based on workflow analysis, not actual time-motion studies
- **ROI calculations:** Assume stable case volume and labor costs; real-world variance applies
- **SQL pseudocode:** Illustrative only; actual schema and queries would depend on deployment database

This dashboard demonstrates **product thinking around metrics ownership**, not claims of deployed performance.

---

**Version:** 1.0  
**Last Updated:** February 2026  
**Author:** Nicholas Leko
