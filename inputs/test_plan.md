# Synthetic Test Plan — PA Readiness Copilot

## Purpose
Expand coverage to reduce regressions and validate conservative extraction + rules behavior.

## Ground Rules
- Any required item NOT_DOCUMENTED => overall_status = CANNOT_DETERMINE => expected_label = incomplete
- Borderline is only allowed when:
  - not_documented_count == 0
  - not_met_count <= 1
  - score >= 60

## Categories to Cover
1) Boundary values
- 6 weeks exactly vs 5 weeks
- 6 weeks symptom duration vs 5 weeks

2) Negation variants (red flags)
- "denies weakness"
- "no weakness"
- "weakness absent"
- "bowel/bladder intact"
- "no bowel or bladder changes"

3) Ambiguity / documentation gaps
- "no red flags mentioned" (should be NOT_DOCUMENTED)
- "imaging noted" (inconclusive)
- "prior imaging" without modality/result (inconclusive)

4) Conflicts
- "denies weakness" + later "reports weakness" (positive cue wins)

5) Noisy notes
- templated text
- copied forward sections
- irrelevant numbers ("6 weeks pregnant", etc.)

## Expansion Targets
- 25 cases: baseline credibility
- 50 cases: strong flagship signal
