# API

## v2.0 source-located corrections

The existing `POST /evaluate` path accepts an ordered `corrections` list in PARequest. Values must match the requirement contract without coercion; boolean/numeric strings, unknown enums and reviewer-excluded values are rejected. Clients cannot supply statuses, reasons, effective facts or derived annotations. The original proposal is retained; the last correction event for a key supplies its effective fact. This synthetic example produces NOT_READY because reviewer-supplied false fails the OSA equals_true operator, not because the API determines a clinical diagnosis:

```json
{
  "payer": "Aetna",
  "procedure_code": "CPAP_DEVICE",
  "note_text": "Patient denies OSA. Sleep study completed 2024-02-29. AHI 22.",
  "corrections": [{
    "requirement_key": "osa_diagnosis",
    "action": "SET_VALUE",
    "value": false,
    "reason": "incorrect_value",
    "editor": "Synthetic example editor",
    "edited_at": "2026-01-01T00:00:00Z",
    "note_hash": "181305c61d87d0bb5d3df6caf4f408521955b04d2ade313a2d8a465e1eb57159",
    "evidence_spans": [{"start": 0, "end": 19, "text": "Patient denies OSA."}]
  }]
}
```

Save a complete request as `correction-request.json` and use `.venv/bin/python cli.py evaluate --request-file correction-request.json --json`, or POST the same JSON to `/evaluate`. The editor and timestamp above are synthetic fixture metadata; use actual self-reported metadata for an interactive review. SET_MISSING carries `document_review` with the submitted note's full SHA-256 and offending proposal spans where present. SET_NEEDS_REVIEW and RESTORE_ORIGINAL carry no value or quotation. Supporting dates for date-presence facts are optional ISO detail, never checked for recency or ordering; completed sleep studies count, scheduled/ordered/pending studies do not.

For a passing correction, first evaluate without `fact_verifications`, then review the returned effective facts and submit the returned requirement fingerprints with attestations. Any correction content/order change invalidates every attestation through the whole fact-set fingerprint. All requirement facts still need HUMAN_VERIFIED before READY. The engine enforces self-reported timestamp ordering: attestation time must be strictly later than the latest correction. This is not action separation, distinct reviewers, or proof of review; a single correction-T/attestation-T+1s request can pass without backdating. Exact spans are source-located, not proof of semantic support; human misreading of negation or borrowed qualifiers remains a risk. Corrected decisions are viewable, not replayable, even after RESTORE_ORIGINAL. Structured exports retain original proposals and the full correction list; letters disclose supplied facts/identities and exclude audit comments from reasoning.

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
signature. This HTTP surface does not persist attestations; CLI archiving can durably retain supplied verification records, but does not authenticate reviewers or prove review occurred. Human verification cannot bypass demo,
stale or invalid policy/rulebook trust. Unknown monitoring frequencies fail
freshness checks closed. Captured evidence offsets are original-note Python
character offsets, not byte/UTF-16 offsets; text equals the source slice, which
does not prove semantic support.

Streamlit exposes per-fact checkboxes and reviewer entry under **Verify proposed
facts**. CLI accepts the same PARequest with `evaluate --request-file request.json
--json`, or a mapping file with `--verifications-file attestations.json` alongside
`--demo-case`. The cross-surface regression submits identical unverified and
human-verified requests and compares status, submission readiness and attestations.

The FastAPI layer exposes evaluation and read-only governance views. Archive registration, explicit policy-version selection, historical decision reads, and replay are available through the CLI, not these HTTP endpoints.

Run locally:

```bash
make api
```

Direct equivalent: `.venv/bin/python -m uvicorn api:app --reload`

Base URL in local examples: `http://127.0.0.1:8000`

## Endpoints

`GET /` and `GET /status` also return the same status payload as `GET /health`.

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
- `captured_fact_states` (distinguishes missing and ambiguous captures, including fields outside current requirements)
- `policy_version` (sealed criteria, identity, date, and content hash)
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
- API evaluations embed `policy_version` in the result and audit trace but are not automatically persisted. The opt-in CLI SQLite archive retains decisions, full requests, captured evidence, and verification records; see [policy replay](policy_replay.md). It is not an authenticated, encrypted, or production patient-record service.
- There is no authentication layer.
- There is no autonomous action endpoint.
