# WORKLOG

## Final Freeze Polish - 2026-04-09 - Audit, cleanup, and verification

- What changed:
  - Performed a final freeze-candidate audit across README, docs, Streamlit, CLI, governance outputs, generated artifacts, golden outputs, and tests.
  - Fixed remaining portability issues by replacing machine-specific markdown links with relative links.
  - Cleaned up final reviewer-facing wording:
    - split `expected_status` from `fixture_label` in CLI demo-case output
    - clarified featured-case wording in Streamlit
    - clarified the difference between coarse synthetic fixture checks and golden acceptance snapshots
  - Removed low-value dead or duplicate complexity:
    - deleted empty `engine/score.py`
    - reused shared featured-demo helpers in `app.py`
    - removed repeated service calls in artifact generation
  - Normalized governance file-path outputs to repo-relative values.
  - Fixed the final governance-summary inconsistency so stale or missing monitored baselines now set `any_review_required=true`, which keeps JSON, CLI, and Streamlit gating aligned.
  - Added final review artifacts:
    - `FINAL_FREEZE_AUDIT.md`
    - `PUSH_SUMMARY.md`
    - `RELEASE_NOTES_LAST_3_SPRINTS.md`
- Why it changed:
  - The repo no longer needed more product surface area. It needed a final trust pass that removed portability issues, ambiguous wording, and small inconsistencies before freeze.
- Tests run:
  - `ruff check .` -> passed
  - `pytest -q` -> `59 passed in 1.31s`
  - `make acceptance` -> passed
  - `make verify` -> passed
  - `python3 cli.py list-demo-cases` -> passed
  - `python3 cli.py list-procedures` -> passed
  - `python3 cli.py drift-status --json` -> passed
  - `python3 cli.py rulebook-status --json` -> passed
  - `python3 cli.py evaluate --demo-case MRI-KNEE-01-ready` -> passed
  - `python3 -m scripts.generate_artifacts` -> passed
  - `python3 -m scripts.generate_golden_outputs` -> passed
- Blockers encountered:
  - A final drift-summary mismatch surfaced during verification: the repo correctly flagged a stale monitored source, but the top-level `any_review_required` flag remained `false`. I fixed the summary semantics and regenerated artifacts and goldens.
  - The Streamlit AppTest needed one small update to acknowledge the governance gate before loading a featured case, which now mirrors the actual UI flow.
- Follow-up items:
  - Freeze the repo.
  - Human reviewer can now commit and push with the generated summary files as the handoff packet.

## Marathon Pass - 2026-04-09 - Re-audit and execution plan

- What changed:
  - Re-audited the repo after the first two upgrade passes.
  - Confirmed the current baseline already includes:
    - shared deterministic service surfaces
    - typed procedure/provenance metadata
    - three supported procedures
    - governance-only drift reporting
    - artifact generation
    - regression and Streamlit sanity coverage
  - Identified the next highest-ROI backlog for the marathon pass:
    - one defensible non-spine procedure if possible
    - rulebook versioning and promotion workflow
    - stronger offline drift artifacts
    - golden outputs and acceptance checks
    - tighter docs and local ergonomics
  - Created `MARATHON_PASS_PLAN.md` to keep the pass scoped and sequential.
- Why it changed:
  - The repo is past the point where broad architecture work adds value. The remaining meaningful gains are depth, governance clarity, and regression safety.
- Tests run:
  - Baseline assumed from the end of the prior pass:
    - `ruff check .` -> passed
    - `pytest -q` -> `45 passed in 0.73s`
- Blockers encountered:
  - None.
- Follow-up items:
  - Add a non-spine deterministic pathway only if it stays narrow and defensible.
  - Build a lightweight rulebook and promotion workflow without changing runtime behavior.
  - Add golden outputs, acceptance checks, and richer drift artifacts.

## Marathon Pass - 2026-04-09 - Non-spine procedure depth and rulebook governance

- What changed:
  - Added a new supported deterministic non-spine procedure: `MRI_KNEE`.
  - Introduced one narrow new extractor field, `mechanical_symptoms_documented`, to support a defensible orthopedic MRI contract without changing the engine shape.
  - Added knee rule metadata, provenance, synthetic fixtures, featured demo coverage, artifacts, and regression tests.
  - Built a lightweight rulebook registry under `rulebook/` with:
    - reviewed snapshot `v0.4`
    - active snapshot `v0.5`
    - manifest-based stage assignment
  - Added rulebook validation and diff utilities through the shared service, CLI, and API.
  - Surfaced rulebook metadata in service status output and evaluation audit traces.
- Why it changed:
  - The repo still had room for one more high-confidence deterministic pathway. After that, governance maturity was the next highest-ROI improvement because it strengthens the interview story without widening product claims.
- Tests run:
  - `python3 -m json.tool inputs/synthetic_cases.json >/dev/null` -> passed
  - `pytest -q test/test_extract_contracts.py test/test_service.py test/test_config_contracts.py test/test_api.py test/test_cli.py test/test_artifact_generation.py test/test_streamlit_app.py` -> `40 passed in 0.69s`
  - `pytest -q test/test_rulebook.py test/test_service.py test/test_api.py test/test_cli.py` -> `28 passed in 0.51s`
  - `python3 cli.py evaluate --demo-case MRI-KNEE-01-ready` -> passed
  - `python3 cli.py rulebook-status` -> passed
  - `python3 cli.py rulebook-diff --from-release 2026-04-09-reviewed-v0.4 --to-release 2026-04-09-active-v0.5` -> passed
- Blockers encountered:
  - The first mechanical-symptom extractor pass over-matched denials as positives because of an overly broad fallback token match. I removed the fallback and kept only contextual positive patterns.
- Follow-up items:
  - Deepen drift artifacts and stale-review visibility.
  - Add golden outputs and an acceptance-style harness.
  - Refresh docs and demo surfaces to explain the new procedure and rulebook workflow cleanly.

## Marathon Pass - 2026-04-09 - Drift visibility, acceptance harness, docs, and final verification

- What changed:
  - Enriched drift status with freshness metadata, stale-source counts, review reasons, and diff-path visibility.
  - Added markdown governance artifacts:
    - `docs/artifacts/drift_report.md`
    - `docs/artifacts/rulebook_diff_reviewed_vs_active.md`
  - Added a golden-output acceptance harness:
    - `engine/acceptance.py`
    - `scripts/generate_golden_outputs.py`
    - `test/golden/...`
    - `test/test_acceptance_snapshots.py`
  - Added lightweight Makefile ergonomics:
    - `make acceptance`
    - `make goldens`
    - fallback to `python3` when `.venv` does not exist
  - Updated README, API/architecture/testing/safety/demo docs, interview narrative, product overview, and next steps for the third pass.
  - Added `PRODUCT_OVERVIEW.md` and `WHY_THIS_EXISTS.md` to make the recruiter-facing story faster to absorb.
- Why it changed:
  - After scope and governance were in place, the highest-ROI work was locking behavior down and making the repo’s product narrative easier to understand quickly.
- Tests run:
  - `pytest -q test/test_rulebook.py test/test_service.py test/test_api.py test/test_artifact_generation.py` -> `22 passed in 0.59s`
  - `pytest -q test/test_acceptance_snapshots.py test/test_streamlit_app.py test/test_cli.py` -> `11 passed in 0.95s`
  - `pytest -q` -> `59 passed in 1.48s`
  - `ruff check .` -> passed
  - `python3 -m py_compile app.py api.py cli.py engine/*.py scripts/*.py` -> passed
  - `python3 -m scripts.generate_artifacts` -> passed
  - `python3 -m scripts.generate_golden_outputs` -> passed
  - `make acceptance` -> passed
  - `make verify` -> passed
- Blockers encountered:
  - `make acceptance` initially assumed `.venv/bin/python` existed. I changed the Makefile to fall back to `python3` automatically.
  - Ruff flagged a few final line-length and import-order issues before the last verification sweep; those were cleaned up directly.
- Follow-up items:
  - Optional: add screenshot automation later only if it stays lightweight and reproducible.
  - Optional: add a second monitored source only with a clean offline baseline.

## Second Pass - 2026-04-09 - Re-audit and plan

- What changed:
  - Re-audited the current second-pass starting point across rules, shared service, API, CLI, Streamlit app, artifacts, docs, and test coverage.
  - Confirmed the repo is currently green before making changes.
  - Identified the highest-ROI gaps for this pass:
    - only two supported procedures
    - limited rule/provenance metadata surfaced to users
    - drift reporting is still minimal
    - no direct Streamlit sanity coverage
    - demo-case taxonomy and regression fixtures can be stronger
  - Created `SECOND_PASS_PLAN.md` to scope the next set of improvements.
- Why it changed:
  - The repo no longer needs broad architectural work. This pass should deepen credibility and regression safety around the existing deterministic backbone.
- Tests run:
  - `pytest -q` -> `34 passed in 0.20s`
  - `ruff check .` -> passed
- Blockers encountered:
  - None.
- Follow-up items:
  - Add carefully scoped new deterministic procedure coverage.
  - Enrich supported-procedure and provenance metadata surfaces.
  - Add lightweight Streamlit sanity coverage and refreshed artifacts.
  - Expand regression fixtures and update docs accordingly.

## Second Pass - 2026-04-09 - Deterministic coverage and metadata depth

- What changed:
  - Added a new supported deterministic procedure: `MRI_CERVICAL`.
  - Extended the rule registry with procedure metadata for all supported procedures:
    - category
    - rule family
    - summary
    - supported sites
    - last rule update
    - rule notes
  - Extended provenance metadata with structured rule source fields:
    - rule source label
    - source URL where available
    - last reviewed
    - rule last updated
    - monitored source linkage
  - Added a stronger monitored-source label to `rules/policy_sources.yaml`.
  - Wired enriched metadata through the shared service, supported-procedure outputs, evaluation outputs, CLI summaries, Streamlit views, and drift status surfaces.
  - Added cervical MRI synthetic demo cases and improved featured-case taxonomy with scenario labels and tags.
- Why it changed:
  - The repo needed more depth, not more architecture. A second spine MRI pathway plus richer registry/provenance output materially improves realism and interview defensibility while preserving the deterministic core.
- Tests run:
  - `python3 -m json.tool inputs/synthetic_cases.json >/dev/null` -> passed
  - `pytest -q` -> `45 passed in 0.95s`
  - `python3 cli.py list-procedures` -> passed
- Blockers encountered:
  - None.
- Follow-up items:
  - Refresh artifacts to include the new cervical pathway and featured-case registry.
  - Add Streamlit sanity coverage and finish doc updates.

## Second Pass - 2026-04-09 - Demo quality, regression hardening, and final verification

- What changed:
  - Added artifact-generation coverage and new generated outputs:
    - `MRI-CERV-01-ready.json`
    - `featured_demo_cases.json`
    - `status.json`
  - Added Streamlit AppTest sanity coverage to ensure the app loads and produces results from featured demo input.
  - Expanded tests for:
    - invalid rule metadata
    - provenance metadata presence
    - contradictory red-flag evidence precedence
    - cervical procedure registry behavior
    - unsupported site-of-care handling
    - enriched drift surface integrity
    - artifact generation output
  - Added lightweight Makefile ergonomics:
    - `make verify`
    - `make smoke-ui`
    - `make evaluate-case CASE=...`
  - Normalized the walkthrough doc path to `docs/demo_walkthrough.md`.
  - Updated README, architecture/API/testing/demo/interview/next-steps docs for the second pass.
- Why it changed:
  - This step improves the repo’s live-demo clarity, regression safety, and local usability without widening scope into new infrastructure.
- Tests run:
  - `ruff check .` -> passed
  - `pytest -q` -> `45 passed in 0.73s`
  - `python3 cli.py evaluate --demo-case MRI-CERV-01-ready` -> passed
  - `python3 -m scripts.generate_artifacts` -> passed
  - `python3 -m py_compile app.py api.py cli.py engine/*.py scripts/*.py` -> passed
- Blockers encountered:
  - Two long-line lint failures in the Streamlit metadata panel were cleaned up before final verification.
- Follow-up items:
  - Optional: add one more non-spine deterministic pathway only if it meets the same rigor.
  - Optional: add screenshot automation later if it can remain lightweight and reproducible.

## Milestone 0 - Audit and baseline

- What changed:
  - Audited the current repo structure, core engine modules, Streamlit app flow, rules/config files, tests, and CI.
  - Established the first-pass upgrade strategy: preserve deterministic evaluation logic and add a thin shared service layer for API, CLI, UI, and artifact generation.
  - Created this worklog to record overnight progress.
- Why it changed:
  - The repo already has a strong deterministic core. The highest-leverage improvement is not a rewrite; it is turning the existing logic into a cleaner, typed, reusable product surface that is easier to defend in interviews.
- Tests run:
  - `pytest -q` -> `21 passed in 0.10s`
- Blockers encountered:
  - None.
- Follow-up items:
  - Write `IMPLEMENTATION_PLAN.md`.
  - Extract evaluation orchestration out of `app.py`.
  - Add central config, structured logging, API, CLI, and stronger tests without widening scope.

## Milestone 1 - Shared service foundation

- What changed:
  - Expanded `engine/schemas.py` with typed models for evidence spans, requirement definitions, supported procedures, demo cases, blockers, metrics, audit traces, drift reports, and service status.
  - Added `engine/config.py` for central path/config validation and `.env.example` for lightweight local overrides.
  - Added `engine/logging_utils.py` for structured JSON logging.
  - Added `engine/demo_cases.py`, `engine/service.py`, and `engine/rendering.py` so Streamlit, API, CLI, and artifacts can share one deterministic orchestration path.
  - Updated `engine/evaluate.py` to preserve normalized evidence span references in requirement results without changing readiness semantics.
  - Added initial `api.py` and `cli.py` shells on top of the shared service.
- Why it changed:
  - The repo’s main weakness was orchestration living inside `app.py`. This step creates a narrow enterprise-style application layer without rewriting the deterministic extraction or rule engine.
- Tests run:
  - `pytest -q` -> `21 passed in 0.06s`
- Blockers encountered:
  - None.
- Follow-up items:
  - Route Streamlit through the shared service.
  - Finish CLI/API behavior and add tests.
  - Add reproducible artifact generation and updated docs.

## Milestone 2 - Product surfaces and regression coverage

- What changed:
  - Rebuilt `app.py` as a thinner operator-style Streamlit UI that consumes the shared service instead of assembling evaluation state inline.
  - Added a FastAPI surface in `api.py` with typed endpoints for health/status, supported procedures, demo cases, readiness evaluation, and drift status.
  - Added `cli.py` for local demo workflows: status, procedure listing, demo case listing, evaluation, validation, export, and drift inspection.
  - Added `scripts/generate_artifacts.py` for reproducible JSON artifacts under `docs/artifacts`.
  - Expanded test coverage with new service, API, and CLI tests.
  - Added minimal dependencies and Makefile targets required to run the new surfaces and lint checks.
- Why it changed:
  - These changes convert the repo from a single-demo surface into a compact internal-product artifact with reusable programmatic interfaces, reproducible exports, and stronger interview defensibility.
- Tests run:
  - `pytest -q` -> `34 passed in 0.19s`
- Blockers encountered:
  - FastAPI was not installed locally, so I added the minimal dependencies required for the API, CLI tests, and linting.
- Follow-up items:
  - Generate stable artifacts.
  - Overhaul recruiter-facing docs and CI.
  - Run full lint and final verification.

## Milestone 3 - Docs, artifacts, CI, and final verification

- What changed:
  - Replaced the top-level README with a tighter product narrative, setup instructions, API/CLI examples, artifact links, and a docs index.
  - Added the requested recruiter-facing docs:
    - `docs/architecture.md`
    - `docs/api.md`
    - `docs/demo_walkthrough.md`
    - `docs/testing.md`
    - `docs/safety_and_scope.md`
    - `DESIGN_DECISIONS.md`
    - `LIMITATIONS.md`
    - `NEXT_STEPS.md`
    - `INTERVIEW_TALKING_POINTS.md`
  - Added `pyproject.toml` for lightweight Ruff and pytest config.
  - Updated GitHub Actions CI to run lint, tests, and artifact generation.
  - Generated stable JSON artifacts under `docs/artifacts/`.
  - Added `test/conftest.py` to make repo-root imports stable under pytest.
  - Tuned the default log level to `WARNING` so CLI and artifact commands stay clean by default.
- Why it changed:
  - This step turns the repo into a more defensible overnight artifact: easier to demo, easier to explain, easier to run locally, and more honest about scope and limitations.
- Tests run:
  - `ruff check .` -> passed
  - `pytest -q` -> `34 passed in 0.16s`
  - `python3 cli.py evaluate --demo-case MRI-01-complete` -> passed
  - `python3 -m scripts.generate_artifacts` -> passed
- Blockers encountered:
  - `pytest` lost repo-root imports after the config pass, so I fixed that with `test/conftest.py` rather than relying on external environment behavior.
- Follow-up items:
  - Optional: capture an updated Streamlit screenshot if the README needs a fresh visual.
  - Optional: add one or two more supported procedures using the same deterministic discipline.
