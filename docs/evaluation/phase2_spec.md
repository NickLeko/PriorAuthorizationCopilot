# Phase 2 implementation specification

November 17, 2026. **Status: not implemented. Implementation needs explicit authorization from the repository owner.**

This replaces the proposal in [phase2_proposal.md](phase2_proposal.md) as the implementation reference. The proposal still holds the metric audit and the failure analysis.

## 1. Basis

The change rests on two textual decisions recorded as verified labels in `evaluation/datasets/review_log_v1.json`:

| Case | Requirement | Decision |
| --- | --- | --- |
| CH-02 "Missed NSAIDs for 8 weeks with no improvement." | therapy duration, response | `NEEDS_REVIEW` |
| CH-04 "…no improvement initially, now much improved." | response | `NEEDS_REVIEW` |

Policy opinions recorded in the same log are not verified and do not block the change. In each of these cases review is the most conservative destination the reviewer considered:

- **MRI-01:** "minimal improvement" counts as no improvement, as the current rule already assumes.
- **CH-03 and CH-15:** an old or pre-flare course goes to review.
- **CH-05:** a barely-taken course goes to review.

Four of the seven opinions were given by accepting agent proposals in bulk. A policy owner can still overturn any of them. If one were overturned towards `MET`, this change would turn a false `MET` into an unnecessary review for that case.

## 2. The change

**Where.** `engine/extract.py`, `_collect_cpb_therapy_candidates`, lumbar CPB 0236 pathway only.

**Rule.** When an accepted duration match in a clause comes from the class-name course patterns (`CPB_0236_THERAPY_AFTER_RE`, `CPB_0236_THERAPY_BEFORE_RE`), the whole clause must match the course grammar below, ignoring trailing sentence punctuation. If it does not, set `linkage_ambiguous = True` for that candidate. The existing resolver then returns `NEEDS_REVIEW` for both therapy facts.

There are no new outcomes, operators, schema fields or sentinel values.

**Why this shape.** The current extractor accepts a class-name course anywhere in a clause and ignores the remaining words unless they match a fixed list of disqualifiers. When the list misses a word, the result is a false `MET`. This rule inverts the default: words must be accounted for by a closed grammar. When the grammar misses a framing word, the result is a review, not a false `MET`. The drug-name and newer duration patterns already work this way, and this extends the same approach to the oldest pattern.

**Course grammar.** Built from existing constants where they exist.

| Slot | Allowed | Source |
| --- | --- | --- |
| Section header (optional) | `conservative therapy:`, `conservative treatment:`, `conservative management:`, `therapy:`, `treatment:`, `treatments:`, `medication:`, `medications:`, optionally with `history` before the colon | New, closed list (PC-08) |
| Subject (optional) | `patient`, `the patient`, `she`, `he` | Existing `CPB_DRUG_USE_PREFIX` plus pronouns (PC-04) |
| Use verb (optional) | Existing verbs in `CPB_DRUG_USE_PREFIX`, plus `has/have/had been on` and `reports taking/using` | Existing, plus PC-16 and PC-19 |
| Modifier (optional) | `over-the-counter`, `otc`, `prescription` | New, closed list (PC-15) |
| Modality | One class name, or several joined by `,`, `and`, `plus`, `+` | `CPB_0236_THERAPY_CONTEXT`, coordination as in `CPB_0236_GROUP_DURATION_RE` |
| Dose and frequency (optional) | Existing `CPB_DRUG_DOSE` | Existing |
| Duration | `x`, `for` or `over` followed by a value and a unit; or `(a/an) N-unit (course/trial) of <modality>` | Existing value and unit forms |
| Response (optional) | `with`, a comma, or `produced`, `provided`, `gave`, `yielded` or `resulted in`; then `no`, `minimal`, `little`, `insufficient`, `substantial`, `significant`, `meaningful` or `good` + `improvement`, `relief`, `response` or `benefit`. Or `without` + one of those nouns. | Existing response words; verb forms from an existing test |
| Response object (optional) | `in (her/his/the patient's) (back/leg/low back) pain/symptoms` | New, closed (PC-06, PC-07) |
| Qualifier (optional) | `so far`, `to date` | New, closed (PC-13) |

**Rules for changing the grammar later.** An allowance is added only when:

- a written control shows valid documentation being sent to review;
- the allowance admits no remainder that the challenge set or the negative unit tests below require to stay in review.

Disqualifier phrases are not added in this phase.

**Deliberately unchanged:**

- the drug-name patterns, which are already anchored;
- the newer duration forms;
- the generic pathways (cervical, knee, CPAP);
- the objective-exam extractor;
- cross-sentence response linkage;
- vocabulary and recall.

## 3. Expected effect

These are estimates from an analysis-only simulation run against the recorded labels. The implementation must reproduce them, or explain each difference.

| Set | Measure | Before | Expected after |
| --- | --- | --- | --- |
| Challenge, verified labels | False MET | 3 of 3 | 0 of 3 |
| Challenge, provisional labels | False MET | 11 of 15 | 5 of 15 |
| Challenge, provisional labels | Missed MET | 11 of 59 | 12 of 59 |
| Challenge, provisional labels | Predicted `NEEDS_REVIEW` | 0 of 74 | 7 of 74 |
| Framing controls | Missed MET | 2 of 80 | 2 of 80 |
| Bundled corpus | Agreement | 193 of 193 | 193 of 193 |

- **Fixed (9 labels):** CH-02 (2), CH-03 (2), CH-04 response, CH-05 (2), CH-15 (2).
- **Still false MET (5):** CH-06 historical exam, CH-14 response reversed in the next sentence, CH-16 imaging and symptom duration, CH-17 knee therapy.
- **New missed MET (1):** CH-04 therapy duration. The rule sends both facts to review, and duration was labeled `MET`. This is the accepted price of a per-clause rule: separating duration from response would also leave CH-15's duration as a false `MET`.

All of these counts are on selected synthetic notes. They are not rates.

## 4. Positive controls

`evaluation/datasets/framing_controls_v1.json` contains 20 lumbar notes, each documenting one valid course. Labels were written and committed (`ba09922`) before any of the notes was run.

**Must stay MET for both therapy facts (18 notes):**

| Case | Framing form |
| --- | --- |
| PC-01 | Patient completed NSAIDs for 8 weeks with no improvement. |
| PC-02 | The patient has tried NSAIDs for 8 weeks without relief. |
| PC-03 | Took NSAIDs for 8 weeks with no improvement. |
| PC-04 | She completed NSAIDs for 8 weeks with no improvement. |
| PC-06 | NSAIDs for 8 weeks with no improvement in her pain. |
| PC-07 | NSAIDs for 8 weeks with no improvement in symptoms. |
| PC-08 | Conservative therapy: NSAIDs for 8 weeks with no improvement. |
| PC-09 | Muscle relaxants for 6 weeks with minimal improvement. |
| PC-10 | Analgesics for 7 weeks with insufficient relief. |
| PC-11 | Ibuprofen 600 mg twice daily for 8 weeks without relief. |
| PC-12 | Patient took naproxen for 8 weeks with no improvement. |
| PC-13 | NSAIDs for 8 weeks with no improvement so far. |
| PC-14 | Moderate activity for 6 weeks with no improvement. |
| PC-15 | Over-the-counter NSAIDs for 8 weeks with no improvement. |
| PC-16 | Has been on NSAIDs for 8 weeks with no improvement. |
| PC-17 | Completed 8 weeks of NSAIDs with no improvement. |
| PC-18 | Tried 8 weeks of NSAIDs with little relief. |
| PC-19 | Patient reports taking NSAIDs for 8 weeks with no improvement. |

**Must not get worse (2 notes, already missed today, outside this change):**

- PC-05 "NSAIDs daily for 8 weeks…": duration is not found.
- PC-20 "Completed NSAIDs for 8 weeks. There was no improvement.": the response is not linked.

Applying the existing drug-path grammar without the new allowances would send 8 of the 18 to review. That result is why the allowances exist.

**Required unit tests.** Each allowance gets a positive test from the controls. Each also gets a negative test showing it does not open a hole:

| Allowance | Must stay MET | Must go to review |
| --- | --- | --- |
| Pronoun subject | She completed NSAIDs for 8 weeks with no improvement. | She missed NSAIDs for 8 weeks with no improvement. |
| Header | Conservative therapy: NSAIDs for 8 weeks with no improvement. | Conservative therapy (2019): NSAIDs for 8 weeks with no improvement. |
| Modifier | Over-the-counter NSAIDs for 8 weeks with no improvement. | Over-the-counter NSAIDs for 8 weeks in 2019 with no improvement. |
| Response object | …with no improvement in her pain. | …with no improvement in sleep. |
| Qualifier | …with no improvement so far. | …with no improvement at the time. |
| Use verb | Has been on NSAIDs for 8 weeks with no improvement. | Has been off NSAIDs for 8 weeks with no improvement. |
| Response verb | NSAIDs for 9 weeks produced no improvement. | NSAIDs for 8 weeks provided little improvement initially. |

All seven must-go-to-review notes return both therapy facts as `MET` today, after the standard lumbar diagnosis and exam sentences. They are further false-`MET` examples as well as guards.

## 5. Existing tests expected to change

A scan of literal note strings in `test/` and the fixture corpora found 232 notes with a live lumbar therapy fact. Two of them would change expectation:

| Test | Note | Today | After | Recommendation |
| --- | --- | --- | --- | --- |
| `test/test_attestation_context.py::test_n1b_shows_following_contradiction_for_all_four_attestations` | "Prior visit note (2019): …NSAIDs for 8 weeks with no improvement. Today: asymptomatic." | All four requirements `MET` | Therapy facts `NEEDS_REVIEW` | Update. This is a copy-forward false `MET` that the test was relying on the reviewer to catch. Keep its context assertions, which already work for review-required facts. |
| `test/test_service.py`, conservative-therapy parameter case 2 | "Analgesics for 2 weeks were stopped. NSAIDs and muscle relaxants for 6 weeks with no improvement." | 6 weeks, no improvement, `PENDING_VERIFICATION` | Both `NEEDS_REVIEW` | **Owner decision.** The qualifying course is clean; the stopped 2-week course is not. The rule works per note, not per course, so any unexplained course sends both facts to review. Recommend accepting it: it is the same adherence signal as CH-02, and a narrower rule would need per-course resolution, which is out of scope. |

This scan is a lower bound, because notes built in code are not covered. If the full suite shows any other changed expectation, implementation stops for review. Goldens and generated artifacts are expected to be byte-identical; any diff also stops for review.

## 6. Acceptance criteria

1. `python -m evaluation.report` reproduces section 3, or each difference is explained in the pull request.
2. No new false `MET` in any evaluated set, in any tier.
3. All 18 must-stay controls stay `MET`, and PC-05 and PC-20 do not get worse.
4. The bundled corpus stays at 193 of 193, and the exact-status fixture stays at 52 of 52.
5. Every unit test in section 4 passes.
6. Only the two section 5 expectations change, each updated in its own commit with the reason in the message.
7. Goldens and artifacts are byte-identical, and the suite and Ruff pass on Python 3.12 and 3.13.
8. Engine version moves to 2.7.1, because extraction behaviour changes.

## 7. After the change is frozen

1. A human labels `holdout_v1` from `labeling_packet.csv`, priority 4, without running the tool on it.
2. With separate authorization, the holdout is run once and the result is reported, whatever it shows.
3. Holdout notes that fail are not used to tune Phase 2. They move to the challenge set for later work.

## 8. Not in this change

- Phrase disqualifiers.
- Recall work, such as months, "wks", "failed" or "unchanged".
- Cross-sentence linkage (CH-14, PC-20).
- Historical exam handling (CH-06).
- Borrowed-evidence fixes on the generic pathways (CH-16, CH-17).
- Any relationship model or model-based extraction.
