from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


def _add_ev(evidence: Dict[str, List[str]], key: str, snippet: str) -> None:
    snippet = (snippet or "").strip()
    if not snippet:
        return
    evidence.setdefault(key, [])
    if snippet not in evidence[key]:
        evidence[key].append(snippet)


def _is_dob_date(text: str, date_start: int) -> bool:
    """
    Skip DOB dates: if 'dob' appears shortly before the date, treat it as DOB not sleep study.
    """
    left = max(0, date_start - 12)
    prefix = text[left:date_start]
    return "dob" in prefix


def _find_contextual_sleep_study_date(text: str, window: int = 90) -> Optional[str]:
    """
    Returns a date ONLY if it appears near a sleep-study context term,
    and the date is NOT a DOB date.
    """
    date_pat = re.compile(r"\b(20\d{2}|19\d{2})[-/]\d{1,2}[-/]\d{1,2}\b")
    context_terms = ["sleep study", "polysomnogram", "psg"]

    for m in date_pat.finditer(text):
        if _is_dob_date(text, m.start()):
            continue

        start, end = m.start(), m.end()
        left = max(0, start - window)
        right = min(len(text), end + window)
        neighborhood = text[left:right]

        if any(ct in neighborhood for ct in context_terms):
            return m.group(0)

    return None


def extract_facts(note_text: str) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
    """
    Deterministic extraction for MVP with evidence snippets.

    Returns:
      facts: dict used by rules engine
      evidence: dict mapping fact_key -> list of evidence snippets

    Design principles:
      - Conservative: if not explicitly documented, return None
      - Avoid substring traps and negated mentions ("AHI not documented")
      - Fake PHI-safe: DOB dates should not satisfy sleep-study date
    """

    evidence: Dict[str, List[str]] = {}

    # Input validation
    if not isinstance(note_text, str):
        note_text = "" if note_text is None else str(note_text)

    if len(note_text.strip()) == 0:
        return (
            {
                "conservative_therapy_weeks": None,
                "neuro_deficit_or_red_flags": None,
                "neuro_red_flags_documented": None,
                "prior_imaging_result": None,
                "symptom_duration_weeks": None,
                "osa_diagnosis": None,
                "sleep_study_date": None,
                "ahi_documented": None,
            },
            evidence,
        )

    t = note_text.lower()

    # -----------------------------------------
    # Conservative therapy weeks (context-aware, strict)
    # Only set conservative_therapy_weeks when the duration is explicitly tied
    # to a conservative-therapy term (avoid borrowing symptom duration).
    # -----------------------------------------
    weeks: Optional[int] = None
    
    therapy_terms = [
        "pt",
        "physical therapy",
        "therapy",
        "nsaids",
        "ibuprofen",
        "naproxen",
        "meloxicam",
        "activity modification",
        "home exercise",
        "conservative care",
        "conservative therapy",
        "conservative management",
    ]
    
    # Pattern A: term then duration (preferred)
    # Examples:
    #  - "PT x 8 weeks"
    #  - "physical therapy for 6 wks"
    #  - "NSAIDs 6wk"
    m1 = re.search(
        r"\b("
        + "|".join(re.escape(x) for x in therapy_terms)
        + r")\b\s*(?:x|for)?\s*(\d+)\s*(?:week|weeks|wk|wks)\b",
        t,
    )
    if m1:
        try:
            weeks = int(m1.group(2))
            _add_ev(evidence, "conservative_therapy_weeks", t[m1.start():m1.end()])
        except ValueError:
            weeks = None
    else:
        # Pattern B: duration then term, but ONLY when immediately tied (no loose neighborhood)
        # Examples:
        #  - "8 weeks of PT"
        #  - "6 wks of physical therapy"
        #  - "8wk of conservative care"
        m2 = re.search(
            r"\b(\d+)\s*(?:week|weeks|wk|wks)\b\s*(?:of\s+)?\b("
            + "|".join(re.escape(x) for x in therapy_terms)
            + r")\b",
            t,
        )
        if m2:
            try:
                weeks = int(m2.group(1))
                _add_ev(evidence, "conservative_therapy_weeks", t[m2.start():m2.end()])
            except ValueError:
                weeks = None


    # -----------------------------------------
    # Neuro red flags: presence vs documented
    # -----------------------------------------
    denial_phrases = [
        "denies weakness",
        "no weakness",
        "weakness absent",
        "weakness is absent",
        "strength intact",
        "motor intact",
        "denies bowel",
        "no bowel",
        "denies bladder",
        "no bladder",
        "denies bowel/bladder",
        "no bowel/bladder",
        "bowel/bladder function intact",
        "no bowel or bladder changes",
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
    ]

    positive_cues = [
        "reports weakness",
        "has weakness",
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

    neuro_denials = [p for p in denial_phrases if p in t]
    neuro_positive = [p for p in positive_cues if p in t]

    if not neuro_denials and not neuro_positive:
        neuro_deficit_or_red_flags = None
        neuro_red_flags_documented = None
    else:
        # Positive cues override denials if both present (conflict case)
        neuro_present = len(neuro_positive) > 0
        neuro_deficit_or_red_flags = True if neuro_present else False
        neuro_red_flags_documented = True

        for snip in (neuro_positive[:2] + neuro_denials[:2]):
            _add_ev(evidence, "neuro_red_flags_documented", snip)
        _add_ev(
            evidence,
            "neuro_deficit_or_red_flags",
            neuro_positive[0] if neuro_positive else neuro_denials[0],
        )

    # -----------------------------------------
    # Prior imaging result
    # -----------------------------------------
    prior_imaging: Optional[str] = None

    if any(p in t for p in ["no prior imaging", "no imaging yet", "no imaging to date"]):
        prior_imaging = "none"
        for p in ["no prior imaging", "no imaging yet", "no imaging to date"]:
            if p in t:
                _add_ev(evidence, "prior_imaging_result", p)
                break

    elif any(mod in t for mod in ["x-ray", "xray", "ct", "mri", "imaging"]):
        # normal/unremarkable => inconclusive (escalation still plausible)
        if any(neg in t for neg in ["no abnormal", "no abnormalities", "no acute findings", "normal", "unremarkable"]):
            prior_imaging = "inconclusive"
            for p in ["no abnormalities", "no acute findings", "normal", "unremarkable", "no abnormal"]:
                if p in t:
                    _add_ev(evidence, "prior_imaging_result", p)
                    break
        elif any(w in t for w in ["inconclusive", "equivocal", "limited", "unclear"]):
            prior_imaging = "inconclusive"
            for p in ["inconclusive", "equivocal", "limited", "unclear"]:
                if p in t:
                    _add_ev(evidence, "prior_imaging_result", p)
                    break
        elif any(w in t for w in ["abnormal", "herni", "stenosis", "disc bulge", "fracture", "disc"]):
            prior_imaging = "abnormal"
            for p in ["abnormal", "herni", "stenosis", "disc bulge", "fracture", "disc"]:
                if p in t:
                    _add_ev(evidence, "prior_imaging_result", p)
                    break
        else:
            prior_imaging = "inconclusive"
            _add_ev(evidence, "prior_imaging_result", "imaging mentioned; result unclear")

    # -----------------------------------------
    # Symptom duration weeks (separate from therapy)
    # -----------------------------------------
    symptom_weeks: Optional[int] = None

    mm = re.search(r"\b(\d+)\s*(month|months)\b", t)
    if mm:
        try:
            symptom_weeks = int(mm.group(1)) * 4
            _add_ev(evidence, "symptom_duration_weeks", t[mm.start():mm.end()])
        except ValueError:
            symptom_weeks = None
    else:
        wm = re.search(r"\b(\d+)\s*(week|weeks|wk|wks)\b", t)
        if wm:
            try:
                symptom_weeks = int(wm.group(1))
                _add_ev(evidence, "symptom_duration_weeks", t[wm.start():wm.end()])
            except ValueError:
                symptom_weeks = None

    # -----------------------------------------
    # OSA diagnosis (affirmative only; avoid "OSA not stated")
    # -----------------------------------------
    osa_dx: Optional[bool] = None

    # affirmative patterns
    if "obstructive sleep apnea" in t:
        osa_dx = True
        _add_ev(evidence, "osa_diagnosis", "obstructive sleep apnea")
    elif re.search(r"\b(dx|diagnosis)\s*:\s*osa\b", t):
        osa_dx = True
        _add_ev(evidence, "osa_diagnosis", "dx: osa")
    elif re.search(r"\bosa\b", t) and not any(
        bad in t for bad in ["osa not stated", "osa not documented", "no osa", "without osa", "denies osa"]
    ):
        # still conservative: only count plain "OSA" if not explicitly negated
        osa_dx = True
        _add_ev(evidence, "osa_diagnosis", "osa")

    # -----------------------------------------
    # Sleep study date (contextual + DOB-safe)
    # -----------------------------------------
    sleep_study_date: Optional[bool] = None
    date_str = _find_contextual_sleep_study_date(t, window=90)
    if date_str is not None:
        sleep_study_date = True
        _add_ev(evidence, "sleep_study_date", date_str)

    # -----------------------------------------
    # AHI/RDI documented (avoid negations)
    # -----------------------------------------
    ahi: Optional[bool] = None

    # Negated phrases should NOT count as documented
    if any(p in t for p in ["ahi not documented", "ahi not provided", "ahi unknown", "no ahi", "ahi unavailable"]):
        ahi = None
        for p in ["ahi not documented", "ahi not provided", "ahi unknown", "no ahi", "ahi unavailable"]:
            if p in t:
                _add_ev(evidence, "ahi_documented", p)
                break
    else:
        if "ahi" in t:
            ahi = True
            _add_ev(evidence, "ahi_documented", "ahi")
        elif "rdi" in t:
            ahi = True
            _add_ev(evidence, "ahi_documented", "rdi")

    facts = {
        "conservative_therapy_weeks": weeks,
        "neuro_deficit_or_red_flags": neuro_deficit_or_red_flags,
        "neuro_red_flags_documented": neuro_red_flags_documented,
        "prior_imaging_result": prior_imaging,
        "symptom_duration_weeks": symptom_weeks,
        "osa_diagnosis": osa_dx,
        "sleep_study_date": sleep_study_date,
        "ahi_documented": ahi,
    }

    return facts, evidence
