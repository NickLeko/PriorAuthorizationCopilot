from __future__ import annotations

import re
from typing import Any, Dict, Optional


def extract_facts(note_text: str) -> Dict[str, Any]:
    """
    Deterministic extraction for MVP.

    Produces a dict of facts used by the rules engine.
    Intentionally conservative:
      - If something isn't explicitly documented, return None (NOT_DOCUMENTED), not False.
      - Handle common negations so "no abnormalities" doesn't get misread as "abnormal".
      - Distinguish between:
          (a) red flags PRESENT vs
          (b) red flags DOCUMENTED (present OR explicitly denied)
    """

    # -----------------------------------------
    # Input validation (v0.2+ semantics)
    # -----------------------------------------
    if not isinstance(note_text, str):
        note_text = "" if note_text is None else str(note_text)

    if len(note_text.strip()) == 0:
        # Empty note = no documentation. Use None where "not documented" is the correct semantics.
        return {
            "conservative_therapy_weeks": None,
            "neuro_deficit_or_red_flags": None,      # unknown (not documented)
            "neuro_red_flags_documented": None,      # unknown (not documented)
            "prior_imaging_result": None,
            "symptom_duration_weeks": None,
            "osa_diagnosis": None,                   # unknown (not documented)
            "sleep_study_date": None,                # unknown (not documented)
            "ahi_documented": None,                  # unknown (not documented)
        }

    t = note_text.lower()

    # -----------------------------------------
    # Conservative therapy weeks (context-aware)
    # -----------------------------------------
    # DESIGN DECISION (v0.3):
    # - Only count weeks as "conservative therapy" if therapy context exists (PT/NSAIDs/activity modification).
    # - This prevents accidentally using symptom duration weeks as therapy weeks.
    weeks: Optional[int] = None

    THERAPY_CONTEXT = [
        "pt", "physical therapy", "therapy", "home exercise", "exercise program",
        "nsaids", "ibuprofen", "naproxen", "meloxicam", "activity modification",
        "conservative management", "conservative care",
    ]

    has_therapy_context = any(k in t for k in THERAPY_CONTEXT)

    if has_therapy_context:
        # Prefer explicit "PT x N weeks" patterns
        m = re.search(r"\b(pt|physical therapy|therapy)\s*(x|for)?\s*(\d+)\s*(week|weeks)\b", t)
        if m:
            try:
                weeks = int(m.group(3))
            except ValueError:
                weeks = None
        else:
            # Fall back to any "N weeks" mention (still guarded by therapy context)
            m2 = re.search(r"\b(\d+)\s*(week|weeks)\b", t)
            if m2:
                try:
                    weeks = int(m2.group(1))
                except ValueError:
                    weeks = None

    # -----------------------------------------
    # Neuro deficit / red flags
    # -----------------------------------------
    # IMPORTANT:
    # - neuro_deficit_or_red_flags means PRESENT (not just mentioned).
    # - neuro_red_flags_documented means addressed (present OR explicitly denied).
    RED_FLAG_TERMS = [
        "weakness",
        "bowel",
        "bladder",
        "saddle anesthesia",
        "foot drop",
        "progressive deficit",
        "urinary retention",
        "fecal incontinence",
        "cauda equina",
    ]

    # Expanded denial variants (to reduce false positives)
    DENIAL_PHRASES = [
        "denies weakness",
        "no weakness",
        "weakness absent",
        "weakness is absent",
        "strength intact",
        "motor intact",
        "neuro intact",
        "denies bowel",
        "no bowel",
        "bowel intact",
        "denies bladder",
        "no bladder",
        "bladder intact",
        "denies bowel/bladder",
        "no bowel/bladder",
        "denies saddle anesthesia",
        "no saddle anesthesia",
        "denies foot drop",
        "no foot drop",
        "denies progressive deficit",
        "no progressive deficit",
        "denies numbness",
        "no numbness",
        "denies tingling",
        "no tingling",
        "bowel/bladder function intact",
        "no bowel or bladder changes",
    ]

    POSITIVE_CUES = [
        "reports weakness",
        "has weakness",
        "with weakness",
        "objective weakness",
        "new weakness",
        "progressive weakness",
        "bowel incontinence",
        "bladder incontinence",
        "urinary retention",
        "fecal incontinence",
        "saddle anesthesia present",
        "foot drop present",
        "progressive deficit noted",
        "cauda equina",
    ]

    neuro_denials = any(p in t for p in DENIAL_PHRASES)

    # Explicit positive cues override denial heuristics
    neuro_present = any(p in t for p in POSITIVE_CUES)

    # If no explicit positive cue, fall back to generic term matching ONLY when no denials exist.
    # This avoids "denies bowel/bladder" incorrectly triggering presence.
    if not neuro_present and not neuro_denials:
        neuro_present = any(term in t for term in RED_FLAG_TERMS)

    neuro_deficit_or_red_flags: Optional[bool]
    neuro_red_flags_documented: Optional[bool]

    # If neither present nor denied, it's not documented (None)
    if not neuro_present and not neuro_denials:
        neuro_deficit_or_red_flags = None
        neuro_red_flags_documented = None
    else:
        neuro_deficit_or_red_flags = bool(neuro_present)
        neuro_red_flags_documented = True

    # -----------------------------------------
    # Prior imaging result (with negation handling)
    # -----------------------------------------
    # DESIGN DECISION (v0.2+):
    # - "normal" prior imaging is treated as "inconclusive" for escalation purposes
    #   because normal X-ray does not rule out soft tissue pathology → MRI may still be appropriate.
    # - Conservative default: avoid blocking clinically justified escalation.
    # - Check order matters: "no abnormalities" must be checked BEFORE "abnormal" (substring trap).
    prior_imaging: Optional[str] = None

    # Explicit "no prior imaging" statements
    if any(p in t for p in ["no prior imaging", "no imaging yet", "no imaging to date"]):
        prior_imaging = "none"

    # If imaging modality is mentioned, infer a category *only* from documented findings
    elif any(mod in t for mod in ["x-ray", "xray", "ct", "mri", "imaging"]):
        # Negation/normal findings FIRST
        if any(
            neg in t
            for neg in [
                "no abnormal",
                "no abnormalities",
                "no acute findings",
                "normal",
                "unremarkable",
            ]
        ):
            prior_imaging = "inconclusive"
        elif any(w in t for w in ["inconclusive", "equivocal", "limited", "unclear"]):
            prior_imaging = "inconclusive"
        elif any(w in t for w in ["abnormal", "herni", "stenosis", "disc bulge", "fracture", "disc"]):
            prior_imaging = "abnormal"
        else:
            # Imaging referenced but result unclear
            prior_imaging = "inconclusive"

    # -----------------------------------------
    # Symptom duration (weeks)
    # -----------------------------------------
    symptom_weeks: Optional[int] = None

    mm = re.search(r"\b(\d+)\s*(month|months)\b", t)
    if mm:
        try:
            symptom_weeks = int(mm.group(1)) * 4
        except ValueError:
            symptom_weeks = None
    else:
        wm = re.search(r"\b(\d+)\s*(week|weeks)\b", t)
        if wm:
            try:
                symptom_weeks = int(wm.group(1))
            except ValueError:
                symptom_weeks = None

    # -----------------------------------------
    # OSA / sleep study facts
    # -----------------------------------------
    osa_dx: Optional[bool] = None
    if ("obstructive sleep apnea" in t) or re.search(r"\bosa\b", t):
        osa_dx = True

    # Strict date pattern: YYYY-MM-DD or YYYY/MM/DD
    sleep_study_date: Optional[bool] = None
    if re.search(r"\b(20\d{2}|19\d{2})[-/]\d{1,2}[-/]\d{1,2}\b", t):
        sleep_study_date = True

    ahi: Optional[bool] = None
    if ("ahi" in t) or ("rdi" in t):
        ahi = True

    return {
        "conservative_therapy_weeks": weeks,
        "neuro_deficit_or_red_flags": neuro_deficit_or_red_flags,
        "neuro_red_flags_documented": neuro_red_flags_documented,
        "prior_imaging_result": prior_imaging,
        "symptom_duration_weeks": symptom_weeks,
        "osa_diagnosis": osa_dx,
        "sleep_study_date": sleep_study_date,
        "ahi_documented": ahi,
    }
