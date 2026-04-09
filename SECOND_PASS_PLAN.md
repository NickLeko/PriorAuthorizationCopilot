# SECOND PASS PLAN

## What Already Exists

The first pass already established the repo as a compact enterprise-style artifact:

- shared typed service layer for deterministic orchestration
- central config and structured logging
- FastAPI and CLI surfaces
- rebuilt Streamlit app using shared outputs
- reproducible JSON artifact generation
- expanded tests across service, API, CLI, extraction, rules, provenance, and drift logic
- improved README, architecture, testing, safety, and interview docs
- lightweight Ruff + CI

The core architecture is not the problem anymore. The next gains should come from depth.

## What Is Still Weak

1. Supported deterministic scope is still narrow.
   - Only two procedures are currently supported.
   - The repo can support one more carefully chosen deterministic pathway without architecture churn.

2. Rule registry and provenance detail are still thinner than they could be.
   - Supported procedures expose only basic fields today.
   - Provenance metadata exists but is not consistently normalized or surfaced as a strong registry story.

3. Drift/governance surfaces are still fairly minimal.
   - There is one monitored source.
   - The repo could do a better job surfacing monitored-source metadata and rule lineage without widening scope.

4. Demo quality can still improve.
   - Artifacts exist, but demo-case taxonomy and walkthrough clarity can be stronger.
   - There is still no direct Streamlit sanity coverage.

5. Regression safety has room to grow.
   - The most important remaining gaps are malformed/partial input handling, contradictory evidence behavior, registry metadata integrity, and UI startup sanity.

## What This Pass Will Improve

1. Add one carefully chosen new deterministic procedure if it can reuse the current extraction rigor cleanly.
   - If a second new procedure starts to feel vague, stop at one.

2. Strengthen procedure registry and provenance metadata.
   - Add richer procedure-level metadata to the rule registry.
   - Normalize and surface provenance fields that matter in interviews:
     - rule version
     - rule source label
     - last reviewed / last updated
     - monitored-for-drift status
     - rule family / category where useful

3. Improve governance and drift visibility without changing behavior.
   - Keep drift monitoring governance-only.
   - Make monitored source status easier to inspect through outputs and docs.

4. Improve demo quality and UI sanity coverage.
   - Refresh artifacts after the new procedure/metadata land.
   - Add lightweight Streamlit sanity coverage rather than heavy browser infrastructure unless a minimal browser path proves low-cost.

5. Expand regression tests around the repo’s product identity.
   - new procedure coverage
   - ambiguous or contradictory evidence handling
   - registry/provenance integrity
   - artifact generation
   - Streamlit startup/smoke sanity

6. Tighten local ergonomics where useful.
   - Add only lightweight improvements, such as small Makefile target additions and clearer run/verify commands.

## What Will Intentionally Remain Unchanged

- no LLM layer
- no database
- no auth
- no claims workflow platform
- no payer scraping
- no approval prediction
- no medical-necessity or clinical recommendation logic
- no autonomous action
- no rewrite of the shared service architecture unless a concrete defect appears

## Execution Order

1. Re-audit and record second-pass scope
2. Add one carefully chosen deterministic procedure and corresponding synthetic fixtures
3. Enrich rule registry, provenance, and drift metadata surfaces
4. Add Streamlit sanity coverage and refresh demo artifacts
5. Expand regression tests and tighten local ergonomics
6. Update README, docs, interview notes, and next steps
7. Run Ruff, tests, artifact generation, and a final simplification pass

## Decision Rules For This Pass

- Prefer one well-finished new procedure over two shallow ones.
- If metadata and testing improvements are higher ROI than procedure count, bias toward metadata and tests.
- If browser-style screenshot automation becomes dependency-heavy, fall back to stronger artifact generation and Streamlit sanity coverage.
- Every change must remain explainable by one person in an interview.
