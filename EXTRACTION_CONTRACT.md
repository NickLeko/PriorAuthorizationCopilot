# Extraction Contract v1.4

Project: Prior Authorization Readiness Copilot  
Scope: Deterministic extraction only  
Current repo status: implemented and deterministic; no LLM is used anywhere in the extraction path  
Internal output: `(facts, evidence_map)`; service/API facts replace the internal review marker with `null`

This document describes the extraction behavior implemented in [engine/extract.py](engine/extract.py).

## 1. Core Rules

- Extraction is deterministic.
- A field remains missing when no supported affirmative or explicit-missingness pattern matches; this narrow regex behavior is not a general clinical-language guarantee.
- Evidence spans are copied from the original note text when a supporting or missingness span is available.
- The evidence map may omit fields that had no captured span.
- No LLM is used for extraction.

Revision note, June 9, 2026:
- The extractor is designed to prefer under-extraction over false-positive `MET` determinations, but prior over-extraction edge cases were identified in negated therapy, future-planned therapy, and therapy-to-symptom duration leakage.
- Those edge cases are patched with deterministic context filters and covered by regression tests.

Revision note, August 21, 2026:
- Symptom durations now require supported symptom context in the same sentence.
- Imaging findings are classified only within the sentence containing the imaging mention, and negated abnormal findings are not treated as abnormal.
- Common diagnosis negations such as `does not have OSA` are excluded from affirmative OSA extraction.

Revision note, August 22, 2026:
- Explicitly normal imaging now uses `normal`; a supported negative finding such as `no fracture` uses `negative`. Neither is conflated with inconclusive or unrecognized results.
- The verified Aetna lumbar-radiculopathy pathway adds three narrow facts: back pain with radiculopathy, objective motor/reflex change in a named nerve-root distribution, and explicit conservative-therapy non-response.

Revision note, August 31, 2026:
- For the implemented lumbar diagnosis, objective-finding, and therapy patterns, relevant candidates are collected before scalar resolution; tested contradictory order variants resolve identically.
- Explicit supported family attribution before or after a mention, supported uncertainty/future-state phrases, and question-form evidence fail closed. This remains bounded phrase matching, not general coreference or clinical-language understanding.
- Contradictory supported evidence returns the internal review-required sentinel. The evaluator maps it to `NEEDS_REVIEW`.
- For the verified lumbar branch, therapy duration and response must resolve to one unambiguous modality candidate within a clause. Contrast clauses, conflicting candidates, and unsupported cross-modality linkage are not merged.

`extract_facts` may use the internal string marker `__REVIEW_REQUIRED__` while evaluating a rule. `ReadinessService` converts that marker to `null` in public `facts` and audit payloads; the corresponding requirement result remains `NEEDS_REVIEW` with its evidence spans.

## 2. Returned Fields

### `conservative_therapy_weeks`

Internal type: `int | null | review-required marker`; public fact type: `int | null`

Current behavior:
- Extracts only week-based durations tied directly to therapy context such as PT, NSAIDs, activity modification, HEP, or chiropractic care.
- Supports patterns like `PT x 8 weeks`, `PT for 8 weeks`, or `8 weeks of PT`.
- Rejects therapy durations when the local context indicates negation, refusal, declined therapy, or future/planned therapy.
- Does not currently normalize therapy months to weeks.
- If therapy is mentioned without a linked duration, returns `null`.
- Distinct supported durations that cannot safely be resolved to one course require human review.

### `symptom_duration_weeks`

Internal type: `int | null | review-required marker`; public fact type: `int | null`

Current behavior:
- Extracts an explicit weeks or months duration linked to supported symptom context.
- Months are normalized as `months * 4`.
- A duration must appear in the same sentence as supported symptom context.
- Therapy-context durations are skipped so completed, negated, or planned therapy durations do not populate symptom duration.
- Distinct supported values or question-form duration evidence require human review instead of selecting one value.

### `back_pain_with_radiculopathy`

Internal type: `bool | null | review-required marker`; public fact type: `bool | null`

Current behavior:
- Returns `True` only when supported back-pain and radiculopathy/radicular-pain wording appears in the same sentence without supported negation.
- Returns `False` when both concepts are present but one is explicitly negated.
- Returns `null` when the combined finding is not explicitly documented.

### `objective_motor_or_reflex_change_in_root_distribution`

Internal type: `bool | null | review-required marker`; public fact type: `bool | null`

Current behavior:
- Requires a named lumbar or sacral nerve-root distribution in the same sentence as supported objective strength or reflex wording.
- Returns `True` for supported abnormal strength/reflex findings, `False` for supported normal findings, and `null` for subjective or ambiguous weakness wording.
- Does not infer a nerve-root distribution from anatomy; the distribution must be explicit in the note.

### `cpb_0236_conservative_therapy_weeks`

Internal type: `int | null | review-required marker`; public fact type: `int | null`

Current behavior:
- Extracts week-based duration only for modalities named by CPB 0236 Footnote 1: moderate activity, analgesics, NSAIDs/anti-inflammatories, and muscle relaxants.
- Multiple distinct supported course candidates require human review; the resolver never selects the longest course or adds shorter courses together.
- A total duration spanning sequential modalities must be stated explicitly to be extracted as that overall duration.
- This source-scoped fact prevents a generic PT duration from silently satisfying the verified pathway.
- A duration used with therapy-response evidence must resolve to the same unambiguous modality candidate within a supported clause.
- Existing demo pathways continue to use the broader `conservative_therapy_weeks` fact.

### `cpb_0236_conservative_therapy_no_improvement`

Internal type: `bool | null | review-required marker`; public fact type: `bool | null`

Current behavior:
- Returns `True` when an unambiguous supported therapy candidate explicitly states no, minimal, little, or insufficient improvement/relief/response.
- Returns `False` for supported explicit meaningful response language.
- Returns `null` when therapy response is absent or ambiguous, and ignores future/planned therapy language.
- Conflicting response statements, contrast clauses, or duration and response split across unlinked therapy candidates require human review.

### `neuro_red_flags_documented`

Internal type: `bool | null | review-required marker`; public fact type: `bool | null`

Current behavior:
- Returns `True` when neurologic red flags are explicitly addressed in the note, whether affirmed or denied.
- Returns `null` when the note does not explicitly address the supported red-flag phrases.
- The current implementation does not use `False` for this field.

### `prior_imaging_result`

Internal type: `"none" | "normal" | "negative" | "inconclusive" | "abnormal" | "unrecognized" | null | review-required marker`; public fact replaces the marker with `null`

Current behavior:
- `none` when the note explicitly says there was no prior imaging.
- `normal` when the note explicitly reports a normal, unremarkable, or no-acute-findings result.
- `negative` when the note negates a supported specific abnormal finding, such as `no fracture` or `no evidence of stenosis`.
- `abnormal` when supported abnormal-result language is present.
- `inconclusive` when findings are explicitly unclear, unknown, or indeterminate.
- Result language is evaluated only within the sentence containing the imaging mention.
- Negated abnormal findings such as `x-ray showed no fracture` are classified as recognized `negative` findings, not globally normal imaging and not `abnormal`. The applicable demo imaging-documentation rules accept this category; the verified lumbar CPB 0236 branch does not use prior imaging as a requirement. Rule evaluation, not extraction, determines the policy outcome.
- `unrecognized` only when imaging is followed by one of the enumerated result introducers `showed`, `shows`, `showing`, `demonstrated`, `demonstrates`, `revealed`, `reveals`, `equivocal`, or `limited`, or by `finding(s)`/`result(s)` plus a following token, and no supported result category matches. The service maps it to `NEEDS_REVIEW`, not to a threshold failure.
- Stated-result phrasing outside that enumerated set returns `null` and falls through to `NOT_DOCUMENTED`; this narrowness is intentional so deterministic matching is used instead of fuzzy interpretation.
- Imaging mention without a stated result remains `null`.

### `mechanical_symptoms_documented`

Internal type: `bool | null | review-required marker`; public fact type: `bool | null`

Current behavior:
- Returns `True` when supported mechanical symptom phrasing such as `locking`, `catching`, `buckling`, `giving way`, or `instability` is explicitly present.
- Returns `False` when those symptoms are explicitly denied with supported negation phrasing.
- Returns `null` when the note does not explicitly address the supported symptom phrases.
- Contradictory positive and negative statements require human review; neither statement takes precedence because of order.

### `osa_diagnosis`

Internal type: `bool | null | review-required marker`; public fact type: `bool | null`

Current behavior:
- Returns `True` when a non-negated `OSA` or `obstructive sleep apnea` mention appears.
- Supported negated forms such as `OSA ruled out`, `no evidence of OSA`, and `does not have OSA` remain `null`.
- Explicit family/non-patient mentions are excluded. Uncertain or contradictory patient diagnosis language requires human review.
- Returns `null` otherwise.

### `sleep_study_date`

Internal type: `bool | null | review-required marker`; public fact type: `bool | null`

Current behavior:
- Returns `True` when a date in `YYYY-MM-DD` or `YYYY/MM/DD` format appears near sleep-study context such as `sleep study`, `PSG`, `polysomnography`, `HST`, or `home sleep test`.
- Returns `null` otherwise.
- Question-form date evidence requires human review.
- This field records whether a contextualized date was found. It does not return the parsed date value.

### `ahi_documented`

Internal type: `bool | null | review-required marker`; public fact type: `bool | null`

Current behavior:
- Returns `True` when a numeric `AHI` or `RDI` value is present.
- Returns `null` when the note explicitly says the value is missing or when no numeric value is found.
- Uncertain or question-form numeric evidence requires human review.
- This field records whether the numeric value is documented. It does not return the numeric value itself.

## 3. Evidence Map

Return type:
- `Dict[str, List[{"start": int, "end": int, "text": str}]]`

Current behavior:
- Each captured span stores `start`, `end`, and `text`.
- Supporting spans are included when the extractor matched text for that field.
- Missingness spans may be included for fields such as `ahi_documented`.
- The current implementation does not attach status or span type metadata.
- The evidence map may be empty for a missing field.
- When a fact requires review, every supported conflicting or ambiguous span is retained rather than selecting the first span.

## 4. Examples

- `Completed PT for 8 weeks` -> `conservative_therapy_weeks = 8`
- `NSAIDs for 8 weeks with minimal improvement` -> `cpb_0236_conservative_therapy_weeks = 8` and `cpb_0236_conservative_therapy_no_improvement = true`
- `Low back pain with right leg radiculopathy` -> `back_pain_with_radiculopathy = true`
- `Right L5 distribution: dorsiflexion strength 4/5` -> `objective_motor_or_reflex_change_in_root_distribution = true`
- `Back pain x 2 months` -> `symptom_duration_weeks = 8`
- `Denies weakness. No saddle anesthesia.` -> `neuro_red_flags_documented = True`
- `Prior MRI reviewed` -> `prior_imaging_result = null`
- `No prior imaging yet` -> `prior_imaging_result = "none"`
- `Denies locking or instability` -> `mechanical_symptoms_documented = false`
- `Sleep study completed 2024-05-18` -> `sleep_study_date = True`
- `AHI 22 documented` -> `ahi_documented = True`
- `AHI not stated` -> `ahi_documented = null`

## 5. Limits

- The extractor is intentionally narrow and regex-based.
- Subject, uncertainty, and temporal-state safeguards cover explicit supported phrasing only. Text outside those patterns may remain unrecognized; this contract does not claim general coreference or longitudinal episode resolution.
- The current implementation supports only the phrasing patterns encoded in the code and tests.
- Bundled and test inputs are synthetic. Free-form input is not screened and must not contain real patient information. This is not a production clinical NLP pipeline.

## 6. Possible Extensions

- Return parsed date or numeric values for fields that are currently boolean presence checks.
- Expand phrase coverage with additional regression tests.
