# Model Card

Project: Prior Authorization Readiness Copilot  
Version: 2.3.0 (record schema 2.0.0)

Changelog: 2.3.0 — Releases five bounded exp-001 extraction fixes: auxiliary-verb
negation, reflex descriptor linkage, intact reflexes, negated numeric-strength
review and cross-sentence sleep-date association. Human-verification, policy
trust and record-schema semantics are unchanged. See [release notes](docs/releases/v2.3.0.md).

Automated extraction is a drafting aid, not a decision gate. v1.4.0's posture over-trusted extraction: negated diagnoses returned affirmative facts and contradicted the extraction contract as written. v1.5.0 resolves the contradiction by changing what the engine may assert rather than by making extraction match the contract. Known false proposals remain; the executable contract records them explicitly.

## Current Repo

- Deterministic administrative readiness review
- Deterministic write-only letter drafting
- Sealed policy snapshots on every service evaluation; opt-in CLI SQLite decision archive and non-destructive replay
- No LLM implementation
- Verified provenance is limited to the supported Aetna CPB 0236 lumbar-radiculopathy branch; all other pathways remain synthetic/demo
- Bundled case data is synthetic; the official policy snapshot and rule provenance are source material; input is not screened and must not contain real PHI, with screening remaining the operator's responsibility

## Intended Use

- Local demo and offline review of synthetic prior authorization cases
- Review of missing documentation versus documented threshold failures
- Inspection of audit artifacts and deterministic decision logic

## Out of Scope

- Clinical decision support
- Approval prediction
- Autonomous submission or appeals
- Runtime policy interpretation
- Production PHI workflows

## Inputs

- Payer
- Procedure code
- Diagnosis codes
- Site of care
- Specialty
- Free-form note text; unscreened and restricted to synthetic data by operator policy

## Outputs

- Requirement-level `MET`, `NOT_MET`, `NOT_DOCUMENTED`, and `NEEDS_REVIEW`
- Overall `PENDING_VERIFICATION`, `READY`, `NOT_READY`, `CANNOT_DETERMINE`, or `NEEDS_REVIEW`
- Each requirement's proposed value, verification state, reviewer/time and proposal fingerprint
- Blocking issues
- Deterministic write-only letter draft
- Audit JSON including the selected policy snapshot
- CLI replay reports with criterion differences, category counts and denominators; all-met replays are PENDING_VERIFICATION

## Safety Boundaries

- Automated proposals can misread missing, negated, resolved or unrelated information
- All-MET proposals remain `PENDING_VERIFICATION` until every requirement fact is `HUMAN_VERIFIED`
- Any `NOT_DOCUMENTED` result forces `CANNOT_DETERMINE`
- With no missing result, any `NEEDS_REVIEW` result forces the human-review disposition instead of a threshold failure
- Policy drift does not update rules automatically
- Drafting cannot override evaluated statuses

## Evaluation

The repo includes pytest coverage for extraction, verification, evaluation, drafting, rule loading, policy-monitor helpers, archive immutability, and replay categories. All bundled evaluation cases are synthetic. The checked-in fixture reports 52/52 exact statuses and 0 false `READY` results among 52 expected non-`READY` cases, including seven `PENDING_VERIFICATION` cases. Zero automated READY is enforced structurally; it is not an extraction-accuracy estimate. The executable contract tests cover every numbered guarantee and published exact example, including the resolved auxiliary-verb denial and the remaining neither/nor
and same-sentence date gaps. Fresh suite: **1123 passed, 10 xfailed**. The
negated-strength False expectation remains disputed; implementation requires
review rather than proposing a normal exam. Corpus false PENDING_VERIFICATION
is zero; original authored cases score 45/45 with zero false pending, while the
expanded 47 still have two false pending results. The always-abstain canary
also achieves zero false pending, so that metric alone proves no improvement.

## Known Limits

- Narrow rule coverage
- Regex-based extraction with limited phrase support
- Source spans now exactly equal original-note slices at Python character offsets, including Unicode. This does not establish semantic support, attribution or complete context.
- Human-verification identity is self-reported, not authenticated; the local demo cannot establish that a person actually reviewed a fact. Incorrect human attestations can still permit false READY.
- v2.3.0 rejects the cross-sentence borrowed study date. Same-sentence unrelated
  visit dates remain a false-proposal path; incorrect attestations can still
  yield READY, with submission_readiness=false under CPAP demo trust. Neither/nor
  lumbar denial also remains an unsafe proposal under the verification gate.
- `MRI_LUMBAR` is monitored for drift; `MRI_CERVICAL`, `MRI_KNEE`, and `CPAP_DEVICE` are supported in rules but not monitored for drift
- `MRI_LUMBAR` receives `verified` trust only for the implemented Aetna CPB 0236 radiculopathy branch while its scoped source hash and freshness checks remain valid; all other procedures remain `demo`
- CPB 0236 does not explicitly prescribe a required combination of its listed conservative-therapy modalities; the prototype accepts a qualifying documented modality and does not sum shorter sequential courses without explicit overall duration
- The local archive retains full synthetic requests and verification records without authentication, encryption, or production retention controls; ordinary UI/API evaluation is not automatically persisted
- Replay uses captured evidence only, never re-extracts notes, and never carries attestations forward; removed requirements can resolve old refusals without creating READY
- No production integration

## Possible Extensions

- Expand rule coverage with provenance updates and tests
- Add production integration layers outside this repo
- Evaluate optional LLM-assisted text formatting behind strict contracts if the scope ever changes
