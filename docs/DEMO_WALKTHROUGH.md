# Demo Walkthrough

This is the fastest way to explain the repo to an interviewer, hiring manager, or healthcare AI stakeholder.

## One-Sentence Pitch
Prior Authorization Readiness Copilot is a deterministic healthcare AI demo that checks whether a prior auth request is administratively ready based on documented payer criteria, while refusing to decide when required documentation is missing.

## What To Say First
- This is not a clinical model and not an approval predictor.
- It supports administrative readiness review only.
- The key product choice is refusal: missing documentation leads to `CANNOT_DETERMINE`, not inference.
- The repo is designed to show governance discipline as much as implementation skill.

## Demo Flow
1. Open the app with `make run`.
2. Start with one of the `Featured Showcase Cases` at the top of the app so the audience can see a realistic example immediately.
3. Point out that the showcase case preloads the editable intake rather than relying on a hidden prompt or hard-coded output.
4. Show that rules and provenance are loaded from versioned YAML, not hidden prompts.
5. Run a case and show requirement-level outputs: `MET`, `NOT_MET`, `NOT_DOCUMENTED`.
6. Highlight the overall status logic:
   `NOT_DOCUMENTED` -> `CANNOT_DETERMINE`
   else any `NOT_MET` -> `NOT_READY`
   else -> `READY`
7. Show the blocking-items section to illustrate missing vs unmet documentation.
8. Show the extracted facts and evidence mapping so the audience can see what the note actually supported.
9. Show the audit summary first, then optionally open the raw audit JSON and point back to the policy provenance banner.
10. Generate a letter and explain that it is write-only and downstream of the evaluated results.
11. Mention the policy drift monitor as a governance safeguard rather than an automation feature.

## What Makes This Repo Interview-Strong
- The scope is disciplined.
- The refusal behavior is explicit and test-backed.
- The architecture separates extraction, evaluation, drafting, and governance cleanly.
- The code uses structured outputs and validation rather than vague model behavior.
- The docs make intended use and non-use very clear.

## Good Questions This Repo Answers
- How do you design healthcare AI tools that are useful without becoming unsafe?
- How do you handle missingness without hallucinating?
- How do you make policy-dependent systems auditable?
- How do you keep LLM-adjacent systems from drifting into generic chatbot behavior?

## Honest Limitations To Mention
- Coverage is intentionally narrow.
- It is a demo app, not a production deployment.
- Extraction is deterministic but still limited to supported phrasing patterns.
- Policy drift detection helps trigger review, but does not solve policy interpretation automatically.

## Best Supporting Docs
- [README.md](/Users/nicholasleko/projects/PriorAuthorizationCopilot/README.md)
- [FAILURE_MODES.md](/Users/nicholasleko/projects/PriorAuthorizationCopilot/FAILURE_MODES.md)
- [MODEL_CARD.md](/Users/nicholasleko/projects/PriorAuthorizationCopilot/MODEL_CARD.md)
- [docs/REFUSAL_IS_A_FEATURE.md](/Users/nicholasleko/projects/PriorAuthorizationCopilot/docs/REFUSAL_IS_A_FEATURE.md)
