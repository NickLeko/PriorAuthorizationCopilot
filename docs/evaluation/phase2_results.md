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

## Pre-merge review finding (November 17, 2026)

A pre-merge review found one substantive cost that neither the specification's measurement nor the framing controls covered.

**The sibling-clause rule downgrades clean courses for unrelated commentary.** A clean course followed in the same sentence by any clause that names no therapy now sends both therapy facts to `NEEDS_REVIEW`. On eight probe notes, each after the standard lumbar diagnosis and exam sentences:

| Note ending | 2.7.0 | 2.7.1 (this PR) |
| --- | --- | --- |
| "…no improvement; pain is severe." | `MET` (correct) | review (unnecessary) |
| "…no improvement; MRI requested." | `MET` (correct) | review (unnecessary) |
| "…no improvement; referred to spine clinic." | `MET` (correct) | review (unnecessary) |
| "…no improvement, though she still works full time." | `MET` (correct) | review (unnecessary) |
| "…no improvement, but she declines injections." | `MET` (correct) | review (unnecessary) |
| "…no improvement; see attached records." | `MET` (correct) | review (unnecessary) |
| "…no improvement; stopped after 3 days." | `MET` (false) | review (correct) |
| "…no improvement at the time; that was before the current flare…" | `MET` (false) | review (correct) |

This is fail-safe: it adds no false `MET`. It is still more frequent than section 4 of the specification implies, because that measurement covered only existing notes. The earlier statement that there were no unexpected regressions was withdrawn for this behaviour until the resolution below.

A narrower rule was tested in a scratch copy, not on this branch. It counts a sibling clause as commentary only when it begins with a reference back to the course ("that", "this", "it", "which", "these", "those", "they").

- The full suite and the committed evaluation baseline are unchanged under it.
- It restores `MET` on the six unrelated-commentary notes and still sends CH-15 to review.
- It leaves "…; stopped after 3 days." as a false `MET`, the same as 2.7.0.

**Resolution (owner request, November 17).** The owner rejected both "merge as is" and the back-reference rule. In their place, a sibling clause that names no therapy keeps a clean course `MET` only when the whole clause is one of a closed set of clearly independent statements:

- an MRI request;
- a referral to a spine, pain, neurosurgery, orthopedic or physiatry clinic;
- "see attached records";
- the patient still working full or part time;
- the patient declining injections or surgery.

"Pain is severe" describes the response, so it is accepted only when the course itself states a non-response, where the two agree. Anything unlisted or only partly matching still sends the course to review.

Tests were written and committed first (`047dbe8`, `7c1f844`), and the change followed (`a423225`).

| Note ending | 2.7.0 | 2.7.1 before | 2.7.1 after |
| --- | --- | --- | --- |
| "; pain is severe." | 8, true | review | 8, true |
| "; MRI requested." | 8, true | review | 8, true |
| "; referred to spine clinic." | 8, true | review | 8, true |
| ", though she still works full time." | 8, true | review | 8, true |
| ", but she declines injections." | 8, true | review | 8, true |
| "; see attached records." | 8, true | review | 8, true |
| "; stopped after 3 days." | 8, true (false `MET`) | review | review |
| CH-15 "…at the time; that was before the current flare…" | 8, true (false `MET`) | review | review |
| "; she works as a nurse." (unrecognized) | 8, true | review | review |
| "; MRI requested after she stopped them." | 8, true | review | review |
| "; referred to spine clinic, stopped after 3 days." | 8, true | review | review |
| "; pain is severe but now improving." | 8, true | review | review |
| "; pain is no longer severe." | review | review | review |
| "…significant improvement; pain is severe." | 8, false | review | review |
| "NSAIDs for 8 weeks; pain is severe." | 8, none | review | review |

**Results:**

- The committed evaluation baseline is byte-identical before and after the change: no new false `MET` or missed `MET` in any set or tier.
- The full suite gives 2,061 passed and 9 xfailed on Python 3.12 and 3.13, with no existing expectation changed.
- Goldens and artifacts are unchanged.

**Limits that remain:**

- The allowlist covers only these forms. Any other harmless commentary still goes to review, which is the conservative direction.
- A sibling clause that names a therapy is treated as a separate course and not checked as commentary. For example, "; referred because NSAIDs were stopped" can leave the first course `MET`. This behaviour predates Phase 2 and is unchanged.
