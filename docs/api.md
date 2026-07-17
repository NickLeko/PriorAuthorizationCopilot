# API

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
- `submission_readiness`
- `results`
- `blockers`
- `facts`
- `evidence_map`
- `audit_trail`

### `GET /drift-status`

Returns governance-only drift status for configured monitored sources, including:

- source name
- source type
- check frequency
- freshness status
- days since last snapshot check
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
curl "http://127.0.0.1:8000/rulebook/diff?from_release_id=2026-04-09-reviewed-v0.4&to_release_id=2026-07-17-active-v0.6"
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
