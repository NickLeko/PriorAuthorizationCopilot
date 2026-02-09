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


def _months_to_weeks(months: int) -> int:
    # Conservative, deterministic normalization
    return int(months) * 4


def _extract_duration_weeks(
    raw: str,
    lowered: str,
    *,
    context_regex: Optional[re.Pattern] = None,
) -> Tuple[Optional[int], Optional[Tuple[int, int]]]:
    """
    Extract a duration expressed in weeks or months.
    If context_regex is provided, require context to exist in a proximity window.

    Returns:
      (duration_weeks_or_none, (start,end)_span_or_none)
    """
    # Find candidate durations (months first is NOT enough; we want max across all candidates)
    candidates: List[Tuple[int, int, int]] = []  # (weeks_value, start, end)

    for m in re.finditer(r"\b(\d+)\s*(month|months)\b", lowered):
        months = int(m.group(1))
        weeks = _months_to_weeks(months)
        candidates.append((weeks, m.start(), m.end()))

    for m in re.finditer(r"\b(\d+)\s*(week|weeks)\b", lowered):
        weeks = int(m.group(1))
        candidates.append((weeks, m.start(), m.end()))

    if not candidates:
        return None, None

    # If context-gated, keep only candidates with context nearby
    if context_regex is not None:
        gated: List[Tuple[int, int, int]] = []
        for weeks, start, end in candidates:
            window_start = max(0, start - 80)
            window_end = min(len(lowered), end + 80)
            window = lowered[window_start:window_end]
            if context_regex.search(window):
                gated.append((weeks, start, end))
        candidates = gated

    if not candidates:
        return None, None

    # If multiple durations exist, maximum wins (per contract)
    weeks, start, end = max(candidates, key=lambda x: x[0])
    return weeks, (start, end)


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
    # Conservative therapy weeks (context-gated)
    # ----------------------------
    # Contract: duration extracted ONLY if therapy context exists; normalize months->weeks; max duration wins.
    THERAPY_CTX = re.compile(r"\b(pt|physical therapy|nsaid|nsaids|anti-?inflammator(y|ies)|activity modification|home exercise|hep|chiropractic|chiro)\b")

    therapy_weeks, span = _extract_duration_weeks(raw, t, context_regex=THERAPY_CTX)
    if therapy_weeks is not None and span is not None:
        _add_span(evidence, "conservative_therapy_weeks", span[0], span[1], raw[span[0]: span[1]])

    # ----------------------------
    # Symptom duration (weeks) (symptom-context gated to avoid noise like pregnancy)
    # ----------------------------
    # Contract: explicit duration tied to symptoms. We apply a lightweight context gate.
    SYMPTOM_CTX = re.compile(r"\b(back pain|low back pain|pain|symptom|radiculopathy|sciatica|leg pain|neck pain)\b")

    symptom_weeks, span = _extract_duration_weeks(raw, t, context_regex=SYMPTOM_CTX)
    if symptom_weeks is not None and span is not None:
        _add_span(evidence, "symptom_duration_weeks", span[0], span[1], raw[span[0]: span[1]])

    # ----------------------------
    # Neuro deficit / red flags
    # ----------------------------
    # Outputs:
    #   neuro_deficit_or_red_flags: True/False/None
    #   neuro_red_flags_documented: True/None  (True if explicitly addressed, None if not mentioned)
    #
    # IMPORTANT (contract alignment):
    # - Meta phrases like "no red flags documented" => NOT_DOCUMENTED (do NOT treat as a denial).
    #
    # We treat "denies ..." and explicit "no weakness/bowel/bladder..." as addressed denials.
    # We treat explicit positives as present.
    #
    m_meta = re.search(r"\bno red flags documented\b", t)
    if m_meta:
        neuro_present: Optional[bool] = None
        neuro_documented: Optional[bool] = None
        # Capture as evidence of documentation gap (missingness signal)
        _add_span(
            evidence,
            "neuro_red_flags_documented",
            m_meta.start(),
            m_meta.end(),
            raw[m_meta.start(): m_meta.end()],
        )
    else:
        denial_patterns = [
            r"\bdenies\b.*\b(weakness|bowel|bladder|saddle anesthesia|foot drop|urinary retention)\b",
            r"\bno\b.*\b(weakness|bowel|bladder|saddle anesthesia|foot drop|urinary retention)\b",
            r"\bbowel/bladder\b.*\bdenied\b",
            r"\bweakness\b.*\b(absent|denied)\b",
            r"\bbowel/bladder\b.*\b(intact|normal)\b",
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
            neuro_present = True
            neuro_documented = True
            _add_span(
                evidence,
                "neuro_red_flags_documented",
                positive_match.start(),
                positive_match.end(),
                raw[positive_match.start(): positive_match.end()],
            )
        elif denial_match:
            neuro_present = False
            neuro_documented = True
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
    # Prior imaging result
    # ----------------------------
    prior_imaging: Optional[str] = None

    # Explicit "no imaging" should be "none"
    m_no_img = re.search(r"\bno (prior )?imaging( documented| yet| to date)?\b", t)
    if m_no_img:
        prior_imaging = "none"
        _add_span(evidence, "prior_imaging_result", m_no_img.start(), m_no_img.end(), raw[m_no_img.start(): m_no_img.end()])
    else:
        # If any modality mentioned, infer result category
        m_mod = re.search(r"\b(x-?ray|xray|ct|mri|imaging)\b", t)
        if m_mod:
            # Normal/negation first => treat as inconclusive for escalation logic
            m_norm = re.search(r"\b(no abnormalities|no abnormal|no acute findings|normal|unremarkable)\b", t)
            if m_norm:
                prior_imaging = "inconclusive"
                _add_span(evidence, "prior_imaging_result", m_norm.start(), m_norm.end(), raw[m_norm.start(): m_norm.end()])
            else:
                m_abn = re.search(r"\b(abnormal|herniat|stenosis|disc bulge|fracture|degenerative)\b", t)
                if m_abn:
                    prior_imaging = "abnormal"
                    _add_span(evidence, "prior_imaging_result", m_abn.start(), m_abn.end(), raw[m_abn.start(): m_abn.end()])
                else:
                    # modality mentioned but unclear
                    prior_imaging = "inconclusive"
                    _add_span(evidence, "prior_imaging_result", m_mod.start(), m_mod.end(), raw[m_mod.start(): m_mod.end()])

    # ----------------------------
    # OSA diagnosis
    # ----------------------------
    osa_dx: Optional[bool] = None
    m_osa = re.search(r"\b(obstructive sleep apnea|osa)\b", t)
    if m_osa:
        osa_dx = True
        _add_span(evidence, "osa_diagnosis", m_osa.start(), m_osa.end(), raw[m_osa.start(): m_osa.end()])

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
            _add_span(
                evidence,
                "sleep_study_date",
                m_date.start(),
                m_date.end(),
                raw[m_date.start(): m_date.end()],
            )
            break

    # ----------------------------
    # AHI / RDI documented (must have numeric value; missingness aware)
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
            raw[m_ahi_missing.start(): m_ahi_missing.end()],
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
                raw[m_ahi_val.start(): m_ahi_val.end()],
            )
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
