# Policy versions and historical replay

This extension wraps the v1.5.0 deterministic evaluator. `engine/evaluate.py`,
`engine/extract.py`, the runtime rule files, and the existing rulebook releases
are unchanged. There is no language model in evaluation or replay.

Every service evaluation now embeds a `policy_version` in its result and audit
trace. The snapshot contains a policy-family identifier, version identifier,
effective date, payer/procedure/site scope, canonical criteria, and SHA-256 hash.
The hash covers the entire snapshot content except the hash itself, including
identifiers and effective date. `criteria_json` is canonical JSON; the Python
`requirements` property returns a fresh decoded copy. The snapshot is deeply
immutable. Identical content imports are idempotent; changing content under an
existing family/version identity is rejected.

Legacy runtime rules become snapshots automatically. Their declared rule-update
date supplies the effective date of the local criteria artifact; this is **not a
claim about the payer's effective date**. Newly imported versions declare their
own effective date. Selection is explicit: importing a policy does not promote
runtime rules, and replay can target older or future versions for comparison.

## Archive and CLI

The archive is a local SQLite file with two tables: policies and decisions.
Primary keys, foreign keys, and triggers reject updates, deletes, and replacement
inserts. A decision includes its original request, captured facts, evidence spans,
verification records, requirement results, policy snapshot, and audit trace. Its
SHA-256 hash binds the decision ID and the serialized evaluation. Reads validate
both decision and policy hashes. Replays open SQLite in read-only mode and return
new reports. CLI report output uses exclusive creation and cannot overwrite an
existing decision export, database, or report.

Persistent recording is explicit through `evaluate --store`; ordinary UI/API/CLI
evaluations still embed their policy snapshot without creating a database.
The archive has no update/delete API. A caller can edit an in-memory evaluation
copy, but it cannot change an already archived decision. Old v1.5.0 JSON exports
that lack a policy snapshot and capture states are not guessed into replayable
history. Re-evaluating an old note now creates a new decision, not a historical
reconstruction.

From the repository root:

```bash
.venv/bin/python cli.py policy-add --store /tmp/pa-history.sqlite \
  --file inputs/replay/policies/v1.json
.venv/bin/python cli.py policy-add --store /tmp/pa-history.sqlite \
  --file inputs/replay/policies/v2.json
.venv/bin/python cli.py policy-add --store /tmp/pa-history.sqlite \
  --file inputs/replay/policies/v3.json
.venv/bin/python cli.py policy-list --store /tmp/pa-history.sqlite

.venv/bin/python cli.py evaluate --demo-case MRI-CERV-01-ready \
  --store /tmp/pa-history.sqlite --decision-id cervical-001 \
  --policy-id synthetic-cervical-mri --policy-version v1 --json

.venv/bin/python cli.py replay --store /tmp/pa-history.sqlite \
  --policy-id synthetic-cervical-mri --from-version v1 --target-version v2 \
  --output /tmp/cervical-v1-to-v2.json
.venv/bin/python cli.py decision-show --store /tmp/pa-history.sqlite \
  --decision-id cervical-001
```

Use repeated `replay --decision-id ID` arguments to select a particular set
instead of `--from-version`. Omitting both selects all decisions in the requested
policy family. Duplicate IDs, unknown IDs/versions, and mismatched policy family,
procedure, or site scope fail explicitly; nothing is silently dropped from the
denominator. An empty selection returns zero counts with zero denominators.

`policy-add --file` accepts a sealed snapshot, as bundled, or a descriptor with
`policy_id`, `version_id`, `effective_date` (`YYYY-MM-DD`), `payer`,
`procedure_code`, `supported_sites`, and `requirements`. For a descriptor, the
loader validates the existing rule operators and creates the canonical hash.
Requirement keys must be unique and the criterion list must be nonempty.

## Replay contract

Replay invokes the existing `evaluate_requirements` and `compute_overall_status`
functions on the archived facts. It never extracts from the old note again,
fetches evidence, or reads current runtime policies. Capture states distinguish
missing values from ambiguous values, including facts that were captured but
were not required by the original policy. An uncaptured target fact stays
missing. An ambiguous captured fact stays ambiguous.
If a target operator requires a different scalar type, the incompatible captured
value routes to review; for example, a stored boolean cannot become a numeric
duration. Both explicit policy evaluation and replay apply this check before
calling the existing evaluator.

The existing precedence remains: missing documentation → `CANNOT_DETERMINE`;
otherwise ambiguity → `NEEDS_REVIEW`; otherwise a failed criterion → `NOT_READY`.
Missing information takes precedence even when another documented value fails a
new threshold. Removing a criterion can legitimately resolve a refusal if all
remaining required evidence supports evaluation. Such transitions have their own
category and never imply that the formerly missing evidence was obtained.

Human attestations never transfer to replay results, even for same-version
replay. All replay reports set `human_review_required=true` and
`submission_readiness=false`. All-met replays are `PENDING_VERIFICATION`.
The original human-verified `READY` remains unchanged in the archive. Fresh
evaluation under an explicit version binds attestations to that version's hash
as well as the existing request/bundle fingerprint. Selecting an alternate
snapshot does not inherit verified policy trust from the current runtime policy.

To avoid confusing a verification reset with a policy outcome change, the
comparison uses `CRITERIA_MET` for both original `READY` and original
`PENDING_VERIFICATION`. The report also retains `original_overall_status` and
the actual replay `overall_status`.

Each case belongs to exactly one category:

| Category | Meaning |
| --- | --- |
| `BECAME_UNDETERMINABLE` | Target requires missing evidence; source was not `CANNOT_DETERMINE`. |
| `BECAME_REVIEW_REQUIRED` | Target requires ambiguous evidence; source was not `NEEDS_REVIEW`. |
| `REFUSAL_RESOLVED` | Original `CANNOT_DETERMINE` or `NEEDS_REVIEW` becomes evaluable using the same captured evidence under the target criteria. Relaxing evidence requirements can resolve a refusal; fresh human review is still required and READY is never automatic. |
| `OUTCOME_CHANGED` | Evaluable criterion outcome flips between `CRITERIA_MET` and `NOT_READY`. |
| `REASONING_CHANGED` | Criterion outcome stays the same, but criterion definitions or results differ. |
| `UNCHANGED` | Same criterion outcome, definitions, and results. Verification reset is reported separately. |

Resolved refusal is the mirror image of becoming newly undeterminable: adding
evidence requirements can make an old case insufficient, while relaxing them can
make its existing evidence sufficient. It is a separate category from an outcome
flip between two determinations. The old refusal was correct under the old
policy; resolving it does not mean the old decision was an error or that missing
evidence has since been collected.

Operationally, this is a reason to re-run an archive when a policy changes.
A case correctly refused under an older policy may now be determinable, so
leaving old refusals untouched can miss cases that warrant another review.
The replay surfaces the removed or relaxed criterion and the resulting proposal
for human review. Even when every remaining criterion is met, a resolved refusal
returns `PENDING_VERIFICATION`, with `human_review_required=true` and
`submission_readiness=false`; it does not automatically become `READY`.

`criterion_differences` provides added/removed/modified criterion keys, old/new
definitions, statuses, and reasons. `outcome_driving_criteria` identifies the
changed blockers involved in an outcome transition; it is not a claim that each
is independently sufficient when several blockers coexist. `missing_evidence`
lists all target gaps; `newly_required_missing_evidence` isolates added criteria.
Thus an already-undeterminable case gaining another evidence gap remains visible
even though it is not counted as newly undeterminable.

Category counts carry the full selected-decision denominator. The additional
`refusals_preserved` measure uses the number of original refusals as its
denominator. `target_outcomes` shares `total_decisions` as its denominator.

## Demonstration and actual results

The bundled policy is an **illustrative cervical-MRI documentation pathway**
using the existing synthetic Aetna cervical scope. These are hypothetical policy
revisions, not actual Aetna changes or coverage guidance:

| Version | Effective date | Criteria |
| --- | --- | --- |
| v1 | 2026-01-01 | Therapy ≥6 weeks, symptoms ≥6 weeks, prior imaging in the enumerated pathway. |
| v2 | 2026-04-01 | Therapy tightened to ≥8 weeks; explicit neurologic red-flag documentation added. |
| v3 | 2026-07-01 | Prior-imaging criterion removed; v2's other criteria retained. |

The 14 hand-authored synthetic cases were constructed to exercise each
differential category across three synthetic policy versions. They include
six-/seven-/eight-week therapy, short symptoms,
abnormal/unrecognized/missing imaging, missing neurologic documentation, missing
therapy duration, and conflicting symptom durations. Three cases carry explicitly
labeled **fabricated historical human-verification fixtures** when all criteria
are met. They are not presented as actual human review.

Run the full demonstration into a **new** directory:

```bash
.venv/bin/python -m scripts.replay_demo --output-dir /tmp/pa-replay-run
```

The command records the same 14 hand-authored synthetic cases under each of
three synthetic policy versions (42 synthetic historical decisions), then replays
every source cohort against every target, including same-version controls:
**126 comparisons across nine reports**. These constructed cases exercise the
differential categories; the counts demonstrate the mechanism's distinctions,
not how frequently real policy changes produce each outcome. It writes the
archive, all nine detailed JSON reports, and `summary.json`. The archive's bytes
are checked before and after replay. A checked-in summary of the actual run is
[policy_replay_summary.json](artifacts/policy_replay_summary.json).

Every row below has denominator **14 decisions from the same 14 hand-authored
synthetic cases**, evaluated across **three synthetic policy versions**. The
cases were constructed to exercise each differential category. These counts
demonstrate that the mechanism correctly distinguishes outcome flips,
newly-undeterminable cases, unchanged outcomes with changed reasoning, and
resolved refusals. **They are not an estimate of how often real policy changes
produce each outcome.**

| Replay | Outcome flip | Newly undeterminable | Newly needs review | Refusal resolved | Same outcome, different reasoning | Unchanged |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| v1 → v1 | 0 | 0 | 0 | 0 | 0 | 14 |
| v1 → v2 | 2 | 3 | 0 | 0 | 9 | 0 |
| v1 → v3 | 3 | 3 | 0 | 2 | 6 | 0 |
| v2 → v1 | 2 | 0 | 0 | 3 | 9 | 0 |
| v2 → v2 | 0 | 0 | 0 | 0 | 0 | 14 |
| v2 → v3 | 1 | 0 | 0 | 2 | 11 | 0 |
| v3 → v1 | 3 | 1 | 1 | 3 | 6 | 0 |
| v3 → v2 | 1 | 1 | 1 | 0 | 11 | 0 |
| v3 → v3 | 0 | 0 | 0 | 0 | 0 | 14 |

For v1 → v2 in this constructed set of 14 hand-authored synthetic cases,
C01/C02 fail the tightened therapy threshold; C06/C07/C08 lack
the newly required neurologic documentation. C07 also fails the new threshold,
and C08 already failed the old threshold: both correctly become undeterminable.
All four original refusals remain refusals (4/4). This is a demonstration of
correct refusal preservation in selected synthetic cases, not a real-world
frequency estimate.

For v2 → v3 in the same constructed set of 14 hand-authored synthetic cases,
C09's abnormal-imaging failure disappears, C10's missing-imaging
refusal resolves, and C12's unrecognized-imaging review requirement disappears.
All three become `PENDING_VERIFICATION`, never automatically `READY`.
Five of seven original refusals remain refusals (5/7); two cases resolve their
refusals (2/14 of the synthetic cohort, 2/7 of its original refusals). These counts
demonstrate the resolved-refusal mechanism, not its prevalence under real policy
changes. The newer synthetic policy requires less evidence: removing the imaging
criterion makes the existing case files sufficient for the remaining criteria.
These cases still require human review and fresh verification. Missing therapy
and conflicting symptom durations continue to refuse across all versions.

These are fixture counts, not estimates of policy impact in a real population.
SQLite triggers and hashes protect the supported local workflow and detect
corruption; they are not authentication, encryption, or protection against a
privileged actor rewriting the database and its schema. Replay adds no queue,
intake API, routing, monitoring, or web console.
