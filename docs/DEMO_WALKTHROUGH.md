# Demo Walkthrough

This is the fastest way to explain the repo.

## One-Sentence Pitch

Prior Authorization Readiness Copilot is a deterministic demo that checks whether a prior auth request is administratively ready based on documented payer criteria, and returns `CANNOT_DETERMINE` when required documentation is missing.

## What To Say First

- The current repo is deterministic.
- The current repo does not use an LLM.
- It supports administrative readiness review only.
- Missing documentation leads to refusal, not inference.

## Demo Flow

1. Run `streamlit run app.py`.
2. Open a featured showcase case.
3. Show requirement-level outputs: `MET`, `NOT_MET`, `NOT_DOCUMENTED`.
4. Show the overall status mapping.
5. Show blockers, extracted facts, and evidence spans.
6. Generate a letter and note that drafting is deterministic and downstream of the evaluated results.
7. Show the policy monitor as governance support for configured monitored sources, not for every supported procedure.

## Honest Limitations

- Coverage is intentionally narrow.
- Inputs are synthetic.
- Extraction supports only the implemented phrasing patterns.
- Policy drift monitoring only applies to configured sources. In the current repo, that means `MRI_LUMBAR`, not `CPAP_DEVICE`.

## Best Supporting Docs

- [README.md](/Users/nicholasleko/projects/PriorAuthorizationCopilot/README.md)
- [EXTRACTION_CONTRACT.md](/Users/nicholasleko/projects/PriorAuthorizationCopilot/EXTRACTION_CONTRACT.md)
- [FAILURE_MODES.md](/Users/nicholasleko/projects/PriorAuthorizationCopilot/FAILURE_MODES.md)
- [MODEL_CARD.md](/Users/nicholasleko/projects/PriorAuthorizationCopilot/MODEL_CARD.md)
