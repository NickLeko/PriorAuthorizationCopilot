from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


def _add_span(evidence: Dict[str, List[Dict[str, Any]]], key: str, full_text: str, start: int, end: int) -> None:
    start = max(0, int(start))
    end = min(len(full_text), int(end))
    if end <= start:
        return
    text = full_text[start:end].strip()
    if not text:
        return

    evidence.setdefault(key, [])
    item = {"start": start, "end": end, "text": text}

    # Deduplicate by identical span
    for existing in evidence[key]:
        if existing.get("start") == start and existing.get("end") == end:
            return
    evidence[key].append(item)


_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


def _normalize_number_words(text: str) -> str:
    if not text:
        return text
    out = text
    for w, n in _NUM_WORDS.items():
        out = re.sub(rf"\b{w}\b", str(n), out)
    return out


def _is_dob_date(text: str, date_start: int) -> bool:
    left = max(0, date_start - 12)
    prefix = text[left:date_start]
    return "dob" in prefix


def _find_contextual_sleep_study_date(text: str, window: int = 90) -> Optional[re.Match]:
    date_pat = re.compile(r"\b(20\d{2}|19\d{2})[-/]\d{1,2}[-/]\d{1,2}\b")
    context_terms = ["sleep study", "polysomnogram", "psg"]

    for m in date_pat.finditer(text):
        if _is_dob_date(text, m.start()):
            continue
        left = max(0, m.start() - window)
        right = min(len(text), m.end() + window)
        neighborhood = text[left:right]
        if any(ct in neighborhood for ct in context_terms):
            return m
    return None


def extract_facts(note_text: str) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    evidence: Dict[str, List[Dict[str, Any]]] = {}

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

    raw = note_text
    t = _normalize_number_words(note_text.lower())

    # -----------------------------------------
    # Conservative therapy weeks (context-aware, strict)
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

    m1 = re.search(
        r"\b(" + "|".join(re.escape(x) for x in therapy_terms) + r")\b\s*(?:x|for)?\s*(\d+)\s*(?:week|weeks|wk|wks)\b",
        t,
    )
    if m1:
        try:
            weeks = int(m1.group(2))
            _add_span(evidence, "conservative_therapy_weeks", raw, m1.start(), m1.end())
        except ValueError:
            weeks = None
    else:
        m2 = re.search(
            r"\b(\d+)\s*(?:week|weeks|wk|wks)\b\s*(?:of\s+)?\b(" + "|".join(re.escape(x) for x in therapy_terms) + r")\b",
            t,
        )
        if m2:
            try:
                weeks = int(m2.group(1))
                _add_span(evidence, "conservative_therapy_weeks", raw, m2.start(), m2.end())
            except ValueError:
                weeks = None

    # -----------------------------------------
    # Neuro red flags
    # -----------------------------------------
    denial_phrases = [
        "denies weakness", "no weakness", "weakness absent", "weakness is absent",
        "strength intact", "motor intact",
        "denies bowel", "no bowel", "denies bladder", "no bladder",
        "denies bowel/bladder", "no bowel/bladder", "bowel/bladder function intact",
        "no bowel or bladder changes",
        "denies saddle anesthesia", "no saddle anesthesia",
        "denies foot drop", "no foot drop",
        "denies progressive deficit", "no progressive deficit",
        "denies numbness", "no numbness", "denies tingling", "no tingling",
    ]
    positive_cues = [
        "reports weakness", "has weakness", "objective weakness", "new weakness",
        "progressive weakness",
        "bowel incontinence", "bladder incontinence", "urinary retention",
        "fecal incontinence", "saddle anesthesia present", "foot drop present",
        "progressive deficit noted", "cauda equina",
    ]

    neuro_denials = [p for p in denial_phrases if p in t]
    neuro_positive = [p for p in positive_cues if p in t]

    if not neuro_denials and not neuro_positive:
        neuro_deficit_or_red_flags = None
        neuro_red_flags_documented = None
    else:
        neuro_present = len(neuro_positive) > 0
        neuro_deficit_or_red_flags = True if neuro_present else False
        neuro_red_flags_documented = True

        # Evidence: capture first match spans for positive/denial
        for phrase in (neuro_positive[:1] + neuro_denials[:1]):
            idx = t.find(phrase)
            if idx >= 0:
                _add_span(evidence, "neuro_red_flags_documented", raw, idx, idx + len(phrase))

    # -----------------------------------------
    # Prior imaging result
    # -----------------------------------------
    prior_imaging: Optional[str] = None
    if any(p in t for p in ["no prior imaging", "no imaging yet", "no imaging to date"]):
        prior_imaging = "none"
        for p in ["no prior imaging", "no imaging yet", "no imaging to date"]:
            idx = t.find(p)
            if idx >= 0:
                _add_span(evidence, "prior_imaging_result", raw, idx, idx + len(p))
                break
    elif any(mod in t for mod in ["x-ray", "xray", "ct", "mri", "imaging"]):
        if any(neg in t for neg in ["no abnormal", "no abnormalities", "no acute findings", "normal", "unremarkable"]):
            prior_imaging = "inconclusive"
        elif any(w in t for w in ["inconclusive", "equivocal", "limited", "unclear"]):
            prior_imaging = "inconclusive"
        elif any(w in t for w in ["abnormal", "herni", "stenosis", "disc bulge", "fracture", "disc"]):
            prior_imaging = "abnormal"
        else:
            prior_imaging = "inconclusive"

        # Evidence (best-effort): capture first modality mention
        for mod in ["mri", "ct", "x-ray", "xray", "imaging"]:
            idx = t.find(mod)
            if idx >= 0:
                _add_span(evidence, "prior_imaging_result", raw, idx, idx + len(mod))
                break

    # -----------------------------------------
    # Symptom duration weeks
    # -----------------------------------------
    symptom_weeks: Optional[int] = None
    mm = re.search(r"\b(\d+)\s*(month|months)\b", t)
    if mm:
        try:
            symptom_weeks = int(mm.group(1)) * 4
            _add_span(evidence, "symptom_duration_weeks", raw, mm.start(), mm.end())
        except ValueError:
            symptom_weeks = None
    else:
        wm = re.search(r"\b(\d+)\s*(week|weeks|wk|wks)\b", t)
        if wm:
            try:
                symptom_weeks = int(wm.group(1))
                _add_span(evidence, "symptom_duration_weeks", raw, wm.start(), wm.end())
            except ValueError:
                symptom_weeks = None

    # -----------------------------------------
    # OSA diagnosis (affirmative only)
    # -----------------------------------------
    osa_dx: Optional[bool] = None
    if "obstructive sleep apnea" in t:
        osa_dx = True
        idx = t.find("obstructive sleep apnea")
        _add_span(evidence, "osa_diagnosis", raw, idx, idx + len("obstructive sleep apnea"))
    elif re.search(r"\b(dx|diagnosis)\s*:\s*osa\b", t):
        osa_dx = True
    elif re.search(r"\bosa\b", t) and not any(bad in t for bad in ["osa not stated", "osa not documented", "no osa", "without osa", "denies osa"]):
        osa_dx = True

    # -----------------------------------------
    # Sleep study date (contextual + DOB-safe)
    # -----------------------------------------
    sleep_study_date: Optional[bool] = None
    mdate = _find_contextual_sleep_study_date(t, window=90)
    if mdate is not None:
        sleep_study_date = True
        _add_span(evidence, "sleep_study_date", raw, mdate.start(), mdate.end())

    # -----------------------------------------
    # AHI/RDI documented (avoid negations)
    # -----------------------------------------
    ahi: Optional[bool] = None
    if any(p in t for p in ["ahi not documented", "ahi not provided", "ahi unknown", "no ahi", "ahi unavailable"]):
        ahi = None
    else:
        if "ahi" in t:
            ahi = True
        elif "rdi" in t:
            ahi = True
    if "ahi" in t:
        idx = t.find("ahi")
        _add_span(evidence, "ahi_documented", raw, idx, idx + 3)

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
