# Demo Walkthrough

## Goal

Demonstrate the product boundary, deterministic decision trace, failure behavior, and policy-governance controls.

For clone/install/test/artifact inspection steps, use the shorter reviewer path in [docs/reviewer_guide.md](reviewer_guide.md).

## Setup

```bash
make install PYTHON=python3.12
make run
```

Optional:

```bash
make api
.venv/bin/python cli.py list-demo-cases
```

## Recommended 5-Minute Demo Flow

### 1. Open the Streamlit app

Start with the scope language:

- deterministic
- bundled synthetic demo data; free-form input is not screened
- administrative readiness only
- no clinical judgment
- no approval prediction

### 2. Show the quality gates

Point out:

- exact-status regression accuracy, false-READY count, and abstention rate
- policy drift status
- rulebook governance with reviewed vs active snapshots
- supported procedure registry with category, rule family, and provenance labels

These checks make regression behavior and governance state visible during a review.

### 3. Run the straight-line ready case

Use `MRI-01-complete`.

Call out:

- evidence mapping
- requirement-level reasoning
- audit trace
- deterministic letter drafting

### 4. Run the documented-but-not-ready case

Use `MRI-08-edge-below-threshold`.

Call out the difference between:

- present but below threshold -> `NOT_READY`
- missing or unclear -> not this case
- ambiguous, contradictory, or otherwise unsafe-to-resolve evidence -> `NEEDS_REVIEW`, not a threshold failure

### 5. Run the refusal-first case

Use `CPAP-02-borderline`.

Call out:

- `CANNOT_DETERMINE` is deliberate
- the system refuses to infer missing documentation
- this is safer than pretending certainty

### 6. Show the same logic through API or CLI

Example:

```bash
.venv/bin/python cli.py evaluate --demo-case CPAP-02-borderline
curl http://127.0.0.1:8000/supported-procedures
```

That makes the artifact feel like a compact internal product instead of a UI-only demo.

### 7. Show the second supported spine MRI pathway

Use `MRI-CERV-01-ready`.

Call out:

- the engine was not rewritten to add it
- the same deterministic extraction contract was reused
- the procedure registry now surfaces rule family and provenance metadata
- procedure-specific behavior remains explicit and testable

### 8. Show the non-spine deterministic expansion

Use `MRI-KNEE-01-ready`.

Call out:

- this is a different clinical domain but still a narrow administrative contract
- only one new extractor field was added
- prior imaging is now a documented threshold, not just a missingness check
- the repo still avoids medical-necessity scoring or approval prediction

### 9. Show the governance diff

Use:

```bash
.venv/bin/python cli.py rulebook-diff --from-release 2026-04-09-reviewed-v0.4 --to-release 2026-08-22-active-v1.0
```

Call out:

- a human can see exactly what changed between reviewed and active rulebooks
- drift monitoring remains separate from promotion
- this is a compact governance story without pretending to be a platform

## Good Sound Bites During The Demo

- "This checks administrative readiness, not approval likelihood."
- "The system is narrow on purpose so every output can be defended."
- "Missing data produces refusal, not fake confidence."
- "The same deterministic workflow powers the UI, API, CLI, and exported artifacts."
- "The active release keeps one verified policy branch separate from three synthetic demo pathways, with versioned rules and reproducible acceptance artifacts."
