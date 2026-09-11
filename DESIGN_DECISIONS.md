# Design Decisions

## 1. Deterministic Before LLM

Reason:

- easier to explain requirement by requirement
- easier to audit
- easier to regression test

Tradeoff:

- narrower extraction coverage
- less tolerance for messy phrasing

## 2. `CANNOT_DETERMINE` As A First-Class Result

Reason:

- missing documentation should not be silently inferred away

Tradeoff:

- more refusals
- lower apparent throughput because uncertain cases abstain

## 3. Shared Service Layer Instead Of Rewriting The Engine

Reason:

- the deterministic core already separated extraction from evaluation
- the real weakness was orchestration inside the UI

Tradeoff:

- some engine modules still use dictionary-shaped internals under the service boundary

## 4. Shared Surfaces And An Explicit Local Archive

Reason:

- UI, API, and CLI share evaluation logic
- every service evaluation embeds a sealed policy snapshot
- CLI `evaluate --store` explicitly persists decisions and their policies in an append-only SQLite archive
- replay reads captured evidence and writes a separate report, preserving historical decisions and refusals

Tradeoff:

- ordinary UI/API evaluations are not automatically persisted; archive and replay have no web/API endpoints
- the archive is a local file, with no multi-user workflow, authenticated reviewer identity, encryption, or production retention controls
- triggers reject updates, deletes, and replacements; hashes detect corruption, but do not protect against a privileged database/schema rewrite
- replay requires fresh human verification even when criteria are unchanged or an old refusal resolves

See [policy versioning and replay](docs/policy_replay.md).

## 5. Governance-Only Drift Monitoring

Reason:

- detects source changes without automating policy interpretation or rule promotion

Tradeoff:

- humans must still update rules and tests after drift

## 6. Synthetic Fixtures Reused Everywhere

Reason:

- reusable cases in `inputs/synthetic_cases.json` support the UI/API/CLI and ordinary artifacts
- a separate hand-authored corpus in `inputs/replay/cases.json` exercises policy-change categories; test-specific fixtures also exist

Tradeoff:

- realism is intentionally bounded
