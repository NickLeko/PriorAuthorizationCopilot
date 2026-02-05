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


def _find_contextual_date(text: str, context_terms: List[str], window: int = 60) -> Optional[str]:
    """
    Returns a date string only if it appears near a relevant context term.
    Prevents DOB or unrelated dates from triggering "sleep_study_date".
    """
    # Date formats: YYYY-MM-DD or YYYY/MM/DD
    date_pat = re.compile(r"\b(20\d{2}|19\d{2})[-/]\d{1,2}[-/]\d{1,2}\b")

    # Scan all date matches and check nearby context
    for m in date_pat.finditer(text):
        start, end = m.start(), m.end()
        left = max(0, start - window)
        right = min(len(text), end + window)
        neighborhood = text[left:right]

        if any(ct in neighborhood for ct in context_terms):
            return m.group(0)

    # Also handle "sleep study 2023-..." in the other direction (context before date)
    # Already covered by neighborhood scan, but kept explicit for clarity.
    return None


def extract_facts(note_text: str) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
    """
    Deterministic extraction for MVP with evidence snippets.

    Returns:
      facts: dict used by rules engine
      evidence: dict mapping fact_key -> list of evidence snippets (substrings)

    Semantics:
      - Missing documentation => None (drives NOT_DOCUMENTED downstream)
      - Explicit denial => False where appropriate
      - Explicit presence => True / concrete values
    """

    evidence: Dict[str, List[str]] = {}

    # -----------------------------------------
    # Input validation
    # -----------------------------------------
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
    # Conservative therapy weeks (context-aware)
    # -----------------------------------------
    weeks: Optional[int] = None

    THERAPY_CONTEXT = [
        "pt",
        "physical therapy",
        "therapy",
        "home exercise",
        "exercise program",
        "nsaids",
        "ibuprofen",
        "naproxen",
        "meloxicam",
        "activity modification",
        "conservative management",
        "conservative care",
    ]
    has_therapy_context = any(k in t for k in THERAPY_CONTEXT)

    if has_therapy_context:
        # Prefer explicit PT duration patterns
        m = re.search(r"\b(pt|physical therapy|therapy)\s*(x|for)?\s*(\d+)\s*(week|weeks)\b", t)
        if m:
            try:
                weeks = int(m.group(3))
                _add_ev(evidence, "conservative_therapy_weeks", t[m.start():m.end()])
            except ValueError:
                weeks = None
        else:
            # Fallback: any N weeks mention (still guarded by therapy context)
            m2 = re.search(r"\b(\d+)\s*(week|weeks)\b", t)
            if m2:
                try:
                    weeks = int(m2.group(1))
                    _add_ev(evidence, "conservative_therapy_weeks", t[m2.start():m2.end()])
                except ValueError:
                    weeks = None

    # -----------------------------------------
    # Neuro deficit / red flags (presence vs documented)
    # -----------------------------------------
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

    neuro_denials = [p for p in DENIAL_PHRASES if p in t]
    neuro_positive = [p for p in POSITIVE_CUES if p in t]

    neuro_present: bool = len(neuro_positive) > 0

    # If no explicit positive cues, do NOT infer presence from generic terms.
    # (We keep this conservative and evidence-based.)
    if not neuro_present and not neuro_denials:
        neuro_deficit_or_red_flags = None
        neuro_red_flags_documented = None
    else:
        neuro_deficit_or_red_flags = bool(neuro_present)
        neuro_red_flags_documented = True

        # Evidence: include representative snippets (cap list size)
        for snip in (neuro_positive[:2] + neuro_denials[:2]):
            _add_ev(evidence, "neuro_red_flags_documented", snip)
        if neuro_positive:
            _add_ev(evidence, "neuro_deficit_or_red_flags", neuro_positive[0])
        elif neuro_denials:
            # Denials imply present=False; document one snippet
            _add_ev(evidence, "neuro_deficit_or_red_flags", neuro_denials[0])

    # -----------------------------------------
    # Prior imaging result (with negation handling)
    # -----------------------------------------
    # DESIGN DECISION:
    # - "normal/unremarkable" imaging => inconclusive (x-ray doesn't rule out soft tissue pathology)
    # - Order matters: "no abnormalities" must be checked before "abnormal"
    prior_imaging: Optional[str] = None

    if any(p in t for p in ["no prior imaging", "no imaging yet", "no imaging to date"]):
        prior_imaging = "none"
        # Choose the first matching phrase for evidence
        for p in ["no prior imaging", "no imaging yet", "no imaging to date"]:
            if p in t:
                _add_ev(evidence, "prior_imaging_result", p)
                break

    elif any(mod in t for mod in ["x-ray", "xray", "ct", "mri", "imaging"]):
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
    # Symptom duration (weeks)
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
        wm = re.search(r"\b(\d+)\s*(week|weeks)\b", t)
        if wm:
            try:
                symptom_weeks = int(wm.group(1))
                _add_ev(evidence, "symptom_duration_weeks", t[wm.start():wm.end()])
            except ValueError:
                symptom_weeks = None

    # -----------------------------------------
    # OSA / sleep study facts (contextual)
    # -----------------------------------------
    osa_dx: Optional[bool] = None
    if ("obstructive sleep apnea" in t) or re.search(r"\bosa\b", t):
        osa_dx = True
        _add_ev(evidence, "osa_diagnosis", "osa" if "osa" in t else "obstructive sleep apnea")

    # Sleep study date should only trigger if date appears near sleep-study context
    sleep_study_date: Optional[bool] = None
    sleep_context = ["sleep study", "polysomnogram", "psg"]
    date_str = _find_contextual_date(t, context_terms=sleep_context, window=80)
    if date_str is not None:
        sleep_study_date = True
        _add_ev(evidence, "sleep_study_date", date_str)

    ahi: Optional[bool] = None
    if ("ahi" in t) or ("rdi" in t):
        ahi = True
        _add_ev(evidence, "ahi_documented", "ahi" if "ahi" in t else "rdi")

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
