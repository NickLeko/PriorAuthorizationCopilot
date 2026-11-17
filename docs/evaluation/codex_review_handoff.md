# Independent review handoff: PRs #23 and #24

November 17, 2026. Prepared by Claude for an independent Codex review. **No independent review has taken place.** Everything below is the author's account, so verify it in the code.

## What to review

| PR | Base | Head at handoff | Scope |
| --- | --- | --- | --- |
| [#23](https://github.com/NickLeko/PriorAuthorizationCopilot/pull/23) | `main` at `6b583df` | `5f6b8a6`, merged into `main` as `8cf737d` (merge commit) | Evaluation infrastructure, datasets, human-review record, Phase 2 specification. No extraction change. |
| [#24](https://github.com/NickLeko/PriorAuthorizationCopilot/pull/24) | `main` at `8cf737d` | Code head `a423225`, followed only by docs commits | Phase 2 production change, engine 2.7.1. |

After #24's code head `a423225`, only documentation under `docs/` changes. `git diff a423225 <#24 head> --stat` should show that.

## Architectural changes

**#23.**
- Adds an `evaluation/` package that no production module imports: a label schema, a metrics module, a harness that runs `ReadinessService.evaluate` with no verifications, and a report generator.
- Adds datasets under `evaluation/datasets/`, plus `docs/evaluation/*`.
- In `engine/test_suites.py`, the false-`READY` metric becomes false `PENDING_VERIFICATION`, because `READY` is unreachable without verifications.
- `app.py` changes only a sidebar caption.

**#24.** In `engine/extract.py`, lumbar CPB 0236 therapy only:
- `CPB_WHOLE_COURSE_RES`: a closed grammar for a whole class-name course.
- `_TherapyCourseCandidate.course_status`: `clean`, `response_uncertain` or `course_uncertain`.
- `_class_name_course_status`: classifies each course.
- `_resolve_with_uncertain_courses`: a branch in front of the unchanged resolver, which is renamed `_resolve_clean_cpb_therapy_candidates`.
- `CPB_INDEPENDENT_COMMENTARY_RE` and `CPB_NONRESPONSE_COMMENTARY_RE`: a closed allowlist of sibling clauses that do not send a clean course to review.

There are no schema, operator, service, correction or verification changes. The version moves to 2.7.1.

## Evaluation method and its limits

- Requirement-level labels, with explicit denominators and constant-predictor controls.
- Label tiers are kept apart:
  - 3 verified textual labels from the owner;
  - 347 provisional agent-authored labels;
  - policy opinions logged as opinions only.
- **The same agent wrote the Phase 2 rule, the challenge notes, most labels and the framing controls.** The measured improvement may be circular.
- 14 of the 20 challenge notes were chosen after their output had been seen.
- The bundled 52-case corpus was written with the extractor, so it is a regression pin rather than evidence of accuracy.
- Everything is synthetic. Nothing has been reviewed by a clinician, and no rates are estimated.
- `holdout_v1` (10 notes) is sealed: unlabeled and never run.

## Known remaining failures

1. **Sibling-clause commentary outside the allowlist still goes to review.** This is conservative, so it never creates a false `MET`. A sibling clause that names a therapy is treated as a separate course, so "; referred because NSAIDs were stopped" can leave the first course `MET`. That predates Phase 2.
2. **CH-06, historical exam** ("Exam two years ago…"): false `MET`. The copied-note test N1B also still asserts a 2019 diagnosis and exam as `MET`.
3. **CH-14, response reversed in the next sentence:** false `MET`.
4. **CH-16 and CH-17, generic demo pathways:** borrowed symptom duration, wrong-region imaging and missed physical therapy are asserted as `MET`.
5. **Evidence attribution:** duration evidence cites every course clause, including set-aside ones. This predates 2.7.1, but it now accompanies a `MET` in the "2019 4-week plus clean 6-week" case.
6. **Recall:** 11 missed `MET` on natural phrasing.

## Where subtle regressions are most likely

- **Grammar breadth.** Could an optional slot admit a temporal, adherence or attribution word? The slots to check are the header, `she`/`he`, the `on` use-verbs, the modifier, the response object and `so far`/`to date`.
- **Clause coordinates.** `_class_name_course_status` receives sentence-relative `clause_start`/`clause_end` and compares them with `_therapy_clause_spans(sentence)`. Check that these always agree.
- **Interaction with existing paths:**
  - drug-name courses, including mixed "NSAIDs (ibuprofen) for 8 weeks";
  - coordinated groups and `paired_signatures`;
  - `unresolved_drug_context`;
  - the existing `response_only_review` route.
- **Units and number words.** Classification is triggered only by the weeks-only legacy patterns, so months or number-word courses are not classified.
- **The longer-uncertain-course guard** (owner Option A) when a clean course's response is `None`.

## Questions to investigate independently

1. Find a note where 2.7.1 produces a `MET` that 2.7.0 did not. One intended case is known: an independent clean course beside a shorter uncertain one. Are there unintended ones?
2. Find a note where a valid, clean course now loses `MET`, other than the sibling-clause class.
3. Can any form in `CPB_INDEPENDENT_COMMENTARY_RE` hide a statement that modifies or contradicts the course? Is the agreement check for "pain is severe" sufficient?
4. Do the 25 tests in `test/test_phase2_therapy_courses.py` test behaviour, or only reproduce the author's own examples?
5. Can anything in the evaluation package run or score the sealed holdout, or verify a label without a logged human decision?
6. Are any changed test expectations unjustified? See `phase2_results.md`. The allowlist commits added tests and changed no existing expectation.
