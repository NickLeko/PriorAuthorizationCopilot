# Demo Artifacts

This directory contains checked-in sample outputs. The procedure evaluation JSON files are generated from bundled synthetic demo cases and active rules; `drift_status.json` and `drift_report.md` derive from the policy-source registry and checked-in snapshot state; rulebook artifacts derive from the manifest and release files; `status.json` reflects the loaded runtime configuration; `supported_procedures.json` derives from active rules; and the demo-case catalogs derive from bundled synthetic cases.

`safety_metrics.json` reports exact-status, false-`READY`, `NEEDS_REVIEW`, and abstention metrics for the bundled labeled synthetic fixture only.

These artifacts are intentionally committed because they make reviewer inspection easier and support stable diffs. Full `note_text` values are replaced by a short SHA-256 hash and `[redacted for repository]`; the files are not patient records, payer responses, production logs, or PHI-bearing outputs.

## How To Inspect An Artifact

Start with:

- `MRI-01-complete.json`: an all-MET `PENDING_VERIFICATION` case with no human attestations.
- `MRI-08-edge-below-threshold.json`: a documented-but-below-threshold `NOT_READY` case.
- `CPAP-02-borderline.json`: a missing-information `CANNOT_DETERMINE` case.

The most useful fields are:

- `overall_status`: `PENDING_VERIFICATION`, `READY`, `NOT_READY`, `CANNOT_DETERMINE`, or `NEEDS_REVIEW`.
- `submission_readiness`: true only when the overall status is `READY` and policy/rulebook trust is verified and current.
- `results[]`: requirement-level `MET`, `NOT_MET`, `NOT_DOCUMENTED`, or `NEEDS_REVIEW` results.
- `blockers`: grouped missing, documented-but-not-met, and documented-but-unevaluable requirements.
- `facts`: extracted deterministic facts.
- `evidence_map`: copied evidence snippets with character offsets.
- `audit_trail`: note hash, rules version, active rulebook release, requirements checked, warnings, and invariant errors.
- `letter`: optional deterministic administrative draft and metadata.
- `documentation_coverage_pct`: documented requirements (`MET`, `NOT_MET`, or `NEEDS_REVIEW`) divided by total required fields.
- `criteria_met_count` and `evaluable_requirement_count`: an explicit count of met criteria among requirements that could be evaluated; missing and human-review requirements remain visible in separate counts.
- `missing_requirement_count`: required fields that were not documented.
- `human_review_count`: documented requirements that could not be categorized deterministically.

## What The Artifacts Do Not Mean

They do not show payer approval, denial, denial prediction, clinical appropriateness, medical necessity, production readiness, or real patient handling.

`READY` requires all requirement facts HUMAN_VERIFIED and all operators MET. Automated all-MET proposals remain PENDING_VERIFICATION. Neither status is a payer authorization or medical-necessity decision. `test/golden/evaluations/MRI-01-human-verified.json` separately demonstrates synthetic attestations; they are fixture data, not real review records.

The safety metrics are fixture-scoped regression checks. They do not estimate accuracy, sensitivity, specificity, or safety on external clinical text.

## Regeneration

Regenerate the checked-in artifacts with:

```bash
make artifacts
```

The generator normalizes volatile values such as run IDs, timestamps, letter hashes, and freshness ages so that changes remain reviewable.

For ad hoc reviewer exports, use `/tmp` rather than adding new JSON files here:

```bash
.venv/bin/python cli.py export-report --demo-case CPAP-02-borderline --output /tmp/pa-copilot-reviewer-demo.json --with-letter --letter-type missing_info_request
```
