# Phase 1 dependency investigation — November 9, 2026

**Release remains blocked. No exception date, exception set or audit guard was
relaxed.** The existing Pillow exceptions expired November 4 at 00:00 UTC. The
unmodified `scripts/audit_dependencies.py` correctly exits 2 before scanning.
The investigation's live scans ran during November 9 Pacific time (November 10
UTC). The October security review is retained unchanged as historical evidence.

## Live findings and narrowly scoped patches

An independent unfiltered `pip-audit==2.10.1` scan of base `6913a99` found 57 raw
advisory rows across 53 dependencies: GitPython 3.2.0 (1), Pillow 12.3.0 (39),
Starlette 0.46.2 (14), and Tornado 6.5.10 (3). Starlette's rows include duplicate
advisory IDs; these are not 57 distinct CVEs. No ignore flags were used.

The candidate updates only GitPython **3.2.0 → 3.2.1** and Tornado
**6.5.10 → 6.6.1**, with hash-locked artifacts and minimum patched constraints.
The same unfiltered scan then reports 53 raw rows, confined to Pillow (39) and
Starlette (14). The four GitPython/Tornado findings disappear without adding any
exception. All other locked package versions remain unchanged.

Vendor advisories supporting these patches:

- [GitPython submodule clone path validation](https://github.com/gitpython-developers/GitPython/security/advisories/GHSA-83vg-56qc-22m7)
- [Tornado folded-header CPU usage](https://github.com/tornadoweb/tornado/security/advisories/GHSA-pcg2-g6cj-q92c)
- [Tornado small-chunk body resource usage](https://github.com/tornadoweb/tornado/security/advisories/GHSA-r4j5-9xpp-3985)
- [Tornado protocol-relative redirect](https://github.com/tornadoweb/tornado/security/advisories/GHSA-pw9p-v7r6-gx4p)

## Why the expired Pillow exceptions are not renewed

The current database lists **39 Pillow advisory rows**, not just the eight
previously excepted findings. Renewing the old eight would neither remove the
underlying vulnerabilities nor account for the additional findings. The
[Pillow vendor advisory](https://github.com/python-pillow/Pillow/security/advisories/GHSA-p4wg-p73j-c528)
identifies 13.0.0 as patched; the current locked Streamlit 1.55.0 requires
`pillow<13`.

Official PyPI metadata shows that
[Streamlit 1.66.1](https://pypi.org/pypi/streamlit/1.66.1/json) accepts `pillow<14`.
However, that release uses the Starlette/ASGI server and no longer has the
`server.useStarlette` switch; our current deployment explicitly uses Tornado.
Its required Starlette version range also requires reviewing the old FastAPI
constraint before selecting patched Starlette. The
[official 1.66.1 configuration source](https://github.com/streamlit/streamlit/blob/1.66.1/lib/streamlit/config.py)
and [FastAPI metadata](https://pypi.org/pypi/fastapi/0.162.2/json) were inspected.

A full security resolution therefore requires a deliberate compatible
Streamlit/Pillow/FastAPI/Starlette/server upgrade, updated server-reachability
validation, and deployment verification. That backend migration is not silently
bundled into the production engineering consolidation. The current branch keeps
the existing server selection and makes no new risk-acceptance claim.

The existing seven Starlette exceptions also remain visible in the unchanged
policy. Their previous local-API/Tornado rationale cannot be carried across a
public Starlette migration without reassessment.

## Reproduction

With a disposable environment containing `pip-audit==2.10.1`:

```sh
python scripts/audit_dependencies.py
# Expected: exit 2, expired exception. This is a merge/release blocker.
python -m pip_audit -r requirements.lock --disable-pip --strict \
  --format json --progress-spinner off > audit-unsuppressed.json
# Expected: nonzero while the remaining findings are present.
```

Keep scan outputs as dated evidence. Re-scan when preparing any dependency
migration; these findings are not a guarantee about a later advisory database.
