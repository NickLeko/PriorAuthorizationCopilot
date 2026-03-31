# Possible Production Data Notes

This file is not a description of the current repo. It is a short note on data that a production prior authorization workflow might need.

## Current Repo

- Deterministic implementation
- No LLM implementation
- Inputs are limited to a few structured fields plus synthetic note text

## If Extended Beyond This Repo

Possible production inputs could include:

- insurance coverage
- diagnosis and procedure coding
- supporting reports or prior treatment history
- payer-specific structured requirements

Any such extension would need new contracts, new tests, and updated governance documentation.
