from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


def _add_span(evidence: Dict[str, List[Dict[str, Any]]], key: str, start: int, end: int, text: str) -> None:
    if start < 0 or end <= start:
        return
    evidence.setdefault(key, []).append({"start": int(start), "end": int(end), "text": text})


def _dedup_spans(evidence: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for k, spans in (evidence or {}).items():
        seen = set()
        kept = []
        for s in spans or []:
            sig = (s.get("start"), s.get("end"), s.get("text"))
            if sig in seen:
                continue
            seen.add(sig)
            kept.append(s)
        out[k] = kept
    return out


def extract_facts(note_text: str) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    """
    Deterministic extraction for MVP.

    Returns:
      facts: Dict[str, Any]
      evidence_map: Dict[key -> List[{start,end,text}]]

    Design:
      - Conservative: if not explicitly documented, use None (unknown) where appropriate.
      - Evidence is captured as spans from the original note text.
    """
    raw = note_text or ""
    t = raw.lower()

    evidence: Dict[str, List[Dict[str, Any]]] = {}

    # ----------------------------
    # Conservative therapy weeks
    # ----------------------------
    # Prefer explicit PT duration if present, otherwise first weeks mention.
    therapy_weeks: Optional[int] = None

    m_pt = re.search(r"\bpt\b.*?\b(\d+)\s*(week|weeks)\b", t)
    if m_pt:
        therapy_weeks = int(m_pt.group(1))
        _add_span(evidence, "conservative_therapy_weeks", m_pt.start(), m_pt.end(), raw[m_pt.start() : m_pt.end()])
    else:
        m_any = re.search(r"\b(\d+)\s*(week|weeks)\b", t)
        if m_any:
            therapy_weeks = int(m_any.group(1))
            _add_span(evidence, "conservative_therapy_weeks", m_any.start(), m_any.end(), raw[m_any.start() : m_any.end()])

    # ----------------------------
    # Symptom duration (weeks)
    # ----------------------------
    symptom_weeks: Optional[int] = None

    m_months = re.search(r"\b(\d+)\s*(month|months)\b", t)
    if m_months:
        symptom_weeks = int(m_months.group(1)) * 4
        _add_span(evidence, "symptom_duration_weeks", m_months.start(), m_months.end(), raw[m_months.start() : m_months.end()])
    else:
        m_weeks = re.search(r"\b(\d+)\s*(week|weeks)\b", t)
        if m_weeks:
            symptom_weeks = int(m_weeks.group(1))
            _add_span(evidence, "symptom_duration_weeks", m_weeks.start(), m_weeks.end(), raw[m_weeks.start() : m_weeks.end()])

    # ----------------------------
    # Neuro deficit / red flags
    # ----------------------------
    # Outputs:
    #   neuro_deficit_or_red_flags: True/False/None
    #   neuro_red_flags_documented: True/None  (True if addressed, None if not mentioned)
    #
    # "No red flags documented" counts as addressed (denial).
    #
    denial_patterns = [
        r"\bdenies\b.*\b(weakness|bowel|bladder|saddle anesthesia|foot drop|urinary retention)\b",
        r"\bno\b.*\b(weakness|bowel|bladder|saddle anesthesia|foot drop|urinary retention)\b",
        r"\bno red flags\b",
        r"\bno red flag\b",
        r"\bno red flags documented\b",
        r"\bdenies red flags\b",
        r"\bred flags denied\b",
    ]

    positive_patterns = [
        r"\breports\b.*\b(weakness|urinary retention|bowel incontinence|bladder incontinence|saddle anesthesia|foot drop)\b",
        r"\bprogressive\b.*\bweakness\b",
        r"\burinary retention\b",
        r"\bfecal incontinence\b",
        r"\bcauda equina\b",
    ]

    denial_match = None
    for pat in denial_patterns:
        mm = re.search(pat, t)
        if mm:
            denial_match = mm
            break

    positive_match = None
    for pat in positive_patterns:
        mm = re.search(pat, t)
        if mm:
            positive_match = mm
            break

    if positive_match:
        neuro_present: Optional[bool] = True
        neuro_documented: Optional[bool] = True
        _add_span(
            evidence,
            "neuro_red_flags_documented",
            positive_match.start(),
            positive_match.end(),
            raw[positive_match.start() : positive_match.end()],
        )
    elif denial_match:
        neuro_present = False
        neuro_documented = True
        _add_span(
            evidence,
            "neuro_red_flags_documented",
            denial_match.start(),
            denial_match.end(),
            raw[denial_match.start() : denial_match.end()],
        )
    else:
        neuro_present = None
        neuro_documented = None

    # ----------------------------
    # Prior imaging result
    # ----------------------------
    prior_imaging: Optional[str] = None

    # Explicit "no imaging" should be "none"
    m_no_img = re.search(r"\bno (prior )?imaging( documented| yet| to date)?\b", t)
    if m_no_img:
        prior_imaging = "none"
        _add_span(evidence, "prior_imaging_result", m_no_img.start(), m_no_img.end(), raw[m_no_img.start() : m_no_img.end()])
    else:
        # If any modality mentioned, infer result category
        m_mod = re.search(r"\b(x-?ray|xray|ct|mri|imaging)\b", t)
        if m_mod:
            # Normal/negation first => treat as inconclusive for escalation logic
            m_norm = re.search(r"\b(no abnormalities|no abnormal|no acute findings|normal|unremarkable)\b", t)
            if m_norm:
                prior_imaging = "inconclusive"
                _add_span(evidence, "prior_imaging_result", m_norm.start(), m_norm.end(), raw[m_norm.start() : m_norm.end()])
            else:
                m_abn = re.search(r"\b(abnormal|herniat|stenosis|disc bulge|fracture|degenerative)\b", t)
                if m_abn:
                    prior_imaging = "abnormal"
                    _add_span(evidence, "prior_imaging_result", m_abn.start(), m_abn.end(), raw[m_abn.start() : m_abn.end()])
                else:
                    # modality mentioned but unclear
                    prior_imaging = "inconclusive"
                    _add_span(evidence, "prior_imaging_result", m_mod.start(), m_mod.end(), raw[m_mod.start() : m_mod.end()])

    # ----------------------------
    # OSA / sleep study facts
    # ----------------------------
    osa_dx: Optional[bool] = None
    m_osa = re.search(r"\b(obstructive sleep apnea|osa)\b", t)
    if m_osa:
        osa_dx = True
        _add_span(evidence, "osa_diagnosis", m_osa.start(), m_osa.end(), raw[m_osa.start() : m_osa.end()])
    else:
        osa_dx = None

    sleep_study_date: Optional[bool] = None
    m_date = re.search(r"\b(20\d{2}|19\d{2})[-/]\d{1,2}[-/]\d{1,2}\b", t)
    if m_date:
        sleep_study_date = True
        _add_span(evidence, "sleep_study_date", m_date.start(), m_date.end(), raw[m_date.start() : m_date.end()])
    else:
        sleep_study_date = None

    ahi_doc: Optional[bool] = None
    m_ahi = re.search(r"\b(ahi|rdi)\b", t)
    if m_ahi:
        ahi_doc = True
        _add_span(evidence, "ahi_documented", m_ahi.start(), m_ahi.end(), raw[m_ahi.start() : m_ahi.end()])
    else:
        ahi_doc = None

    facts: Dict[str, Any] = {
        "conservative_therapy_weeks": therapy_weeks,
        "neuro_deficit_or_red_flags": neuro_present,
        "neuro_red_flags_documented": neuro_documented,
        "prior_imaging_result": prior_imaging,
        "symptom_duration_weeks": symptom_weeks,
        "osa_diagnosis": osa_dx,
        "sleep_study_date": sleep_study_date,
        "ahi_documented": ahi_doc,
    }

    return facts, _dedup_spans(evidence)
