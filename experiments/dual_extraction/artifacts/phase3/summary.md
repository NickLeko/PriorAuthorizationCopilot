# Offline three-mode synthetic experiment

Hand-authored synthetic recordings; no model was called.

Structural comparisons only; no clinical accuracy claim. Labeled shared-error demonstrations compared: 1.

## Coverage

| Count | Cases |
| --- | ---: |
| eligible_synthetic_cases | 177 |
| policy_supported_cases | 148 |
| incomplete_policy_scope_cases | 29 |
| unsupported_policy_scope_cases | 0 |
| valid_recordings | 4 |
| without_recordings | 173 |
| absent_manifest_entries | 173 |
| missing_recording_files | 0 |
| malformed_recordings | 0 |
| integrity_failures | 0 |
| rejected_recordings | 0 |
| successful_three_mode_cases | 3 |
| extraction_only_compared_cases | 1 |
| comparison_failures | 0 |
| known_shared_error_demonstrations | 1 |

## Structural rates

| Metric | Numerator / denominator | Percent | Population |
| --- | ---: | ---: | --- |
| value_agreement_rate | 15 / 17 | 88.2353% | both-CAPTURED fact pairs |
| state_disagreement_rate | 0 / 48 | 0.0% | valid compared fact pairs |
| citation_disagreement_rate | 3 / 48 | 6.25% | valid fact pairs; retained citation sets, including empty sets |
| citation_order_disagreement_rate | 3 / 48 | 6.25% | valid fact pairs; retained citation lists |
| dual_needs_review_rate | 2 / 48 | 4.1667% | valid compared facts |
| invalid_recorded_response_rate | 0 / 4 | 0.0% | available recording attempts; excludes absent/missing files |
| downstream_requirement_status_difference_rate | 1 / 11 | 9.0909% | requirements in successful three-mode cases; any mode differs |

## Compared cases

| Case | Scope | Three-mode overall statuses |
| --- | --- | --- |
| inputs/synthetic_cases.json#MRI-01-complete | SUPPORTED | regex_only: PENDING_VERIFICATION; llm_only: NOT_READY; dual: NEEDS_REVIEW |
| EXTRACTION_CONTRACT.md#neither_nor_negation | SUPPORTED | regex_only: PENDING_VERIFICATION; llm_only: PENDING_VERIFICATION; dual: PENDING_VERIFICATION |
| EXTRACTION_CONTRACT.md#unicode | SUPPORTED | regex_only: PENDING_VERIFICATION; llm_only: PENDING_VERIFICATION; dual: PENDING_VERIFICATION |
| EXTRACTION_CONTRACT.md#therapy_weeks | INCOMPLETE | extraction only; no scope invented |

## Shared-error demonstration

`EXTRACTION_CONTRACT.md#neither_nor_negation`: known neither/nor extraction limitation. Both proposals retain the unsupported affirmative diagnosis as AGREED_CAPTURE; clinical_verification=false and no automatic READY.

## Limits

The bundled recordings were deliberately hand-authored for four selected frozen notes, not produced by a real LLM. This run's coverage is shown above. The three Phase 2 fixture notes do not exactly match this corpus and were not silently substituted.
Absent recordings and extraction failures are coverage outcomes, never MISSING clinical facts. Missing policy scope produces extraction-only comparisons.
Rates include the shared-error demonstration, describe only these compared proposals, and do not estimate correctness, precision, recall, sensitivity, or population performance.
Citation comparisons cover retained spans only; combined totals can be unknown. Numeric literal flags are advisory and can flag valid unit normalization.
The historical governance clock does not refresh policy monitoring. All initial comparisons are unverified; results are stored outside production archives.
