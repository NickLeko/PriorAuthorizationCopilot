# Extraction Contract v1.3

Project: Prior Authorization Readiness Copilot  
Scope: Deterministic extraction only  
Current repo status: implemented and deterministic; no LLM is used anywhere in the extraction path  
Output: `(facts, evidence_map)`

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

## 2. Returned Fields

### `conservative_therapy_weeks`

Type: `int | null`

Current behavior:
- Extracts only week-based durations tied directly to therapy context such as PT, NSAIDs, activity modification, HEP, or chiropractic care.
- Supports patterns like `PT x 8 weeks`, `PT for 8 weeks`, or `8 weeks of PT`.
- Rejects therapy durations when the local context indicates negation, refusal, declined therapy, or future/planned therapy.
- Does not currently normalize therapy months to weeks.
- If therapy is mentioned without a linked duration, returns `null`.

### `symptom_duration_weeks`

Type: `int | null`

Current behavior:
- Extracts the first explicit weeks or months duration linked to supported symptom context.
- Months are normalized as `months * 4`.
- A duration must appear in the same sentence as supported symptom context.
- Therapy-context durations are skipped so completed, negated, or planned therapy durations do not populate symptom duration.

### `back_pain_with_radiculopathy`

Type: `bool | null`

Current behavior:
- Returns `True` only when supported back-pain and radiculopathy/radicular-pain wording appears in the same sentence without supported negation.
- Returns `False` when both concepts are present but one is explicitly negated.
- Returns `null` when the combined finding is not explicitly documented.

### `objective_motor_or_reflex_change_in_root_distribution`

Type: `bool | null`

Current behavior:
- Requires a named lumbar or sacral nerve-root distribution in the same sentence as supported objective strength or reflex wording.
- Returns `True` for supported abnormal strength/reflex findings, `False` for supported normal findings, and `null` for subjective or ambiguous weakness wording.
- Does not infer a nerve-root distribution from anatomy; the distribution must be explicit in the note.

### `cpb_0236_conservative_therapy_weeks`

Type: `int | null`

Current behavior:
- Extracts week-based duration only for modalities named by CPB 0236 Footnote 1: moderate activity, analgesics, NSAIDs/anti-inflammatories, and muscle relaxants.
- When multiple qualifying durations are explicit, selects the longest individually documented course; it never adds shorter courses together.
- A total duration spanning sequential modalities must be stated explicitly to be extracted as that overall duration.
- This source-scoped fact prevents a generic PT duration from silently satisfying the verified pathway.
- Existing demo pathways continue to use the broader `conservative_therapy_weeks` fact.

### `cpb_0236_conservative_therapy_no_improvement`

Type: `bool | null`

Current behavior:
- Returns `True` when a sentence containing a CPB 0236 Footnote 1 modality explicitly states no, minimal, little, or insufficient improvement/relief/response.
- Returns `False` for supported explicit meaningful response language.
- Returns `null` when therapy response is absent or ambiguous, and ignores future/planned therapy language.

### `neuro_red_flags_documented`

Type: `bool | null`

Current behavior:
- Returns `True` when neurologic red flags are explicitly addressed in the note, whether affirmed or denied.
- Returns `null` when the note does not explicitly address the supported red-flag phrases.
- The current implementation does not use `False` for this field.

### `prior_imaging_result`

Type: `"none" | "normal" | "negative" | "inconclusive" | "abnormal" | "unrecognized" | null`

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

Type: `bool | null`

Current behavior:
- Returns `True` when supported mechanical symptom phrasing such as `locking`, `catching`, `buckling`, `giving way`, or `instability` is explicitly present.
- Returns `False` when those symptoms are explicitly denied with supported negation phrasing.
- Returns `null` when the note does not explicitly address the supported symptom phrases.
- Positive phrasing takes precedence if the note contains both denial and later affirmative mechanical-symptom language.

### `osa_diagnosis`

Type: `bool | null`

Current behavior:
- Returns `True` when a non-negated `OSA` or `obstructive sleep apnea` mention appears.
- Supported negated forms such as `OSA ruled out`, `no evidence of OSA`, and `does not have OSA` remain `null`.
- Returns `null` otherwise.

### `sleep_study_date`

Type: `bool | null`

Current behavior:
- Returns `True` when a date in `YYYY-MM-DD` or `YYYY/MM/DD` format appears near sleep-study context such as `sleep study`, `PSG`, `polysomnography`, `HST`, or `home sleep test`.
- Returns `null` otherwise.
- This field records whether a contextualized date was found. It does not return the parsed date value.

### `ahi_documented`

Type: `bool | null`

Current behavior:
- Returns `True` when a numeric `AHI` or `RDI` value is present.
- Returns `null` when the note explicitly says the value is missing or when no numeric value is found.
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
- The current implementation supports only the phrasing patterns encoded in the code and tests.
- Bundled and test inputs are synthetic. Free-form input is not screened and must not contain real patient information. This is not a production clinical NLP pipeline.

## 6. Possible Extensions

- Return parsed date or numeric values for fields that are currently boolean presence checks.
- Expand phrase coverage with additional regression tests.
