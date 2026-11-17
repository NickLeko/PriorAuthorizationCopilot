# Requirement-level evaluation

This directory measures whether each extracted requirement result agrees with a written label. It exists because overall status alone cannot show extraction quality: a wrong `MET` can sit behind another requirement's `NOT_DOCUMENTED`, and a system that abstains on everything never produces a false pass.

It is evaluation only. Nothing here changes extraction, evaluation, archives, verification or readiness.

## What it does and does not measure

- It measures extraction proposals: the `MET`, `NOT_MET`, `NOT_DOCUMENTED` or `NEEDS_REVIEW` result of each requirement, with no human verification supplied.
- It does not measure authorization readiness. `READY` needs human verification, which the harness never supplies, so `READY` is unreachable and no false-`READY` rate is reported anywhere.
- It does not measure clinical accuracy. Every note is synthetic and no label has been reviewed by a clinician.
- It does not estimate an error rate for real notes. The sets are small and selected, so results are counts of observed failures on these notes.

## Files

| File | Purpose |
| --- | --- |
| [requirement_level_baseline.md](requirement_level_baseline.md) | Human-readable baseline for the current extractor |
| [requirement_level_baseline.json](requirement_level_baseline.json) | The same results, machine-readable |
| [decision_packet.md](decision_packet.md) | First review pass: 37 label decisions, without extractor output |
| [labeling_packet.csv](labeling_packet.csv) | Every label awaiting human review, without extractor output |
| [phase2_proposal.md](phase2_proposal.md) | Metric audit and failure mechanisms |
| [phase2_spec.md](phase2_spec.md) | Phase 2 implementation specification (not implemented) |
| `evaluation/datasets/corpus52_labels.json` | Per-requirement labels for the 52 bundled cases |
| `evaluation/datasets/challenge_v1.json` | 20 agent-authored notes aimed at known weak areas |
| `evaluation/datasets/framing_controls_v1.json` | 20 valid-course notes that a conservative change must keep `MET` |
| `evaluation/datasets/review_log_v1.json` | Human review decisions: textual ones as verified labels, policy and clinical ones as opinions |
| `evaluation/datasets/holdout_v1.json` | 10 sealed notes, unlabeled and never run |

Regenerate with `python -m evaluation.report`. `python -m evaluation.report --check` and the test suite both fail when the committed files are out of date, so a change in extraction behaviour shows up as a diff in the baseline.

## Label tiers

Each label covers one requirement of one note and records the expected state, other defensible states, an exact evidence quote, a rationale, its author, and its uncertainty.

| Tier | Meaning | Scored |
| --- | --- | --- |
| `verified` | A named human reviewed the label. The schema rejects this tier without a human reviewer and date. | Yes, reported on its own |
| `provisional` | Agent-authored and defensible from the note text. Not independently reviewed. | Yes, reported on its own |
| `needs_review` | The note or the contract does not settle the answer. | No. Listed with the question to decide |

Requirement tables never combine tiers; case-level results do, and say so. Verified labels exist only where a textual decision was given individually and logged in a review log; the report checks that every verified label has such an entry. Policy and clinical answers are logged as opinions and never verify a label. A requirement with no label is listed as unlabeled and excluded from every rate.

`acceptable_states` lists other states a careful reader could defend, usually a conservative `NEEDS_REVIEW`. `MET` appears there only when asserting the fact would be correct, so an unsupported `MET` always counts as a false `MET`.

## Metrics

Every rate carries its numerator, its denominator and what the denominator means. A zero denominator is reported as not measured.

| Metric | Question it answers |
| --- | --- |
| False MET | Of labels where `MET` is not defensible, how many did the extractor assert? |
| MET precision | Of the extractor's `MET` results, how many are defensible? |
| Missed MET, MET recall | Of labels expected `MET`, how many did the extractor miss or find? |
| Over-abstention | Of labels expected `MET` or `NOT_MET`, how many did the extractor leave undecided? |
| Abstention, review, decided coverage | How often the extractor abstains, asks for review, or decides |
| Evidence coverage, evidence overlap | Whether cited results carry a span, and whether that span overlaps the expected quote |

Each scored tier also reports three constant predictors on the same labels. Always-abstain predictors score zero false `MET` and zero recall, and are flagged `ZERO_MET_RECALL` and `NEVER_DECIDES`. An always-`MET` predictor scores full recall and is flagged `ASSERTS_EVERY_UNSUPPORTED_FACT`. A low false-`MET` count therefore cannot be read alone.

## Reviewing labels

1. Start with `decision_packet.md`. Then open `labeling_packet.csv`, where rows are ordered: decide the open questions first, then confirm medium and high uncertainty labels, then the rest, then label the holdout from scratch.
2. Do not run the tool on a note before labeling it. The packet leaves extractor output out for that reason.
3. Fill the reviewer columns. For each row, record the state, any other defensible state, an exact quote from the note, your name and the date.
4. Transfer decisions into the dataset file by setting `review_status` to `verified` with `reviewer`, `reviewer_type: "human"` and `reviewed_on`. Then regenerate the report.

A reviewer who is not a clinician can settle reading questions, such as whose therapy a sentence describes. Questions that depend on clinical or policy judgment, such as whether weakness in a named muscle satisfies a nerve-root requirement, should stay `needs_review` until a clinician or the policy owner answers them.

## Holdout

`holdout_v1` is sealed. The loader refuses it unless a caller passes an explicit override, the report never evaluates it, and a test pins its note hashes. It should be labeled by a human and run once, after an extraction change has been frozen. Its notes were written by an agent that had read the extractor source, so it is unrun but not independent. A human-written holdout would be stronger.
