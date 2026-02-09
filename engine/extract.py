from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


def _add_span(
    evidence: Dict[str, List[Dict[str, Any]]],
    key: str,
    start: int,
    end: int,
    text: str,
) -> None:
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


def _ensure_all_keys(
    evidence: Dict[str, List[Dict[str, Any]]],
    keys: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    for k in keys:
        evidence.setdefault(k, [])
    return evidence


def _find_duration_near_context(
    t: str,
    context_pat: re.Pattern,
    raw: str,
    key: str,
    evidence: Dict[str, List[Dict[str, Any]]],
    *,
    window: int = 80,
) -> Optional[int]:
    """
    Find a duration (weeks/months) near a context hit.
    Returns weeks as int.
    """
    for m_ctx in context_pat.finditer(t):
        ws = max(0, m_ctx.start() - window)
        we = min(len(t), m_ctx.end() + window)
        chunk = t[ws:we]

        m_months = re.search(r"\b(\d+)\s*(month|months)\b", chunk)
        if m_months:
            weeks = int(m_months.group(1)) * 4
            # Map span to original indices
            start = ws + m_months.start()
            end = ws + m_months.end()
            _add_span(evidence, key, start, end, raw[start:end])
            return weeks

        m_weeks = re.search(r"\b(\d+)\s*(week|weeks)\b", chunk)
        if m_weeks:
            weeks = int(m_weeks.group(1))
            start = ws + m_weeks.start()
            end = ws + m_weeks.end()
            _add_span(evidence, key, start, end, raw[start:end])
            return weeks

    return None


def extract_facts(note_text: str) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    """
    Deterministic extraction for MVP.

    Returns:
      facts: Dict[str, Any]
      evidence_map: Dict[key -> List[{start,end,text}]]

    Design:
      - Conservative: if not explicitly documented, use None (unknown) where appropriate.
      - Evidence is captured as spans from the original note text.
      - Evidence map is schema-stable: every expected key exists (possibly empty list).
    """
    raw = note_text or ""
    t = raw.lower()

    evidence: Dict[str, List[Dict[str, Any]]] = {}

    # ----------------------------
    # Conservative therapy weeks (context-gated)
    # ----------------------------
    therapy_weeks: Optional[int] = None
    THERAPY_CTX = re.compile(r"\b(pt|physical therapy|nsaid|activity modification|home exercise|hep|chiropractic|chiro)\b")

    # Look near therapy context, take the MAX duration if multiple are present.
    durations: List[int] = []
    for m_ctx in THERAPY_CTX.finditer(t):
        ws = max(0, m_ctx.start() - 80)
        we = min(len(t), m_ctx.end() + 120)
        chunk = t[ws:we]

        m_months = re.search(r"\b(\d+)\s*(month|months)\b", chunk)
        if m_months:
            w = int(m_months.group(1)) * 4
            start = ws + m_months.start()
            end = ws + m_months.end()
            _add_span(evidence, "conservative_therapy_weeks", start, end, raw[start:end])
            durations.append(w)

        m_weeks = re.search(r"\b(\d+)\s*(week|weeks)\b", chunk)
        if m_weeks:
            w = int(m_weeks.group(1))
            start = ws + m_weeks.start()
            end = ws + m_weeks.end()
            _add_span(evidence, "conservative_therapy_weeks", start, end, raw[start:end])
            durations.append(w)

    if durations:
        therapy_weeks = max(durations)

    # ----------------------------
    # Symptom duration (weeks) — context-gated to symptom/pain, avoids unrelated “weeks”
    # ----------------------------
    symptom_weeks: Optional[int] = None
    SYMPTOM_CTX = re.compile(r"\b(back pain|low back pain|pain|radiculopathy|symptom|symptoms)\b")
    symptom_weeks = _find_duration_near_context(
        t,
        SYMPTOM_CTX,
        raw,
        "symptom_duration_weeks",
        evidence,
        window=90,
    )

    # ----------------------------
    # Neuro red flags explicitly addressed (present OR denied) => bool|None
    # ----------------------------
    denial_patterns = [
        r"\bdenies\b.*\b(weakness|bowel|bladder|saddle anesthesia|foot drop|urinary retention)\b",
        r"\bno\b.*\b(weakness|bowel|bladder|saddle anesthesia|foot drop|urinary retention)\b",
        r"\bweakness\b\s*absent\b",
        r"\bbowel/bladder\b.*\b(denied|intact)\b",
        r"\bbowel\b.*\bbladder\b.*\b(intact|no changes|denied)\b",
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
            raw[positive_match.start(): positive_match.end()],
        )
    elif denial_match:
        neuro_present = False
        neuro_documented = True  # addressed (denied)
        _add_span(
            evidence,
            "neuro_red_flags_documented",
            denial_match.start(),
            denial_match.end(),
            raw[denial_match.start(): denial_match.end()],
        )
    else:
        neuro_present = None
        neuro_documented = None

    # ----------------------------
    # Prior imaging result: none | inconclusive | abnormal | null
    # ----------------------------
    prior_imaging: Optional[str] = None

    m_no_img = re.search(r"\bno (prior )?imaging( documented| yet| to date)?\b", t)
    if m_no_img:
        prior_imaging = "none"
        _add_span(evidence, "prior_imaging_result", m_no_img.start(), m_no_img.end(), raw[m_no_img.start(): m_no_img.end()])
    else:
        # Look for modality, then classify based on local neighborhood around modality mention.
        m_mod = re.search(r"\b(x-?ray|xray|ct|mri)\b", t)
        if m_mod:
            ws = max(0, m_mod.start() - 60)
            we = min(len(t), m_mod.end() + 160)
            chunk = t[ws:we]

            m_norm = re.search(r"\b(no abnormalities|no abnormal|no acute findings|normal|unremarkable)\b", chunk)
            if m_norm:
                prior_imaging = "inconclusive"
                start = ws + m_norm.start()
                end = ws + m_norm.end()
                _add_span(evidence, "prior_imaging_result", start, end, raw[start:end])
            else:
                m_abn = re.search(r"\b(abnormal|herniat|stenosis|disc bulge|fracture|degenerative)\b", chunk)
                if m_abn:
                    prior_imaging = "abnormal"
                    start = ws + m_abn.start()
                    end = ws + m_abn.end()
                    _add_span(evidence, "prior_imaging_result", start, end, raw[start:end])
                else:
                    prior_imaging = "inconclusive"
                    _add_span(evidence, "prior_imaging_result", m_mod.start(), m_mod.end(), raw[m_mod.start(): m_mod.end()])

    # ----------------------------
    # OSA diagnosis documented (presence-only)
    # ----------------------------
    osa_dx: Optional[bool] = None
    m_osa = re.search(r"\b(obstructive sleep apnea|osa)\b", t)
    if m_osa:
        osa_dx = True
        _add_span(evidence, "osa_diagnosis", m_osa.start(), m_osa.end(), raw[m_osa.start(): m_osa.end()])

    # ----------------------------
    # Sleep study date documented (context-gated)
    # ----------------------------
    sleep_study_date: Optional[bool] = None
    date_iter = list(re.finditer(r"\b(20\d{2}|19\d{2})[-/]\d{1,2}[-/]\d{1,2}\b", t))
    SLEEP_CTX = re.compile(r"\b(sleep study|polysomnography|psg|hst|home sleep test)\b")

    for m_date in date_iter:
        ws = max(0, m_date.start() - 80)
        we = min(len(t), m_date.end() + 80)
        window = t[ws:we]
        if SLEEP_CTX.search(window):
            sleep_study_date = True
            _add_span(evidence, "sleep_study_date", m_date.start(), m_date.end(), raw[m_date.start(): m_date.end()])
            break

    # ----------------------------
    # AHI/RDI documented: value required (presence-only for MVP)
    # ----------------------------
    ahi_doc: Optional[bool] = None

    # Explicit missingness
    m_ahi_missing = re.search(r"\b(ahi|rdi)\b.*\b(not documented|not stated|not available|unknown|n/?a|missing)\b", t)
    if m_ahi_missing:
        ahi_doc = None
        _add_span(evidence, "ahi_documented", m_ahi_missing.start(), m_ahi_missing.end(), raw[m_ahi_missing.start(): m_ahi_missing.end()])
    else:
        m_ahi_val = re.search(r"\b(ahi|rdi)\b\s*[:=]?\s*(\d+(\.\d+)?)\b", t)
        if m_ahi_val:
            ahi_doc = True
            _add_span(evidence, "ahi_documented", m_ahi_val.start(), m_ahi_val.end(), raw[m_ahi_val.start(): m_ahi_val.end()])

    facts: Dict[str, Any] = {
        "conservative_therapy_weeks": therapy_weeks,
        "neuro_deficit_or_red_flags": neuro_present,
        "neuro_red_flags_documented": neuro_documented,  # True if addressed; None if not mentioned
        "prior_imaging_result": prior_imaging,
        "symptom_duration_weeks": symptom_weeks,
        "osa_diagnosis": osa_dx,
        "sleep_study_date": sleep_study_date,
        "ahi_documented": ahi_doc,
    }

    # Evidence map keys must always exist (schema-stable)
    expected_keys = list(facts.keys())
    evidence = _ensure_all_keys(evidence, expected_keys)

    return facts, _dedup_spans(evidence)
