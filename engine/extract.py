from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .schemas import REVIEW_REQUIRED_FACT

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
CPB_0236_GROUP_DURATION_RE = re.compile(
    rf"\b{CPB_0236_THERAPY_CONTEXT}\b"
    rf"(?:\s*(?:,|and|plus|\+)\s*\b{CPB_0236_THERAPY_CONTEXT}\b)+"
    r"(?:\s*(?:x|for|over|about)\s*)\b(?P<value>\d+)\s*(?:week|weeks)\b"
)
CPB_0236_NONRESPONSE_RE = re.compile(
    r"\b(?:no|minimal|little|insufficient)\s+(?:meaningful\s+)?(?:improvement|relief|response)\b"
    r"|\bwithout\s+(?:meaningful\s+)?(?:improvement|relief)\b"
    r"|\bfailed to (?:improve|respond)\b"
)
CPB_0236_RESPONSE_RE = re.compile(
    r"\b(?:substantial|significant|meaningful|good)\s+(?:improvement|relief|response)\b"
    r"|\bsymptoms? resolved\b"
)
THERAPY_CLAUSE_BOUNDARY_RE = re.compile(r"\s*,?\s*\b(?:whereas|while|however|but|although|yet|in contrast)\b\s*[:,]?\s*")
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
    r"\bwill (?:begin|try|complete|undergo)\b",
    r"\bwould (?:start|begin|try|complete|undergo)\b",
    r"\bplan to\b",
    r"\bplans to\b",
    r"\bplan\s*:",
    r"\b(?:the\s+)?plan\s+(?:is|was)\b",
    r"\b(?:the\s+)?plan\s+(?:includes|calls for)\b",
    r"\bplanned\b",
    r"\bproposed\b",
    r"\bintends? to\b",
    r"\bset to\b",
    r"\bgoing to\b",
    r"\bdue to (?:start|begin|try|complete|undergo)\b",
    r"\bconsider(?:ing)?\b",
    r"\bmay (?:start|begin|try|complete|undergo)\b",
    r"\bmight (?:start|begin|try|complete|undergo)\b",
    r"\banticipated\b",
    r"\bpending\b",
    r"\bscheduled for\b",
    r"\bto begin\b",
    r"\bupcoming\b",
    r"\breferral placed\b",
    r"\bordered\b",
    r"\brecommended\b",
    r"\bexpected\b",
    r"\bhypothetical\b",
    r"\bif\b",
    r"\b(?:will|would|may|might|could|should)\s+(?:be\s+)?(?:started|initiated|tried|completed|undertaken)\b",
    r"\b(?:is|are|was|were)\s+(?:intended|slated)\s+to\b",
    r"\b(?:is|are|was|were)\s+to\s+be\s+(?:started|initiated|tried|completed|undertaken)\b",
]
THERAPY_FUTURE_AFTER_PATTERNS = [
    r"\bnext (?:week|month)\b",
    r"\bto begin\b",
    r"\bupcoming\b",
    r"\bstarting\b",
    r"\bplanned\b",
    r"\bscheduled\b",
    r"\bpending\b",
    r"\bexpected\b",
    r"\bhypothetical\b",
    r"\b(?:will|would|may|might|could|should)\s+(?:be\s+)?(?:started|initiated|tried|completed|undertaken)\b",
    r"\b(?:is|are|was|were)\s+(?:intended|slated)\s+to\b",
    r"\bto\s+be\s+(?:started|initiated|tried|completed|undertaken)\b",
]
SENTENCE_BOUNDARY_CHARS = ".!?\n;"
FAMILY_SUBJECT_RE = re.compile(
    r"\b(?:family history|family hx|mother|father|mom|dad|sister|brother|parent|son|daughter|"
    r"spouse|wife|husband|grandmother|grandfather|aunt|uncle|sibling|relative|caregiver|guardian)\b"
)
PATIENT_SUBJECT_RE = re.compile(r"\b(?:patient|member|claimant)\b")
UNCERTAINTY_BEFORE_RE = re.compile(
    r"\b(?:possible|possibly|suspected|suspect|questionable|concern for|question of|rule out|cannot exclude|"
    r"may have|might have|could have|may be|might be|could be|likely|probable|potential|query|evaluate for|"
    r"evaluating for|workup for)"
    r"\b[^.!?;\n]{0,40}$"
)
UNCERTAINTY_AFTER_RE = re.compile(
    r"^\s*(?:(?:is|was|remains?)\s+)?(?:possible|suspected|uncertain|questionable|not confirmed)\b"
    r"|^\s*(?:that\s+)?(?:cannot|could not|can't)\s+be\s+(?:excluded|ruled\s+out)\b"
    r"|^\s*(?:that\s+)?(?:cannot|could not|can't)\s+be\s+confirmed\b"
    r"|^\s*(?:(?:is|was)\s+)?not\s+excluded\b"
    r"|^\s*(?:has\s+)?not(?:\s+yet)?(?:\s+been)?\s+ruled\s+out\b"
    r"|^\s*(?:(?:is|was|remains?)\s+)?(?:under\s+consideration|being\s+considered|"
    r"(?:a\s+)?(?:diagnostic\s+)?(?:possibility|consideration)|(?:in|on)\s+the\s+differential|unconfirmed)\b"
    r"|^\s*(?:was\s+)?considered\b"
    r"|^\s*(?:versus|vs\.?)\b"
)


@dataclass(frozen=True)
class _TherapyCourseCandidate:
    """Narrow internal linkage record for the verified CPB 0236 branch."""

    modality_key: str
    duration_weeks: int | None
    no_improvement: bool | str | None
    start: int
    end: int
    ambiguous_linkage: bool = False


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


def _mention_is_in_questioned_sentence(text: str, end: int) -> bool:
    """Treat a supported mention in a question as uncertain evidence."""
    boundary = re.search(r"[.!?;\n]", text[end:])
    return bool(boundary and boundary.group(0) == "?")


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


def _therapy_clause_spans(sentence: str) -> List[Tuple[int, int]]:
    """Split only on explicit contrast markers that indicate separate assertions."""
    spans: List[Tuple[int, int]] = []
    start = 0
    for boundary in THERAPY_CLAUSE_BOUNDARY_RE.finditer(sentence):
        end = boundary.start()
        if sentence[start:end].strip():
            left_trim = len(sentence[start:end]) - len(sentence[start:end].lstrip())
            right_trim = len(sentence[start:end].rstrip())
            spans.append((start + left_trim, start + right_trim))
        start = boundary.end()
    if sentence[start:].strip():
        left_trim = len(sentence[start:]) - len(sentence[start:].lstrip())
        spans.append((start + left_trim, len(sentence.rstrip())))
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
            r"\b(?:no|denies?|without|negative\s+for|free\s+of|absence\s+of|rule(?:d)?\s+out)\s+"
            r"(?:evidence\s+of\s+)?(?:acute\s+)?$",
            before,
        )
        or re.match(
            r"^\s+(?:(?:is|was|has been)\s+)?(?:later\s+)?(?:absent|negative|not present|ruled out)\b",
            after,
        )
    )


def _finding_is_uncertain(text: str, match: re.Match[str]) -> bool:
    before = text[max(0, match.start() - 80) : match.start()]
    after = text[match.end() : min(len(text), match.end() + 56)]
    return bool(UNCERTAINTY_BEFORE_RE.search(before) or UNCERTAINTY_AFTER_RE.match(after) or after.lstrip().startswith("?"))


def _mention_is_nonpatient_context(text: str, start: int, end: int) -> bool:
    """Return True only for explicit family/non-patient context near a mention."""
    before = text[:start]
    after = text[end:]
    family_before = list(FAMILY_SUBJECT_RE.finditer(before))
    patient_before = list(PATIENT_SUBJECT_RE.finditer(before))
    last_family = family_before[-1].start() if family_before else -1
    last_patient = patient_before[-1].start() if patient_before else -1

    if last_family > last_patient:
        return True
    if re.match(
        r"^\s+(?:in|for)\s+(?:the\s+patient'?s\s+|his\s+|her\s+)?"
        r"(?:mother|father|mom|dad|sister|brother|parent|son|daughter|spouse|wife|husband|"
        r"grandmother|grandfather|aunt|uncle|sibling|relative|caregiver|guardian)\b",
        after,
    ):
        return True

    # Handle explicit non-patient attribution after the mention without trying
    # to solve general coreference. Examples include "completed by her mother",
    # "diagnosed in the father", and "was her mother's finding".
    after_window = after[:160]
    family_after = FAMILY_SUBJECT_RE.search(after_window)
    patient_after = next(
        (
            match
            for match in PATIENT_SUBJECT_RE.finditer(after_window)
            if not re.match(
                r"'?s\s+(?:mother|father|mom|dad|sister|brother|parent|son|daughter|spouse|wife|husband|"
                r"grandmother|grandfather|aunt|uncle|sibling|relative|caregiver|guardian)\b",
                after_window[match.end() :],
            )
        ),
        None,
    )
    if family_after is not None and (patient_after is None or family_after.start() < patient_after.start()):
        bridge = after[: family_after.start()]
        family_tail = after[family_after.end() : family_after.end() + 2]
        attributed_by_relation = re.search(
            r"\b(?:in|for|by|of|according\s+to|belong(?:s|ed)?\s+to)\s+"
            r"(?:the\s+patient'?s\s+|the\s+|his\s+|her\s+|their\s+)?$",
            bridge,
        )
        attributed_by_possessive = family_tail.startswith("'s") and re.search(
            r"\b(?:is|was|are|were)\s+(?:the\s+|his\s+|her\s+|their\s+)?$",
            bridge,
        )
        if attributed_by_relation or attributed_by_possessive:
            return True
    return False


def _dedup_matches(matches: List[re.Match[str]]) -> List[re.Match[str]]:
    deduped: List[re.Match[str]] = []
    seen: set[Tuple[int, int]] = set()
    for match in sorted(matches, key=lambda item: (item.start(), item.end())):
        span = (match.start(), match.end())
        if span not in seen:
            seen.add(span)
            deduped.append(match)
    return deduped


def _collect_cpb_therapy_candidates(text: str) -> List[_TherapyCourseCandidate]:
    candidates: List[_TherapyCourseCandidate] = []

    for sentence_start, sentence_end in _sentence_spans(text):
        sentence = text[sentence_start:sentence_end]
        sentence_is_questioned = text[sentence_end : sentence_end + 1] == "?"
        for clause_start, clause_end in _therapy_clause_spans(sentence):
            clause = sentence[clause_start:clause_end]
            absolute_start = sentence_start + clause_start
            absolute_end = sentence_start + clause_end
            modality_matches = list(CPB_0236_THERAPY_CONTEXT_RE.finditer(clause))
            if not modality_matches:
                continue

            patient_modalities = [
                match for match in modality_matches if not _mention_is_nonpatient_context(clause, match.start(), match.end())
            ]
            if not patient_modalities:
                continue

            # Mixed patient and non-patient therapy references in one clause are
            # not safe to resolve to a single patient course.
            subject_ambiguous = len(patient_modalities) != len(modality_matches)
            if _has_pattern(THERAPY_FUTURE_LOOKBACK_PATTERNS + THERAPY_FUTURE_AFTER_PATTERNS, clause):
                continue

            duration_matches = _dedup_matches(
                [
                    match
                    for pattern in (CPB_0236_THERAPY_AFTER_RE, CPB_0236_THERAPY_BEFORE_RE)
                    for match in pattern.finditer(clause)
                    if not _therapy_duration_is_disqualified(clause, match)
                    and not _mention_is_nonpatient_context(clause, match.start(), match.end())
                ]
            )
            group_matches = list(CPB_0236_GROUP_DURATION_RE.finditer(clause))

            response_mentions: List[Tuple[bool | str, re.Match[str]]] = []
            for match in CPB_0236_NONRESPONSE_RE.finditer(clause):
                value: bool | str = True
                if _finding_is_uncertain(clause, match):
                    value = REVIEW_REQUIRED_FACT
                response_mentions.append((value, match))
            for match in CPB_0236_RESPONSE_RE.finditer(clause):
                value = False
                if _finding_is_uncertain(clause, match):
                    value = REVIEW_REQUIRED_FACT
                response_mentions.append((value, match))

            response_values = {value for value, _ in response_mentions}
            response_value: bool | str | None = None
            if REVIEW_REQUIRED_FACT in response_values or len(response_values) > 1:
                response_value = REVIEW_REQUIRED_FACT
            elif response_values:
                response_value = next(iter(response_values))

            duration_values = {int(match.group("value")) for match in duration_matches}
            duration_value = next(iter(duration_values)) if len(duration_values) == 1 else None

            modality_keys = tuple(match.group(0).strip() for match in patient_modalities)
            modality_key = "+".join(dict.fromkeys(modality_keys))
            coordinated_group = any(
                group.start() <= patient_modalities[0].start()
                and group.end() >= patient_modalities[-1].end()
                and duration_value == int(group.group("value"))
                for group in group_matches
            )
            linkage_ambiguous = bool(
                subject_ambiguous
                or sentence_is_questioned
                or len(duration_values) > 1
                or REVIEW_REQUIRED_FACT in response_values
                or len(response_values) > 1
                or (len(set(modality_keys)) > 1 and not coordinated_group)
            )

            if duration_value is None and response_value is None and not linkage_ambiguous:
                continue
            candidates.append(
                _TherapyCourseCandidate(
                    modality_key=modality_key,
                    duration_weeks=duration_value,
                    no_improvement=response_value,
                    start=absolute_start,
                    end=absolute_end,
                    ambiguous_linkage=linkage_ambiguous,
                )
            )

    return candidates


def _resolve_cpb_therapy_candidates(
    candidates: List[_TherapyCourseCandidate],
) -> Tuple[Optional[int] | str, Optional[bool] | str]:
    if not candidates:
        return None, None
    if any(candidate.ambiguous_linkage for candidate in candidates):
        return REVIEW_REQUIRED_FACT, REVIEW_REQUIRED_FACT

    paired = [candidate for candidate in candidates if candidate.duration_weeks is not None and candidate.no_improvement is not None]
    duration_only = [candidate for candidate in candidates if candidate.duration_weeks is not None and candidate.no_improvement is None]
    response_only = [candidate for candidate in candidates if candidate.duration_weeks is None and candidate.no_improvement is not None]

    response_values = {candidate.no_improvement for candidate in paired + response_only if candidate.no_improvement is not None}
    if REVIEW_REQUIRED_FACT in response_values or len(response_values) > 1:
        return REVIEW_REQUIRED_FACT, REVIEW_REQUIRED_FACT

    paired_signatures = {(candidate.modality_key, candidate.duration_weeks, candidate.no_improvement) for candidate in paired}
    if len(paired_signatures) > 1:
        return REVIEW_REQUIRED_FACT, REVIEW_REQUIRED_FACT

    if paired:
        selected = paired[0]
        # A longer unlinked course could otherwise donate its duration to the
        # selected course's response. Do not select either fact in that case.
        if any(
            candidate.duration_weeks is not None
            and selected.duration_weeks is not None
            and candidate.duration_weeks > selected.duration_weeks
            for candidate in duration_only
        ):
            return REVIEW_REQUIRED_FACT, REVIEW_REQUIRED_FACT
        return selected.duration_weeks, selected.no_improvement

    if duration_only and response_only:
        return REVIEW_REQUIRED_FACT, REVIEW_REQUIRED_FACT

    duration_values = {candidate.duration_weeks for candidate in duration_only if candidate.duration_weeks is not None}
    if len(duration_values) > 1:
        duration: Optional[int] | str = REVIEW_REQUIRED_FACT
    elif duration_values:
        duration = next(iter(duration_values))
    else:
        duration = None

    if response_values:
        response: Optional[bool] | str = next(iter(response_values))
    else:
        response = None
    return duration, response


def _match_is_nonpatient_context(text: str, match: re.Match[str]) -> bool:
    before = _bounded_context_before(text, match.start(), max_chars=200)
    after = _bounded_context_after(text, match.end(), max_chars=200)
    local = before + text[match.start() : match.end()] + after
    local_start = len(before)
    local_end = local_start + match.end() - match.start()
    return _mention_is_nonpatient_context(local, local_start, local_end)


def _add_sentence_span(
    evidence: Dict[str, List[Dict[str, Any]]],
    key: str,
    start: int,
    end: int,
    raw: str,
) -> None:
    _add_span(evidence, key, start, end, raw[start:end])


def _resolve_boolean_candidates(
    candidates: List[Tuple[bool | str, int, int]],
    *,
    key: str,
    evidence: Dict[str, List[Dict[str, Any]]],
    raw: str,
) -> Optional[bool] | str:
    if not candidates:
        return None
    for _, start, end in candidates:
        _add_sentence_span(evidence, key, start, end, raw)
    values = {value for value, _, _ in candidates}
    if REVIEW_REQUIRED_FACT in values or len(values) > 1:
        return REVIEW_REQUIRED_FACT
    value = next(iter(values))
    return bool(value)


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
    therapy_weeks: Optional[int] | str = None
    generic_duration_candidates: List[Tuple[int | str, re.Match[str]]] = []
    for pattern in (THERAPY_AFTER_RE, THERAPY_BEFORE_RE):
        for candidate in pattern.finditer(t):
            if _therapy_duration_is_disqualified(t, candidate) or _match_is_nonpatient_context(t, candidate):
                continue
            value: int | str = int(candidate.group("value"))
            if _mention_is_in_questioned_sentence(t, candidate.end()):
                value = REVIEW_REQUIRED_FACT
            generic_duration_candidates.append((value, candidate))

    generic_duration_values = {value for value, _ in generic_duration_candidates}
    if REVIEW_REQUIRED_FACT in generic_duration_values or len(generic_duration_values) > 1:
        therapy_weeks = REVIEW_REQUIRED_FACT
        for _, candidate in generic_duration_candidates:
            _add_span(
                evidence,
                "conservative_therapy_weeks",
                candidate.start(),
                candidate.end(),
                raw[candidate.start() : candidate.end()],
            )
    elif generic_duration_candidates:
        therapy_weeks, selected = generic_duration_candidates[0]
        _add_span(
            evidence,
            "conservative_therapy_weeks",
            selected.start(),
            selected.end(),
            raw[selected.start() : selected.end()],
        )

    # The verified lumbar branch collects narrow course candidates first, then
    # resolves the two scalar rule facts only when linkage is unambiguous.
    cpb_candidates = _collect_cpb_therapy_candidates(t)
    cpb_0236_therapy_weeks, cpb_0236_therapy_no_improvement = _resolve_cpb_therapy_candidates(cpb_candidates)
    for candidate in cpb_candidates:
        if candidate.duration_weeks is not None or candidate.ambiguous_linkage:
            _add_sentence_span(
                evidence,
                "cpb_0236_conservative_therapy_weeks",
                candidate.start,
                candidate.end,
                raw,
            )
        if candidate.no_improvement is not None or candidate.ambiguous_linkage:
            _add_sentence_span(
                evidence,
                "cpb_0236_conservative_therapy_no_improvement",
                candidate.start,
                candidate.end,
                raw,
            )

    # ----------------------------
    # Official lumbar-radiculopathy branch facts
    # ----------------------------
    back_pain_candidates: List[Tuple[bool | str, int, int]] = []
    for sentence_start, sentence_end in _sentence_spans(t):
        sentence = t[sentence_start:sentence_end]
        back_pain_matches = [
            match for match in BACK_PAIN_RE.finditer(sentence) if not _mention_is_nonpatient_context(sentence, match.start(), match.end())
        ]
        radiculopathy_matches = [
            match
            for match in RADICULOPATHY_RE.finditer(sentence)
            if not _mention_is_nonpatient_context(sentence, match.start(), match.end())
        ]
        if not back_pain_matches or not radiculopathy_matches:
            continue

        back_values: set[bool | str] = set()
        for match in back_pain_matches:
            if _finding_is_uncertain(sentence, match):
                back_values.add(REVIEW_REQUIRED_FACT)
            else:
                back_values.add(not _finding_is_negated(sentence, match))

        radiculopathy_values: set[bool | str] = set()
        for match in radiculopathy_matches:
            mention_is_questioned = t[sentence_end : sentence_end + 1] == "?"
            if _finding_is_uncertain(sentence, match) or mention_is_questioned:
                radiculopathy_values.add(REVIEW_REQUIRED_FACT)
            else:
                radiculopathy_values.add(not _finding_is_negated(sentence, match))

        if (
            REVIEW_REQUIRED_FACT in back_values
            or REVIEW_REQUIRED_FACT in radiculopathy_values
            or len(back_values) > 1
            or len(radiculopathy_values) > 1
        ):
            value: bool | str = REVIEW_REQUIRED_FACT
        else:
            value = back_values == {True} and radiculopathy_values == {True}
        back_pain_candidates.append((value, sentence_start, sentence_end))

    back_pain_with_radiculopathy = _resolve_boolean_candidates(
        back_pain_candidates,
        key="back_pain_with_radiculopathy",
        evidence=evidence,
        raw=raw,
    )

    objective_candidates: List[Tuple[bool | str, int, int]] = []
    for sentence_start, sentence_end in _sentence_spans(t):
        sentence = t[sentence_start:sentence_end]
        root_matches = [
            match
            for match in ROOT_DISTRIBUTION_RE.finditer(sentence)
            if not _mention_is_nonpatient_context(sentence, match.start(), match.end())
        ]
        if not root_matches:
            continue

        finding_values: List[bool | str] = []
        strength_matches = list(re.finditer(r"\b(?P<score>[0-5](?:\.\d)?)/5\b", sentence)) if re.search(r"\bstrength\b", sentence) else []
        has_reflex_context = re.search(r"\b(?:deep tendon\s+)?reflex(?:es)?\b", sentence) is not None
        abnormal_reflex_matches = (
            list(re.finditer(r"\b(?:diminished|decreased|absent|asymmetric|brisk)\b", sentence)) if has_reflex_context else []
        )
        normal_reflex_matches = list(re.finditer(r"\b(?:normal|symmetric)\b", sentence)) if has_reflex_context else []
        objective_weakness_matches = list(re.finditer(r"\bobjective\b[^.!?;\n]{0,50}\b(?:motor deficit|weakness)\b", sentence))

        for match in strength_matches:
            if _mention_is_nonpatient_context(sentence, match.start(), match.end()):
                continue
            if _finding_is_uncertain(sentence, match) or t[sentence_end : sentence_end + 1] == "?":
                finding_values.append(REVIEW_REQUIRED_FACT)
            else:
                finding_values.append(float(match.group("score")) < 5)
        for match in abnormal_reflex_matches + objective_weakness_matches:
            if _mention_is_nonpatient_context(sentence, match.start(), match.end()):
                continue
            if _finding_is_uncertain(sentence, match) or t[sentence_end : sentence_end + 1] == "?":
                finding_values.append(REVIEW_REQUIRED_FACT)
            else:
                finding_values.append(not _finding_is_negated(sentence, match))
        for match in normal_reflex_matches:
            if _mention_is_nonpatient_context(sentence, match.start(), match.end()):
                continue
            if _finding_is_uncertain(sentence, match) or t[sentence_end : sentence_end + 1] == "?":
                finding_values.append(REVIEW_REQUIRED_FACT)
            else:
                finding_values.append(False)

        if not finding_values:
            continue
        distinct_findings = set(finding_values)
        if REVIEW_REQUIRED_FACT in distinct_findings or len(distinct_findings) > 1:
            objective_value: bool | str = REVIEW_REQUIRED_FACT
        else:
            objective_value = bool(next(iter(distinct_findings)))
        objective_candidates.append((objective_value, sentence_start, sentence_end))

    objective_motor_or_reflex_change = _resolve_boolean_candidates(
        objective_candidates,
        key="objective_motor_or_reflex_change_in_root_distribution",
        evidence=evidence,
        raw=raw,
    )

    # ----------------------------
    # Symptom duration (weeks)
    # ----------------------------
    symptom_weeks: Optional[int] | str = None
    symptom_duration_matches: List[Tuple[int | str, int, int]] = []
    for sentence_start, sentence_end in _sentence_spans(t):
        sentence = t[sentence_start:sentence_end]
        candidates = list(SYMPTOM_DURATION_AFTER_RE.finditer(sentence)) + list(SYMPTOM_DURATION_BEFORE_RE.finditer(sentence))
        for candidate in sorted(candidates, key=lambda item: item.start()):
            value_start = sentence_start + candidate.start("value")
            value_end = sentence_start + candidate.end("unit")
            if _duration_is_in_therapy_context(t, value_start, value_end):
                continue
            if _mention_is_nonpatient_context(sentence, candidate.start(), candidate.end()):
                continue
            value = int(candidate.group("value"))
            weeks: int | str = value * 4 if candidate.group("unit").startswith("month") else value
            if t[sentence_end : sentence_end + 1] == "?":
                weeks = REVIEW_REQUIRED_FACT
            symptom_duration_matches.append((weeks, value_start, value_end))

    symptom_values = {value for value, _, _ in symptom_duration_matches}
    if REVIEW_REQUIRED_FACT in symptom_values or len(symptom_values) > 1:
        symptom_weeks = REVIEW_REQUIRED_FACT
        for _, start, end in symptom_duration_matches:
            _add_span(evidence, "symptom_duration_weeks", start, end, raw[start:end])
    elif symptom_duration_matches:
        symptom_weeks, value_start, value_end = symptom_duration_matches[0]
        _add_span(evidence, "symptom_duration_weeks", value_start, value_end, raw[value_start:value_end])

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

    neuro_candidates: List[Tuple[bool | str, int, int]] = []
    for sentence_start, sentence_end in _sentence_spans(t):
        sentence = t[sentence_start:sentence_end]
        denial_match = next((match for pat in denial_patterns if (match := re.search(pat, sentence))), None)
        positive_match = next((match for pat in positive_patterns if (match := re.search(pat, sentence))), None)
        if (
            denial_match is not None
            and positive_match is not None
            and denial_match.start() <= positive_match.start()
            and denial_match.end() >= positive_match.end()
            and re.search(r"\b(?:but|however|later|then)\b", sentence) is None
        ):
            positive_match = None
        if positive_match is not None and _finding_is_negated(sentence, positive_match):
            positive_match = None

        matched = positive_match or denial_match
        if matched is None or _mention_is_nonpatient_context(sentence, matched.start(), matched.end()):
            continue
        if denial_match is not None and positive_match is not None:
            neuro_candidates.append((REVIEW_REQUIRED_FACT, sentence_start, sentence_end))
        elif _finding_is_uncertain(sentence, matched) or t[sentence_end : sentence_end + 1] == "?":
            neuro_candidates.append((REVIEW_REQUIRED_FACT, sentence_start, sentence_end))
        elif positive_match is not None:
            neuro_candidates.append((True, sentence_start, sentence_end))
        else:
            # False represents an explicit denial while candidates are resolved;
            # the public fact remains True because this field means "addressed".
            neuro_candidates.append((False, sentence_start, sentence_end))

    neuro_candidate_values = {value for value, _, _ in neuro_candidates}
    if REVIEW_REQUIRED_FACT in neuro_candidate_values or len(neuro_candidate_values) > 1:
        neuro_documented: Optional[bool] | str = REVIEW_REQUIRED_FACT
    elif neuro_candidates:
        neuro_documented = True
    else:
        neuro_documented = None
    for _, start, end in neuro_candidates:
        _add_sentence_span(evidence, "neuro_red_flags_documented", start, end, raw)

    # ----------------------------
    # Prior imaging result
    # ----------------------------
    prior_imaging: Optional[str] = None
    imaging_candidates: List[Tuple[str, int, int]] = []

    # Imaging findings are interpreted only within their sentence. Distinct,
    # conflicting result categories fail closed instead of using whichever came first.
    for sentence_start, sentence_end in _sentence_spans(t):
        sentence = t[sentence_start:sentence_end]
        imaging_context = IMAGING_CONTEXT_RE.search(sentence)
        if imaging_context is None or _mention_is_nonpatient_context(
            sentence,
            imaging_context.start(),
            imaging_context.end(),
        ):
            continue

        m_no_img = re.search(r"\bno (prior )?imaging( documented| yet| to date)?\b", sentence)
        m_unclear = re.search(
            r"\b(inconclusive|indeterminate)\b"
            r"|\b(findings|result|results)\b.*\b(unclear|unknown|not clear|not specified|indeterminate)\b",
            sentence,
        )
        m_norm = re.search(r"\b(no abnormalities|no abnormal|no acute findings|normal|unremarkable)\b", sentence)
        abnormal_matches = list(re.finditer(r"\b(abnormal|herniat\w*|stenosis|disc bulge|fracture|degenerative)\b", sentence))
        m_abn = next((match for match in abnormal_matches if not _finding_is_negated(sentence, match)), None)
        m_negated_abn = next((match for match in abnormal_matches if _finding_is_negated(sentence, match)), None)
        result_language = re.search(
            r"\b(?:showed|shows|showing|demonstrated|demonstrates|revealed|reveals|equivocal|limited)\b"
            r"|\b(?:finding|findings|result|results)\b\s*(?::|=|was|were|is|are)?\s+\S+",
            sentence,
        )

        result_match = m_no_img or m_unclear or m_abn or m_norm or m_negated_abn or result_language
        if result_match is None:
            continue
        if (_finding_is_uncertain(sentence, result_match) or t[sentence_end : sentence_end + 1] == "?") and m_unclear is None:
            category = REVIEW_REQUIRED_FACT
        elif m_no_img:
            category = "none"
        elif m_unclear:
            category = "inconclusive"
        elif m_abn:
            category = "abnormal"
        elif m_norm:
            category = "normal"
        elif m_negated_abn:
            category = "negative"
        else:
            category = "unrecognized"
        if category in ("negative", "unrecognized", REVIEW_REQUIRED_FACT):
            evidence_start, evidence_end = sentence_start, sentence_end
        else:
            evidence_start = sentence_start + result_match.start()
            evidence_end = sentence_start + result_match.end()
        imaging_candidates.append((category, evidence_start, evidence_end))

    imaging_values = {value for value, _, _ in imaging_candidates}
    if REVIEW_REQUIRED_FACT in imaging_values or len(imaging_values) > 1:
        prior_imaging = REVIEW_REQUIRED_FACT
    elif imaging_candidates:
        prior_imaging = imaging_candidates[0][0]
    for _, start, end in imaging_candidates:
        _add_sentence_span(evidence, "prior_imaging_result", start, end, raw)

    # ----------------------------
    # Mechanical symptoms addressed
    # ----------------------------
    # This field is used for the narrow knee MRI pathway.
    # Semantics:
    #   True  -> explicit positive symptom wording (locking/catching/buckling/etc.)
    #   False -> explicit denial / absence wording
    #   None  -> not addressed explicitly
    mechanical_symptoms_documented: Optional[bool] | str = None

    mechanical_denial_patterns = [
        r"\bdenies\b.*\b(locking|catching|buckling|giving way|instability)\b",
        r"\bno\b.*\b(locking|catching|buckling|giving way|instability)\b",
        r"\bwithout\b.*\b(locking|catching|buckling|giving way|instability)\b",
    ]
    mechanical_positive_patterns = [
        r"\b(reports|reported|endorses|notes|noted|describes|described|with)\b.*\b(locking|catching|buckling|giving way|instability)\b",
        r"\bmechanical symptoms\b",
    ]

    mechanical_candidates: List[Tuple[bool | str, int, int]] = []
    for sentence_start, sentence_end in _sentence_spans(t):
        sentence = t[sentence_start:sentence_end]
        denial_match = next((match for pat in mechanical_denial_patterns if (match := re.search(pat, sentence))), None)
        positive_match = next(
            (match for pat in mechanical_positive_patterns if (match := re.search(pat, sentence))),
            None,
        )
        if positive_match is not None and _finding_is_negated(sentence, positive_match):
            positive_match = None
        matched = denial_match or positive_match
        if matched is None or _mention_is_nonpatient_context(sentence, matched.start(), matched.end()):
            continue
        if denial_match is not None and positive_match is not None:
            value = REVIEW_REQUIRED_FACT
        elif _finding_is_uncertain(sentence, matched) or t[sentence_end : sentence_end + 1] == "?":
            value: bool | str = REVIEW_REQUIRED_FACT
        else:
            value = positive_match is not None and denial_match is None
        mechanical_candidates.append((value, sentence_start, sentence_end))

    mechanical_symptoms_documented = _resolve_boolean_candidates(
        mechanical_candidates,
        key="mechanical_symptoms_documented",
        evidence=evidence,
        raw=raw,
    )

    # ----------------------------
    # OSA diagnosis
    # ----------------------------
    osa_candidates: List[Tuple[bool | str, int, int]] = []
    for sentence_start, sentence_end in _sentence_spans(t):
        sentence = t[sentence_start:sentence_end]
        for candidate in re.finditer(r"\b(obstructive sleep apnea|osa)\b", sentence):
            if _mention_is_nonpatient_context(sentence, candidate.start(), candidate.end()):
                continue
            if _finding_is_uncertain(sentence, candidate) or t[sentence_end : sentence_end + 1] == "?":
                value = REVIEW_REQUIRED_FACT
            elif _osa_mention_is_negated(sentence, candidate):
                value = False
            else:
                value = True
            osa_candidates.append((value, sentence_start + candidate.start(), sentence_start + candidate.end()))

    osa_values = {value for value, _, _ in osa_candidates}
    if REVIEW_REQUIRED_FACT in osa_values or len(osa_values) > 1:
        osa_dx: Optional[bool] | str = REVIEW_REQUIRED_FACT
        for _, start, end in osa_candidates:
            _add_span(evidence, "osa_diagnosis", start, end, raw[start:end])
    elif osa_values == {True}:
        osa_dx = True
        for _, start, end in osa_candidates:
            _add_span(evidence, "osa_diagnosis", start, end, raw[start:end])
    else:
        # A negative-only diagnosis mention is not an established diagnosis.
        osa_dx = None

    # ----------------------------
    # Sleep study date (context-gated)
    # ----------------------------
    sleep_study_date: Optional[bool] | str = None

    date_iter = list(re.finditer(r"\b(20\d{2}|19\d{2})[-/]\d{1,2}[-/]\d{1,2}\b", t))
    SLEEP_CTX = re.compile(r"\b(sleep study|polysomnography|psg|hst|home sleep test)\b")

    for m_date in date_iter:
        window_start = max(0, m_date.start() - 80)
        window_end = min(len(t), m_date.end() + 80)
        window = t[window_start:window_end]

        if (
            SLEEP_CTX.search(window)
            and not _match_is_nonpatient_context(t, m_date)
            and not _has_pattern(THERAPY_FUTURE_LOOKBACK_PATTERNS + THERAPY_FUTURE_AFTER_PATTERNS, window)
        ):
            sleep_study_date = REVIEW_REQUIRED_FACT if _mention_is_in_questioned_sentence(t, m_date.end()) else True
            _add_span(evidence, "sleep_study_date", m_date.start(), m_date.end(), raw[m_date.start() : m_date.end()])
            break

    # ----------------------------
    # AHI / RDI documented (must have numeric value OR explicit missingness)
    # ----------------------------
    ahi_doc: Optional[bool] | str = None

    m_ahi_missing = re.search(r"\b(ahi|rdi)\b.*\b(not documented|not stated|not available|unknown|n/?a|missing)\b", t)
    if m_ahi_missing is not None and _match_is_nonpatient_context(t, m_ahi_missing):
        m_ahi_missing = None
    if m_ahi_missing:
        ahi_doc = REVIEW_REQUIRED_FACT if _mention_is_in_questioned_sentence(t, m_ahi_missing.end()) else None
        _add_span(
            evidence,
            "ahi_documented",
            m_ahi_missing.start(),
            m_ahi_missing.end(),
            raw[m_ahi_missing.start() : m_ahi_missing.end()],
        )
    else:
        m_ahi_val = next(
            (
                candidate
                for candidate in re.finditer(r"\b(ahi|rdi)\b\s*[:=]?\s*(\d+(\.\d+)?)\b", t)
                if not _match_is_nonpatient_context(t, candidate)
            ),
            None,
        )
        if m_ahi_val:
            ahi_doc = (
                REVIEW_REQUIRED_FACT
                if _finding_is_uncertain(t, m_ahi_val) or _mention_is_in_questioned_sentence(t, m_ahi_val.end())
                else True
            )
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

    # Regex coordinates belong to the lowercased string. Unicode lowercase can
    # expand a character (e.g. U+0130); map them back before exposing evidence.
    original_indices = [index for index, char in enumerate(raw) for _ in char.lower()]
    for spans in evidence.values():
        for span in spans:
            start = original_indices[span["start"]]
            end = original_indices[span["end"] - 1] + 1
            span.update(start=start, end=end, text=raw[start:end])
    return facts, _dedup_spans(evidence)
