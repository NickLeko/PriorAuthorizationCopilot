# RELEASE NOTES: LAST 3 SPRINTS

Sprint boundaries below are inferred from `WORKLOG.md` and the plan files. They are trustworthy summaries of the actual upgrade sequence, even though some milestones were recorded inside broader overnight passes.

## 1. Sprint 1 Summary

### What Changed

- Reframed the repo around a shared deterministic service layer instead of having orchestration live mainly inside `app.py`.
- Added typed schemas, central config, and structured logging.
- Added FastAPI and CLI surfaces over the same deterministic workflow.
- Rebuilt the Streamlit app to consume shared outputs instead of assembling evaluation state inline.
- Added reproducible artifact generation and substantially expanded tests.
- Rewrote the README and added core docs for architecture, API, testing, demo walkthrough, safety/scope, design decisions, limitations, next steps, and interview use.
- Added lightweight Ruff and CI support.

### Why It Mattered

Before this sprint, the repo was a strong deterministic demo with a good engine but limited product shape. After this sprint, it became a compact internal-product artifact with clearer boundaries, typed interfaces, reusable surfaces, reproducible outputs, and an interview-defensible story.

### Key Files

- `engine/service.py`
- `engine/schemas.py`
- `engine/config.py`
- `engine/logging_utils.py`
- `engine/rendering.py`
- `api.py`
- `cli.py`
- `app.py`
- `scripts/generate_artifacts.py`
- `README.md`
- `docs/architecture.md`
- `docs/api.md`
- `docs/testing.md`
- `.github/workflows/ci.yml`

## 2. Sprint 2 Summary

### What Changed

- Added a new supported deterministic procedure, `MRI_CERVICAL`.
- Strengthened the supported-procedure registry with category, rule family, summary, supported sites, and rule-update metadata.
- Strengthened provenance output with rule source label, source URL where available, last reviewed, last updated, and monitored-source linkage.
- Improved demo-case taxonomy and featured-case metadata.
- Added Streamlit AppTest sanity coverage and stronger regression tests around metadata integrity, contradictory evidence, unsupported site handling, and artifact generation.
- Tightened Makefile ergonomics and normalized the demo walkthrough path.

### Why It Mattered

This sprint added depth without changing the architecture. The repo became more credible because it could show more than one deterministic imaging pathway, expose clearer rule provenance, and verify that the UI and metadata surfaces stayed intact.

### Key Files

- `rules/payer_rules.yaml`
- `rules/provenance.yaml`
- `rules/policy_sources.yaml`
- `inputs/synthetic_cases.json`
- `engine/service.py`
- `engine/schemas.py`
- `engine/provenance.py`
- `engine/policy_monitor.py`
- `app.py`
- `test/test_streamlit_app.py`
- `test/test_artifact_generation.py`
- `docs/demo_walkthrough.md`

## 3. Sprint 3 Summary

### What Changed

- Added a narrow non-spine deterministic procedure, `MRI_KNEE`, using one carefully scoped new extractor field.
- Introduced a versioned rulebook with reviewed and active snapshots plus manifest-driven stage metadata.
- Added rulebook validation, status, and diff utilities through the service, API, and CLI.
- Deepened drift reporting with freshness metadata, stale-source signaling, and markdown/JSON governance artifacts.
- Added golden acceptance snapshots, normalization logic, and an acceptance command.
- Expanded recruiter-facing docs with clearer product and governance narrative.

### Why It Mattered

This sprint turned the repo from a good multi-surface demo into a more mature governance artifact. It showed not just deterministic evaluation, but also how rules are versioned, reviewed, promoted manually, and monitored for drift without pretending to auto-govern production policy logic.

### Key Files

- `engine/extract.py`
- `engine/rulebook.py`
- `engine/acceptance.py`
- `rulebook/manifest.yaml`
- `api.py`
- `cli.py`
- `scripts/generate_golden_outputs.py`
- `docs/artifacts/drift_report.md`
- `docs/artifacts/rulebook_diff_reviewed_vs_active.md`
- `PRODUCT_OVERVIEW.md`
- `WHY_THIS_EXISTS.md`
- `INTERVIEW_TALKING_POINTS.md`

## 4. Final Freeze-Polish Summary

### What Changed In This Audit Pass

- Fixed portability problems in governance outputs by replacing machine-specific paths with repo-relative paths.
- Aligned stale-monitoring behavior so governance outputs and Streamlit gating both treat stale or missing baselines as review-required.
- Clarified demo-case expectation wording in the CLI and Streamlit UI.
- Clarified the difference between coarse synthetic fixture checks and exact acceptance snapshots.
- Removed one dead file and trimmed a few low-value duplicate paths in the app and artifact generation flow.
- Replaced remaining machine-specific markdown links with relative links.
- Added the final freeze audit, push summary, and this release-notes summary.

### Why It Mattered

These were small changes, but they removed the last rough edges that could undermine recruiter trust or handoff quality. The repo now reads more cleanly, travels better across machines, and tells a more consistent story.

### Key Files

- `engine/service.py`
- `engine/rulebook.py`
- `cli.py`
- `app.py`
- `scripts/generate_artifacts.py`
- `README.md`
- `EXTRACTION_CONTRACT.md`
- `FINAL_FREEZE_AUDIT.md`
- `PUSH_SUMMARY.md`

## 5. Overall Repo Before Vs After

### Before The 3 Sprints

- Deterministic extraction and evaluation existed.
- The primary product surface was Streamlit.
- Docs, artifacts, and tests were narrower.
- Governance, provenance, rulebook, and portable product surfaces were limited or absent.

### After The 3 Sprints

- One deterministic workflow powers Streamlit, FastAPI, CLI, artifacts, and acceptance checks.
- The repo has four supported procedures, including a narrow non-spine case.
- Outputs expose richer provenance, rulebook stage metadata, drift artifacts, and audit traces.
- The repo includes portable docs, reproducible artifacts, golden outputs, interview materials, and a clear governance story.

## 6. Final Narrative For Commit / Push Review

Across the last three sprints, this repo was upgraded from a strong deterministic demo into a compact, interview-defensible internal-product artifact. The core identity stayed fixed: deterministic administrative readiness review, synthetic-only data, narrow explainable scope, refusal-first behavior, and governance-only drift monitoring. The work focused on product surfaces, provenance, rule governance, artifacts, tests, and docs rather than broad platform expansion, which is why the repo now feels substantially more mature without becoming harder to explain.
