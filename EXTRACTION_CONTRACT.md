# Extraction Contract v1.1

Project: Prior Authorization Readiness Copilot  
Scope: Deterministic extraction only  
Current repo status: implemented and deterministic; no LLM is used anywhere in the extraction path  
Output: `(facts, evidence_map)`

This document describes the extraction behavior implemented in [engine/extract.py](engine/extract.py).

## 1. Core Rules

- Extraction is deterministic.
- Missing information remains missing.
- Evidence spans are copied from the original note text when a supporting or missingness span is available.
- The evidence map may omit fields that had no captured span.
- No LLM is used for extraction.

Revision note, June 9, 2026:
- The extractor is designed to prefer under-extraction over false-positive `MET` determinations, but prior over-extraction edge cases were identified in negated therapy, future-planned therapy, and therapy-to-symptom duration leakage.
- Those edge cases are patched with deterministic context filters and covered by regression tests.

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
- Extracts the first explicit weeks or months duration found in the note.
- Months are normalized as `months * 4`.
- The current implementation does not require explicit symptom context for this field.
- Therapy-context durations are skipped so completed, negated, or planned therapy durations do not populate symptom duration.

### `neuro_red_flags_documented`

Type: `bool | null`

Current behavior:
- Returns `True` when neurologic red flags are explicitly addressed in the note, whether affirmed or denied.
- Returns `null` when the note does not explicitly address the supported red-flag phrases.
- The current implementation does not use `False` for this field.

### `prior_imaging_result`

Type: `"none" | "inconclusive" | "abnormal" | null`

Current behavior:
- `none` when the note explicitly says there was no prior imaging.
- `abnormal` when supported abnormal-result language is present.
- `inconclusive` when imaging is mentioned without a usable result, or when findings are normal, unclear, unknown, or otherwise non-blocking.
- Imaging mention without a result is treated as documented `inconclusive`, not `null`.

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
- Returns `True` when `OSA` or `obstructive sleep apnea` appears.
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
- `Back pain x 2 months` -> `symptom_duration_weeks = 8`
- `Denies weakness. No saddle anesthesia.` -> `neuro_red_flags_documented = True`
- `Prior MRI reviewed` -> `prior_imaging_result = "inconclusive"`
- `No prior imaging yet` -> `prior_imaging_result = "none"`
- `Denies locking or instability` -> `mechanical_symptoms_documented = false`
- `Sleep study completed 2024-05-18` -> `sleep_study_date = True`
- `AHI 22 documented` -> `ahi_documented = True`
- `AHI not stated` -> `ahi_documented = null`

## 5. Limits

- The extractor is intentionally narrow and regex-based.
- The current implementation supports only the phrasing patterns encoded in the code and tests.
- This repo uses synthetic inputs. It is not a production clinical NLP pipeline.

## 6. Possible Extensions

- Return parsed date or numeric values for fields that are currently boolean presence checks.
- Expand phrase coverage with additional regression tests.
- Add stricter context gating for symptom duration if the product scope requires it.
