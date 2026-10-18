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
| invalid_raw_responses | 0 |
| extraction_failures | 0 |
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
| downstream_requirement_status_difference_rate | 1 / 11 | 9.0909% | requirements in successful three-mode cases; any mode differs |

## Response accounting

Hand-authored and simulated responses are never measured LLM performance.

### actual_model

| Count or rate | Value |
| --- | --- |
| attempted_cases | 0 |
| declared_responses_received | 0 |
| responses_received | 0 |
| valid_adapted_responses | 0 |
| invalid_responses | 0 |
| extraction_failures | 0 |
| missing_stored_responses | 0 |
| file_integrity_failures | 0 |
| malformed_storage_failures | 0 |
| capture_identity_failures | 0 |
| note_identity_failures | 0 |
| not_attempted_cases | 177 |
| successful_three_mode_evaluations | 0 |
| invalid_recorded_response_rate | 0 / 0; not available; adapter-rejected / validity-assessed raw responses; excludes provider, missing-file, storage and capture-identity failures |
| end_to_end_usable_response_rate | 0 / 0; not available; valid adapted responses / all selected model attempts, including all failures |

### synthetic_raw_demonstration

| Count or rate | Value |
| --- | --- |
| attempted_cases | 0 |
| declared_responses_received | 0 |
| responses_received | 0 |
| valid_adapted_responses | 0 |
| invalid_responses | 0 |
| extraction_failures | 0 |
| missing_stored_responses | 0 |
| file_integrity_failures | 0 |
| malformed_storage_failures | 0 |
| capture_identity_failures | 0 |
| note_identity_failures | 0 |
| not_attempted_cases | 177 |
| successful_three_mode_evaluations | 0 |
| invalid_recorded_response_rate | 0 / 0; not available; adapter-rejected / validity-assessed raw responses; excludes provider, missing-file, storage and capture-identity failures |
| end_to_end_usable_response_rate | 0 / 0; not available; valid adapted responses / all selected model attempts, including all failures |

### hand_authored_adapted

| Count or rate | Value |
| --- | --- |
| selected_recordings | 4 |
| valid_recordings | 4 |
| missing_recordings | 0 |
| malformed_recordings | 0 |
| integrity_failures | 0 |
| measured_llm_performance | False |

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

The default recordings and bundled raw-response examples are hand-authored synthetic data, not produced by a real LLM. This run's declared population, provenance and coverage are shown above. The three Phase 2 fixture notes do not exactly match this corpus and were not silently substituted.
Absent recordings and extraction failures are coverage outcomes, never MISSING clinical facts. Missing policy scope produces extraction-only comparisons.
Rates include the shared-error demonstration, describe only these compared proposals, and do not estimate correctness, precision, recall, sensitivity, or population performance.
Citation comparisons cover retained spans only; combined totals can be unknown. Numeric literal flags are advisory and can flag valid unit normalization.
The historical governance clock does not refresh policy monitoring. All initial comparisons are unverified; results are stored outside production archives.
