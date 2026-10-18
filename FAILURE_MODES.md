# FAILURE_MODES.md

v2.0.0 mitigation: typed correction validation rejects SET_VALUE spans over 300 characters without truncation. Changed correction content/order invalidates every attestation; Streamlit clears stale results and letters when corrections are applied. See the canonical [correction limits](docs/safety_and_scope.md#correction-limits).

## Failure Modes, Safety Analysis, and Mitigations

**Project:** Prior Authorization Readiness Copilot  
**Owner:** Nicholas Leko  
**Last Updated:** October 18, 2026 — v2.7.0 release candidate
**Status:** Versioned current behavior. Changes should update tests and docs.

---

## 1) Scope and Safety Posture

Current repo status:
- deterministic implementation
- no LLM implementation
- bundled case data is synthetic; the official policy snapshot and rule provenance are source material; input is not screened and must not contain real PHI, with screening remaining the operator's responsibility

Automated extraction is a **drafting aid, not a decision gate**. v1.4.0's posture over-trusted extraction. Negated diagnoses returned affirmative facts, contradicting the extraction contract as written. v1.5.0 resolves that contradiction by changing what the engine may assert rather than by making extraction match the contract. v2.7.0 handles the bounded patterns below; the negation, temporality, attribution and other failure classes remain open.

Requirement results describe the captured proposals:
- proposed scalar passes the operator (`MET`), without asserting source support
- proposed scalar fails the operator (`NOT_MET`)
- not documented (`NOT_DOCUMENTED`)
- documented but ambiguous, contradictory, uncertain, or not safely evaluable (`NEEDS_REVIEW`)

It then derives an overall readiness status:
- `READY`
- `PENDING_VERIFICATION`
- `NOT_READY`
- `CANNOT_DETERMINE`
- `NEEDS_REVIEW`

The system is intentionally:
- **non-predictive**
- **non-clinical**
- **non-autonomous**
- **refusal-first when missingness exists**

---

## 2) Safety-Critical Design Guarantees (Invariants)

### 2.1 Current Readiness Invariants
- Any `NOT_DOCUMENTED` ⇒ overall status **must** be `CANNOT_DETERMINE`
- Any `NEEDS_REVIEW` (and no `NOT_DOCUMENTED`) ⇒ overall status **must** be `NEEDS_REVIEW`
- Any `NOT_MET` (and no `NOT_DOCUMENTED` or `NEEDS_REVIEW`) ⇒ overall status **must** be `NOT_READY`
- No blockers and any unverified requirement fact ⇒ `PENDING_VERIFICATION`, submission readiness false
- No blockers and all requirement facts `HUMAN_VERIFIED` ⇒ `READY`
- `submission_readiness=true` additionally requires `READY`, current verified policy trust, a trustworthy active rulebook, and no unresolved or invalid governance state

Invariant violations are surfaced in:
- UI banners
- audit output
- tests (behavioral contract)

### 2.2 Source-location and verification guarantees
- Captured spans have original-note character offsets and exact source-slice text, including Unicode case expansion. This guarantees location integrity, not semantic support or complete context.
- Requirement facts default to `UNVERIFIED`. `HUMAN_VERIFIED` records reviewer/time and is bound to the exact request, rule bundle, proposal and evidence.
- A reviewer must leave unsupported facts unverified. Verification cannot edit scalars or override missing, ambiguous or failed requirements.
- Self-reported identity is not authentication. Rubber-stamping or fabricated attestations can still permit false READY; the CLI archive can retain these records, but is not an authenticated or tamper-resistant production attestation ledger.

### 2.3 Write-only Letter Guarantee
Letter drafting:
- accepts only `LetterDraftInput`, whose typed request metadata has no `note_text` field and rejects extra fields
- cannot change requirement results or readiness status
- renders caller-supplied structured reasons without independently validating them against evidence snippets
- successful templates include non-guarantee framing (“does not guarantee payer approval”); blocked drafts return `DRAFT_BLOCKED` and reasons instead of a complete letter

### 2.4 Policy Drift Governance Guarantee
- Policy drift detection flags **human review** for configured sources and can downgrade policy trust, blocking submission readiness
- Rules are never auto-updated
- Policy meaning is never inferred (no LLM policy interpretation)
- UI gates evaluation if drift is detected for a monitored source (`REVIEW_REQUIRED` acknowledgement required)
- Acknowledgement permits inspection only; it does not restore verified trust or make `submission_readiness` true
- Malformed drift-log state and any recorded drift without an explicit resolution mechanism fail policy trust closed

---

## 3) Failure Mode Taxonomy

### FM-1: False READY (Unsafe Over-Trust)
**Definition:** System outputs `READY` when criteria are actually missing or failing.

**Primary causes:**
- Extraction over-reads numbers (e.g., symptom duration misread as PT duration)
- Regex false positives under noisy notes
- Rule mapping mismatch vs policy source
- Incorrect or fabricated human attestations to unsupported proposals

**Mitigations:**
- v1.5.0 blocks READY on automated extraction alone; every requirement fact needs human verification
- Conservative extraction patterns (therapy duration must be therapy-linked)
- Evidence spans attached to each extracted field
- Synthetic regression tests include noise and edge cases
- Policy drift gating to reduce stale-rule risk

**Residual risk:** Cannot be eliminated in free-text notes; requires human review.

**Revision note, June 9, 2026:** Fable 5 identified three false-positive extraction paths that could produce false `MET` determinations before this fix:
- negated therapy phrasing, such as `Patient denies completing PT x 8 weeks`, could be extracted as completed conservative therapy
- future-tense therapy phrasing, such as `Will start PT for 6 weeks next month`, could be extracted as completed conservative therapy
- therapy durations, such as `Completed PT for 6 weeks`, could leak into `symptom_duration_weeks`

These were failures in the over-extraction direction, which is the direction the safety contract is designed to minimize. The patched extractor now rejects locally negated or future-planned therapy durations and skips therapy-context durations when extracting symptom duration. Regression coverage was added for the original cases and related phrasing variants. The residual risk remains non-zero for untested free-text phrasing.

**Revision note, August 31, 2026:** Candidate resolution now also fails closed for the tested cross-therapy, non-patient attribution, future/hypothetical, uncertainty/question, and contradictory-finding phrase families. The bundled labeled fixture and direct adversarial tests include forward/reversed order and lexical variants. This is bounded deterministic coverage, not a claim of general clinical-language understanding or zero real-world false `READY` risk.

**Revision note, September 4, 2026:** The fourth audit reproduced affirmative proposals from negated diagnoses and strength, reflex qualifiers borrowed from pain, resolved findings, and unrelated therapy. These errors remained at that audit. v2.3.0 fixes the bounded auxiliary-verb,
reflex-qualifier, negated-score and cross-sentence-date examples below; broader
classes remain open. Automated all-MET cases stop at PENDING_VERIFICATION. The borrowed sleep-study date was one case the existing design contained: v1.4.0 produced READY documentation status but submission_readiness=false under demo policy trust, as the README already allowed. This release also fixes Unicode offset corruption, long-lived service cache staleness after rule promotion, and unknown/misspelled monitoring frequencies disabling freshness enforcement. Exact contract examples and numbered guarantees are executable; finite tests cannot prove arbitrary clinical-language correctness.

---

### FM-2: False CANNOT_DETERMINE (Operational Friction)
**Definition:** System refuses (`CANNOT_DETERMINE`) even though documentation exists.

**Primary causes:**
- Under-capture of phrasing variants (“weakness absent”, “bowel/bladder intact”)
- Date formats not recognized for sleep study
- Imaging results described indirectly

**Mitigations:**
- Expand deterministic extraction patterns over time with tests
- Treat “imaging performed but unclear” as documented `inconclusive`
- Evidence snippets and the original note support review; editing synthetic input creates a new evaluation, not an override of an archived decision. Verification alone cannot correct scalars or clear missingness.

**Residual risk:** Some note styles remain unsupported; that’s acceptable given refusal-first posture.

---

### FM-3: Misclassification Between NOT_MET, NOT_DOCUMENTED, And NEEDS_REVIEW
**Definition:** System marks a requirement as failing (`NOT_MET`) when it is actually missing or unevaluable, or otherwise confuses the three states.

**Primary causes:**
- Ambiguous phrasing (e.g., “trialed PT” with no duration)
- Implicit documentation without thresholds

**Mitigations:**
- Hard separation: failed thresholds use `NOT_MET`, missing values use `NOT_DOCUMENTED`, and ambiguous, contradictory, uncertain, or otherwise unsafe-to-resolve values use `NEEDS_REVIEW`
- “duration not specified” ⇒ `NOT_DOCUMENTED`
- Rule reasons explicitly instruct what must be documented

---

### FM-4: Evidence Snippet Coverage Gaps
**Definition:** A requirement status is correct, but evidence snippet is missing.

**Primary causes:**
- Span capture misses the exact triggering substring
- Multi-sentence contexts

**Mitigations:**
- Evidence map stores spans from extraction layer
- UI shows “No supporting snippet was captured for this requirement.” when its snippet list is empty
- Tests validate snippet presence for key pathways

**Residual risk:** Evidence gaps reduce reviewer trust; requires iterative pattern tuning.

---

### FM-5: Policy Drift (Stale Rules)
**Definition:** Payer changes policy; rules remain old; system produces outdated decisions.

**Primary causes:**
- External policy update
- Plan-specific variation not captured by general bulletin

**Mitigations:**
- Snapshot + hash drift detection
- Snapshot structure, source identity, timestamp, stored-content hash, and drift-log validation
- Diff artifact generation
- Drift checker appends events to a JSONL file; unlike the SQLite decision archive, this file has no update/delete enforcement
- UI `REVIEW_REQUIRED` gate
- sealed policy snapshots and opt-in append-only decision archiving identify the version behind each historical result
- replay reports policy-change effects without rewriting history or transferring attestations; relaxed requirements may resolve a correct old refusal for fresh review

**Residual risk:** Drift between checks; mitigated by check frequency + governance.

---

### FM-6: Over-Trust in Generated Letter Text
**Definition:** User treats letter as authoritative or submits without review.

**Primary causes:**
- Automation bias
- Letter phrasing too strong

**Mitigations:**
- Deterministic drafting and prohibited-language constraints
- Explicit “does not guarantee payer approval” line
- No clinical recommendations; no prediction language
- Audit linkage via hash (traceability)

**Residual risk:** Human behavior; mitigated through UI framing and governance policies.

---

### FM-7: Misuse Outside Intended Scope
**Definition:** Used for real PHI, autonomous submission, or clinical decisioning.

**Mitigations:**
- Explicit non-goals in README, MODEL_CARD, and safety docs
- Runtime evaluation records retain the full request, including note text, and runtime exports serialize it; checked-in repository artifacts replace full `note_text` values with a short hash and `[redacted for repository]`
- Audit and export payloads include the request, note hash, facts, evidence spans, provenance, requirements, blockers, warnings, and metrics
- scope panel states that the product checks administrative readiness only

---

## 4) Monitoring & Kill Switches (Operational Controls)

- **Bundled synthetic eval mismatch in the UI** ⇒ local evaluation disabled
- **Pytest failure in CI** ⇒ treat as a regression
- **Policy drift detected for a monitored source** ⇒ evaluation gated behind acknowledgment
- **Invariant violation detected** ⇒ surfaced in UI + audit; treat as a build defect

---

## 5) Change Control

Any change to:
- extraction patterns
- requirement semantics
- overall readiness invariants
- letter drafting constraints
- drift gating behavior

requires:
- updated tests
- version bump
- updated docs (README, model card, safety docs, and this file as needed)

---


## Patterns handled through v2.7.0; classes remain open

These patterns are handled; the class remains open. No row establishes general
correctness for negation, temporality, therapy response, event completion,
attribute association, or missingness scope.

| Failure class and reproduced input | Current disposition |
| --- | --- |
| NSAIDs for 8 weeks with no improvement in sleep **but significant improvement in pain** | Pattern handled; class remains open: linked duration/response require review, including however/though/although/yet/whereas and semicolon variants; full context is displayed with the unchanged citation marked. |
| OSA with ruled out anywhere in its sentence (any passive tense or intervening adverb) | Pattern handled; class remains open: diagnosis is missing, never affirmative. |
| PT x 8 weeks was never completed / not completed | Pattern handled; class remains open: duration is missing. |
| Stopped PT after 1 week. PT x 8 weeks was prescribed. | Pattern handled; class remains open: no completed duration is captured; the 1-week phrasing remains outside the supported duration forms. |
| PT x 8 weeks recommended / ordered / prescribed / not yet started / has not started (anywhere in its sentence) | Pattern handled; class remains open: duration is missing; qualifying NSAID courses receive the same exclusion. |
| Sleep study 2026-01-05 was cancelled / canceled | Pattern handled; class remains open: completed-study presence is missing. |
| OSA confirmed on PSG 2026-01-05, AHI 32. Allergies: N/A. / Bed partner unknown. | Pattern handled; class remains open: AHI presence is captured; unknown/N/A in its own sentence still refuses. No AHI threshold change. |
| Low back pain with radiculopathy resolved last year | Pattern handled; class remains open: same-sentence resolved/history of/prior episode/previous episode findings require review, including qualifying strength, mechanical, OSA and imaging findings. |
| Low back pain with radiculopathy. It resolved last year. | Remaining: cross-sentence historical episode coreference; strict xfail asserts review. |
| does/do/did not have low back pain with radiculopathy | Fixed bounded denial: False / NOT_READY; conflicting affirmative/negative proposals require review. Neither/nor remains open. |
| Root-distribution reflexes assessed, pain decreased | Fixed borrowed descriptor: no motor/reflex evidence; missing rather than affirmative. |
| Root-distribution reflexes intact | Fixed under-capture: normal finding / NOT_MET; not a missing finding. |
| Root-distribution strength not 4/5 | Fixed affirmative over-capture: NEEDS_REVIEW; the unchanged contract False / NOT_READY expectation remains disputed and strict-xfailed. |
| Visit date in another sentence from an undated sleep study | Fixed bounded association: no study-date evidence, CANNOT_DETERMINE. |
| Lumbar therapy actually for headaches | Remaining attribution failure; contract xfail expects missing. |
| Patient has neither low back pain nor radiculopathy | Remaining unsafe affirmative proposal; contract xfail expects False / NOT_READY. |
| Visit date and undated sleep study in the same sentence | Remaining unsafe borrowed-date proposal; contract xfail expects missing / CANNOT_DETERMINE. |
| Isolated NSAIDs for 42 days / two months / six weeks with explicit no improvement | Bounded recall fix: floor completed days to weeks, months to a four-week lower bound, and recognize number words one through twelve. Below-threshold or improved courses correctly fail. Modifiers, comparisons, fractions and episode linkage remain limited. |
| Direct right L5 distribution: strength 4 of 5 / 3 out of 5 / 4.5 of 5 | Bounded objective exam capture; 5 of 5 is normal. Explicit negation, question and alternative attribution review in this word-grade route. Opposite-side radiculopathy qualification is shared with legacy slash-grade and other retained objective-exam routes. |
| Spelled-out non-steroidal anti-inflammatory class names | Recall defect remains: exp-002's vocabulary expansion was reverted when unrelated headache therapy became unsafe passes. Listed drug names are now supported only through the owner-approved reviewed table and isolated course grammar; supported leading verbs and dose/frequency forms now parse, but unlisted course syntax remains limited. |

Objective-exam source qualification runs before shared literal laterality
qualification. Retained explicit opposite-side root findings, normal or abnormal,
require `NEEDS_REVIEW`. Matching, unsided and bilateral examination handling is
unchanged. The check can conservatively review historical or negated opposite-side
radiculopathy mentions; it does not resolve episodes, general negation,
non-patient attribution, omitted laterality or wider anatomical vocabulary.

### Reviewed drug vocabulary and incomplete courses

[engine/data/cpb0236_drugs_v1.json](engine/data/cpb0236_drugs_v1.json) is
owner-approved reviewed data for local use. **ATC codes require human verification
against WHO ATC before any external claim.** The table's human-review notice
remains; approval does not independently certify a transcription or brand alias.
Listed names replace only the class token, retaining existing guards. The first
exp-003 candidate ignored incomplete secondary drug statements and falsely passed
four linkage challenges; it was reverted. The accepted revision requires review
for unresolved eligible drug context alongside another course. It scores 74/74
on development cases with zero false pending across 63 negatives. This guard
may over-trigger, and separate-sentence planning/indication can still escape local
context. Exp-004 now recognizes supported reported-use verbs such as “Took”,
dose/frequency and duration-first ordering, retaining course guards.

### Copied-forward note text, template checkbox text, and persistence negation

Copied-forward note text and template checkbox text are named extraction failure
classes. The shared review path now recognizes previous/prior note,
copied from/forward, carried forward, from (the) prior/previous
note/visit/encounter, per (the) prior/previous note/visit, and
note/visit/encounter dated/from a numeric year or date in the finding's sentence.
The same path recognizes no longer persistence wording with
present/has/have/reports/noted/seen/evident/active, or directly after finding
wording. Checkbox tokens [ ], [x], [X], ☐, ☑ and ☒ before a finding in its
sentence require review regardless of checked state. These cues do not establish
that a finding is current or absent; they do not propose False.

Negation, temporality, copy-forward, template, attribution and cross-sentence
linkage **remain open**. A cue about one finding can over-trigger review of
another finding in the same sentence. A copy-forward header in another sentence
does not carry forward its scope. Improvement on the following line and
cross-sentence copy-forward remain unresolved. Their two strict xfails assert
review as the correct behavior. The explicit contralateral prior-hip-surgery
example now requires review under the shared literal laterality check; that does
not establish its episode or causal attribution. For the remaining unsafe cases,
the current proposals can still reach `READY` and `submission_readiness=true`
with supplied attestations and current verified governance. The new cues reduce
some wrong captured proposals; they do not establish general extraction
correctness or remove dependence on human review.


The independent check used 20 fresh inputs and found five wrong captures before
this pass: case 2 (semicolon response contrast), case 9 (ruled-out negation with
an adverb), case 10 (historical/prior-episode temporality), case 12 (resolved
historical episode across sentences), and case 13 (ordered/not-started therapy).
This pass handles cases 2, 9, 10 and 13; case 12 remains a strict xfail asserting
review. Case 2's secondary generic analgesic duration remains a strict xfail.
v2.3.0 handles case 18's intact reflexes and rejects the unrelated date in case
17. Case 17's input is unchanged, but its owner-approved labels now assert a
missing date / NOT_DOCUMENTED / CANNOT_DETERMINE, and its citation expectation
is empty. All 20 notes are named regressions, not a held-out measure. See
[v2.3.0](docs/releases/v2.3.0.md) for that release's results and
[v2.1.0](docs/releases/v2.1.0.md) for historical measurements.

Rule bundles now include runtime rules, provenance, policy sources, manifest and
referenced release files in their digest. Immutable parsed bundles and rulebook
status are cached by that identity. The final digest guard rejects concurrent
changes; changed disk content loads freshly on the next evaluation. Monitoring
snapshots and clock freshness continue to be checked live.

`ReadinessReport.letter_draft` is always initialized empty; generated letters are
returned separately by `generate_letter`. The obsolete corrected-letter guard
was removed. All existing correction/letter integrity validation remains.


## v2.6.0 safety metric and remaining pathways

Fresh validation: **1461 passed, 10 xfailed**. Four contract xfails comprise
unrelated therapy, neither/nor, same-sentence borrowed dates and the disputed
negated-strength label; six others cover two cross-sentence temporality tests,
generic analgesic duration and the three H1(a) open cases described above.

No automated READY is possible without attestations. The relevant automated
safety gate is false PENDING_VERIFICATION: unsupported all-MET proposals. Corpus
52/52 with zero false pending is unchanged. The original 45 authored cases now
score 45/45 with zero false pending; expanded 47 retain two false pending results.
The always-abstain canary also scores zero false pending, so exact status and
abstention versus expected must accompany that count.

Exp-002 accepted four narrow recall fixes, with all 55 accepted paired cases
exact and eleven additional nonpassing rejection guards. All 69 authored cases
improve 41/69 → 64/69 exact with no false pending across 54 negatives. This
includes twelve correct pending proposals, seven NOT_READY results and four
review results replacing missingness. Three positive misses and two wrong
negative abstentions from the rejected class-name attempt remain. The unsafe
intermediate candidate and its later attribution challenges are preserved in
the [exp-002 report](autoloop/exp-002/REPORT.md); no gain is credited to it.
Historical v2.5.0 owner-reported held-out results remain in that release’s notes.
Current exp-004 evidence and its held-out-discovered safety defect are below;
narrow authored phrasing improvements do not establish clinical generalization.

The remaining neither/nor lumbar proposal can become false READY with supplied
attestations and current verified governance. Same-sentence borrowed CPAP dates
can also become false documentation READY; demo trust keeps submission readiness
false. Neither attestation nor exact source offsets establish semantic truth.
The reflex grammar's bounded vocabulary/lookback, genuine cross-sentence date
links, other negation forms, laterality and episode resolution remain limitations.
See the [experiment report](autoloop/REPORT.md) for the owner-approved correction,
attestation and archive setup rewrites that retain these risks in executable
coverage rather than silently replacing them with easier positive inputs.


## Exp-004: source/performance failure found by held-out evaluation

The owner’s held-out evaluation found a motor grade attributed to the patient
with an exam deferred still returned PENDING_VERIFICATION. Our iteration-2 tests
and perfect visible dev check had missed this defect. Iteration 5 applies one
sentence-wide guard to new typed exams and legacy slash/word strength,
descriptive reflex and objective-weakness paths. Per patient, patient reports or
states, self-reported, by history, deferred, not performed, not examined, unable
to assess and limited by refusal disqualify the finding as objective. Semicolons
and decimal grades do not escape the guard. Qualified evidence alone gives
NOT_DOCUMENTED; conflicting normal/abnormal objective findings elsewhere give
NEEDS_REVIEW, with both sources cited. Agreeing objective evidence remains usable.

Before the repair, 13/24 new negatives falsely passed; after it, 0/24 do. All
102 own cases (30 positives / 72 negatives), visible dev 27/27 and corpus 52/52
pass with zero false pending; all 117 exp-002/003 negatives remain nonpassing.
Supported drug verbs/doses, typed root-linked motor/reflex grades, directly linked
calendar-valid study dates and spelled-out AHI/RDI indices improve coverage;
none establishes general objective provenance, root anatomy or event linkage.
Sentence-wide source exclusion can over-abstain on unrelated qualifiers.

The owner reports a separate never-visible 27-case held-out set, different wording:
exact 10→24/27, zero false PENDING_VERIFICATION. No held-out cases were read or
rerun here; earlier failure-class feedback informed the source guard. The three
remaining exact-status misses were not inspected. This is distinct from visible
dev’s 11→27/27 and from the safety failure on the prior held-out set. See
[v2.6.0](docs/releases/v2.6.0.md) and [exp-004](autoloop/exp-004/REPORT.md).


## v2.7.0 current verification and laterality bounds

Validation: **1681 passed, 9 xfailed**. The historical v2.6.0 counts above describe
that release. The explicit contralateral H1(a) test now passes; the other nine
strict expected failures remain. Source qualification must precede laterality:
agreeing patient-reported evidence is excluded before it can become a spurious
opposite-side review conflict with a legitimate objective examination.

A shared literal predicate handles recognized slash, word, typed motor/reflex,
descriptive reflex and objective-weakness routes. Normal and abnormal unilateral
mismatches require NEEDS_REVIEW. Historical, negated, relative-attributed and
mixed-side mentions can over-trigger review. Current episodes, general negation,
non-patient attribution and anatomical vocabulary remain bounded, not solved.
See [v2.7.0](docs/releases/v2.7.0.md) for release-candidate verification.
