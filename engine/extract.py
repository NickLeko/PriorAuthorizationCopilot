from __future__ import annotations

import re
from typing import Any, Dict


def extract_facts(note_text: str) -> Dict[str, Any]:
    """
    Deterministic extraction for MVP.

    Produces a dict of facts used by the rules engine.
    This is intentionally conservative:
      - If something isn't explicitly documented, prefer None/False over guessing.
      - Handle common negations so "no abnormalities" doesn't get misread as "abnormal".
    """
    t = (note_text or "").lower()

    # -----------------------------------------
    # Conservative therapy weeks
    # -----------------------------------------
    # Look for patterns like: "PT x 6 weeks", "6 weeks of PT", "trial for 8 weeks"
    weeks = None
    m = re.search(r"(\d+)\s*(week|weeks)\b", t)
    if m:
        try:
            weeks = int(m.group(1))
        except ValueError:
            weeks = None

    # -----------------------------------------
    # Neuro deficit / red flags (presence only)
    # -----------------------------------------
    # NOTE: This detects *presence* of red-flag terms. It does not reliably detect
    # explicit denials yet (e.g., "denies weakness"). We'll add that in v0.2.
    neuro_flags = any(
        s in t
        for s in [
            "weakness",
            "bowel",
            "bladder",
            "saddle anesthesia",
            "foot drop",
            "progressive deficit",
        ]
    )

     # Explicit denials (documentation that red flags are NOT present)
    neuro_denials = any(
        s in t for s in [
            "denies weakness",
            "no weakness",
            "denies bowel",
            "denies bladder",
            "no bowel",
            "no bladder",
            "denies saddle anesthesia",
            "no saddle anesthesia",
            "denies numbness",
            "no numbness",
        ]
    )

    neuro_documented = bool(neuro_flags or neuro_denials)


    # -----------------------------------------
    # Prior imaging result (with negation handling)
    # -----------------------------------------
    # IMPORTANT: default None (unknown) unless explicitly documented.
    # Also handle "no abnormalities" so it does NOT map to "abnormal".
    prior_imaging = None

    # Explicit "no prior imaging" statements
    if any(p in t for p in ["no prior imaging", "no imaging yet", "no imaging to date"]):
        prior_imaging = "none"

    # If imaging modality is mentioned, infer a category *only* from documented findings
    elif any(mod in t for mod in ["x-ray", "xray", "ct", "mri", "imaging"]):
        # Negation/normal findings FIRST (avoid substring trap: "abnormalities" contains "abnormal")
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
            # Treat normal prior study as "inconclusive" for escalation purposes in v0.1
            # (You can add a dedicated "normal" bucket later if desired.)
            prior_imaging = "inconclusive"

        elif any(w in t for w in ["inconclusive", "equivocal", "limited"]):
            prior_imaging = "inconclusive"

        elif any(w in t for w in ["abnormal", "herni", "stenosis", "disc bulge", "fracture"]):
            prior_imaging = "abnormal"

        else:
            # Imaging referenced but result not documented clearly
            prior_imaging = "inconclusive"

    # -----------------------------------------
    # Symptom duration (weeks)
    # -----------------------------------------
    symptom_weeks = None

    # crude: if "months" appear, convert to weeks
    mm = re.search(r"(\d+)\s*(month|months)\b", t)
    if mm:
        try:
            symptom_weeks = int(mm.group(1)) * 4
        except ValueError:
            symptom_weeks = None
    else:
        wm = re.search(r"(\d+)\s*(week|weeks)\b", t)
        if wm:
            try:
                symptom_weeks = int(wm.group(1))
            except ValueError:
                symptom_weeks = None

    # -----------------------------------------
    # OSA / sleep study facts
    # -----------------------------------------
    osa_dx = ("obstructive sleep apnea" in t) or ("osa" in t)

    # Strict date pattern: YYYY-MM-DD or YYYY/MM/DD
    sleep_study_date = bool(re.search(r"\b(20\d{2}|19\d{2})[-/]\d{1,2}[-/]\d{1,2}\b", t))

    ahi = ("ahi" in t) or ("rdi" in t)

    return {
        "conservative_therapy_weeks": weeks,
        "neuro_deficit_or_red_flags": neuro_flags,
        "prior_imaging_result": prior_imaging,
        "symptom_duration_weeks": symptom_weeks,
        "osa_diagnosis": osa_dx,
        "sleep_study_date": sleep_study_date,
        "ahi_documented": ahi,
        "neuro_deficit_or_red_flags": neuro_flags,
        "neuro_red_flags_documented": neuro_documented,

    }

