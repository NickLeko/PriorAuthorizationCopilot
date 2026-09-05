# API

## v1.5 human verification

Automated extraction is a drafting aid. An otherwise all-MET request returns
`PENDING_VERIFICATION` with `submission_readiness=false`. Every requirement result
contains its proposed `fact_value`, `verification` (default UNVERIFIED) and
`verification_fingerprint`. Existing NOT_READY, CANNOT_DETERMINE and NEEDS_REVIEW
precedence is unchanged. READY requires every fact HUMAN_VERIFIED.

After personally checking a proposal against the original note and requirement,
repeat `POST /evaluate` with the same request plus this mapping (one record for
each fact actually verified; use the actual reviewer, time and returned hash):

```json
{
  "fact_verifications": {
    "back_pain_with_radiculopathy": {
      "state": "HUMAN_VERIFIED",
      "reviewer": "Reviewer name",
      "verified_at": "2026-09-04T12:00:00Z",
      "fingerprint": "<copy this requirement's verification_fingerprint>"
    }
  }
}
```

The fragment must be merged into a complete PARequest; the placeholder is not a
valid hash. Review every requirement individually. Omit an attestation or send
`{"state":"UNVERIFIED"}` to leave/revert that fact unverified. HUMAN_VERIFIED
requires nonblank identity, a timezone-aware nonfuture timestamp and the matching
fingerprint. Malformed records return 422; unknown keys or stale/mismatched
fingerprints return 400. Attestations cannot override proposed values or statuses.
Changed notes, scope or runtime rule bundles require fresh review. The running
service rereads rules, provenance and sources; a detected bundle change between
evaluation start and end fails the request for retry. Filesystem reads are not
a transactional deployment mechanism; promote bundles while evaluations are idle.

Identity is self-reported in this local prototype. This is not an authenticated
signature or durable verification ledger. Human verification cannot bypass demo,
stale or invalid policy/rulebook trust. Unknown monitoring frequencies fail
freshness checks closed. Captured evidence offsets are original-note Python
character offsets, not byte/UTF-16 offsets; text equals the source slice, which
does not prove semantic support.

Streamlit exposes per-fact checkboxes and reviewer entry under **Verify proposed
facts**. CLI accepts the same PARequest with `evaluate --request-file request.json
--json`, or a mapping file with `--verifications-file attestations.json` alongside
`--demo-case`. The cross-surface regression submits identical unverified and
human-verified requests and compares status, submission readiness and attestations.

The FastAPI layer exposes the current deterministic capabilities of the repo without widening scope.

Run locally:

```bash
make api
```

Direct equivalent: `.venv/bin/python -m uvicorn api:app --reload`

Base URL in local examples: `http://127.0.0.1:8000`

## Endpoints

### `GET /health`

Returns basic service status, including:

- application version
- runtime `rules_version`
- active `rulebook_active_release_id`
- supported procedure count
- monitored source count

```bash
curl http://127.0.0.1:8000/health
```

### `GET /supported-procedures`

Lists payer/procedure combinations currently supported by the rules bundle, including:

- procedure category
- rule family
- supported sites
- last rule update
- provenance summary
- monitored-for-drift status

```bash
curl http://127.0.0.1:8000/supported-procedures
```

### `GET /demo-cases`

Lists bundled synthetic demo cases.

```bash
curl http://127.0.0.1:8000/demo-cases
```

### `POST /evaluate`

Runs deterministic administrative readiness evaluation.

```bash
curl -X POST http://127.0.0.1:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "payer": "Aetna",
    "procedure_code": "CPAP_DEVICE",
    "dx_codes": ["G47.33"],
    "site_of_care": "outpatient",
    "specialty": "Sleep Medicine",
    "note_text": "Dx: OSA. Sleep study completed 2024-05-18. AHI 22 documented. Requests CPAP E0601."
  }'
```

Response highlights:

- `overall_status`
- `submission_readiness` (true only when `overall_status` is `READY` and policy/rulebook trust is verified and current)
- `results`
- `blockers`
- public `facts` (`null` is used when an internal candidate requires review; consult requirement status and evidence for the distinction)
- `evidence_map`
- `audit_trail`

### `GET /drift-status`

Returns governance-only drift status for configured monitored sources, including:

- source name
- source type
- check frequency
- freshness status
- days since the last successful policy check
- latest snapshot hash
- latest event
- latest diff path if present
- linked rule source label
- review reason when stale or drifted

```bash
curl http://127.0.0.1:8000/drift-status
```

### `GET /rulebook`

Returns the current rulebook manifest view, including:

- active release ID
- stage assignments
- reviewed and active release metadata
- runtime-match validation for the active snapshot
- any manifest validation errors

```bash
curl http://127.0.0.1:8000/rulebook
```

### `GET /rulebook/diff`

Returns a structured diff between two rulebook releases.

```bash
curl "http://127.0.0.1:8000/rulebook/diff?from_release_id=2026-04-09-reviewed-v0.4&to_release_id=2026-08-22-active-v1.0"
```

## Error Behavior

Unsupported scope returns a structured error response like:

```json
{
  "error": "unsupported_scope",
  "detail": "Unsupported request scope ..."
}
```

The API is intentionally conservative:

- unsupported procedures are rejected
- unsupported sites of care are rejected
- missing documentation does not raise an error; it drives `CANNOT_DETERMINE`
- governance endpoints never mutate runtime rules

## Notes

- The API is designed for synthetic demo inputs, but `note_text` is not screened; do not submit real patient information.
- There is no persistence layer.
- There is no authentication layer.
- There is no autonomous action endpoint.
