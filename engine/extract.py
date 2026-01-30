from __future__ import annotations
import re
from typing import Any, Dict


def extract_facts(note_text: str) -> Dict[str, Any]:
    """
    Deterministic extraction for MVP.
    Produces a dict of facts used by the rules engine.
    """
    t = (note_text or "").lower()

    # Conservative therapy weeks: look for patterns like "PT x 6 weeks", "6 weeks of PT"
    weeks = None
    m = re.search(r"(\d+)\s*(week|weeks)\b", t)
    if m:
        try:
            weeks = int(m.group(1))
        except ValueError:
            weeks = None

    neuro_flags = any(
        s in t for s in [
            "weakness", "bowel", "bladder", "saddle anesthesia",
            "foot drop", "progressive deficit"
        ]
    )

    # prior imaging result
    # IMPORTANT: default None (unknown) unless explicitly documented
    prior_imaging = None

    if "no prior imaging" in t or "no imaging yet" in t or "no imaging to date" in t:
        prior_imaging = "none"
    elif "x-ray" in t or "xray" in t or "ct" in t or "imaging" in t or "mri" in t:
        if "inconclusive" in t or "equivocal" in t:
            prior_imaging = "inconclusive"
        elif "abnormal" in t or "herni" in t or "stenosis" in t or "disc" in t:
            prior_imaging = "abnormal"
        else:
            # imaging referenced but result unclear
            prior_imaging = "inconclusive"

    symptom_weeks = None
    # crude: if "months" appear, convert to weeks
    mm = re.search(r"(\d+)\s*(month|months)\b", t)
    if mm:
        symptom_weeks = int(mm.group(1)) * 4
    else:
        wm = re.search(r"(\d+)\s*(week|weeks)\b", t)
        if wm:
            symptom_weeks = int(wm.group(1))

    osa_dx = "obstructive sleep apnea" in t or "osa" in t
    sleep_study_date = bool(re.search(r"\b(20\d{2}|19\d{2})[-/]\d{1,2}[-/]\d{1,2}\b", t))
    ahi = "ahi" in t or "rdi" in t

    return {
        "conservative_therapy_weeks": weeks,
        "neuro_deficit_or_red_flags": neuro_flags,
        "prior_imaging_result": prior_imaging,
        "symptom_duration_weeks": symptom_weeks,
        "osa_diagnosis": osa_dx,
        "sleep_study_date": sleep_study_date,
        "ahi_documented": ahi,
    }

