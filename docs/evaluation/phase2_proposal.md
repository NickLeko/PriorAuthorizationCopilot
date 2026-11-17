# Metric audit, failure mechanisms and Phase 2 proposal

Implementation reference: [phase2_spec.md](phase2_spec.md), which supersedes section 3 below.

November 16, 2026. Based on the committed [baseline](requirement_level_baseline.md) for engine 2.7.0. Nothing in this document has been implemented. Every label behind it is provisional and agent-authored.

## 1. Metric audit

**How 193 scored labels reconcile.** On the bundled corpus, 96 labels expect `MET`, 94 are labels where `MET` is not a defensible state, and 3 expect `NEEDS_REVIEW` but also accept `MET` (`SAFETY-01` and `SAFETY-02` therapy weeks, `MRI-KNEE-05` mechanical symptoms). 96 + 94 + 3 = 193. The 3 are in neither the false-`MET` denominator nor the missed-`MET` denominator, because a `MET` there is not an error and a non-`MET` there is not a miss. The same identity holds per requirement.

**Issues found and fixed in this pass.**

| Issue | Fix |
| --- | --- |
| A case added to `inputs/synthetic_cases.json` without labels would not have been reported | The report lists source cases with no labels, and a test covers it |
| Challenge-set results were printed with percentages, which read as rates | Challenge results are counts only, with an explicit statement that they are known failures |
| The controls table said a non-constant predictor "meets minimum utility", which reads as an endorsement | The column now says only whether the predictor is degenerate |

**Things to know that are not errors.** Precision counts a prediction as correct when it is in the label's acceptable set, while recall uses the single expected state, so per-state precision and recall are not computed over mirror-image sets. Case-level results count only cases where every requirement has a scored label.

**Is false `PENDING_VERIFICATION` informative?** Only as a regression invariant. Three reasons:

1. It is implied by the exact-status check. If all 52 overall statuses match, false pending is 0 of 45 by arithmetic.
2. The fixtures were written alongside the extractor, so the match shows the extractor still agrees with its own fixtures.
3. It is blind to most single errors. Of 42 fully scored non-passing cases, only 19 are blocked by exactly one requirement. In the other 23, a false `MET` on one requirement leaves the overall status unchanged.

It can detect an extractor that asserts everything (45 of 45) and it is reachable, unlike `READY`. The artifact's scope note now says it is not a safety estimate. Requirement-level false `MET` is the safety measure.

## 2. Failure mechanisms

The 24 provisional failures on the challenge set come from five mechanisms. Categories such as adherence or temporal attribution describe what the note says. The mechanism is what the extractor does.

| Mechanism | What the extractor does | Failures | Note-level categories |
| --- | --- | --- | --- |
| M1. Unexamined remainder of a therapy clause | The class-name course pattern (`NSAIDs for 8 weeks`, with a response) matches anywhere in a clause. Words outside the match are checked only against a fixed list of disqualifiers, then ignored. The whole sentence is still cited as evidence. | 8 false `MET` on the lumbar pathway: `CH-02` (2), `CH-03` (2), `CH-04`, `CH-05`, `CH-15` (2). 1 more on the generic pathway: `CH-17` therapy weeks. | Adherence, temporal attribution, response change within a sentence |
| M2. Response updated in a later sentence | The response is read from the course sentence. A later sentence that reverses it is not linked. | 1 false `MET`: `CH-14` | Response change, contradictory evidence |
| M3. Unexamined remainder of an exam clause | Same shape as M1 in a different code path: the exam finding matches and "two years ago" is ignored. | 1 false `MET`: `CH-06` | Historical finding |
| M4. Evidence borrowed from an unrelated fact | Generic duration and imaging patterns take the nearest number or result without checking what it describes. | 2 false `MET`: `CH-16` symptom duration and prior imaging | Borrowed evidence |
| M5. Vocabulary and format gaps | Supported wording is narrow: durations in months or "wks" for drug courses, a dose between drug and duration, responses such as "failed" or "unchanged", exam shorthand, onset phrasing. | 11 missed `MET`: lumbar therapy 6, lumbar exam 1, generic pathways 4 | Natural phrasing, abbreviations |

Negation produced no failure on these notes: the negated diagnosis (`CH-13`) and the cancelled study (`CH-18`) were handled.

**What shares a cause.** M1 accounts for 9 of the 13 false `MET`, across three note-level categories that look unrelated. Adding "missed", "intermittent" or a year pattern to the disqualifier list would fix the notes already seen and nothing else, which is how that list reached its current length. M3 is the same idea in separate code. M2 and M4 are different problems. M5 is the opposite failure and pulls in the opposite direction.

**Evidence that M1 is one mechanism.** An analysis-only script removed the course match and the response phrase from each lumbar therapy clause and looked at what was left, without changing the extractor:

- All 16 clauses behind a correct lumbar therapy result, across both datasets, leave nothing.
- All 5 clauses behind the 8 lumbar M1 false `MET` leave something: "missed", "in 2019", "initially now much improved", "intermittent taken twice total", "at the time".

This separation is on notes the extractor or its fixtures were built around, so it shows the mechanism is real, not how often it occurs.

## 3. Proposed Phase 2 intervention

One change, on the lumbar pathway only.

**Change.** When the class-name course pattern matches a lumbar therapy clause and the clause contains content the course and response grammar does not account for, mark the course as unresolved so that both therapy facts become `NEEDS_REVIEW`. The extractor already has this route (`ambiguous_linkage`) and already requires a whole isolated statement for its newer duration forms. This applies the same rule to the older form.

| Question | Answer |
| --- | --- |
| Failure mechanism | M1 on the two lumbar therapy requirements |
| Known cases addressed | `CH-02` (2), `CH-03` (2), `CH-04`, `CH-05`, `CH-15` (2): 8 of the 13 false `MET`. It also changes the unscored `CH-05` response. |
| Not addressed | `CH-14` (M2), `CH-06` (M3), `CH-16` (M4), `CH-17` (generic pathway), and all 11 missed `MET` |
| Risk of more missed `MET` or unnecessary review | Real. A correct course written with ordinary framing words ("Patient completed NSAIDs for 8 weeks with no improvement") leaves a remainder and would go to review unless those words are treated as part of the course statement. That needs a short, closed list of framing words, decided from the existing tests, not from new notes. Neither dataset contains such a case, so this cost is unmeasured today. |
| Effect on recall work | None directly. It does not fix M5 and should land before M5, because widening accepted wording while the remainder is unexamined would widen the path that is over-asserting. |

**How success and regression will be measured.**

1. Challenge set: false `MET` on the two lumbar therapy requirements falls from 9 to 1 (`CH-14` remains). No false `MET` appears anywhere it was not before.
2. Challenge set: missed `MET` does not rise above 11, and the review count is reported (it is 0 of 76 now and should rise by about 8).
3. Bundled corpus: all 193 scored labels still agree, including the 9 therapy-weeks and 10 response labels expected `MET`.
4. Existing suite: every test whose expected value changes is listed in the pull request with a reason. A changed expectation is a decision, not a fix-up. Goldens change only where one of those tests explains it.
5. After the change is frozen: a human labels `holdout_v1`, it is run once, and the result is reported whatever it shows.

**Decisions required before implementation.**

| Decision | Packet rows | Why it matters |
| --- | --- | --- |
| Is a missed course, or one taken twice in 8 weeks, a documented 6-week course? | `CH-02`, `CH-05` | If a reviewer says `MET` is defensible, the change would create over-abstention, not remove a false `MET` |
| Can a course from 2019, or from before the current flare, count? | `CH-03`, `CH-15` | Same. This is a policy reading, so a non-owner's answer stays provisional |
| Does "no improvement initially, now much improved" satisfy "no improvement"? | `CH-04` | Same |
| Does "minimal improvement" satisfy the policy's "no improvement"? | `MRI-01` | The rule already assumes yes. If the answer is no, the response requirement itself is wrong and that outranks this change |

If the textual rows (`CH-02`, `CH-04`) are confirmed, the change is justified on those alone. The policy rows decide whether review is the right destination or whether `NOT_DOCUMENTED` would be.

**What is not proposed.** No new disqualifier phrases, no change to the generic pathways, no recall expansion, no cross-sentence linking, no relationship model, no model-based extraction.

## 4. Evaluation integrity

- `holdout_v1` remains sealed: 10 notes, no labels, never run. The agent will not label or run it.
- The challenge set is adversarial. Fourteen of its 20 notes were chosen after their output had been seen, and the rest were written by an author who had read the extractor. Its counts are a list of known failures. Its proportions are not estimates of real-world or clinical performance.
- The bundled corpus agrees on 193 of 193 because it was built with the extractor. It is a regression pin.

**Towards an independent dataset.** The current sets cannot become independent, because their author knows the extractor. A set that could support a claim would need:

1. Notes written by someone who has not read the extraction code or its tests, working only from a one-page brief naming the four procedures and their requirements. A clinician or a clinical documentation specialist is the right author. Thirty to fifty short notes is enough to start.
2. Labels by a second person, also blind to tool output, using the schema here. Disagreements between the two are kept as `needs_review`, not resolved by the tool.
3. A mix fixed in advance: at least 40% of requirement labels expected `MET`, so recall is measured as firmly as false `MET`.
4. Hashes committed before the first run, one run per frozen extractor version, and no tuning against it. Notes that are used for tuning move to the challenge set.
5. Synthetic or fully public source text only. The project does not screen for PHI, so real clinical notes are out of scope.

Until that exists, results should be described as agreement with provisional labels on synthetic notes.
