# Possible Production Integration Notes

This repo does not implement EHR or payer integration. This note exists only to mark likely integration boundaries if the scope ever expands.

## Current Repo

- Deterministic implementation
- No LLM implementation
- Local demo only
- Synthetic inputs only

## If Extended Beyond This Repo

Likely production concerns would include:

- scoped data access
- PHI minimization
- explicit human review before write-back
- immutable audit logging
- environment separation

Any production integration would be a separate workstream from the current repo.
