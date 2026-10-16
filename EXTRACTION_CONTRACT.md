# Extraction, correction and verification contract v2.6

v2.0.0 retains the extractor and deterministic operators. Typed, source-located corrections materialize effective facts over an immutable original proposal; every ordered event is retained and the last event wins. SET_VALUE requires exact quotations of at most 300 characters per span and the submitted note hash; multiple spans are allowed and overlength spans are rejected, never truncated. SET_MISSING records document review and any offending proposal spans. SET_NEEDS_REVIEW and RESTORE_ORIGINAL preserve explicit state/history. Types, units and reviewer-enterable values come from fact contracts; there is no scalar coercion or free-text fact value.

Sleep-study presence means a completed study, excluding scheduled, ordered, pending or cancelled/canceled studies. Corrections do not verify facts: an otherwise passing effective fact set needs HUMAN_VERIFIED for every requirement before READY. See the canonical [correction limits](docs/safety_and_scope.md#correction-limits).

Automated extraction is a drafting aid, not a decision gate. A requirement's `MET`
status describes an operator applied to a proposed scalar; it does not establish
that the original note supports that scalar. v1.4.0 over-trusted extraction.
Its claim that a diagnosis returned True only without supported negation was
contradicted by `Patient does not have low back pain with radiculopathy`.
v1.5.0 resolves that contradiction by changing what the engine may assert,
not by making extraction match the old contract. Negation, temporality and
attribution errors remain. v2.6 handles the specific patterns listed below; each failure class remains open.

The normative guarantees are G01–G07 below and the exact examples in the JSON
block. `TestExtractionContractAlignment` executes correct expectations; remaining known failures are strict xfails. These finite examples are not universal language claims;
new contract claims must receive executable coverage in that class.

## Guarantees

- **G01**: `extract_facts(note)` is deterministic and uses regex/standard-library
  code plus the owner-approved reviewed drug table below, with no LLM,
  ontology service, RAG or NLP library. It returns `(facts, evidence_map)`.
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
  {"id":"ahi_missing","note":"AHI not stated.","expected":{"ahi_documented":null}},
  {"id":"exp002_days_threshold","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 42 days with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":6},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp002_days_below_threshold","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 41 days with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":5},"procedure":"MRI_LUMBAR","status":"NOT_READY"},
  {"id":"exp002_days_improved","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Analgesics for 56 days with significant improvement.","expected":{"cpb_0236_conservative_therapy_weeks":8},"procedure":"MRI_LUMBAR","status":"NOT_READY"},
  {"id":"exp002_months_nsaid","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 2 months with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":8},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp002_months_short","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 1 month with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":4},"procedure":"MRI_LUMBAR","status":"NOT_READY"},
  {"id":"exp002_words_threshold","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for six weeks with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":6},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp002_words_short","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for five weeks with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":5},"procedure":"MRI_LUMBAR","status":"NOT_READY"},
  {"id":"exp002_exam_of","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4 of 5. NSAIDs for 8 weeks with minimal improvement.","expected":{"objective_motor_or_reflex_change_in_root_distribution":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp002_exam_out_of","note":"Low back pain with radiculopathy. Left S1 distribution: strength 3 out of 5. NSAIDs for 8 weeks with minimal improvement.","expected":{"objective_motor_or_reflex_change_in_root_distribution":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp002_exam_decimal","note":"Low back pain with radiculopathy. L4 distribution: strength 4.5 of 5. NSAIDs for 8 weeks with minimal improvement.","expected":{"objective_motor_or_reflex_change_in_root_distribution":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp002_exam_normal","note":"Low back pain with radiculopathy. Right L5 distribution: strength 5 out of 5. NSAIDs for 8 weeks with minimal improvement.","expected":{"objective_motor_or_reflex_change_in_root_distribution":false},"procedure":"MRI_LUMBAR","status":"NOT_READY"},
  {"id":"exp002_exam_negated","note":"Low back pain with radiculopathy. Right L5 distribution: strength not 4 of 5. NSAIDs for 8 weeks with minimal improvement.","expected":{"objective_motor_or_reflex_change_in_root_distribution":"__REVIEW_REQUIRED__"},"procedure":"MRI_LUMBAR","status":"NEEDS_REVIEW"},
  {"id":"exp002_exam_contralateral","note":"Low back pain with left leg radiculopathy. Right L5 distribution: strength 4 of 5. NSAIDs for 8 weeks with minimal improvement.","expected":{"objective_motor_or_reflex_change_in_root_distribution":"__REVIEW_REQUIRED__"},"procedure":"MRI_LUMBAR","status":"NEEDS_REVIEW"},
  {"id":"exp003_nsaid_generic","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Ibuprofen for 6 weeks with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":6,"cpb_0236_conservative_therapy_no_improvement":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp003_nsaid_brand","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Completed Aleve for 56 days with minimal relief.","expected":{"cpb_0236_conservative_therapy_weeks":8,"cpb_0236_conservative_therapy_no_improvement":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp003_analgesic_generic","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. 42 days of acetaminophen with little relief.","expected":{"cpb_0236_conservative_therapy_weeks":6,"cpb_0236_conservative_therapy_no_improvement":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp003_analgesic_brand","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Tylenol for six weeks with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":6,"cpb_0236_conservative_therapy_no_improvement":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp003_relaxant_generic","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Cyclobenzaprine for 2 months with insufficient response.","expected":{"cpb_0236_conservative_therapy_weeks":8,"cpb_0236_conservative_therapy_no_improvement":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp003_relaxant_brand","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Completed Robaxin for eight weeks with minimal improvement.","expected":{"cpb_0236_conservative_therapy_weeks":8,"cpb_0236_conservative_therapy_no_improvement":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {"id":"exp003_ibuprofen_short","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Ibuprofen for 41 days with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":5},"procedure":"MRI_LUMBAR","status":"NOT_READY"},
  {"id":"exp003_tylenol_improved","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Tylenol for 8 weeks with significant improvement.","expected":{"cpb_0236_conservative_therapy_no_improvement":false},"procedure":"MRI_LUMBAR","status":"NOT_READY"},
  {"id":"exp003_robaxin_future","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Will start Robaxin for 8 weeks with no improvement expected.","expected":{"cpb_0236_conservative_therapy_weeks":null,"cpb_0236_conservative_therapy_no_improvement":null},"procedure":"MRI_LUMBAR","status":"CANNOT_DETERMINE"},
  {"id":"exp003_ibuprofen_nonpatient","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Mother completed Ibuprofen for 8 weeks with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":null},"procedure":"MRI_LUMBAR","status":"CANNOT_DETERMINE"},
  {"id":"exp003_tylenol_unrelated","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Tylenol for 8 weeks for headaches with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":null,"cpb_0236_conservative_therapy_no_improvement":null},"procedure":"MRI_LUMBAR","status":"CANNOT_DETERMINE"},
  {"id":"exp003_unlisted_steroid","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Prednisone for 8 weeks with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":null},"procedure":"MRI_LUMBAR","status":"CANNOT_DETERMINE"},
  {"id":"exp003_blocker","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Rocuronium for 8 weeks with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":null},"procedure":"MRI_LUMBAR","status":"CANNOT_DETERMINE"},
  {"id":"exp003_challenge_partial_response","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Ibuprofen for 8 weeks with no improvement. Tylenol with significant improvement.","expected":{"cpb_0236_conservative_therapy_weeks":"__REVIEW_REQUIRED__","cpb_0236_conservative_therapy_no_improvement":"__REVIEW_REQUIRED__"},"procedure":"MRI_LUMBAR","status":"NEEDS_REVIEW"},
  {"id":"exp003_topical","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Diclofenac gel for 8 weeks with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":null},"procedure":"MRI_LUMBAR","status":"CANNOT_DETERMINE"},
  {"id":"exp003_leading_verb_missed","note":"Low back pain with radiculopathy. Right L5 distribution: strength 4/5. Took ibuprofen for 6 weeks with no improvement.","expected":{"cpb_0236_conservative_therapy_weeks":6,"cpb_0236_conservative_therapy_no_improvement":true},"procedure":"MRI_LUMBAR","status":"PENDING_VERIFICATION"},
  {
    "id": "exp004_therapy_used_dosed",
    "note": "Persistent lumbar back pain with radiculopathy. Right S1 distribution: strength 3/5. Used etodolac 400 mg BID for seven weeks without meaningful relief.",
    "expected": {
      "cpb_0236_conservative_therapy_weeks": 7,
      "cpb_0236_conservative_therapy_no_improvement": true
    },
    "procedure": "MRI_LUMBAR",
    "status": "PENDING_VERIFICATION"
  },
  {
    "id": "exp004_therapy_received_relaxant",
    "note": "Persistent lumbar back pain with radiculopathy. Right S1 distribution: strength 3/5. Patient received Dantrium 25 mg nightly for 56 days, no benefit.",
    "expected": {
      "cpb_0236_conservative_therapy_weeks": 8,
      "cpb_0236_conservative_therapy_no_improvement": true
    },
    "procedure": "MRI_LUMBAR",
    "status": "PENDING_VERIFICATION"
  },
  {
    "id": "exp004_therapy_course_first",
    "note": "Persistent lumbar back pain with radiculopathy. Right S1 distribution: strength 3/5. A 49-day course of sulindac 150 mg twice a day with minimal benefit.",
    "expected": {
      "cpb_0236_conservative_therapy_weeks": 7,
      "cpb_0236_conservative_therapy_no_improvement": true
    },
    "procedure": "MRI_LUMBAR",
    "status": "PENDING_VERIFICATION"
  },
  {
    "id": "exp004_therapy_short_dosed",
    "note": "Persistent lumbar back pain with radiculopathy. Right S1 distribution: strength 3/5. Used etodolac 400 mg BID for four weeks without meaningful relief.",
    "expected": {
      "cpb_0236_conservative_therapy_weeks": 4,
      "cpb_0236_conservative_therapy_no_improvement": true
    },
    "procedure": "MRI_LUMBAR",
    "status": "NOT_READY"
  },
  {
    "id": "exp004_therapy_unlisted",
    "note": "Persistent lumbar back pain with radiculopathy. Right S1 distribution: strength 3/5. Received amitriptyline 25 mg nightly for nine weeks without relief.",
    "expected": {
      "cpb_0236_conservative_therapy_weeks": null,
      "cpb_0236_conservative_therapy_no_improvement": null
    },
    "procedure": "MRI_LUMBAR",
    "status": "CANNOT_DETERMINE"
  },
  {
    "id": "exp004_exam_iliopsoas",
    "note": "Persistent back pain with right-sided radiculopathy. Right L3 nerve root distribution: iliopsoas 4-/5. Piroxicam for 7 weeks with minimal relief.",
    "expected": {
      "objective_motor_or_reflex_change_in_root_distribution": true
    },
    "procedure": "MRI_LUMBAR",
    "status": "PENDING_VERIFICATION"
  },
  {
    "id": "exp004_exam_gastrocnemius",
    "note": "Persistent back pain with right-sided radiculopathy. Right S1 distribution: gastrocnemius power 4+/5. Piroxicam for 7 weeks with minimal relief.",
    "expected": {
      "objective_motor_or_reflex_change_in_root_distribution": true
    },
    "procedure": "MRI_LUMBAR",
    "status": "PENDING_VERIFICATION"
  },
  {
    "id": "exp004_exam_ankle_low",
    "note": "Persistent back pain with right-sided radiculopathy. Ankle jerk 1+ in the right S1 distribution. Piroxicam for 7 weeks with minimal relief.",
    "expected": {
      "objective_motor_or_reflex_change_in_root_distribution": true
    },
    "procedure": "MRI_LUMBAR",
    "status": "PENDING_VERIFICATION"
  },
  {
    "id": "exp004_exam_full_power",
    "note": "Persistent back pain with right-sided radiculopathy. Right L3 distribution: iliopsoas power 5/5. Piroxicam for 7 weeks with minimal relief.",
    "expected": {
      "objective_motor_or_reflex_change_in_root_distribution": false
    },
    "procedure": "MRI_LUMBAR",
    "status": "NOT_READY"
  },
  {
    "id": "exp004_exam_opposite",
    "note": "Persistent back pain with right-sided radiculopathy. Left L3 distribution: iliopsoas 4-/5. Piroxicam for 7 weeks with minimal relief.",
    "expected": {
      "objective_motor_or_reflex_change_in_root_distribution": "__REVIEW_REQUIRED__"
    },
    "procedure": "MRI_LUMBAR",
    "status": "NEEDS_REVIEW"
  },
  {
    "id": "exp004_date_day_month",
    "note": "Established OSA. Overnight polysomnogram conducted 21 February 2025, AHI: 7.",
    "expected": {
      "sleep_study_date": true
    },
    "procedure": "CPAP_DEVICE",
    "status": "PENDING_VERIFICATION"
  },
  {
    "id": "exp004_date_dotted",
    "note": "Confirmed obstructive sleep apnea. HST completed 2024.12.02; AHI 17.",
    "expected": {
      "sleep_study_date": true
    },
    "procedure": "CPAP_DEVICE",
    "status": "PENDING_VERIFICATION"
  },
  {
    "id": "exp004_date_calendar_invalid",
    "note": "Established OSA. HST completed April 31, 2024; RDI 13.",
    "expected": {
      "sleep_study_date": null
    },
    "procedure": "CPAP_DEVICE",
    "status": "CANNOT_DETERMINE"
  },
  {
    "id": "exp004_date_office_same_sentence",
    "note": "Established OSA. Clinic appointment 11-19-2024, HST date unknown; RDI 13.",
    "expected": {
      "sleep_study_date": null
    },
    "procedure": "CPAP_DEVICE",
    "status": "CANNOT_DETERMINE"
  },
  {
    "id": "exp004_index_rdi_measured",
    "note": "Established OSA. HST completed 2024-04-17. The respiratory disturbance index measured at 14.6 events/hour.",
    "expected": {
      "ahi_documented": true
    },
    "procedure": "CPAP_DEVICE",
    "status": "PENDING_VERIFICATION"
  },
  {
    "id": "exp004_index_british",
    "note": "Confirmed obstructive sleep apnea. PSG completed 2024-04-17. Apnoea–hypopnoea index was 9.2/h.",
    "expected": {
      "ahi_documented": true
    },
    "procedure": "CPAP_DEVICE",
    "status": "PENDING_VERIFICATION"
  },
  {
    "id": "exp004_index_planned_value",
    "note": "Established OSA. HST completed 2024-04-17. Will record respiratory disturbance index of 19.",
    "expected": {
      "ahi_documented": null
    },
    "procedure": "CPAP_DEVICE",
    "status": "CANNOT_DETERMINE"
  },
  {
    "id": "exp004_index_explicit_missing",
    "note": "Established OSA. HST completed 2024-04-17. Respiratory disturbance index of 19, value not available.",
    "expected": {
      "ahi_documented": null
    },
    "procedure": "CPAP_DEVICE",
    "status": "CANNOT_DETERMINE"
  },
  {
    "id": "exp004_source_legacy_strength_exam",
    "note": "Persistent back pain with right-sided radiculopathy. On exam, right L4 distribution: strength 3/5. Piroxicam for 7 weeks with minimal relief.",
    "expected": {
      "objective_motor_or_reflex_change_in_root_distribution": true
    },
    "procedure": "MRI_LUMBAR",
    "status": "PENDING_VERIFICATION"
  },
  {
    "id": "exp004_source_per_patient",
    "note": "Persistent back pain with right-sided radiculopathy. Right S1 distribution: soleus power 3/5 per patient report. Piroxicam for 7 weeks with minimal relief.",
    "expected": {
      "objective_motor_or_reflex_change_in_root_distribution": null
    },
    "procedure": "MRI_LUMBAR",
    "status": "CANNOT_DETERMINE"
  },
  {
    "id": "exp004_source_exam_deferred",
    "note": "Persistent back pain with right-sided radiculopathy. Right S1 distribution: plantar flexion 4/5 per patient report; exam deferred. Piroxicam for 7 weeks with minimal relief.",
    "expected": {
      "objective_motor_or_reflex_change_in_root_distribution": null
    },
    "procedure": "MRI_LUMBAR",
    "status": "CANNOT_DETERMINE"
  },
  {
    "id": "exp004_source_legacy_reflex_reports",
    "note": "Persistent back pain with right-sided radiculopathy. Patient reports absent reflexes in the right S1 distribution. Piroxicam for 7 weeks with minimal relief.",
    "expected": {
      "objective_motor_or_reflex_change_in_root_distribution": null
    },
    "procedure": "MRI_LUMBAR",
    "status": "CANNOT_DETERMINE"
  },
  {
    "id": "exp004_source_word_grade_deferred",
    "note": "Persistent back pain with right-sided radiculopathy. Right L4 distribution: strength 3 of 5; examination was deferred. Piroxicam for 7 weeks with minimal relief.",
    "expected": {
      "objective_motor_or_reflex_change_in_root_distribution": null
    },
    "procedure": "MRI_LUMBAR",
    "status": "CANNOT_DETERMINE"
  },
  {
    "id": "exp004_source_conflicting_motor",
    "note": "Persistent back pain with right-sided radiculopathy. Patient reports right S1 distribution: soleus power 3/5. On exam, right S1 distribution: soleus power 5/5. Piroxicam for 7 weeks with minimal relief.",
    "expected": {
      "objective_motor_or_reflex_change_in_root_distribution": "__REVIEW_REQUIRED__"
    },
    "procedure": "MRI_LUMBAR",
    "status": "NEEDS_REVIEW"
  }
]
```

Historically, the cross-sentence borrowed sleep-study date already had
`submission_readiness=false` in v1.4.0 despite `READY` documentation status, as the README allowed for demo
policies. v1.5.0 returns `PENDING_VERIFICATION` without attestations; v2.3 now
rejects that cross-sentence association. The executable
`same_sentence_borrowed_date` example remains incorrect. Human reviewers must
decline unsupported proposals. This API records attestations; it cannot prove a person read the note.
Use synthetic notes only. There is no production clinical-language guarantee.


## Patterns handled through v2.6; failure classes remain open

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
| Isolated qualifying CPB course with explicit response, duration in whole days/months or number words one through twelve | Completed days floor to whole weeks; months use a four-week lower bound. Six weeks with no/minimal/little/insufficient improvement can pass; short or improved courses fail. | Duration and episode attribution |
| Listed generic/brand drug in an isolated complete course/response sentence | Only table membership replaces the qualifying class keyword; existing duration, response and safety guards apply. An unresolved eligible drug mention alongside another course requires review. | Drug vocabulary, course linkage and indication |
| Direct named-root statement “strength 4 of 5” / “3 out of 5”, including decimals | Observed score below five is an objective change; 5 of 5 is normal. Negation, question, alternative attribution or opposite-side radiculopathy requires review. | Objective finding and attribution |
| Reported listed-drug course with use verb, dose/frequency or duration-first ordering | Whole-course duration and explicit response are linked; existing patient, indication, plan, negation and unresolved-course guards apply. | Course grammar and episode attribution |
| Named-root motor/action/muscle grade without “strength”, with +/- modifiers, or numeric tendon-reflex grade | Typed grade can document change; normal grades do not pass, uncertain/conflicting findings review. No muscle-to-root inference. | Objective exam vocabulary and laterality |
| Motor/reflex sentence attributed to patient/history, or with deferred/unperformed/refused exam | Qualified-only evidence is NOT_DOCUMENTED; conflicting normal/abnormal objective evidence elsewhere is NEEDS_REVIEW. Applies to new and legacy paths. | Source attribution and exam performance |
| Calendar-valid US numeric/dotted year-first/English month study dates | New formats require directly adjoining completed study context; plans, invalid calendars and unrelated dates do not qualify. Legacy year-first association remains limited. | Date and event association |
| Full apnea-hypopnea / respiratory disturbance index names with explicit measurements | AHI/RDI aliases include British spelling and space/hyphen forms; planned, missing and non-patient values do not document a measurement. | Measurement vocabulary and linkage |

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

Current release validation: **1461 passed, 10 xfailed**. Contract JSON alone
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

## Earlier exp-002 recall bounds

Thirteen added executable examples document exp-002 without changing any earlier
expectation or known-failure marker. New course forms require the entire sentence
to be an isolated course plus explicit response, without indication modifiers,
comparisons, ranges or fractional durations. New word strength grades require a
direct named-root exam statement and use real sentence boundaries to preserve
decimal scores. These additions leave legacy numeric-week and slash-grade
attribution gaps intact; the broad laterality failure class is not solved.

Full non-steroidal anti-inflammatory class names remain missed: the exp-002
expansion was reverted after unrelated headache therapy produced unsafe passes.
See the historical [v2.4.0 release](docs/releases/v2.4.0.md) and the
[exp-002 report](autoloop/exp-002/REPORT.md).

## Reviewed drug data and current course grammar

[engine/data/cpb0236_drugs_v1.json](engine/data/cpb0236_drugs_v1.json) is
**owner-approved reviewed data**: 26 records with generic name, aliases/common
US brands, WHO ATC code and Footnote 1 class. The owner approved this artifact
for the local deterministic experiment. **ATC codes require human verification
against WHO ATC before any external claim.** Owner approval does not certify
each transcribed code or brand mapping; the file's human-review notice remains.

Only listed entries in M01A (NSAIDs), M03B/M03C (central/direct muscle relaxants,
excluding M03A neuromuscular blockers), or N02 (analgesics) may replace a class
keyword. Class eligibility does not establish indication, course completion,
duration, response, formulation or clinical appropriateness. Unlisted back-pain
drugs never qualify by inference. The versioned table is outside the existing
governance bundle; this does not promote it into payer policy or change hashes.

Drug recognition uses an isolated course-sentence grammar with optional patient
subject, reported-use verbs (including “Took”), dose/frequency and duration-first
ordering. Duration and explicit response must belong to that course. Supported
response forms include “with” and “without” benefit/improvement wording. Other
verbs, formulation, indication or combination wording may still be missed. All
existing safety guards apply. If an eligible drug mention cannot be resolved
while another course candidate exists, both course facts require review;
incomplete drug mentions alone remain missing. This can over-trigger review
and does not solve general sentence-to-sentence episode or indication linkage.

The sixteen examples introduced in v2.5 cover all three classes, generic and
brand names, short/improved courses, future/non-patient/unrelated context,
non-listed drugs, neuromuscular blockers, topical wording and unresolved linkage.
During exp-004 the owner authorized correcting only the leading-verb example’s
therapy facts/status; its ID and note remain unchanged. Release preparation
preserves all 67 existing examples and all four known-failure objects. The full exp-003 set is 74/74 exact with zero false pending;
its unsafe first candidate was reverted before the linkage revision was retained.
See [v2.5.0](docs/releases/v2.5.0.md) and [exp-003](autoloop/exp-003/REPORT.md).


## v2.6 exp-004 grammar and source safeguards

Twenty-four additional executable examples cover reported drug courses, typed
motor/reflex grades, study dates, named indices, and source/performance guards.
There are 91 examples total, with four unchanged known-failure objects. Runtime
code does not load example IDs or the owner dev set. The prior contract correction
was authorized during development, not performed during release preparation.

A grade is not objective when its sentence says per patient, patient reports or
states, self-reported, by history, deferred, not performed, not examined, unable
to assess or limited by refusal. The same guard covers typed exams, legacy slash
and word strength, descriptive reflexes and objective-weakness candidates. It
uses real sentences, including semicolons and decimal grades. Qualified evidence
alone yields NOT_DOCUMENTED; conflicting normal/abnormal objective evidence in
another sentence yields NEEDS_REVIEW with both sources cited. An agreeing
objective source remains usable. A statement such as “on exam” or “examination
shows” does not override a disqualifying qualifier in that same sentence.

New dates are syntax/calendar validated without reading a clock. Full-name index
safeguards do not generally repair all legacy abbreviation contexts. Root linkage,
source recognition and drug use still depend on finite regex vocabularies; broad
negation, laterality, episode attribution and same-sentence date borrowing remain
open. Sentence-wide exclusion can conservatively abstain on a qualifier about a
different event. See [v2.6.0](docs/releases/v2.6.0.md) and
[exp-004](autoloop/exp-004/REPORT.md) for development versus held-out evidence.
