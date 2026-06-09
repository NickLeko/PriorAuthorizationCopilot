# Demo Artifacts

This directory contains checked-in sample outputs generated from synthetic demo cases.

These artifacts are intentionally committed because they make reviewer inspection easier and support stable diffs. They are not patient records, payer responses, production logs, or PHI-bearing outputs.

## How To Inspect An Artifact

Start with:

- `MRI-01-complete.json`: a `READY` case.
- `MRI-08-edge-below-threshold.json`: a documented-but-below-threshold `NOT_READY` case.
- `CPAP-02-borderline.json`: a missing-information `CANNOT_DETERMINE` case.

The most useful fields are:

- `overall_status`: `READY`, `NOT_READY`, or `CANNOT_DETERMINE`.
- `submission_readiness`: boolean derived from the overall status.
- `results[]`: requirement-level `MET`, `NOT_MET`, or `NOT_DOCUMENTED` results.
- `blockers`: grouped missing and documented-but-not-met requirements.
- `facts`: extracted deterministic facts.
- `evidence_map`: copied evidence snippets with character offsets.
- `audit_trail`: note hash, rules version, active rulebook release, requirements checked, warnings, and invariant errors.
- `letter`: optional deterministic administrative draft and metadata.

## What The Artifacts Do Not Mean

They do not show payer approval, denial, denial prediction, clinical appropriateness, medical necessity, production readiness, or real patient handling.

`READY` means only that the synthetic note met the currently versioned demo-rule documentation requirements.

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
