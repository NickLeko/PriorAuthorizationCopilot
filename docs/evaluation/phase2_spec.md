# Phase 2 implementation specification

Revised November 17, 2026. **Status: not implemented. Implementation needs explicit authorization from the repository owner.**

This replaces section 3 of [phase2_proposal.md](phase2_proposal.md) as the implementation reference.

## 1. What changed from the first draft

The first draft sent both therapy facts to review whenever any course in the note had unexplained wording. The owner rejected that on November 17, for two reasons:

1. **Independent courses.** A stopped two-week analgesic course must not invalidate a separate six-week NSAID and muscle-relaxant course that independently documents duration and no improvement. The existing test that expects this stays unchanged.
2. **Per-fact decisions.** In CH-04 the 8-week duration is documented and only the response changes. Duration stays `MET` and only the response goes to `NEEDS_REVIEW`.

This revision decides per course and per fact. Every result below comes from a scratch prototype that patches the extractor inside a test process only. The prototype is not committed.

## 2. Basis

Textual decisions, recorded as verified labels in `evaluation/datasets/review_log_v1.json`:

- **CH-02**, "Missed NSAIDs for 8 weeks with no improvement.": duration and response are both `NEEDS_REVIEW`.
- **CH-04**, "…no improvement initially, now much improved.": response is `NEEDS_REVIEW`.

Policy opinions are logged without verifying any label:

- **MRI-01:** "minimal improvement" counts as no improvement.
- **CH-03 and CH-15:** an old or pre-flare course goes to review.
- **CH-05:** a barely-taken course goes to review.

In each of those, review is the most conservative destination the reviewer considered. A policy owner may still overturn them.

## 3. The change

**Where:**
- `engine/extract.py`, lumbar CPB 0236 therapy only.
- `_collect_cpb_therapy_candidates` classifies each course.
- `_resolve_cpb_therapy_candidates` gains one branch ahead of its existing logic.

There are no new outcomes, operators, schema fields or sentinel values. Courses that the existing code already marks ambiguous keep today's behaviour exactly.

### 3.1 Classify each class-name course

The rule applies when a course's duration comes from the class-name patterns (`CPB_0236_THERAPY_AFTER_RE` or `CPB_0236_THERAPY_BEFORE_RE`). Each such course is classified as follows:

| Class | Condition | Meaning |
| --- | --- | --- |
| Clean | The whole clause matches the course grammar in 3.3 | Today's behaviour |
| Response uncertain | The clause matches the grammar up to the end of its response phrase, and the remaining words come after that phrase in the same clause | Duration is documented; the response is qualified (CH-04, "…no improvement in sleep") |
| Course uncertain | Anything else: unexplained words before or inside the course ("Missed", "In 2019,", "Intermittent … taken twice total"), or a sibling clause in the same sentence that names no therapy at all (CH-15's "; that was before the current flare…") | It is unclear whether this course counts at all |

A sibling clause that names a therapy, including non-Footnote-1 therapy such as "PT also completed", is a separate course, not commentary on this one. Drug-name courses and the newer whole-statement duration forms are already anchored and are not reclassified.

### 3.2 Resolve per course

Today's resolver runs unchanged unless at least one course is uncertain and no course is already marked ambiguous by existing code. In that case:

1. **No clean course.** If there is exactly one course and it is response-uncertain, return its duration and `NEEDS_REVIEW` for the response. This reuses the existing single-course response-only path. Otherwise return `NEEDS_REVIEW` for both facts.
2. **At least one clean course.** Resolve the clean courses with today's logic. Return that result when all of these hold:
   - it gives a numeric duration;
   - its response is not under review;
   - no uncertain course is longer than the selected duration.
   
   Otherwise return `NEEDS_REVIEW` for both.

Rule 2's length check copies the resolver's existing guard against a longer unlinked course donating its duration.

### 3.3 Course grammar

| Slot | Allowed | Source |
| --- | --- | --- |
| Section header (optional) | `conservative therapy:`, `conservative treatment:`, `conservative management:`, `therapy:`, `treatment:`, `treatments:`, `medication:`, `medications:`, optionally with `history` before the colon | New, closed (PC-08) |
| Subject (optional) | `patient`, `the patient`, `she`, `he` | `CPB_DRUG_USE_PREFIX` plus pronouns (PC-04) |
| Use verb (optional) | The verbs in `CPB_DRUG_USE_PREFIX`, plus `has/have/had been on` and `reports taking/using` | Existing, plus PC-16 and PC-19 |
| Modifier (optional) | `over-the-counter`, `otc`, `prescription` | New, closed (PC-15) |
| Modality | A class name, or several joined by `,`, `and`, `plus`, `+` | `CPB_0236_THERAPY_CONTEXT`, with coordination as in `CPB_0236_GROUP_DURATION_RE` |
| Dose and frequency (optional) | `CPB_DRUG_DOSE` | Existing |
| Duration | `x`, `for` or `over` followed by a value and unit; or `(a/an) N-unit (course/trial) of <modality>` | Existing value and unit forms |
| Response (optional) | One of: `with`, a comma, `produced`, `provided`, `gave`, `yielded`, `resulted in`; then one of `no`, `minimal`, `little`, `insufficient`, `substantial`, `significant`, `meaningful`, `good`; then one of `improvement`, `relief`, `response`, `benefit`. Or `without` followed by one of those nouns. | Existing response words; verb forms from an existing test |
| Response object (optional) | `in (her/his/the patient's) (back/leg/low back) pain/symptoms` | New, closed (PC-06, PC-07) |
| Qualifier (optional) | `so far`, `to date` | New, closed (PC-13) |

**Why the grammar is an allowlist.** Today, unexplained words become a false `MET` unless a fixed disqualifier list happens to cover them. Under this grammar, a missing framing word costs a review instead.

**Changing the grammar later.** An allowance may be added only when a written control shows valid documentation going to review. It must also admit no remainder that the tests in section 5 require to stay in review. No disqualifier phrases are added in this phase.

## 4. Architectural limitation and the remaining decision

The extractor emits one value per fact without knowing the policy minimum. That is deliberate: policy replay re-evaluates archived facts under other policy versions, so facts cannot depend on the active threshold. As a result, the extractor cannot tell whether a clean course already qualifies on its own.

So when an uncertain course is longer than the clean one, rule 2 sends both facts to review. That happens even when the clean course already meets 6 weeks:

> Muscle relaxants for 6 weeks with no improvement. Intermittent NSAIDs for 10 weeks, taken twice total, with no improvement.

Today this note goes to review for both facts as well, so this is not a regression. It is a case the revision does not improve.

| Option | When the uncertain course is longer | Risk |
| --- | --- | --- |
| A. Review both (recommended) | `NEEDS_REVIEW` for both facts | An unnecessary review when the clean course already qualifies |
| B. Always use the clean course | The clean course's duration and response | A short clean course gives `NOT_MET` while a longer uncertain course goes unseen. That is never a false `MET`, but the evidence a reviewer should look at is hidden. |
| C. Give the extractor the threshold | Exact | Breaks policy-independent facts and replay; out of scope |

**Recommendation: A.** It matches the existing longer-course guard, and its cost is visible to the reviewer rather than silent. **This is the one decision left for the owner.**

**Known result that moves toward MET.** One prototype case moves from review today to `MET`:

> In 2019, NSAIDs for 4 weeks with no improvement. Muscle relaxants for 6 weeks with no improvement.

The 2019 course is set aside because it is uncertain and shorter, and the clean 6-week course qualifies on its own. This follows the owner's independent-course principle. It is listed so that the increase in `MET` is explicit, not silent. No existing test or evaluation label covers it.

**Known cost of the sibling-clause rule.** A course followed by any non-therapy clause in the same sentence goes to review for both facts. In existing test and fixture notes this fired on 7 of 189 class-name course clauses. All 7 were real changes of meaning: reversed responses, courses not started or stopped, and pre-flare timing.

One of those, "…provided little improvement initially; she now reports good relief…", is a response-only change. Its duration goes to review even though it is documented. Telling course-level commentary apart from response-level commentary in a separate clause would need semantic parsing, so this stays conservative.

## 5. Tests

### 5.1 Framing controls

`evaluation/datasets/framing_controls_v1.json` has 20 notes whose labels were committed in `ba09922` before the notes were first run.

- **18 must stay `MET` for both therapy facts:** PC-01 to PC-04 and PC-06 to PC-19.
- **2 must not get worse:** PC-05 (duration not found) and PC-20 (response in the next sentence). Both are missed today.

### 5.2 Framing allowances: positive and negative pairs

The first column must stay `MET` for both facts.

| Allowance | Must stay `MET` | Must not be `MET` (resulting state) |
| --- | --- | --- |
| Pronoun subject | She completed NSAIDs for 8 weeks with no improvement. | She missed NSAIDs for 8 weeks with no improvement. (both review) |
| Header | Conservative therapy: NSAIDs for 8 weeks with no improvement. | Conservative therapy (2019): NSAIDs for 8 weeks with no improvement. (both review) |
| Modifier | Over-the-counter NSAIDs for 8 weeks with no improvement. | Over-the-counter NSAIDs for 8 weeks in 2019 with no improvement. (both review) |
| Response object | …with no improvement in her pain. | …with no improvement in sleep. (8 weeks, response review) |
| Qualifier | …with no improvement so far. | …with no improvement at the time. (8 weeks, response review) |
| Use verb | Has been on NSAIDs for 8 weeks with no improvement. | Has been off NSAIDs for 8 weeks with no improvement. (both review) |
| Response verb | NSAIDs for 9 weeks produced no improvement. | NSAIDs for 8 weeks provided little improvement initially. (8 weeks, response review) |

All seven right-hand notes return `MET` for both facts today, after the standard lumbar diagnosis and exam sentences.

### 5.3 Multiple courses, historical courses and response changes

Every note follows the standard lumbar diagnosis and exam sentences. "Today" and "required" are (duration, response).

| Group | Note | Today | Required |
| --- | --- | --- | --- |
| Multiple | Analgesics for 2 weeks were stopped. NSAIDs and muscle relaxants for 6 weeks with no improvement. | 6, true | 6, true (existing test, unchanged) |
| Multiple | Missed muscle relaxants for 2 weeks. NSAIDs for 8 weeks with no improvement. | 8, true | 8, true |
| Multiple | In 2019, NSAIDs for 4 weeks with no improvement. Muscle relaxants for 6 weeks with no improvement. | review, review | 6, true (moves toward `MET`; see section 4) |
| Multiple | Muscle relaxants for 6 weeks with no improvement. Intermittent NSAIDs for 10 weeks, taken twice total, with no improvement. | review, review | review, review (limitation; Option A) |
| Multiple | Muscle relaxants for 2 weeks produced no improvement, whereas NSAIDs for 8 weeks were also documented. | review, review | review, review (existing contrast handling, unchanged) |
| Historical | In 2019, NSAIDs for 8 weeks with no improvement. | 8, true | review, review |
| Historical | NSAIDs for 8 weeks with no improvement at the time; that was before the current flare began last week. | 8, true | review, review |
| Historical | Prior visit note (2019): NSAIDs for 8 weeks with no improvement. | 8, true | review, review |
| Historical | NSAIDs for 8 weeks with no improvement so far. | 8, true | 8, true |
| Historical | Patient completed NSAIDs for 8 weeks with minimal improvement; PT also completed. | 8, true | 8, true |
| Response | NSAIDs for 8 weeks with no improvement initially, now much improved. | 8, true | 8, review |
| Response | NSAIDs for 8 weeks with no improvement in sleep. | 8, true | 8, review |
| Response | NSAIDs for 8 weeks provided little improvement initially. | 8, true | 8, review |
| Response | NSAIDs for 8 weeks with no improvement, then marked improvement after week 6. | 8, true | 8, review |
| Response | NSAIDs for 8 weeks with no improvement in sleep but significant improvement in pain. | review, review | review, review (existing contrast handling, unchanged) |
| Response | NSAIDs for 8 weeks with significant improvement. | 8, false | 8, false |

The prototype reproduces every "required" value in 5.2 and 5.3.

## 6. Expected effect

From the prototype, against the recorded labels.

| Set | Measure | Before | Prototype |
| --- | --- | --- | --- |
| Challenge, verified labels | False `MET` | 3 of 3 | 0 of 3 |
| Challenge, provisional labels | False `MET` | 11 of 15 | 5 of 15 |
| Challenge, provisional labels | Missed `MET` | 11 of 59 | 11 of 59 |
| Challenge, all scored labels | Predicted `NEEDS_REVIEW` | 0 of 77 | 9 of 77 |
| Framing controls | Missed `MET` | 2 of 80 | 2 of 80 |
| Bundled corpus | Agreement | 193 of 193 | 193 of 193 |

- **Fixed (9 labels):** CH-02 (2), CH-03 (2), CH-04 response, CH-05 (2), CH-15 (2).
- **Still false `MET` (5):** CH-06 historical exam, CH-14 response reversed in the next sentence, CH-16 imaging and symptom duration, CH-17 knee therapy.
- **New missed `MET`:** none.

These are counts on selected synthetic notes, not rates.

## 7. Existing tests

The full existing suite was run with the prototype patched in: 1,996 passed, 1 failed and 9 xfailed. The only expectation that changes is:

| Test | Note | Today | Prototype | Proposal |
| --- | --- | --- | --- | --- |
| `test/test_attestation_context.py::test_n1b_shows_following_contradiction_for_all_four_attestations` | "Prior visit note (2019): …NSAIDs for 8 weeks with no improvement. Today: asymptomatic." | All four requirements `MET` | Therapy facts `NEEDS_REVIEW` | Update the two status assertions; keep the context assertions. **Needs owner approval before the change is made.** |

The test exists to check that reviewer context shows the contradicting "Today: asymptomatic." The copied 2019 course is the false `MET` this change targets, and the companion test `test_original_n1_attestation_view_renders_review_required_facts` shows that context still renders for review-required facts.

Goldens and generated artifacts were unchanged under the prototype. No strict expected failure started passing.

## 8. Acceptance criteria

1. `python -m evaluation.report` matches section 6, or the pull request explains each difference.
2. No new false `MET` in any evaluated set or tier, and no new missed `MET`.
3. All 18 must-stay controls stay `MET`, and PC-05 and PC-20 do not get worse.
4. Every row in sections 5.2 and 5.3 is a unit test, and each passes.
5. The only changed expectation is the one in section 7, made in its own commit after approval. Any other changed expectation stops the work for review.
6. Goldens and artifacts are byte-identical. The suite and Ruff pass on Python 3.12 and 3.13.
7. The engine version moves to 2.7.1.

## 9. After the change is frozen

1. A human labels `holdout_v1` from `labeling_packet.csv`, priority 4, without running the tool on it.
2. With separate authorization, the holdout is run once and the result is reported, whatever it shows.
3. Failing holdout notes are not used to tune Phase 2. They move to the challenge set.

## 10. Not in this change

- Phrase disqualifiers.
- Recall work.
- Cross-sentence response linkage (CH-14, PC-20).
- Historical exam handling (CH-06).
- Borrowed evidence on the generic pathways (CH-16, CH-17).
- Policy-aware extraction.
- Relationship models or model-based extraction.
