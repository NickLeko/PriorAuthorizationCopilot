# Offline three-mode synthetic experiment

Offline response attempts; provenance is declared per population.

Structural comparisons only; no clinical accuracy claim. Labeled shared-error demonstrations compared: 0.

## Coverage

| Count | Cases |
| --- | ---: |
| eligible_synthetic_cases | 177 |
| policy_supported_cases | 148 |
| incomplete_policy_scope_cases | 29 |
| unsupported_policy_scope_cases | 0 |
| valid_recordings | 1 |
| without_recordings | 170 |
| absent_manifest_entries | 169 |
| missing_recording_files | 1 |
| malformed_recordings | 0 |
| integrity_failures | 1 |
| rejected_recordings | 5 |
| invalid_raw_responses | 4 |
| extraction_failures | 1 |
| successful_three_mode_cases | 1 |
| extraction_only_compared_cases | 0 |
| comparison_failures | 0 |
| known_shared_error_demonstrations | 0 |

## Structural rates

| Metric | Numerator / denominator | Percent | Population |
| --- | ---: | ---: | --- |
| value_agreement_rate | 1 / 1 | 100.0% | both-CAPTURED fact pairs |
| state_disagreement_rate | 2 / 12 | 16.6667% | valid compared fact pairs |
| citation_disagreement_rate | 2 / 12 | 16.6667% | valid fact pairs; retained citation sets, including empty sets |
| citation_order_disagreement_rate | 2 / 12 | 16.6667% | valid fact pairs; retained citation lists |
| dual_needs_review_rate | 2 / 12 | 16.6667% | valid compared facts |
| downstream_requirement_status_difference_rate | 2 / 3 | 66.6667% | requirements in successful three-mode cases; any mode differs |

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
| not_attempted_cases | 177 |
| successful_three_mode_evaluations | 0 |
| invalid_recorded_response_rate | 0 / 0; not available; adapter-rejected / adaptation-attempted raw responses; excludes provider, missing-file, integrity and storage failures |
| end_to_end_usable_response_rate | 0 / 0; not available; valid adapted responses / all selected model attempts, including all failures |

### synthetic_raw_demonstration

| Count or rate | Value |
| --- | --- |
| attempted_cases | 8 |
| declared_responses_received | 7 |
| responses_received | 5 |
| valid_adapted_responses | 1 |
| invalid_responses | 4 |
| extraction_failures | 1 |
| missing_stored_responses | 1 |
| file_integrity_failures | 1 |
| malformed_storage_failures | 0 |
| not_attempted_cases | 169 |
| successful_three_mode_evaluations | 1 |
| invalid_recorded_response_rate | 4 / 5; 80.0%; adapter-rejected / adaptation-attempted raw responses; excludes provider, missing-file, integrity and storage failures |
| end_to_end_usable_response_rate | 1 / 8; 12.5%; valid adapted responses / all selected model attempts, including all failures |

### hand_authored_adapted

| Count or rate | Value |
| --- | --- |
| selected_recordings | 0 |
| valid_recordings | 0 |
| missing_recordings | 0 |
| malformed_recordings | 0 |
| integrity_failures | 0 |
| measured_llm_performance | False |

## Compared cases

| Case | Scope | Three-mode overall statuses |
| --- | --- | --- |
| inputs/synthetic_cases.json#CPAP-01-complete | SUPPORTED | regex_only: PENDING_VERIFICATION; llm_only: CANNOT_DETERMINE; dual: NEEDS_REVIEW |

## Shared-error demonstration

No shared-error demonstration was successfully compared in this run.

## Limits

The default recordings and bundled raw-response examples are hand-authored synthetic data, not produced by a real LLM. This run's declared population, provenance and coverage are shown above. The three Phase 2 fixture notes do not exactly match this corpus and were not silently substituted.
Absent recordings and extraction failures are coverage outcomes, never MISSING clinical facts. Missing policy scope produces extraction-only comparisons.
Rates include the shared-error demonstration, describe only these compared proposals, and do not estimate correctness, precision, recall, sensitivity, or population performance.
Citation comparisons cover retained spans only; combined totals can be unknown. Numeric literal flags are advisory and can flag valid unit normalization.
The historical governance clock does not refresh policy monitoring. All initial comparisons are unverified; results are stored outside production archives.
