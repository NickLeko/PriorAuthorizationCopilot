from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

THERAPY_CONTEXT = r"(?:pt|physical therapy|nsaids?|anti-?inflammator(?:y|ies)|activity modification|home exercise|hep|chiropractic|chiro)"
THERAPY_AFTER_RE = re.compile(rf"\b{THERAPY_CONTEXT}\b(?:\s*(?:x|for|over|about)\s*)\b(?P<value>\d+)\s*(?:week|weeks)\b")
THERAPY_BEFORE_RE = re.compile(rf"\b(?P<value>\d+)\s*(?:week|weeks)\b\s+of\s+\b{THERAPY_CONTEXT}\b")
THERAPY_DURATION_CONTEXT_RE = re.compile(
    rf"(?:\b{THERAPY_CONTEXT}\b(?:\s*(?:x|for|over|about)\s*)\b\d+\s*(?:week|weeks|month|months)\b)"
    rf"|(?:\b\d+\s*(?:week|weeks|month|months)\b\s+of\s+\b{THERAPY_CONTEXT}\b)"
)
THERAPY_CONTEXT_RE = re.compile(rf"\b{THERAPY_CONTEXT}\b")
CPB_0236_THERAPY_CONTEXT = r"(?:moderate activity|analgesics?|nsaids?|anti-?inflammator(?:y|ies)|muscle relaxants?)"
CPB_0236_THERAPY_AFTER_RE = re.compile(rf"\b{CPB_0236_THERAPY_CONTEXT}\b(?:\s*(?:x|for|over|about)\s*)\b(?P<value>\d+)\s*(?:week|weeks)\b")
CPB_0236_THERAPY_BEFORE_RE = re.compile(rf"\b(?P<value>\d+)\s*(?:week|weeks)\b\s+of\s+\b{CPB_0236_THERAPY_CONTEXT}\b")
CPB_0236_THERAPY_CONTEXT_RE = re.compile(rf"\b{CPB_0236_THERAPY_CONTEXT}\b")
SYMPTOM_CONTEXT = r"(?:symptoms?|(?:low\s+)?back pain|neck pain|cervical pain|knee pain|radicular pain|radiculopathy|pain)"
SYMPTOM_DURATION_AFTER_RE = re.compile(rf"\b{SYMPTOM_CONTEXT}\b[^.!?;\n]{{0,60}}?\b(?P<value>\d+)\s*(?P<unit>week|weeks|month|months)\b")
SYMPTOM_DURATION_BEFORE_RE = re.compile(rf"\b(?P<value>\d+)\s*(?P<unit>week|weeks|month|months)\b\s+(?:of\s+)?\b{SYMPTOM_CONTEXT}\b")
IMAGING_CONTEXT_RE = re.compile(r"\b(?:(?:prior\s+)?imaging|x-?ray|xray|ct|mri)\b")
BACK_PAIN_RE = re.compile(r"\b(?:low\s+)?back pain\b")
RADICULOPATHY_RE = re.compile(r"\b(?:lumbar\s+)?radiculopathy\b|\bradicular (?:back )?pain\b")
ROOT_DISTRIBUTION_RE = re.compile(r"\b(?:l[1-5]|s[1-5])(?:\s+(?:nerve\s+)?root)?\s+distribution\b|\bnerve[- ]root distribution\b")

THERAPY_NEGATION_PATTERNS = [
    r"\bdenies\b",
    r"\bdenied\b",
    r"\bhas not\b",
    r"\bdid not\b",
    r"\bunable to complete\b",
    r"\bdeclined\b",
    r"\brefused\b",
    r"\bno\s+(?:conservative therapy|pt|physical therapy|nsaids?|anti-?inflammator(?:y|ies)|home exercise|hep|chiropractic|chiro)\b",
]
THERAPY_FUTURE_LOOKBACK_PATTERNS = [
    r"\bwill start\b",
    r"\bplan to\b",
    r"\bplans to\b",
    r"\bplan\s*:",
    r"\bscheduled for\b",
    r"\bto begin\b",
    r"\bupcoming\b",
    r"\breferral placed\b",
    r"\bordered\b",
    r"\brecommended\b",
]
THERAPY_FUTURE_AFTER_PATTERNS = [
    r"\bnext (?:week|month)\b",
    r"\bto begin\b",
    r"\bupcoming\b",
    r"\bstarting\b",
]
SENTENCE_BOUNDARY_CHARS = ".!?\n;"


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


def _bounded_context_before(text: str, start: int, max_chars: int = 80) -> str:
    lower = max(0, start - max_chars)
    boundary = max(text.rfind(ch, lower, start) for ch in SENTENCE_BOUNDARY_CHARS)
    if boundary >= 0:
        lower = boundary + 1
    return text[lower:start]


def _bounded_context_after(text: str, end: int, max_chars: int = 80) -> str:
    upper = min(len(text), end + max_chars)
    boundaries = [text.find(ch, end, upper) for ch in SENTENCE_BOUNDARY_CHARS]
    boundaries = [idx for idx in boundaries if idx >= 0]
    if boundaries:
        upper = min(boundaries)
    return text[end:upper]


def _has_pattern(patterns: List[str], text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _sentence_spans(text: str) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    start = 0
    for boundary in re.finditer(r"[.!?;\n]+", text):
        end = boundary.start()
        if text[start:end].strip():
            left_trim = len(text[start:end]) - len(text[start:end].lstrip())
            right_trim = len(text[start:end].rstrip())
            spans.append((start + left_trim, start + right_trim))
        start = boundary.end()
    if text[start:].strip():
        left_trim = len(text[start:]) - len(text[start:].lstrip())
        spans.append((start + left_trim, len(text.rstrip())))
    return spans


def _therapy_duration_is_disqualified(text: str, match: re.Match[str]) -> bool:
    before = _bounded_context_before(text, match.start())
    matched = text[match.start() : match.end()]
    after = _bounded_context_after(text, match.end())

    if _has_pattern(THERAPY_NEGATION_PATTERNS, before + matched):
        return True
    if _has_pattern(THERAPY_FUTURE_LOOKBACK_PATTERNS, before):
        return True
    if _has_pattern(THERAPY_FUTURE_AFTER_PATTERNS, matched + after):
        return True
    return False


def _osa_mention_is_negated(text: str, match: re.Match[str]) -> bool:
    before = _bounded_context_before(text, match.start(), max_chars=48)
    after = _bounded_context_after(text, match.end(), max_chars=32)

    return bool(
        re.search(
            r"\b(?:"
            r"no(?:\s+(?:evidence|diagnosis)\s+of)?|"
            r"denies?(?:\s+(?:having|history\s+of))?|"
            r"without(?:\s+evidence\s+of)?|"
            r"(?:does|do|did)\s+not\s+have|"
            r"has\s+no|negative\s+for|rule(?:d)?\s+out"
            r")\s+$",
            before,
        )
        or re.match(r"^\s+(?:is\s+)?(?:ruled out|absent|negative|not present)\b", after)
    )


def _finding_is_negated(text: str, match: re.Match[str]) -> bool:
    before = text[max(0, match.start() - 40) : match.start()]
    after = text[match.end() : min(len(text), match.end() + 24)]
    return bool(
        re.search(
            r"\b(?:no|denies?|without|negative\s+for|free\s+of|absence\s+of)\s+"
            r"(?:evidence\s+of\s+)?(?:acute\s+)?$",
            before,
        )
        or re.match(r"^\s+(?:is\s+)?(?:absent|negative|not present|ruled out)\b", after)
    )


def _duration_is_in_therapy_context(text: str, start: int, end: int) -> bool:
    window_start = max(0, start - 80)
    window_end = min(len(text), end + 80)
    window = text[window_start:window_end]
    rel_start = start - window_start
    rel_end = end - window_start

    for match in THERAPY_DURATION_CONTEXT_RE.finditer(window):
        if match.start() <= rel_start and match.end() >= rel_end:
            return True

    before = _bounded_context_before(text, start)
    near_before = _bounded_context_before(text, start, max_chars=40)
    if THERAPY_CONTEXT_RE.search(before) and _has_pattern(THERAPY_FUTURE_LOOKBACK_PATTERNS, before):
        return True
    if THERAPY_CONTEXT_RE.search(near_before) and re.search(
        r"\b(completed|complete|trialed|tried|finished|course|duration|total|ordered)\b", near_before
    ):
        return True
    return False


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

    # Pattern A: "PT x 8 weeks" / "PT for 8 weeks" / "NSAIDs for 6 weeks"
    m_therapy_after = None
    for candidate in THERAPY_AFTER_RE.finditer(t):
        if _therapy_duration_is_disqualified(t, candidate):
            continue
        m_therapy_after = candidate
        break

    if m_therapy_after:
        try:
            therapy_weeks = int(m_therapy_after.group("value"))
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
        m_therapy_before = None
        for candidate in THERAPY_BEFORE_RE.finditer(t):
            if _therapy_duration_is_disqualified(t, candidate):
                continue
            m_therapy_before = candidate
            break

        if m_therapy_before:
            try:
                therapy_weeks = int(m_therapy_before.group("value"))
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

    cpb_0236_therapy_weeks: Optional[int] = None
    cpb_0236_duration_matches = [
        candidate
        for pattern in (CPB_0236_THERAPY_AFTER_RE, CPB_0236_THERAPY_BEFORE_RE)
        for candidate in pattern.finditer(t)
        if not _therapy_duration_is_disqualified(t, candidate)
    ]
    cpb_0236_duration_match = max(
        cpb_0236_duration_matches,
        key=lambda candidate: int(candidate.group("value")),
        default=None,
    )
    if cpb_0236_duration_match is not None:
        cpb_0236_therapy_weeks = int(cpb_0236_duration_match.group("value"))
        _add_span(
            evidence,
            "cpb_0236_conservative_therapy_weeks",
            cpb_0236_duration_match.start(),
            cpb_0236_duration_match.end(),
            raw[cpb_0236_duration_match.start() : cpb_0236_duration_match.end()],
        )

    # ----------------------------
    # Conservative therapy response (explicit non-response only)
    # ----------------------------
    cpb_0236_therapy_no_improvement: Optional[bool] = None
    for sentence_start, sentence_end in _sentence_spans(t):
        sentence = t[sentence_start:sentence_end]
        if not CPB_0236_THERAPY_CONTEXT_RE.search(sentence):
            continue
        if _has_pattern(THERAPY_FUTURE_LOOKBACK_PATTERNS + THERAPY_FUTURE_AFTER_PATTERNS, sentence):
            continue

        nonresponse = re.search(
            r"\b(?:no|minimal|little|insufficient)\s+(?:meaningful\s+)?(?:improvement|relief|response)\b"
            r"|\bwithout\s+(?:meaningful\s+)?(?:improvement|relief)\b"
            r"|\bfailed to (?:improve|respond)\b",
            sentence,
        )
        response = re.search(
            r"\b(?:substantial|significant|meaningful|good)\s+(?:improvement|relief|response)\b"
            r"|\bsymptoms? resolved\b",
            sentence,
        )
        if nonresponse:
            cpb_0236_therapy_no_improvement = True
        elif response:
            cpb_0236_therapy_no_improvement = False
        else:
            continue

        _add_span(
            evidence,
            "cpb_0236_conservative_therapy_no_improvement",
            sentence_start,
            sentence_end,
            raw[sentence_start:sentence_end],
        )
        break

    # ----------------------------
    # Official lumbar-radiculopathy branch facts
    # ----------------------------
    back_pain_with_radiculopathy: Optional[bool] = None
    for sentence_start, sentence_end in _sentence_spans(t):
        sentence = t[sentence_start:sentence_end]
        back_pain_match = BACK_PAIN_RE.search(sentence)
        radiculopathy_match = RADICULOPATHY_RE.search(sentence)
        if back_pain_match is None or radiculopathy_match is None:
            continue

        back_pain_with_radiculopathy = not (
            _finding_is_negated(sentence, back_pain_match) or _finding_is_negated(sentence, radiculopathy_match)
        )
        _add_span(
            evidence,
            "back_pain_with_radiculopathy",
            sentence_start,
            sentence_end,
            raw[sentence_start:sentence_end],
        )
        break

    objective_motor_or_reflex_change: Optional[bool] = None
    for sentence_start, sentence_end in _sentence_spans(t):
        sentence = t[sentence_start:sentence_end]
        if ROOT_DISTRIBUTION_RE.search(sentence) is None:
            continue

        strength = re.search(r"\bstrength\s*(?:is|of|:)?\s*(?P<score>[0-5](?:\.\d)?)/5\b", sentence)
        abnormal_reflex = re.search(
            r"\b(?:diminished|decreased|absent|asymmetric|brisk)\s+(?:deep tendon\s+)?reflex(?:es)?\b"
            r"|\b(?:deep tendon\s+)?reflex(?:es)?\s+(?:is|are|:)?\s*(?:diminished|decreased|absent|asymmetric|brisk)\b",
            sentence,
        )
        normal_reflex = re.search(
            r"\b(?:normal|symmetric)\s+(?:deep tendon\s+)?reflex(?:es)?\b"
            r"|\b(?:deep tendon\s+)?reflex(?:es)?\s+(?:is|are|:)?\s*(?:normal|symmetric)\b",
            sentence,
        )
        objective_weakness = re.search(r"\bobjective\b[^.!?;\n]{0,50}\b(?:motor deficit|weakness)\b", sentence)

        if strength:
            objective_motor_or_reflex_change = float(strength.group("score")) < 5
        elif abnormal_reflex or objective_weakness:
            objective_motor_or_reflex_change = True
        elif normal_reflex:
            objective_motor_or_reflex_change = False
        else:
            continue

        _add_span(
            evidence,
            "objective_motor_or_reflex_change_in_root_distribution",
            sentence_start,
            sentence_end,
            raw[sentence_start:sentence_end],
        )
        break

    # ----------------------------
    # Symptom duration (weeks)
    # ----------------------------
    symptom_weeks: Optional[int] = None

    symptom_duration_match = None
    for sentence_start, sentence_end in _sentence_spans(t):
        sentence = t[sentence_start:sentence_end]
        candidates = list(SYMPTOM_DURATION_AFTER_RE.finditer(sentence)) + list(SYMPTOM_DURATION_BEFORE_RE.finditer(sentence))
        for candidate in sorted(candidates, key=lambda item: item.start()):
            value_start = sentence_start + candidate.start("value")
            value_end = sentence_start + candidate.end("unit")
            if _duration_is_in_therapy_context(t, value_start, value_end):
                continue
            symptom_duration_match = (candidate, value_start, value_end)
            break
        if symptom_duration_match:
            break

    if symptom_duration_match:
        match, value_start, value_end = symptom_duration_match
        value = int(match.group("value"))
        symptom_weeks = value * 4 if match.group("unit").startswith("month") else value
        _add_span(
            evidence,
            "symptom_duration_weeks",
            value_start,
            value_end,
            raw[value_start:value_end],
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
        # Imaging findings are interpreted only within the sentence containing the
        # imaging mention. This prevents unrelated or negated findings elsewhere in
        # the note from being treated as an abnormal imaging result.
        for sentence_start, sentence_end in _sentence_spans(t):
            sentence = t[sentence_start:sentence_end]
            if not IMAGING_CONTEXT_RE.search(sentence):
                continue

            m_unclear = re.search(
                r"\b(inconclusive|indeterminate)\b"
                r"|\b(findings|result|results)\b.*\b(unclear|unknown|not clear|not specified|indeterminate)\b",
                sentence,
            )
            m_norm = re.search(r"\b(no abnormalities|no abnormal|no acute findings|normal|unremarkable)\b", sentence)
            abnormal_matches = list(re.finditer(r"\b(abnormal|herniat\w*|stenosis|disc bulge|fracture|degenerative)\b", sentence))
            m_abn = next((match for match in abnormal_matches if not _finding_is_negated(sentence, match)), None)
            m_negated_abn = next((match for match in abnormal_matches if _finding_is_negated(sentence, match)), None)

            if m_unclear:
                prior_imaging = "inconclusive"
                result_start = sentence_start + m_unclear.start()
                result_end = sentence_start + m_unclear.end()
                _add_span(
                    evidence,
                    "prior_imaging_result",
                    result_start,
                    result_end,
                    raw[result_start:result_end],
                )
                break

            if m_abn:
                prior_imaging = "abnormal"
                result_start = sentence_start + m_abn.start()
                result_end = sentence_start + m_abn.end()
                _add_span(
                    evidence,
                    "prior_imaging_result",
                    result_start,
                    result_end,
                    raw[result_start:result_end],
                )
                break

            if m_norm:
                prior_imaging = "normal"
                result_start = sentence_start + m_norm.start()
                result_end = sentence_start + m_norm.end()
                _add_span(
                    evidence,
                    "prior_imaging_result",
                    result_start,
                    result_end,
                    raw[result_start:result_end],
                )
                break

            if m_negated_abn:
                prior_imaging = "negative"
                result_start = sentence_start
                result_end = sentence_end
                _add_span(
                    evidence,
                    "prior_imaging_result",
                    result_start,
                    result_end,
                    raw[result_start:result_end],
                )
                break

            result_language = re.search(
                r"\b(?:showed|shows|showing|demonstrated|demonstrates|revealed|reveals|equivocal|limited)\b"
                r"|\b(?:finding|findings|result|results)\b\s*(?::|=|was|were|is|are)?\s+\S+",
                sentence,
            )
            if result_language:
                prior_imaging = "unrecognized"
                _add_span(
                    evidence,
                    "prior_imaging_result",
                    sentence_start,
                    sentence_end,
                    raw[sentence_start:sentence_end],
                )
                break

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
    m_osa = None
    for candidate in re.finditer(r"\b(obstructive sleep apnea|osa)\b", t):
        if _osa_mention_is_negated(t, candidate):
            continue
        m_osa = candidate
        break
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
        "cpb_0236_conservative_therapy_weeks": cpb_0236_therapy_weeks,
        "cpb_0236_conservative_therapy_no_improvement": cpb_0236_therapy_no_improvement,
        "back_pain_with_radiculopathy": back_pain_with_radiculopathy,
        "objective_motor_or_reflex_change_in_root_distribution": objective_motor_or_reflex_change,
        "neuro_red_flags_documented": neuro_documented,
        "prior_imaging_result": prior_imaging,
        "symptom_duration_weeks": symptom_weeks,
        "mechanical_symptoms_documented": mechanical_symptoms_documented,
        "osa_diagnosis": osa_dx,
        "sleep_study_date": sleep_study_date,
        "ahi_documented": ahi_doc,
    }

    return facts, _dedup_spans(evidence)
