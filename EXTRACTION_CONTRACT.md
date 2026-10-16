# Extraction, correction and verification contract v2.3

v2.0.0 retains the extractor and deterministic operators. Typed, source-located corrections materialize effective facts over an immutable original proposal; every ordered event is retained and the last event wins. SET_VALUE requires exact quotations of at most 300 characters per span and the submitted note hash; multiple spans are allowed and overlength spans are rejected, never truncated. SET_MISSING records document review and any offending proposal spans. SET_NEEDS_REVIEW and RESTORE_ORIGINAL preserve explicit state/history. Types, units and reviewer-enterable values come from fact contracts; there is no scalar coercion or free-text fact value.

Sleep-study presence means a completed study, excluding scheduled, ordered, pending or cancelled/canceled studies. Corrections do not verify facts: an otherwise passing effective fact set needs HUMAN_VERIFIED for every requirement before READY. See the canonical [correction limits](docs/safety_and_scope.md#correction-limits).

Automated extraction is a drafting aid, not a decision gate. A requirement's `MET`
status describes an operator applied to a proposed scalar; it does not establish
that the original note supports that scalar. v1.4.0 over-trusted extraction.
Its claim that a diagnosis returned True only without supported negation was
contradicted by `Patient does not have low back pain with radiculopathy`.
v1.5.0 resolves that contradiction by changing what the engine may assert,
not by making extraction match the old contract. Negation, temporality and
attribution errors remain. v2.3 handles the specific patterns listed below; each failure class remains open.

The normative guarantees are G01–G07 below and the exact examples in the JSON
block. `TestExtractionContractAlignment` executes correct expectations; remaining known failures are strict xfails. These finite examples are not universal language claims;
new contract claims must receive executable coverage in that class.

## Guarantees

- **G01**: `extract_facts(note)` is deterministic and uses regex/standard-library
  code, with no LLM, ontology, RAG or NLP library. It returns `(facts, evidence_map)`.
- **G02**: Each captured span has zero-based, end-exclusive Python character
  offsets into the original note, with `0 <= start < end <= len(note)` and
  `span.text == note[start:end]`, including Unicode case expansion. This is
  source-location integrity, not a guarantee of semantic support, complete
  context, correct attribution, or preservation of every relevant sentence.
  The evidence map may be empty for missing fields.
- **G03**: Every service evaluation requirement result exposes `fact_value`, `verification`, and a
  `verification_fingerprint`. Verification defaults to `UNVERIFIED` without
  metadata. `HUMAN_VERIFIED` requires a nonblank reviewer, timezone-aware,
  nonfuture timestamp, and the matching proposal fingerprint. Identity is
  self-reported in this local demo, not authenticated or independently audited.
- **G04**: Frozen overall status precedence is: any `NOT_DOCUMENTED` gives
  `CANNOT_DETERMINE`; otherwise any `NEEDS_REVIEW` gives `NEEDS_REVIEW`; otherwise
  any `NOT_MET` gives `NOT_READY`; otherwise any unverified requirement gives
  `PENDING_VERIFICATION`; otherwise `READY`. Empty requirements give
  `CANNOT_DETERMINE`. `PENDING_VERIFICATION` always has `submission_readiness=false`.
- **G05**: Attestations cannot change scalars or requirement statuses. Each is
  bound to the whole fact-set fingerprint plus its requirement key. The input
  fingerprint covers the normalized request excluding attestations/corrections,
  policy, bundle and contract version. The fact-set fingerprint additionally
  covers the immutable original snapshot, ordered correction events, effective
  values, states and evidence. Any correction content/order change invalidates
  every attestation, including facts not directly edited. Changed inputs or rule bundles invalidate prior attestations; unknown keys
  are rejected. The caller submits `fact_verifications` keyed by requirement.
- **G06**: Internal `__REVIEW_REQUIRED__` becomes public `null` in facts and
  requirement fact values, with `NEEDS_REVIEW` and captured spans preserved.
- **G07**: Even fully human-verified `READY` has `submission_readiness=false`
  for demo policy trust, stale/invalid monitoring or an untrusted active rulebook.
  Human verification cannot bypass those existing governance gates.

## Executable examples

Fields are boolean presence proposals (diagnosis, objective finding, response,
red-flag documentation, mechanical documentation, OSA, date and AHI), integer
week proposals, or imaging category proposals. Missing values are `null`;
ambiguity can use the internal review marker. The sleep-date and AHI fields
do not return parsed dates or numeric AHI values. The examples below specify
correct expectations, with known failures explicitly marked, rather than promising semantic accuracy
for whole phrase families. Optional `procedure` and `status` exercise the service
with Aetna/outpatient and no human attestations.

```json
[
  {"id":"negation_first","note":"Patient does not have low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with minimal improvement.","expected":{"back_pain_with_radiculopathy":false},"procedure":"MRI_LUMBAR","status":"NOT_READY"},
  {"id":"negated_strength","note":"Low back pain with radiculopathy. Right L5 distribution: dorsiflexion strength not 4/5. NSAIDs for 8 weeks with minimal improvement.","expected":{"objective_motor_or_reflex_change_in_root_distribution":false},"procedure":"MRI_LUMBAR","status":"NOT_READY","known_failure":"negation: score is explicitly negated"},
  {"id":"reflex_attribution","note":"Low back pain with radiculopathy. Right L5 distribution: reflexes assessed, pain decreased. NSAIDs for 8 weeks with minimal improvement.","expected":{"objective_motor_or_reflex_change_in_root_distribution":null},"procedure":"MRI_LUMBAR","status":"CANNOT_DETERMINE"},
  {"id":"resolved_diagnosis","note":"Low back pain with radiculopathy resolved last year. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with minimal improvement.","expected":{"back_pain_with_radiculopathy":"__REVIEW_REQUIRED__"},"procedure":"MRI_LUMBAR","status":"NEEDS_REVIEW"},
  {"id":"unrelated_therapy","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks for headaches with minimal improvement.","expected":{"cpb_0236_conservative_therapy_weeks":null,"cpb_0236_conservative_therapy_no_improvement":null},"procedure":"MRI_LUMBAR","status":"CANNOT_DETERMINE","known_failure":"attribution: headache therapy borrowed for lumbar episode"},
  {"id":"borrowed_date","note":"OSA. Visit date 2024-05-18. Sleep study date not recorded. AHI 22.","expected":{"sleep_study_date":null},"procedure":"CPAP_DEVICE","status":"CANNOT_DETERMINE"},
  {"id":"neither_nor_negation","note":"Patient has neither low back pain nor radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with no improvement.","expected":{"back_pain_with_radiculopathy":false},"procedure":"MRI_LUMBAR","status":"NOT_READY","known_failure":"negation: neither/nor scope is unsupported"},
  {"id":"same_sentence_borrowed_date","note":"OSA. Visit date 2024-05-18, sleep study date not recorded. AHI 22.","expected":{"sleep_study_date":null},"procedure":"CPAP_DEVICE","status":"CANNOT_DETERMINE","known_failure":"date association: unrelated visit date in the same sentence"},
  {"id":"unicode","note":"İ. OSA. Sleep study completed 2024-05-18. AHI 22.","expected":{"osa_diagnosis":true,"sleep_study_date":true,"ahi_documented":true},"procedure":"CPAP_DEVICE","status":"PENDING_VERIFICATION"},
  {"id":"therapy_weeks","note":"Completed PT for 8 weeks.","expected":{"conservative_therapy_weeks":8,"symptom_duration_weeks":null}},
  {"id":"therapy_negation_supported","note":"Patient denies completing PT x 8 weeks.","expected":{"conservative_therapy_weeks":null}},
  {"id":"therapy_future_supported","note":"Will start NSAIDs for 8 weeks with minimal improvement expected.","expected":{"cpb_0236_conservative_therapy_weeks":null,"cpb_0236_conservative_therapy_no_improvement":null}},
  {"id":"symptom_months","note":"Back pain x 2 months.","expected":{"symptom_duration_weeks":8}},
  {"id":"symptom_anchor","note":"Knee pain. Work leave for 8 weeks.","expected":{"symptom_duration_weeks":null}},
  {"id":"dx_negation_supported","note":"Low back pain without radiculopathy.","expected":{"back_pain_with_radiculopathy":false}},
  {"id":"dx_positive","note":"Low back pain with right leg radiculopathy.","expected":{"back_pain_with_radiculopathy":true}},
  {"id":"dx_family","note":"Mother has low back pain with radiculopathy.","expected":{"back_pain_with_radiculopathy":null}},
  {"id":"dx_hedge","note":"Low back pain with suspected radiculopathy.","expected":{"back_pain_with_radiculopathy":"__REVIEW_REQUIRED__"}},
  {"id":"objective_positive","note":"Right L5 distribution: strength 4/5.","expected":{"objective_motor_or_reflex_change_in_root_distribution":true}},
  {"id":"objective_normal","note":"Right L5 distribution: strength 5/5.","expected":{"objective_motor_or_reflex_change_in_root_distribution":false}},
  {"id":"objective_subjective","note":"Patient reports weakness in the right L5 distribution.","expected":{"objective_motor_or_reflex_change_in_root_distribution":null}},
  {"id":"cpb_response","note":"NSAIDs for 6 weeks with significant improvement.","expected":{"cpb_0236_conservative_therapy_weeks":6,"cpb_0236_conservative_therapy_no_improvement":false}},
  {"id":"cpb_linkage","note":"NSAIDs for 8 weeks. Analgesics with minimal improvement.","expected":{"cpb_0236_conservative_therapy_weeks":"__REVIEW_REQUIRED__","cpb_0236_conservative_therapy_no_improvement":"__REVIEW_REQUIRED__"}},
  {"id":"red_flags","note":"Denies weakness. No saddle anesthesia.","expected":{"neuro_red_flags_documented":true}},
  {"id":"imaging_missing","note":"Prior MRI reviewed.","expected":{"prior_imaging_result":null}},
  {"id":"imaging_none","note":"No prior imaging yet.","expected":{"prior_imaging_result":"none"}},
  {"id":"imaging_normal","note":"X-ray normal.","expected":{"prior_imaging_result":"normal"}},
  {"id":"imaging_negative","note":"X-ray showed no fracture.","expected":{"prior_imaging_result":"negative"}},
  {"id":"imaging_abnormal","note":"MRI showed stenosis.","expected":{"prior_imaging_result":"abnormal"}},
  {"id":"imaging_unclear","note":"MRI inconclusive.","expected":{"prior_imaging_result":"inconclusive"}},
  {"id":"imaging_unrecognized","note":"MRI showed edema.","expected":{"prior_imaging_result":"unrecognized"}},
  {"id":"mechanical_denial","note":"Denies locking or instability.","expected":{"mechanical_symptoms_documented":false}},
  {"id":"mechanical_positive","note":"Reports locking.","expected":{"mechanical_symptoms_documented":true}},
  {"id":"osa_denial","note":"Patient does not have OSA.","expected":{"osa_diagnosis":null}},
  {"id":"osa_positive","note":"OSA.","expected":{"osa_diagnosis":true}},
  {"id":"sleep_date","note":"Sleep study completed 2024-05-18.","expected":{"sleep_study_date":true}},
  {"id":"ahi_value","note":"AHI 22 documented.","expected":{"ahi_documented":true}},
  {"id":"ahi_missing","note":"AHI not stated.","expected":{"ahi_documented":null}}
]
```

Historically, the cross-sentence borrowed sleep-study date already had
`submission_readiness=false` in v1.4.0 despite `READY` documentation status, as the README allowed for demo
policies. v1.5.0 returns `PENDING_VERIFICATION` without attestations; v2.3 now
rejects that cross-sentence association. The executable
`same_sentence_borrowed_date` example remains incorrect. Human reviewers must
decline unsupported proposals. This API records attestations; it cannot prove a person read the note.
Use synthetic notes only. There is no production clinical-language guarantee.


## Patterns handled through v2.3; failure classes remain open

The following bounded patterns are handled; the class remains open in every row:

| Pattern covered by regressions | Current behavior | Open class |
| --- | --- | --- |
| Therapy nonresponse with unqualified but/however/though/although/yet/whereas response, including semicolon contrast | Response requires review; ambiguous linkage also reviews duration. An explicitly initial response in a single course preserves its documented duration. | Response/attribute association |
| OSA with ruled out anywhere in its sentence, including passive tense and intervening adverbs | Diagnosis is missing. A completed PSG in that sentence is still a documented study, not the diagnosis being excluded. | Negation |
| Therapy/study ordered, prescribed, recommended, not yet started, has not started, not completed, never completed, cancelled/canceled anywhere in its sentence | Therapy duration/response or study presence is missing. Other qualifying findings with these exclusions require review. | Planned/incomplete events |
| Resolved, history of, prior episode, previous episode in the candidate's sentence | Qualifying findings and durations require review. | Temporality |
| Same-sentence persistence negation with no longer present/has/have/reports/noted/seen/evident/active, or no longer directly after finding wording | Matching findings use the shared review path. Comparative no longer than wording alone is not a persistence cue. | Negation and temporality |
| Copied-forward note text: previous/prior note, copied from/forward, carried forward, from the prior/previous note/visit/encounter, per the prior/previous note/visit, or note/visit/encounter dated/from a numeric year or date | Matching findings in that sentence use the shared review path; a header in another sentence does not scope later findings. | Copy-forward |
| Template checkbox text: [ ], [x], [X], ☐, ☑ or ☒ before the finding in its sentence | Any of these checkbox tokens routes the matching finding to review; checked and unchecked states are not interpreted. | Template |
| Numeric AHI with N/A or unknown in a different sentence | AHI presence remains captured; missingness in its own sentence refuses. | Missingness scope |
| does/do/did not have immediately before back pain or radiculopathy | Explicit denial produces False; competing affirmative/denied proposals require review. Neither/nor remains open. | Negation |
| Reflex descriptors versus pain/sensation descriptors | Require a reflex noun/predicate link; unrelated descriptors cannot establish a reflex change. Bounded predicate vocabulary/lookback remains limited. | Attribute association |
| Intact reflexes in a named root distribution | Explicit normal finding produces False / NOT_MET; uncertainty and conflicting findings still require review. | Under-capture |
| Explicitly negated numeric strength score | Requires review before numeric threshold evaluation; does not infer normal strength from not 4/5. | Numeric negation |
| Appointment date in another sentence from an undated sleep study | Does not supply sleep-study date evidence. Same-sentence borrowed dates and genuine cross-sentence links remain open. | Date association |

Safety triggers use real sentence boundaries: period, question mark, exclamation
mark, or newline; semicolons and decimal points do not end that context. Narrow
finding clauses retain their existing attribute scope. Review surfaces derive
full containing sentences with ⟦span⟧ markers without changing facts, evidence,
fingerprints or the record schema (2.0.0). API/CLI citation context retains that
representation. Streamlit attestation and correction citation lists show up to
one neighboring sentence on either side, capped at 1,000 characters with an
explicit truncation marker. The cited span is preserved in full; if it cannot
fit, a literal notice directs the reviewer to the expanded original note.
The attestation note is expanded by default, and context is rendered as literal
text. Reviewers must still read the full note: contradiction farther than one
sentence away can be outside the window, reviewers can still attest without
reading, and reviewer identity remains self-reported. This display aid does not
change extraction, statuses, the readiness gate or the remaining false-READY
pathways.

Current release validation: **1123 passed, 10 xfailed**. Contract JSON alone
drives known-failure markers; there is no exemption list. Four contract examples
are marked: `unrelated_therapy`, `neither_nor_negation`,
`same_sentence_borrowed_date`, and the disputed `negated_strength` expectation.
For that last example, the unchanged False / NOT_READY label remains disputed:
the implementation returns review because not 4/5 establishes no observed score.
It is not a remaining affirmative numeric-strength proposal.

The six other strict xfails cover two cross-sentence temporality tests, generic
analgesic duration, next-line improvement, contralateral attribution, and a
copy-forward header in another sentence. Independent case 18 (intact reflexes)
now passes. Independent case 17's input is unchanged; the owner corrected its
missing-date labels to null / NOT_DOCUMENTED / CANNOT_DETERMINE and its citation
expectation to an empty list. The 20 notes are regressions, not held-out data.
See [v2.3.0 release notes](docs/releases/v2.3.0.md) and the
[experiment report](autoloop/REPORT.md) for classification and coverage audits.

Negation, temporality, copy-forward, template, attribution and cross-sentence
linkage **remain open failure classes**. The H1(a) regressions cover selected
same-sentence cues, not general note provenance or clinical interpretation.
Sentence-wide cues can over-trigger review when they refer to a different
finding. Improvement on a following line, contralateral strength attributed to
prior surgery, and copy-forward headers in another sentence remain correct-value
strict xfails in `test/test_h1_review_triggers.py`. With supplied attestations,
these remaining examples can still reach `READY` and
`submission_readiness=true` on the verified lumbar pathway. Human attestation
remains a necessary safety gate and does not establish extraction accuracy.
