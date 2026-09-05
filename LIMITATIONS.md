# Limitations

v1.5.0 treats extraction as a drafting aid. Negation, temporality and attribution
errors remain, including negated lumbar diagnoses returning true. All-MET
proposals require per-fact human verification before READY; identity is
self-reported, so this is not a production attestation system. Exact source spans
guarantee source location, not semantic support. See EXTRACTION_CONTRACT.md.

## Scope Limits

- only a small number of procedures are supported
- payer coverage is intentionally narrow
- supported sites of care are constrained

## Extraction Limits

- extraction is pattern-based, not language-model-based
- unusual phrasing can remain unparsed
- the system prefers missingness over aggressive inference
- revision note, June 9, 2026: over-extraction edge cases have been identified and patched, including negated therapy, future-planned therapy, and therapy-duration leakage into symptom duration; regression tests now cover those cases
- revision note, August 31, 2026: tested subject-attribution, future/hypothetical, uncertainty/question, cross-therapy, and contradictory-candidate forms fail closed; general coreference, longitudinal episode resolution, and untested language remain unsupported

## Governance Limits

- drift monitoring is partial
- only configured sources are monitored
- rules are still curated offline

## Product Limits

- no persistence
- no authentication
- no user management
- no deployment packaging beyond local/demo use

## Healthcare Limits

- not validated for real-world clinical or administrative operations
- not suitable for real PHI workflows as currently packaged
- not a substitute for payer policy review or human chart review
