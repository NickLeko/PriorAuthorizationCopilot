# Phase 2 results and accounting of changed expectations

November 17, 2026. Engine 2.7.1 on the branch `claude/phase2-per-course-therapy`, stacked on the evaluation work in pull request #23. Specification: [phase2_spec.md](phase2_spec.md). Not merged or deployed.

All notes are synthetic. Three labels are human-verified textual readings, the rest are provisional and agent-authored, and none has been reviewed by a clinician. Counts on the challenge set are known failures on selected notes, not rates.

## Measured results

From `python -m evaluation.report`, comparing PR #23's pre-change baseline with this branch.

| Set and tier | Measure | Before | After |
| --- | --- | --- | --- |
| Challenge, verified | False `MET` | 3 of 3 | 0 of 3 |
| Challenge, provisional | False `MET` | 11 of 15 | 5 of 15 |
| Challenge, provisional | Missed `MET` | 11 of 59 | 11 of 59 |
| Challenge, all scored | Predicted `NEEDS_REVIEW` (review burden) | 0 of 77 | 9 of 77 |
| Challenge, all scored | Exact agreement with labels | 52 of 77 | 61 of 77 |
| Challenge, case level | All requirements `MET` when one must not be | 8 of 12 | 3 of 12 |
| Bundled corpus, provisional | False `MET` / missed `MET` / review | 0 of 94 / 0 of 96 / 14 of 193 | unchanged |
| Framing controls, provisional | Missed `MET` / review | 2 of 80 / 0 of 80 | unchanged |

These match the specification's expected effect (section 6) exactly.

- **Resolved (9 labels):** CH-02 duration and response, CH-03 duration and response, CH-04 response, CH-05 duration and response, CH-15 duration and response. Each now returns `NEEDS_REVIEW`, as its label requires.
- **Kept:** CH-04's documented 8-week duration stays `MET`.
- **New false `MET` or new missed `MET`:** none in any set or tier.
- **Review burden:** all 9 new reviews are labels that require review. No review was added to the bundled corpus or the controls.
- **Still false `MET` (5, out of scope):** CH-06 historical exam, CH-14 response reversed in the next sentence, CH-16 imaging and symptom duration, CH-17 knee therapy.

## Every changed expectation

Six test files and twelve generated files changed. Nothing else in `test/` changed.

| File | Change | Reason |
| --- | --- | --- |
| `test/test_attestation_context.py` | `test_n1b_…`: the two therapy facts are expected `NEEDS_REVIEW`, and overall status `NEEDS_REVIEW`, instead of four `MET` and `PENDING_VERIFICATION`. Reviewer-context, attestation, checkbox and correction-window assertions are unchanged and pass. | Owner-approved (spec section 7). The copied 2019 course was a false `MET`. |
| `test/test_requirement_eval_datasets.py` | `test_known_lumbar_failures_…` now pins the post-change baseline: the 9 resolved labels must not reappear, and the remaining known failures stay pinned. `test_challenge_results_…` expects `5 of 15` instead of `11 of 15`. | These tests pinned the pre-change baseline so that this change would have to update them deliberately. The new values are the measured results above. |
| `test/test_api.py` | `app_version` expected `2.7.1`. | Version bump required by the specification. |
| `test/test_v210_safety.py` | `engine_version` expected `2.7.1`. | Version bump. |
| `test/test_phase2_therapy_courses.py` | New: 7 framing pairs, 16 multiple-course, historical and response-change cases, a service-level CH-04 check, and the framing controls. | Required by the specification (sections 5.1 to 5.3). |
| `test/golden/evaluations/*.json` (6 files) | `engine_version` field only. | Version bump. No status, fact or evidence changed. |
| `docs/artifacts/*.json` (6 files) | `engine_version` or `app_version` field only. | Version bump. |

**Unchanged on purpose:**

- The stopped-analgesic test in `test/test_service.py` still expects 6 weeks and no improvement.
- No strict expected failure started passing.
- The 52-case exact-status fixture is still 52 of 52.

## Behaviour that moved toward MET

One note in the required tests moves from review to `MET`: "In 2019, NSAIDs for 4 weeks with no improvement. Muscle relaxants for 6 weeks with no improvement." It now returns 6 weeks and no improvement. This is the owner-required independent-course behaviour. No evaluation label or existing test moved from review to `MET`.

## Validation

- `pytest -q`: 2,045 passed and 9 xfailed on Python 3.12 and 3.13.
- `ruff check .` and `ruff format --check .` pass.
- Artifacts and goldens were regenerated with the acceptance clock; their only differences are the version fields above.
- `python -m evaluation.report --check` passes.
- The holdout was not labeled or run, and the LLM pathway was not touched.

## Unexpected regressions

None found. Two expectations changed for reasons outside the specification's list: the version pins in `test_api.py` and `test_v210_safety.py`. Both follow directly from the required version bump and are listed above.
