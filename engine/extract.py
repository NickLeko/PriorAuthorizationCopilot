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


def _combined_span_text(raw: str, first: re.Match[str], second: re.Match[str]) -> Tuple[int, int, str]:
    start = min(first.start(), second.start())
    end = max(first.end(), second.end())
    return start, end, raw[start:end]


def extract_facts(note_text: str) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    """
    Deterministic extraction for MVP.

    Returns:
      facts: Dict[str, Any]
      evidence_map: Dict[key -> List[{start,end,text}]]

    Contract:
      - Conservative: if not explicitly documented, use None.
      - Evidence is captured as spans from the original note text.
    """
    raw = note_text or ""
    t = raw.lower()

    evidence: Dict[str, List[Dict[str, Any]]] = {}

    # ----------------------------
    # Conservative therapy weeks (STRICTLY therapy-linked)
    # ----------------------------
    # Only extract therapy duration if a duration is explicitly attached to therapy context.
    # This prevents symptom duration ("pain x 8 weeks") from being misread as PT duration.
    therapy_weeks: Optional[int] = None

    THERAPY_CONTEXT = r"(pt|physical therapy|nsaids?|anti-?inflammator(?:y|ies)|activity modification|home exercise|hep|chiropractic|chiro)"

    # Pattern A: "PT x 8 weeks" / "PT for 8 weeks" / "NSAIDs for 6 weeks"
    m_therapy_after = re.search(rf"\b{THERAPY_CONTEXT}\b(?:\s*(?:x|for|over|about)\s*)\b(\d+)\s*(week|weeks)\b", t)
    if m_therapy_after:
        # Grouping note: THERAPY_CONTEXT is capturing => digits are group(2)
        try:
            therapy_weeks = int(m_therapy_after.group(2))
        except Exception:
            therapy_weeks = None

        if therapy_weeks is not None:
            _add_span(
                evidence,
                "conservative_therapy_weeks",
                m_therapy_after.start(),
                m_therapy_after.end(),
                raw[m_therapy_after.start() : m_therapy_after.end()],
            )

    # Pattern B: "8 weeks of PT" / "6 weeks of physical therapy"
    if therapy_weeks is None:
        m_therapy_before = re.search(rf"\b(\d+)\s*(week|weeks)\b\s+of\s+\b{THERAPY_CONTEXT}\b", t)
        if m_therapy_before:
            try:
                therapy_weeks = int(m_therapy_before.group(1))
            except Exception:
                therapy_weeks = None

            if therapy_weeks is not None:
                _add_span(
                    evidence,
                    "conservative_therapy_weeks",
                    m_therapy_before.start(),
                    m_therapy_before.end(),
                    raw[m_therapy_before.start() : m_therapy_before.end()],
                )

    # ----------------------------
    # Symptom duration (weeks)
    # ----------------------------
    symptom_weeks: Optional[int] = None

    m_months = re.search(r"\b(\d+)\s*(month|months)\b", t)
    if m_months:
        symptom_weeks = int(m_months.group(1)) * 4
        _add_span(
            evidence,
            "symptom_duration_weeks",
            m_months.start(),
            m_months.end(),
            raw[m_months.start() : m_months.end()],
        )
    else:
        m_weeks = re.search(r"\b(\d+)\s*(week|weeks)\b", t)
        if m_weeks:
            symptom_weeks = int(m_weeks.group(1))
            _add_span(
                evidence,
                "symptom_duration_weeks",
                m_weeks.start(),
                m_weeks.end(),
                raw[m_weeks.start() : m_weeks.end()],
            )

    # ----------------------------
    # Neuro deficit / red flags addressed
    # ----------------------------
    # We store:
    #   neuro_red_flags_documented: True if addressed (present OR explicitly denied), else None
    #
    # NOTE: This is "addressed", not "present". Presence/absence belongs to a different field if needed later.
    denial_patterns = [
        r"\bdenies\b.*\b(weakness|numbness|bowel|bladder|bowel/bladder|saddle anesthesia|foot drop|urinary retention|incontinence)\b",
        r"\bno\b.*\b(weakness|numbness|bowel|bladder|bowel/bladder|saddle anesthesia|foot drop|urinary retention|incontinence)\b",
        r"\bweakness\b.*\b(absent|denied|none)\b",
        r"\bbowel/bladder\b.*\b(intact|normal|denied|no changes)\b",
        r"\bno\b\s+\bsaddle anesthesia\b",
        r"\bbowel\b/\bbladder\b.*\b(no changes|intact|normal|denied)\b",
    ]

    positive_patterns = [
        r"\breports\b.*\b(weakness|urinary retention|bowel incontinence|bladder incontinence|saddle anesthesia|foot drop|numbness)\b",
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
        neuro_documented: Optional[bool] = True
        _add_span(
            evidence,
            "neuro_red_flags_documented",
            positive_match.start(),
            positive_match.end(),
            raw[positive_match.start() : positive_match.end()],
        )
    elif denial_match:
        neuro_documented = True
        _add_span(
            evidence,
            "neuro_red_flags_documented",
            denial_match.start(),
            denial_match.end(),
            raw[denial_match.start() : denial_match.end()],
        )
    else:
        neuro_documented = None

    # ----------------------------
    # Prior imaging result
    # ----------------------------
    prior_imaging: Optional[str] = None

    # Explicit "no imaging"
    m_no_img = re.search(r"\bno (prior )?imaging( documented| yet| to date)?\b", t)
    if m_no_img:
        prior_imaging = "none"
        _add_span(
            evidence,
            "prior_imaging_result",
            m_no_img.start(),
            m_no_img.end(),
            raw[m_no_img.start() : m_no_img.end()],
        )
    else:
        # Accept "prior imaging performed" / "imaging noted" even without modality/result
        m_any_img = re.search(r"\b(prior )?imaging\b", t)
        m_mod = re.search(r"\b(x-?ray|xray|ct|mri)\b", t)

        # If they explicitly say unclear/unknown findings, count as inconclusive (documented)
        m_unclear = re.search(r"\b(findings|result|results)\b.*\b(unclear|unknown|not clear|not specified|indeterminate)\b", t)

        if m_unclear and (m_any_img or m_mod):
            prior_imaging = "inconclusive"
            if m_mod:
                start, end, text = _combined_span_text(raw, m_mod, m_unclear)
                _add_span(evidence, "prior_imaging_result", start, end, text)
            else:
                _add_span(
                    evidence,
                    "prior_imaging_result",
                    m_unclear.start(),
                    m_unclear.end(),
                    raw[m_unclear.start() : m_unclear.end()],
                )

        elif m_mod or m_any_img:
            # Normal/negation => inconclusive
            m_norm = re.search(r"\b(no abnormalities|no abnormal|no acute findings|normal|unremarkable)\b", t)
            if m_norm:
                prior_imaging = "inconclusive"
                if m_mod:
                    start, end, text = _combined_span_text(raw, m_mod, m_norm)
                    _add_span(evidence, "prior_imaging_result", start, end, text)
                else:
                    _add_span(
                        evidence,
                        "prior_imaging_result",
                        m_norm.start(),
                        m_norm.end(),
                        raw[m_norm.start() : m_norm.end()],
                    )
            else:
                m_abn = re.search(r"\b(abnormal|herniat|stenosis|disc bulge|fracture|degenerative)\b", t)
                if m_abn:
                    prior_imaging = "abnormal"
                    _add_span(
                        evidence,
                        "prior_imaging_result",
                        m_abn.start(),
                        m_abn.end(),
                        raw[m_abn.start() : m_abn.end()],
                    )
                else:
                    # Imaging referenced but result not specified => documented as inconclusive
                    prior_imaging = "inconclusive"
                    m_span = m_mod or m_any_img
                    _add_span(
                        evidence,
                        "prior_imaging_result",
                        m_span.start(),
                        m_span.end(),
                        raw[m_span.start() : m_span.end()],
                    )

    # ----------------------------
    # Mechanical symptoms addressed
    # ----------------------------
    # This field is used for the narrow knee MRI pathway.
    # Semantics:
    #   True  -> explicit positive symptom wording (locking/catching/buckling/etc.)
    #   False -> explicit denial / absence wording
    #   None  -> not addressed explicitly
    mechanical_symptoms_documented: Optional[bool] = None

    mechanical_denial_patterns = [
        r"\bdenies\b.*\b(locking|catching|buckling|giving way|instability)\b",
        r"\bno\b.*\b(locking|catching|buckling|giving way|instability)\b",
        r"\bwithout\b.*\b(locking|catching|buckling|giving way|instability)\b",
    ]
    mechanical_positive_patterns = [
        r"\b(reports|reported|endorses|notes|noted|describes|described|with)\b.*\b(locking|catching|buckling|giving way|instability)\b",
        r"\bmechanical symptoms\b",
    ]

    mechanical_denial_match = None
    for pat in mechanical_denial_patterns:
        mm = re.search(pat, t)
        if mm:
            mechanical_denial_match = mm
            break

    mechanical_positive_match = None
    for pat in mechanical_positive_patterns:
        mm = re.search(pat, t)
        if mm:
            text = raw[mm.start() : mm.end()].lower()
            if not any(token in text for token in ("denies", "no ", "without")):
                mechanical_positive_match = mm
                break

    if mechanical_positive_match:
        mechanical_symptoms_documented = True
        _add_span(
            evidence,
            "mechanical_symptoms_documented",
            mechanical_positive_match.start(),
            mechanical_positive_match.end(),
            raw[mechanical_positive_match.start() : mechanical_positive_match.end()],
        )
    elif mechanical_denial_match:
        mechanical_symptoms_documented = False
        _add_span(
            evidence,
            "mechanical_symptoms_documented",
            mechanical_denial_match.start(),
            mechanical_denial_match.end(),
            raw[mechanical_denial_match.start() : mechanical_denial_match.end()],
        )

    # ----------------------------
    # OSA diagnosis
    # ----------------------------
    osa_dx: Optional[bool] = None
    m_osa = re.search(r"\b(obstructive sleep apnea|osa)\b", t)
    if m_osa:
        osa_dx = True
        _add_span(evidence, "osa_diagnosis", m_osa.start(), m_osa.end(), raw[m_osa.start() : m_osa.end()])

    # ----------------------------
    # Sleep study date (context-gated)
    # ----------------------------
    sleep_study_date: Optional[bool] = None

    date_iter = list(re.finditer(r"\b(20\d{2}|19\d{2})[-/]\d{1,2}[-/]\d{1,2}\b", t))
    SLEEP_CTX = re.compile(r"\b(sleep study|polysomnography|psg|hst|home sleep test)\b")

    for m_date in date_iter:
        window_start = max(0, m_date.start() - 80)
        window_end = min(len(t), m_date.end() + 80)
        window = t[window_start:window_end]

        if SLEEP_CTX.search(window):
            sleep_study_date = True
            _add_span(evidence, "sleep_study_date", m_date.start(), m_date.end(), raw[m_date.start() : m_date.end()])
            break

    # ----------------------------
    # AHI / RDI documented (must have numeric value OR explicit missingness)
    # ----------------------------
    ahi_doc: Optional[bool] = None

    m_ahi_missing = re.search(r"\b(ahi|rdi)\b.*\b(not documented|not stated|not available|unknown|n/?a|missing)\b", t)
    if m_ahi_missing:
        ahi_doc = None
        _add_span(
            evidence,
            "ahi_documented",
            m_ahi_missing.start(),
            m_ahi_missing.end(),
            raw[m_ahi_missing.start() : m_ahi_missing.end()],
        )
    else:
        m_ahi_val = re.search(r"\b(ahi|rdi)\b\s*[:=]?\s*(\d+(\.\d+)?)\b", t)
        if m_ahi_val:
            ahi_doc = True
            _add_span(
                evidence,
                "ahi_documented",
                m_ahi_val.start(),
                m_ahi_val.end(),
                raw[m_ahi_val.start() : m_ahi_val.end()],
            )

    facts: Dict[str, Any] = {
        "conservative_therapy_weeks": therapy_weeks,
        "neuro_red_flags_documented": neuro_documented,
        "prior_imaging_result": prior_imaging,
        "symptom_duration_weeks": symptom_weeks,
        "mechanical_symptoms_documented": mechanical_symptoms_documented,
        "osa_diagnosis": osa_dx,
        "sleep_study_date": sleep_study_date,
        "ahi_documented": ahi_doc,
    }

    return facts, _dedup_spans(evidence)
