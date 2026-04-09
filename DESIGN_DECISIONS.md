# Design Decisions

## 1. Deterministic Before LLM

Reason:

- easier to defend in interviews
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
- less superficially impressive throughput

## 3. Shared Service Layer Instead Of Rewriting The Engine

Reason:

- the original deterministic core was already credible
- the real weakness was orchestration inside the UI

Tradeoff:

- some engine modules still use dictionary-shaped internals under the service boundary

## 4. FastAPI And CLI Added, No Database Added

Reason:

- interview-friendly product shape
- no need for persistence in the current scope

Tradeoff:

- no multi-user state
- no historical run store

## 5. Governance-Only Drift Monitoring

Reason:

- useful enterprise signal without pretending to solve policy lifecycle management

Tradeoff:

- humans must still update rules and tests after drift

## 6. Synthetic Fixtures Reused Everywhere

Reason:

- one source of truth across demo, tests, CLI, API, and artifact generation

Tradeoff:

- realism is intentionally bounded
