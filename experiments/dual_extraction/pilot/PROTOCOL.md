# Proposed 15-note synthetic pilot — not started

Use [the fixed roster](cases-v1.json) and [developer prompt pa-extraction-bare-v1](prompt-v1.md).
The roster contains exact frozen case IDs and note SHA-256 values: 7 ordinary
cases, 6 challenge cases and 2 known regex failures, all with supported policy
scope. The selected frozen regex captures exercise all twelve existing fact keys
across lumbar MRI, cervical MRI, knee MRI and CPAP. This is coverage evidence,
not semantic ground truth. Do not show regex captures, case labels, policy passing
thresholds or prior model responses to the model.

| Frozen case | Pathway | Stratum and focus |
| --- | --- | --- |
| `inputs/synthetic_cases.json#MRI-01-complete` | Lumbar | Ordinary: current findings, linked treatment duration/response |
| `EXTRACTION_CONTRACT.md#exp002_exam_contralateral` | Lumbar | Challenge: opposite-side examination |
| `test/fixtures/v210_independent.json#10` | Lumbar | Challenge: historical 2019 episode versus current findings |
| `inputs/synthetic_cases.json#MRI-CERV-01-ready` | Cervical | Ordinary: therapy, symptom duration, addressed red flags, imaging |
| `inputs/synthetic_cases.json#MRI-CERV-02-not-ready` | Cervical | Ordinary: short therapy, explicitly denied findings |
| `inputs/synthetic_cases.json#MRI-CERV-03-cannot-determine` | Cervical | Ordinary: missing red-flag evidence |
| `inputs/synthetic_cases.json#MRI-KNEE-01-ready` | Knee | Ordinary: mechanical symptoms and prior imaging |
| `inputs/synthetic_cases.json#MRI-KNEE-04-ready-denied-mechanical` | Knee | Ordinary: explicit symptom denial |
| `inputs/synthetic_cases.json#MRI-KNEE-05-conflict-deny-then-positive` | Knee | Challenge: earlier denial and later positive finding |
| `inputs/synthetic_cases.json#CPAP-01-complete` | CPAP | Ordinary: diagnosis, completed study and AHI |
| `inputs/synthetic_cases.json#CPAP-09-noise-contains-date-unrelated` | CPAP | Challenge: unrelated date and missing AHI |
| `EXTRACTION_CONTRACT.md#unicode` | CPAP | Challenge: Python Unicode offsets |
| `EXTRACTION_CONTRACT.md#neither_nor_negation` | Lumbar | Known regex failure; prior hand-authored shared-error demonstration |
| `EXTRACTION_CONTRACT.md#unrelated_therapy` | Lumbar | Known regex failure: treatment belongs to headaches |
| `inputs/synthetic_cases.json#SAFETY-08-uncertain-diagnosis-variant` | Lumbar | Challenge: “not yet ruled out” negates exclusion, not uncertainty |

Negation coverage includes explicit denials and neither/nor. The compound/double
negation challenge is “not yet ruled out”: do not collapse this clinical uncertainty
into a confirmed diagnosis. The frozen corpus has no literal “does not deny”
example; that narrower grammatical form remains a coverage limitation. Conflicting
findings, historical episodes and unrelated treatment are explicitly labeled
challenges. The earlier hand-authored shared-error example remains a demonstration;
do not assume the actual model will repeat it.

## One model and one capture per case

Recommended fixed baseline: OpenAI `gpt-4.1-2025-04-14`, rather than a moving alias.
This is a bounded instruction-following extraction pilot, not a comparison of
models or a claim that this older snapshot is the strongest clinical extractor.
The snapshot and Responses API support are documented in
[official OpenAI documentation](https://developers.openai.com/api/docs/models/gpt-4.1).
Account access has not been checked and no API request was made.

Proposed fixed generation settings: `temperature=0`, `top_p=1`,
`max_output_tokens=8192`, plain text output, no tools, `store=false`. No automatic
SDK retries, application retries, fallback models, JSON repair or response
continuations. Record the actual request settings and requested/returned model
identity in the capture log. If the selected snapshot or settings are unavailable,
stop and revise the protocol before any generation; do not silently substitute.
Fixed settings do not promise deterministic model output; original capture is
what makes the later offline comparison reproducible.

Send the exact contents of prompt-v1.md as developer instructions and the exact
original note alone as the user message. Offsets refer to that note string only.
Preserve the original Python note string and its hash; do not change whitespace,
Unicode normalization, casing or line endings. The prompt requests the exact twelve
FactContracts, bare JSON with facts/counts, all three states, strict scalar types,
source quotations and Python end-exclusive character offsets. It never requests
provider metadata or hashes from the model.

A trusted capture process records one attempt per roster case, regardless of
outcome. Store the original model text content as UTF-8 bytes with no stripping,
pretty printing, JSON reserialization, metadata insertion or offset adjustment.
Retain the provider envelope/capture log separately so transport metadata and
failure declarations can be audited. If the provider returns multiple content
parts or a refusal without extraction text, preserve that response and explicit
capture failure; do not concatenate or transform it into a plausible extraction.
No capture client is implemented by this patch.

Write a version-2 `actual_model_study` manifest with the selected attempted-case
roster and an entry for every case. Supply provider, model, prompt version,
provider response ID when available, source/origin, attempt ID, exact note hash,
stored file path and SHA-256. The model-generated body contains only facts/counts.
Provider failures can precede response IDs. Manifest identity and outcome are
trusted capture assertions, not authenticated provider facts; preserve the log
that supports them. The runner intentionally reports
`provider_outcomes_authenticated=false`. Missing/corrupt stored files remain
attempts and cannot be silently relabeled as never attempted.

## Initial analysis and stopping rule

Run the existing offline runner once captures are complete. Report attempts,
declared responses, integrity-verified replies entering the adapter, valid outputs,
invalid outputs, provider failures, missing files, storage/capture/note-identity
failures, and successful three-mode evaluations. Model-output invalidity is
`invalid / (valid + invalid)`, excluding capture failures. End-to-end usability
is `valid / all selected attempts`, including every failure. Show exact numerators,
denominators and exclusions; zero denominators stay null.

For each rejected model output, inspect the preserved raw response and assign a
manual invalidity-cause label: UTF-8/JSON format, fact schema/type/vocabulary,
uncited capture, citation quotation/offset, or other adapter rejection. Separate
Python-character versus UTF-8/UTF-16 offset errors. The current fixed error codes
remain payload-free; this pilot does not require a new error taxonomy or logger.

For valid captures, report state/value/citation disagreements and downstream
requirement/status changes using the same request, frozen bundle and governance
clock. Keep ordinary, challenge and known-regex-failure strata separate. Examine
possible shared errors semantically; agreement alone is not a correctness label.
All evaluations remain unverified. Do not claim accuracy, precision, recall or
clinical validity without independent reviewed semantic labels.

Stop after this patch's verification. The pilot needs explicit live-call approval,
provider access and an accountable capture process. There is no known remaining
adapter-code blocker after the tests pass; these execution prerequisites and
coverage limits remain. No real patient data, live call, merge, release or deployment
is authorized by this protocol.
