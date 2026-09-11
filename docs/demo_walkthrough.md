# Five-Minute Demo Walkthrough

Demonstrate three decisions in order: distinct evidence outcomes, human verification despite exact citations, and policy-change replay that preserves history. Installation, app startup, and generating the replay fixture happen before the five-minute presentation.

## Prepare Before Starting The Clock

```bash
make install PYTHON=python3.12
make run
```

In a second terminal:

```bash
.venv/bin/python cli.py evaluate --demo-case CPAP-02-borderline
.venv/bin/python cli.py evaluate --demo-case MRI-08-edge-below-threshold
.venv/bin/python cli.py evaluate --demo-case MRI-KNEE-05-conflict-deny-then-positive
.venv/bin/python -m scripts.replay_demo --output-dir /tmp/pa-replay-run
```

Use a new output directory for each replay run; existing directories are rejected. Keep the three short CLI outputs available. Open `v1-to-v2.json`, `v2-to-v3.json`, and `summary.json` from the generated directory in an editor. Find the case IDs below in advance. In Streamlit, load `MRI-01-complete` and scroll to Results.

The replay fixture consists of **14 hand-authored synthetic cases across three synthetic policy versions**, constructed to exercise the differential categories. All counts in the generated reports demonstrate that the mechanism distinguishes outcome flips, newly undeterminable cases, unchanged outcomes with changed reasoning, and resolved refusals. They do not estimate how often real policy changes produce these outcomes. Fabricated historical attestations are labeled as fixture data.

If setup is unavailable, use the checked-in [ordinary artifacts](artifacts/README.md), [human-verified golden fixture](../test/golden/evaluations/MRI-01-human-verified.json), [replay explanation and case results](policy_replay.md), and [synthetic replay summary](artifacts/policy_replay_summary.json). The summary comes from the same 14 constructed synthetic cases and three synthetic policy versions; its counts are mechanism demonstrations, not prevalence estimates.

## 0:00–1:30 — Different Evidence Problems Need Different Outcomes

State the scope in one sentence: “This is a synthetic administrative documentation demo; it does not determine medical necessity or predict payer approval.”

Show the prepared CLI outputs:

| Case | Result | What the reviewer needs to distinguish |
| --- | --- | --- |
| `CPAP-02-borderline` | `CANNOT_DETERMINE` | Sleep-study date and numeric AHI/RDI evidence were not captured. Missing evidence must not be treated as a failed threshold. |
| `MRI-08-edge-below-threshold` | `NOT_READY` | Five captured therapy weeks fail the six-week minimum. The other three lumbar requirements pass. |
| `MRI-KNEE-05-conflict-deny-then-positive` | `NEEDS_REVIEW` | Denied locking and later reported buckling create conflicting mechanical-symptom evidence requiring interpretation. |

Point out the precedence: missing evidence, then ambiguity, then a failed operator. These are results over captured proposals; the next step is reviewing whether those proposals are supported.

## 1:30–2:45 — Exact Citations Do Not Establish Correct Facts

Show the prepared `MRI-01-complete` result in Streamlit. All four operators pass, but the result is `PENDING_VERIFICATION`.

Open the original synthetic note and inspect each proposed fact and cited source span. Enter the reviewer's name and check only the facts actually verified. Select **Record human verification**. This example becomes `READY` after all four attestations because every operator is `MET` and every requirement fact is `HUMAN_VERIFIED`. Policy trust is not a prerequisite for documentation status `READY`. The separate `submission_readiness=true` gate additionally requires current verified policy provenance, a trusted active rulebook, and no unresolved drift. Documentation can remain `READY` while `submission_readiness=false`.

Explain: “The extractor can produce an affirmative lumbar diagnosis from a negated sentence. Exact offsets only prove where the text came from. A person must check its meaning.” The [executable extraction contract](../EXTRACTION_CONTRACT.md) retains that failure explicitly.

Reviewer identity is self-reported, and the app cannot prove review happened. If source freshness has expired, acknowledge the governance warning for inspection; do not claim that acknowledgement restores trust. The [verified golden fixture](../test/golden/evaluations/MRI-01-human-verified.json) shows the fixed historical example with synthetic attestations.

## 2:45–4:45 — Replay Changed Policy Without Rewriting History

Show the prepared replay reports. These examples use the same 14 hand-authored synthetic cases across three synthetic policy versions; they were constructed to exercise categories, and any displayed counts demonstrate the mechanism rather than real-world prevalence.

In `v1-to-v2.json`, inspect:

- `v1:C01`: `OUTCOME_CHANGED`; therapy minimum changes from six to eight weeks, and the captured six weeks now fail. `outcome_driving_criteria` identifies `conservative_therapy_weeks`.
- `v1:C06`: `BECAME_UNDETERMINABLE`; the target adds neurologic documentation that was never captured. Replay leaves the gap missing rather than manufacturing a determination.
- `v1:C03`: `REASONING_CHANGED`; its eight weeks still pass, but the threshold and required criteria differ.

In `v2-to-v3.json`, inspect `v2:C10`: `REFUSAL_RESOLVED`. The old missing-imaging refusal was correct. The new policy removes that requirement, so the same captured evidence can now be evaluated. This is a reason to revisit old refusals instead of leaving them untouched. `v2:C12` similarly resolves an unrecognized-imaging refusal.

Show `human_review_required=true`, `submission_readiness=false`, and `PENDING_VERIFICATION` on the all-met replay. Even a resolved refusal never automatically becomes READY. The original decision and its policy remain intact; the report is a separate artifact.

## 4:45–5:00 — Close On The Boundary

Point to `archive_unchanged_after_replay` in the prepared summary. Explain: “Policy identity makes the old decision explainable; replay shows what changes; fresh human review decides whether the new proposal is supported.”

The summary counts refer only to the 14 constructed synthetic cases across three synthetic policy versions. They demonstrate category distinctions, not policy-change prevalence. The archive is local append-only SQLite, not a production patient-record or authenticated review system.

## Optional Follow-Up After The Five Minutes

Read an original record with the existing CLI:

```bash
.venv/bin/python cli.py decision-show --store /tmp/pa-replay-run/history.sqlite --decision-id v2:C10
```

See [policy versioning and replay](policy_replay.md) for import, archive, selection, and read-only replay commands. `make reviewer-demo` remains the original evaluation/export smoke path; it does not run replay. The [reviewer guide](reviewer_guide.md) covers installation, artifacts, and broader boundaries.
