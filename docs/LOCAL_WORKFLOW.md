# Local Workflow

## Setup
```bash
make install
```

If you prefer to do it manually:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run The App
```bash
make run
```

## Run The Contract Tests
```bash
make test
```

These tests are meant to lock:
- refusal semantics,
- deterministic extraction behavior,
- write-only letter constraints,
- config validation,
- policy drift normalization behavior.

## Suggested Local Change Workflow
1. Update rules, extraction patterns, or governance code in a small commit.
2. Run `make test`.
3. Open the app with `make run`.
4. Verify the policy provenance banner and blocking-item behavior on a synthetic case.
5. If letter behavior changed, generate a letter and inspect the metadata hash plus blocked-language behavior.
6. If policy-source artifacts changed, review the snapshot and diff outputs before treating rules as aligned.

## Policy Drift Review Notes
- `rules/policy_sources.yaml` declares monitored external policy sources.
- `policy_snapshots/` stores committed governance artifacts.
- Drift detection should trigger review, not rule mutation.
- Rule updates should happen only after human review plus test updates.
