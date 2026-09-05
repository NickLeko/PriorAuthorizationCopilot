# Extraction and verification contract v1.5

Automated extraction is a drafting aid, not a decision gate. A requirement's `MET`
status describes an operator applied to a proposed scalar; it does not establish
that the original note supports that scalar. v1.4.0 over-trusted extraction.
Its claim that a diagnosis returned True only without supported negation was
contradicted by `Patient does not have low back pain with radiculopathy`.
v1.5.0 resolves that contradiction by changing what the engine may assert,
not by making extraction match the old contract. Negation, temporality and
attribution errors remain. No language patterns were repaired in this release.

The normative guarantees are G01–G07 below and the exact examples in the JSON
block. `TestExtractionContractAlignment` executes them, including the known
incorrect proposals. These finite examples are not universal language claims;
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
- **G03**: Every requirement result exposes `fact_value`, `verification`, and a
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
  bound to the normalized request, runtime rules/provenance/source/manifest
  bytes, requirement definition, proposed value, operator result and evidence.
  Changed inputs or rule bundles invalidate prior attestations; unknown keys
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
exact behavior, including known errors, rather than promising semantic accuracy
for whole phrase families. Optional `procedure` and `status` exercise the service
with Aetna/outpatient and no human attestations.

```json
[
  {"id":"negation_first","note":"Patient does not have low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with minimal improvement.","expected":{"back_pain_with_radiculopathy":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"negated_strength","note":"Low back pain with radiculopathy. Right L5 distribution: dorsiflexion strength not 4/5. NSAIDs for 8 weeks with minimal improvement.","expected":{"objective_motor_or_reflex_change_in_root_distribution":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"reflex_attribution","note":"Low back pain with radiculopathy. Right L5 distribution: reflexes assessed, pain decreased. NSAIDs for 8 weeks with minimal improvement.","expected":{"objective_motor_or_reflex_change_in_root_distribution":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"resolved_diagnosis","note":"Low back pain with radiculopathy resolved last year. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with minimal improvement.","expected":{"back_pain_with_radiculopathy":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"unrelated_therapy","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks for headaches with minimal improvement.","expected":{"cpb_0236_conservative_therapy_weeks":8,"cpb_0236_conservative_therapy_no_improvement":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"borrowed_date","note":"OSA. Visit date 2024-05-18. Sleep study date not recorded. AHI 22.","expected":{"sleep_study_date":true},"procedure":"CPAP_DEVICE","status":"PENDING_VERIFICATION"},
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

The borrowed sleep-study date already had `submission_readiness=false` in
v1.4.0 despite `READY` documentation status, as the README allowed for demo
policies. v1.5.0 returns `PENDING_VERIFICATION` without attestations; the date
association itself remains incorrect. Human reviewers must decline unsupported
proposals. This API records attestations; it cannot prove a person read the note.
Use synthetic notes only. There is no production clinical-language guarantee.
