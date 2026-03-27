# Prior Authorization Readiness Copilot

A safety-first healthcare AI demo for deterministic prior authorization readiness review.

This project is intentionally narrow: it helps determine whether a prior authorization request is administratively ready based on documented payer criteria. It does not make clinical judgments, predict approval, or act autonomously.

## At a Glance
- Problem: prior authorization requests are often delayed or denied because documentation is incomplete or misaligned with payer requirements.
- Product stance: support administrative workflow quality, not clinical decision-making.
- Core behavior: extract a few structured facts deterministically, evaluate explicit rules, and refuse to decide when required documentation is missing.
- Safety posture: refusal-first, rules-first, auditable, and governance-aware.
- Why this repo exists: to demonstrate strong healthcare AI product judgment, safety boundaries, and practical implementation discipline.

## Quick Facts
- Type: deterministic administrative decision-support demo
- Domain: prior authorization readiness review
- Primary signal: safety-first healthcare AI product judgment
- Stack: Python, Streamlit, YAML rules, Pydantic, pytest
- Non-goal: clinical decision-making or approval prediction

## What This System Is
- A deterministic administrative decision-support tool.
- A rules-first evaluator of documentation readiness.
- A write-only letter drafting system downstream of evaluated results.
- A governance-aware demo with policy drift monitoring artifacts and audit outputs.

## What This System Is Not
- Not a clinical decision support system.
- Not an approval prediction model.
- Not a generic chatbot.
- Not an autonomous submission or appeals agent.
- Not a system that infers missing facts or reinterprets payer policy with an LLM.

## Why It Is Credible
- Frozen readiness semantics: `READY`, `NOT_READY`, and `CANNOT_DETERMINE`.
- Conservative extraction: missing facts stay missing.
- Refusal is explicit: any missing required element forces `CANNOT_DETERMINE`.
- Letter generation is constrained: it cannot change statuses, add facts, or promise approval.
- Policy drift is treated as a governance problem, not a prompt-engineering problem.
- Contract tests lock behavior across extraction, evaluation, drafting, and drift monitoring.

## 2-Minute Architecture

```text
Structured Intake + Synthetic Note
                ↓
Deterministic Fact Extraction
                ↓
Requirement-by-Requirement Rules Evaluation
                ↓
Frozen Readiness Outcome
                ↓
Audit Record + Optional Write-Only Letter Draft
```

### Main flow
1. Load versioned payer rules and provenance metadata.
2. Accept structured intake fields plus synthetic note text.
3. Extract a small set of facts deterministically with evidence spans.
4. Evaluate each requirement as `MET`, `NOT_MET`, or `NOT_DOCUMENTED`.
5. Compute the overall readiness status using frozen invariants.
6. Produce blocking issues, an audit record, and an optional write-only administrative letter.

These design choices help surface documentation problems before submission, reduce preventable rework, and keep administrative gaps explicit instead of implicit.

### Key files
- [app.py](./app.py): Streamlit demo app and orchestration layer.
- [engine/extract.py](./engine/extract.py): deterministic extraction logic.
- [engine/evaluate.py](./engine/evaluate.py): rules evaluation and overall status computation.
- [engine/letter_draft.py](./engine/letter_draft.py): write-only administrative letter generation.
- [engine/policy_monitor.py](./engine/policy_monitor.py): policy drift snapshot/diff/log handling.
- [rules/payer_rules.yaml](./rules/payer_rules.yaml): payer and procedure requirements.
- [rules/provenance.yaml](./rules/provenance.yaml): trust framing for current rules.
- [rules/policy_sources.yaml](./rules/policy_sources.yaml): monitored external policy sources.
- [test/](./test): contract tests for deterministic and safety-critical behavior.

## Safety, Refusal, and Governance

### Frozen readiness contract
- `MET`: documented and meets the threshold.
- `NOT_MET`: documented but below threshold.
- `NOT_DOCUMENTED`: not explicitly present in the note.

### Frozen overall outcomes
- `READY`: all required elements are documented and meet criteria.
- `NOT_READY`: all required elements are documented, but one or more do not meet criteria.
- `CANNOT_DETERMINE`: one or more required elements are not documented.

### Non-negotiable invariants
- Any `NOT_DOCUMENTED` must force `CANNOT_DETERMINE`.
- The system does not infer undocumented facts.
- Policy drift does not change rules automatically.
- The drafting layer cannot override evaluation outputs.

For the fuller safety narrative, see [FAILURE_MODES.md](./FAILURE_MODES.md), [docs/REFUSAL_IS_A_FEATURE.md](./docs/REFUSAL_IS_A_FEATURE.md), and [MODEL_CARD.md](./MODEL_CARD.md).

## Quick Demo

### Setup
```bash
make install
```

Manual setup also works:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run
```bash
make run
```

### Test
```bash
make test
```

### What to look for in the UI
- A clear policy provenance banner.
- Blocking items separated into missing documentation vs documented failures.
- `CANNOT_DETERMINE` when required evidence is absent.
- Deterministic, write-only letter output with metadata.
- Audit JSON that captures evidence, invariants, and trust framing.

## Scope and Limitations
- Uses synthetic/demo inputs, not production PHI workflows.
- Covers a narrow set of payer rules and extraction patterns.
- Does not integrate with an EHR, clearinghouse, or payer system.
- Policy drift monitoring is governance support, not automated policy interpretation.
- The UI is a demo surface; the repo’s strongest signal is the contracts, tests, and decision boundaries.

## Safe Expansion Path
- Expand rule coverage only with explicit provenance updates and regression tests.
- Add CI to run the contract suite automatically on each change.
- Add a small artifact example set for audit and governance reviewers.

## Recommended Reading Order
1. This README for scope, behavior, and run instructions.
2. [docs/DEMO_WALKTHROUGH.md](./docs/DEMO_WALKTHROUGH.md) for a fast portfolio/demo tour.
3. [FAILURE_MODES.md](./FAILURE_MODES.md) for the safety and governance posture.
4. [MODEL_CARD.md](./MODEL_CARD.md) for intended use and non-use.

## Supporting Docs
- [docs/DEMO_WALKTHROUGH.md](./docs/DEMO_WALKTHROUGH.md): fastest way to demo and explain the repo.
- [docs/LOCAL_WORKFLOW.md](./docs/LOCAL_WORKFLOW.md): local run/test workflow.
- [EXTRACTION_CONTRACT.md](./EXTRACTION_CONTRACT.md): extraction behavior contract.
- [LETTER_DRAFTING_CONTRACT.md](./LETTER_DRAFTING_CONTRACT.md): drafting constraints and safety boundaries.
- [PRD.md](./PRD.md): product framing and goals/non-goals.

Future changes should preserve the administrative scope, refusal-first behavior, deterministic evaluation, and explicit governance boundaries documented here.
