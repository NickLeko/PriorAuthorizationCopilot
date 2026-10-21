# Temporary Pillow security exception review — October 21, 2026

## Decision and scope

The eight individually reviewed Pillow exceptions are technically defensible for
the current text/JSON application and the pinned dependency set, through
**November 4, 2026 at 00:00 UTC**. They are temporary risk acceptance, not patches.
Pillow 12.3.0 remains vulnerable. In particular, its TIFF decoder must not receive
untrusted image bytes. Adding image processing invalidates this decision before
the calendar deadline.

Review baseline: commit `2c927647592553546955bba932b7e708bd95d253` in
`NickLeko/PriorAuthorizationCopilot`, branch `fix/emudhra-certifi`, worktree
`/Users/nicholasleko/projects/PriorAuthorizationCopilot-security`. The worktree was
clean before this review. The existing `certifi==2026.10.19` lock update is
preserved. PR #21 and the original checkout were not modified.

This decision applies to the repository's synthetic demo with Streamlit 1.55.0,
Pillow 12.3.0 and the configured Tornado server. It does not authorize processing
patient information, adding image features, changing server backends or exposing
additional services. This review did not inspect the deployed host's actual
environment, reverse proxy or platform extensions.

## Individual advisory findings

Every linked vendor advisory identifies 13.0.0 as a patched version. The installed
12.3.0 falls within every advisory's affected range. Each row was reviewed
separately; the three TIFF decoder exceptions rely on input reachability rather
than an absent specialized operation.

| Advisory | Trigger and consequence | Application / Streamlit 1.55.0 assessment |
| --- | --- | --- |
| [CVE-2026-112895](https://github.com/python-pillow/Pillow/security/advisories/GHSA-p4wg-p73j-c528) | Appending to an existing untrusted PDF invokes `PdfParser`; cyclic/duplicated page trees or long trailer chains cause recursion and CPU/memory exhaustion. | No PDF append or `PdfParser` calls found in production code or Streamlit. Streamlit's image conversion does not save PDF. Specialized trigger absent in reviewed sources. |
| [CVE-2026-112400](https://github.com/python-pillow/Pillow/security/advisories/GHSA-65qm-jvmh-6pqg) | A later GIF frame leaves oversized dimensions after `DecompressionBombError`; catching the error and continuing with the same image can exhaust memory. | Neither production code nor Streamlit implements that seek/error/reuse sequence. Ordinary open/load is not this advisory's trigger. Current app does not decode GIFs. |
| [CVE-2026-112397](https://github.com/python-pillow/Pillow/security/advisories/GHSA-58r4-6rv3-gfh8) | A zero-width image, including PPM/PGM input, reaches native `ImageMorph` edge indexing; crash and possible memory corruption. | No `ImageMorph` operations in application or Streamlit. Opening a PPM/PGM alone does not establish this morphology trigger. |
| [CVE-2026-112896](https://github.com/python-pillow/Pillow/security/advisories/GHSA-pchr-8j38-3x4p) | Saving an accepted TIFF with retained ColorMap metadata through the libtiff encoder can over-read a heap allocation. The advisory demonstrates the native read/termination; arbitrary heap disclosure is not established. | Application does not encode TIFFs. Streamlit's converter chooses JPEG, PNG or GIF, not TIFF. The required TIFF save path is absent. |
| [CVE-2026-112897](https://github.com/python-pillow/Pillow/security/advisories/GHSA-q45j-58j2-45rg) | Short JPEG/fax strip or tile decoding can leave uninitialized heap bytes in returned TIFF pixels; previews/conversions can disclose those bytes. | Streamlit conversion can load and re-encode TIFF pixels. No route from current app inputs or reviewed upload/media handlers to that conversion was found. Exception depends on maintaining this boundary. |
| [CVE-2026-112395](https://github.com/python-pillow/Pillow/security/advisories/GHSA-462x-pgg6-55fp) | Tiled TIFF decoding trusts an insufficient tile allocation while copying rows; over-read can crash or expose adjacent heap data in pixels. | Same input boundary as above. A future image preview could expose this without using a specialized Pillow API. No current input-to-decoder path found. |
| [CVE-2026-112404](https://github.com/python-pillow/Pillow/security/advisories/GHSA-c6hw-5grf-ff96) | TIFF tile/RGBA decoding lacks row bounds checks when Pillow and libtiff disagree on layout; crafted tags can cause heap disclosure through pixels or a crash. | Same input boundary as above. No current input-to-decoder path found; Pillow's normal size limits do not eliminate this risk. |
| [CVE-2026-112899](https://github.com/python-pillow/Pillow/security/advisories/GHSA-vx6w-vv9f-6gvg) | EPS `load(scale>1)` starts Ghostscript with enlarged geometry before checking the scaled pixel limit, consuming excess CPU and temporary disk. | No EPS scaled-load operation in application or Streamlit. This determination does not depend on Ghostscript being absent from the host. |

## Reachability evidence

The review went beyond searching for direct PIL imports:

1. Production Python entry points and engine imports were searched for PIL,
   image decoding, upload and image widget use. The Streamlit app accepts text
   and selections, evaluates structured records, and exports JSON. Its
   `set_page_config` call does not provide `page_icon`. `st.write` arguments are
   strings or structured application data, rather than PIL image objects. The
   FastAPI routes consume JSON and return structured results; they register no
   image or multipart upload endpoint. Policy fetching consumes bounded text,
   not image previews. No clinical/extraction/readiness implementation changed.
2. Streamlit's `elements/lib/image_utils.py` uses Pillow `Image.open`, resizing,
   and conversion. `st.image`, custom favicons, logos, image chat avatars, and
   `st.write(PIL.Image)` can reach it. TIFF input can be decoded while converting
   to JPEG/PNG; choosing a safe output extension does not protect the decoder.
   These image-producing paths are not used by the current app.
3. The Tornado server registers an upload route even without an upload widget.
   `UploadFileRequestHandler.put` parses multipart content into `UploadedFileRec`
   and calls `MemoryUploadedFileManager.add_file`, which stores the bytes. It
   neither opens images nor creates thumbnails. Therefore, absence of a widget
   is not the upload-handler argument; the handler's actual behavior is.
4. `MediaFileHandler.get_content` retrieves and slices stored bytes. Media
   storage hashes bytes; it does not decode them. The app's download button
   supplies `json.dumps(...)` and `application/json`; its download marshaller
   does not invoke the image converter. Static handlers serve files without
   Pillow conversion. The favicon converter is called only when a page icon
   is supplied. Widget deserialization uses registered metadata and protobuf/
   JSON values; no PIL deserialization path was identified.
5. Eleven reviewed installed Streamlit source files were compared byte for byte
   against the official `streamlit-1.55.0-py3-none-any.whl`, whose SHA-256 is
   `1e4a16449c6131696180f4ddb40ea8c51834e89c2a43e1b0362bc9b1cfd9b415`.
   That digest appears in the repository's hashed lock. The files were the image
   utility, page configuration, write dispatcher, upload/media/static/server
   handlers, uploaded/media file stores, session state and download utility.
6. `test/test_pillow_reachability.py` exercises actual upload and media handler
   methods with TIFF-like bytes and verifies that Pillow never opens them.
   It runs every featured demo and image-like untrusted text with a failing
   `PIL.Image.open` guard. A benign TIFF-to-JPEG positive control establishes
   that Streamlit's converter really can decode TIFFs.

The byte-store/byte-return behavior is confirmed for the traced methods, and
the tested app runs performed no Pillow opens. These observations are **not a
proof of global unreachability** across all inputs, all UI branches, forged
WebSocket messages, dependency behavior or deployed platform integrations. The
tests do not execute exploit payloads, exhaustively fuzz the protocol, or
instrument the live deployment. A missed path into TIFF decoding would expose
the broad decoder findings. Browser-side Markdown image rendering is distinct
from server-side Pillow decoding and is not evidence that Pillow ran.

## Upstream compatibility blocker

On October 21, public PyPI metadata was checked for all 15 non-yanked Streamlit
releases from 1.55.0 through the latest 1.66.0. All require Pillow `<13`.
[Streamlit 1.55.0 metadata](https://pypi.org/pypi/streamlit/1.55.0/json) requires
`pillow>=7.1.0,<13`; [1.66.0 metadata](https://pypi.org/pypi/streamlit/1.66.0/json)
requires `pillow>=9.2.0,<13`. Resolver dry-runs with both versions plus
`pillow==13.0.0` returned `ResolutionImpossible` with those constraints.

[Pillow's published releases](https://pypi.org/pypi/pillow/json) contain 13.0.0
as the current fix and no later patched 12.x release. Its
[release policy](https://pillow.readthedocs.io/en/stable/releasenotes/) does not
promise security backports. The checked
[Streamlit development dependency declaration](https://github.com/streamlit/streamlit/blob/develop/lib/pyproject.toml)
also retains `<13`. No published supported combination fixing all eight was
identified. Search results or a development branch are not a supported release.
No dependency constraint override, `--no-deps` install, source patch or fork was
introduced. Those alternatives would require a separate compatibility and
security review; a successful forced import would not establish support.

## Audit enforcement

`scripts/audit_dependencies.py` scans the actual deployment lock with the CI
tool version, pip-audit 2.10.1, retaining `--strict` and `--disable-pip`. It asks
for the complete JSON report without any global `--ignore-vuln` switches, then
matches reviewed CVEs or their aliases within the named package. Pillow
exceptions match only version 12.3.0. Other packages, other Pillow versions and
new CVEs remain blocking. If a single advisory names multiple distinct CVEs,
every CVE must have an exception for that same package and reviewed version;
one allowed CVE cannot hide an unapproved alias. GHSA/PYSEC identifiers and
duplicate references to the same CVE remain supported. Unresolved output lists
the CVEs without matching authorization.

Only the eight named Pillow CVEs and the seven existing Starlette CVEs are
recognized. Every new Pillow entry requires exactly `package`, nonempty
`reason`, and canonical `expires` fields. Dates later than November 4 are
rejected. The UTC calendar date is checked before scanning: November 4 itself
fails, even if the vulnerability service is clean. No CLI/environment clock
override is provided. Duplicate JSON keys, malformed entries, unknown fields,
unrecognized exceptions, invalid scan JSON, skipped dependencies, **zero audited
dependencies even on scanner exit 0**, and scanner errors fail closed. A
nonempty dependency list is required without hardcoding a platform-specific
count. Active exceptions print their package, CVE, reason and
deadline; each suppressed and unresolved finding is visible.

The seven existing Starlette entries and reasons are unchanged, including
their legacy lack of expiration. Their CVE aliases still match, accounting for
14 findings in the current report. They cannot authorize arbitrary new
Starlette CVEs. The Pillow deadline does not silently expire, renew or broaden
the separate legacy Starlette policy.

## Image-processing regression guard

`test/test_pillow_exposure_guard.py` runs in CI's full pytest quality job while
any Pillow exception remains configured (conservatively including an expired
entry until it is removed). It parses Python ASTs across repository production
modules, including root entry points, `engine/`, `scripts/` and new helper
packages. It excludes hidden/environment directories, `test/`, `tests/`,
`docs/`, `autoloop/` and `node_modules/`; syntax errors fail the test. Production
code must not be moved into those excluded development directories.

The guard detects Streamlit image display, file uploads, camera input, logos,
pyplot, explicit page icons and avatars, and chat inputs accepting files. It
resolves direct imports, imported aliases, simple callable aliases and common
sidebar/container/column bindings. Unknown expanded arguments to page config,
chat messages or chat input require reassessment. Direct Pillow imports are
flagged conservatively, including unused imports, so ordinary direct Pillow
operations cannot enter production without review. Comments, docstrings and
ordinary string contents are not interpreted as calls.

Omitted/None page icons, Streamlit's `random` icon, default/builtin chat avatars,
and explicitly text-only chat inputs remain permitted. Other explicit icon or
avatar values, even harmless literal emoji/material icons, deliberately prompt
review rather than attempting to prove that every supported value is safe.

A detected pathway fails CI with file/line evidence and a reassessment message.
Before accepting it, remove the Pillow exceptions or document a fresh
path-specific review, update the guard narrowly, and rerun the full validation.
Do not bypass the guard with a broad skip. The dependency-audit entry point
alone does not run this pytest guard; both CI jobs are required.

This is a syntax-based change detector, not a complete call graph, type checker
or proof of exploit unreachability. It can conservatively flag dead code and
does not model all rebinding/control flow, dynamic imports, reflection, runtime
monkeypatching, native code, external plugins, symlinked source directories or
platform integrations. Its API list and directory exclusions need review when
architecture/dependencies change. The existing dynamic tests add evidence for
selected flows; **residual Pillow exposure cannot be ruled out globally**.

## Removal and reassessment conditions

- Remove the eight Pillow entries as soon as a supported Streamlit release
  accepts a patched Pillow, or a supported compatible Pillow security release
  appears. Deliberately regenerate the hashed lock while preserving the certifi
  security fix; run compatibility, lint, tests and an unsuppressed audit. Verify
  all eight findings disappear, then remove obsolete Pillow policy constants.
- Reassess immediately before any image upload/display/preview, custom
  favicon/logo/avatar, TIFF conversion, PDF append, morphology, EPS rendering,
  dynamic plugin or dependency/backend change. If untrusted bytes can reach a
  vulnerable path, remove its exception and block release until remediation.
- Stop relying on these exceptions at the deadline. If upstream remains
  blocked, keep CI failing while choosing a reviewed remediation such as a
  maintained patched dependency stack or removal of the affected feature/
  dependency. Do not extend the date automatically.
- **November 4, 2026 at 00:00 UTC is the remediation decision point.** Before
  that gate, the repository maintainer must record either a supported patched
  stack/removal of Pillow with all eight exceptions removed and validation
  passing, or a blocked-release decision. If remediation is unavailable, leave
  CI/releases blocked and obtain an owner decision to suspend the affected
  deployment or remove the dependency pending remediation. A constraint override
  or automatic exception renewal is not an acceptable default. No deployment
  action is authorized or performed by this review.
- Keep the synthetic-data restriction. A no-PHI notice is not an exploit
  mitigation; a memory-disclosure path could expose process data and secrets.

## Validation

The unchanged CI entry point was first run in an isolated Python 3.13.16
environment with pip-audit 2.10.1: **exit 1**, eight unresolved Pillow findings,
14 existing Starlette findings excepted, 53 dependencies audited. The raw
unsuppressed report contains 22 findings in two packages.

After implementation, the same entry point returned **exit 0**, zero unresolved
findings and 22 excepted findings: eight Pillow plus 14 legacy Starlette alias
reports. This is a passing audit under the documented policy, not a scan with
zero known vulnerabilities. Live vulnerability data was queried; no fake clean
report or dependency override was used.

The initial 62 focused exception/reachability tests covered expiration on and
after the deadline, invalid configuration, CVE aliases, package/version
boundaries, scanner failures and mixed unsuppressed findings. These have been
expanded with the independent-review regressions. Current validation results:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m ruff check .` | Passed |
| `.venv/bin/python -m ruff format --check .` | Passed; 81 Python files formatted |
| `.venv/bin/python -m pytest -q` | 1,784 passed, 9 xfailed in 40.05 seconds; one existing Starlette/AnyIO deprecation warning |
| Focused audit, exposure guard, reachability and existing v2.1.3 security tests | 118 passed in 3.37 seconds |
| Python 3.13.16 / pip-audit 2.10.1: `python scripts/audit_dependencies.py` | Passed with 53 dependencies, zero unresolved findings, 22 excepted reports |
| `uv pip check --python .venv/bin/python` | 53 installed packages compatible |
| `git diff --check` | Passed |
| Lock and legacy exceptions | Lock byte-for-byte unchanged; all seven original Starlette JSON entries unchanged |

The lint/test environment is local Python 3.12.3 on macOS. The audit uses isolated
Python 3.13.16, matching the major/minor and patch version of the observed GitHub
audit job, also on macOS. No new GitHub Actions run was triggered for these
uncommitted changes. Existing PR quality jobs passed on Python 3.12.3 and 3.13;
their original audit failed on these eight Pillow findings.

Dependency counts above are measurements of those runs, not universal totals or
a required count of 53. The audit reports the dependency list produced for its
OS, Python and requirement markers; installed-environment compatibility checks
measure a different population. CI and other supported environments must record
their actual counts, which can differ. An empty audit always fails.

### Independent-review follow-up

H1 and L1 regression tests were run against the earlier implementation first:
the successful empty scan and mixed approved/unapproved CVE advisory reproduced
the bypasses. Scanner-error handling remains intact after the corrections.
The new AST guard has positive/negative fixtures for executable APIs, aliases,
containers, non-app helper modules, comments and harmless strings. The validation
table records the follow-up runs: the actual Python 3.13.16 macOS ARM64 audit
measured 53 dependencies and the Python 3.12.3 macOS ARM64 compatibility check
measured 53 installed packages. These are observed environment-specific totals.
The exception JSON, November 4 expiry, entire hashed lock and existing dynamic
reachability tests are byte-for-byte unchanged from the start of the follow-up.

**Recommendation: APPROVE this temporary policy for the reviewed application
and dependency set**, subject to the removal/reassessment conditions above.
Block image-processing expansion or reliance on the exception at/after expiry.
No commit, push, merge or deployment was performed.
