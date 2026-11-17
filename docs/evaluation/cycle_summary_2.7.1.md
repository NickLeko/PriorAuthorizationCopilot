# Development cycle summary: engine 2.7.0 to 2.7.1

November 17, 2026. Covers PRs #23 and #24. Neither is merged or deployed.

## What changed

- **Measurement (#23).** Requirement-level evaluation replaced a false-`READY` headline that could not fail. Results carry explicit denominators, constant-predictor controls and separated label tiers, and the holdout is sealed.
- **Extraction (#24).** Lumbar CPB 0236 therapy courses are resolved per course and per fact. A course whose wording is not fully accounted for by a closed course grammar goes to review instead of `MET`. A separate clean course still counts, and a documented duration survives when only the response is qualified.

## Measured results

These are on synthetic notes, mostly with agent-authored labels.

| | 2.7.0 | 2.7.1 |
| --- | --- | --- |
| Challenge false `MET` | 14 | 5 |
| Challenge missed `MET` | 11 | 11 |
| Challenge review burden | 0 of 77 | 9 of 77 |
| Bundled corpus agreement | 193 of 193 | 193 of 193 |
| Framing controls `MET` | 78 of 80 | 78 of 80 |

The challenge counts are known failures on selected notes. They are not estimates of real-world performance.

## Human review and holdout

- **Owner review:** 3 textual labels verified, and 7 policy opinions logged without verifying anything (4 given by accepting agent proposals in bulk).
- **Clinician review:** none.
- **Payer-policy authority:** none claimed.
- **Holdout:** `holdout_v1` is sealed, unlabeled and never run.

## Remaining known defects, ranked by risk

1. **False `MET` on objective-exam temporality.** A historical or copied exam (CH-06, N1B) can satisfy the verified lumbar exam criterion.
2. **False `MET` from a response reversed in a later sentence** (CH-14).
3. **Sibling-clause over-review in 2.7.1** (fail-safe). It is a usability cost on common note wording and needs an owner decision before #24 merges.
4. **Evidence attribution for set-aside courses.** Duration evidence lists courses that did not decide the value.
5. **False `MET` on the generic demo pathways** (CH-16, CH-17). These pathways are not policy-verified.
6. **Recall gaps on natural phrasing** (11 missed `MET`).
7. **Governance items from the November 16 review:**
   - the policy snapshot was last checked on August 31 and is stale;
   - the CPB 0236 drug table sits outside the bundle fingerprint;
   - the policy opinions are unconfirmed by a policy owner.

## Defer rather than develop now

- Recall expansion.
- Cross-sentence linkage.
- Exam temporality.
- Generic-pathway fixes.
- Relationship models.
- The LLM pathway.

The next step is evaluation, not development. A human labels the holdout without running it. Then, with authorization, it is run once against the frozen 2.7.1, and the result decides which defect to address next.

## Branches and worktrees for these PRs

| Item | Purpose | After verified merges |
| --- | --- | --- |
| `claude/gallant-bardeen-0kt5bf` (local and `origin`) | PR #23 head | Can be removed once #23 is merged and #24 has been retargeted and merged |
| `claude/phase2-per-course-therapy` (local and `origin`) | PR #24 head | Can be removed after #24 is merged |
| `main` (local) | Tracks `origin/main` at `6b583df` | Keep; fast-forward after the merges |
| Worktree `/home/user/PriorAuthorizationCopilot` | The only worktree in this cloud container | Ephemeral container; nothing to remove |

The other 34 remote branches (`autoloop/*`, `codex/*`, `feat/*`, `fix/*`, `integration/*`, `v2*`) are unrelated to these PRs and were not touched. The local research and audit worktrees described in the November 16 handoff are on the owner's machine and were not visible here.
