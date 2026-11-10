# Production integration validation — November 10, 2026

**READY for a PR, subject to remote CI and normal manual review.** The candidate
continues `integration/production-remediation-phase1` from `5fed08c` on verified
main `6913a99`. Nothing has been pushed, merged or deployed. The research
maintenance branch at `a500803` remains separate.

## Security resolution

The Phase 1 lock's 53 advisory rows represent **46 unique affected-package/version
vulnerabilities**: 39 Pillow and 7 Starlette. Seven Starlette rows were duplicates.
Deduplication joins primary identifiers/aliases only within the same normalized
package and resolved version; unrelated packages/versions are never merged.

| Package | Phase 1 installed/resolved version | Final installed/resolved version |
|---|---|---|
| Streamlit | 1.55.0 | 1.66.1 |
| Pillow | 12.3.0 | 13.0.0 |
| FastAPI | 0.115.14 | 0.162.2 |
| Starlette | 0.46.2 | 1.10.0 |
| Uvicorn | 0.35.0 | 0.54.0 |

The same versions are installed from the hash-locked requirements on Python
3.12.3 and 3.13.16. Pydantic 2.12.5 and unrelated retained package versions are
unchanged. Newly required ASGI dependencies are locked; Tornado and other unused
transitives are removed by resolution rather than carried into the new server.

This is the smallest supported server upgrade path verified here:

- Official Streamlit 1.65.0 and **1.66.0 still require `pillow<13`**. Version
  1.66.1 permits `<14`, allowing the patched Pillow 13 release. Removing Pillow
  from the old framework or overriding its metadata would leave an unsupported
  installation; neither was used.
- FastAPI 0.115.14 caps Starlette below 0.47.0. The selected supported FastAPI
  version permits patched Starlette. Uvicorn is updated alongside the required
  WebSocket dependency, avoiding the old Uvicorn/new-websockets incompatibility.
- Streamlit's selected release uses its upstream Starlette/ASGI server; the
  retired `server.useStarlette` option is removed. The command remains
  `streamlit run app.py`. No clinical code, application route, evaluation
  operator, policy or custom server architecture is rewritten.

Pillow is a **runtime transitive dependency**, even though the application is
text/JSON-only and its tested input flows never call the image decoder. The
framework's converter can decode TIFF; a positive control retains that evidence.
It would be inaccurate to call Pillow development-only or assume global
unreachability. All 39 findings are patched regardless of that boundary.

Starlette served the local FastAPI previously and now also serves public
framework HTTP/WebSocket, upload and static/media routes. Old exceptions for
unused multipart/FileResponse paths cannot justify the new backend. All seven
vulnerabilities are patched, rather than carried forward under that rationale.

**`security/pip-audit-ignores.json` is now empty.** The original fail-closed audit
script, strict scanning and no-ignore command remain unchanged. Both Python audit
runtimes report **53 dependencies, 0 unresolved findings, 0 excepted findings**.
No expiry was extended, finding suppressed or risk silently accepted. Historical
security reviews and scan evidence remain intact.

Source metadata: [Streamlit 1.66.0](https://pypi.org/pypi/streamlit/1.66.0/json),
[1.66.1](https://pypi.org/pypi/streamlit/1.66.1/json),
[old FastAPI](https://pypi.org/pypi/fastapi/0.115.14/json),
[selected FastAPI](https://pypi.org/pypi/fastapi/0.162.2/json),
[Pillow security release](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html).

## Exact test-count reconciliation

The original **2,542** count was the whole `test/` suite on the remediation
research history, not 2,542 production-only clinical tests. Comparing collected
node IDs with Phase 1 identifies **739 omitted nodes and 179 added nodes**:

`2,542 - 739 + 103 security tests + 76 boundary tests = 1,982`.

The same nine strict expected failures are present in both collections.

| Classification of the 739 nodes | Count | Disposition |
|---|---:|---|
| Historical experiment baseline/examples and semantic/offline scoring | 105 | Retained with research; no production implementation dependency |
| Research proposal/adapters, model capture, reconciliation and injection API | 632 | Depend on research-only code; intentionally excluded |
| Mixed capped-citation / injected-adapter comparison | 1 | Production count/cap/round-trip assertions already covered by `test_v213_security.py`; injected-adapter comparison remains research-only |
| Ordinary service extraction call regression | 1 | Restored in `test_production_default_extraction.py`, without the injection API |

The 103 added security tests were already merged in main via PR #21 and absent
from the research-based audit branch: 66 audit-policy, 34 image-scope and 3
upload/media checks. Phase 1 added 76 new letter/archive/governance checks.
None of those additions accounts for deleted clinical regression assertions.

The restored production regression plus **four new ASGI browser-boundary tests**
bring the final result to **1,987 passed / 9 xfailed** on both runtimes. Existing
UI assertions are unchanged in meaning: AppTest entrypoints are absolute because
the supported framework resolves relative paths against the calling test file;
the session-cache assertion uses its documented `keys()` mapping API instead of
the retired `filtered_state` testing property. No test is skipped to accommodate
the upgrade. Frozen study files, manifests and hashes are untouched.

## Validation of the exact code and lock

- Fresh hash-verified Python **3.12.3** and **3.13.16** environments: each has
  **1,987 passed, 9 xfailed**, with installed dependency compatibility checks clean.
- Ruff check/format and diff whitespace checks pass. The security gate passes
  without exceptions under both audit runtimes.
- **178 retained records** match main on both Python versions after existing
  volatile audit-identity normalization; **25 generated artifacts/goldens** remain
  byte-identical. Clinical facts/states, evidence, fingerprints, requirement
  results, readiness and archive compatibility have no new differences.
- Actual patched upload/media routes preserve untrusted bytes without invoking
  Pillow. Missing/mismatched XSRF tokens are rejected; cross-origin WebSockets
  are rejected before session allocation. Health cookies remain SameSite=Lax,
  cross-origin response headers remain restricted, and app static serving remains
  disabled. The existing text-only scope checks still run after exceptions end.
- Real loopback CLI servers on both runtimes returned healthy HTTP and frontend
  responses, accepted same-origin WebSockets and rendered the application through
  script completion without exceptions. Only the temporary test servers were stopped.

Warnings are the deliberately wrong-type regression inputs and an upstream
test-client deprecation. They are visible, not suppressed. The nine known
extraction failures remain limitations; synthetic parity is not clinical validation.

## Integration and manual review

Review the focused dependency/backend selection, retained security tests and
empty exception policy. The business logic, research exclusions and Phase 1
archive safeguards remain unchanged. After approval, push only this integration
branch and create a PR into main; do not merge the research maintenance branch.

Linux GitHub Actions must pass on the pushed commit before merge. Deployment
requires a cold restart and an owner check of HTTPS/proxy WebSocket forwarding,
cookie behavior/session affinity and one synthetic request in the actual host.
Local smoke tests do not certify the hosted environment. No tag, policy-source
refresh or automatic deployment is included.
