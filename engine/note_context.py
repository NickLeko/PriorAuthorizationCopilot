"""Literal note vocabulary and per-operation indexes; no shared note caches."""

from __future__ import annotations

import json
import re
from bisect import bisect_left, bisect_right
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

BOUNDARY_RE = re.compile(r"(?<!\d)[.!?]|[.!?](?!\d)|\n")
CLAUSE_RE = re.compile(r"[.!?;\n]+")
_indexes: ContextVar[dict | None] = ContextVar("note_indexes", default=None)
MAX_NOTE_CHARACTERS = 20_000
MAX_EVIDENCE_SPANS = 10
MAX_REQUEST_BYTES = 1_048_576


class ExtractionInputError(ValueError):
    """Expected input rejection, without reflecting submitted text."""


def validate_note(text: str) -> str:
    if len(text) > MAX_NOTE_CHARACTERS:
        raise ExtractionInputError("Note text must be at most 20000 characters.")
    if re.search(r"\d{7,}", text):
        raise ExtractionInputError("Numeric tokens longer than 6 digits are unparseable.")
    return text


class EvidenceMap(dict):
    """Bounded citations with exact pre-cap counts for truncated facts."""

    def __init__(self, evidence):
        super().__init__((key, spans[:MAX_EVIDENCE_SPANS]) for key, spans in evidence.items())
        self.total_counts = {key: len(spans) for key, spans in evidence.items() if len(spans) > MAX_EVIDENCE_SPANS}


class NoteIndex:
    def __init__(self, text: str):
        self.text = text
        boundaries = list(BOUNDARY_RE.finditer(text))
        self.starts = [m.start() for m in boundaries]
        self.ends = [m.end() for m in boundaries]
        self.clauses = list(CLAUSE_RE.finditer(text))
        self.punctuation = [i for i, char in enumerate(text) if char in ".!?;\n"]
        self.searches: dict = {}
        self.subjects: dict = {}
        self.spans: dict = {}

    def containing(self, start: int, end: int) -> tuple[int, int]:
        left = bisect_right(self.ends, start)
        right = bisect_left(self.starts, end)
        return (self.ends[left - 1] if left else 0, self.starts[right] if right < len(self.starts) else len(self.text))

    def next_boundary(self, end: int):
        i = bisect_left(self.starts, end)
        return i if i < len(self.starts) else None


def note_index(text: str) -> NoteIndex:
    indexes = _indexes.get()
    if indexes is None:
        return NoteIndex(text)
    if text not in indexes:
        indexes[text] = NoteIndex(text)
    return indexes[text]


@contextmanager
def indexed_note(text: str):
    token = _indexes.set({text: NoteIndex(text)})
    try:
        yield
    finally:
        _indexes.reset(token)


# Versioned literal vocabulary for Footnote 1 note contexts.
DRUG_TABLE_PATH = Path(__file__).parent / "data/cpb0236_drugs_v1.json"


def load_drug_classes(path: Path = DRUG_TABLE_PATH) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["version"] != 1:
        raise ValueError("Unsupported CPB 0236 drug table version.")
    names: dict[str, str] = {}
    for entry in payload["drugs"]:
        if set(entry) != {"name", "aliases", "atc_code", "class"}:
            raise ValueError("Invalid CPB 0236 drug record.")
        code, therapy_class = entry["atc_code"], entry["class"]
        # M03A contains peripheral neuromuscular blockers: deliberately excluded.
        # Validate the reviewed class label; never derive a drug class from prose.
        allowed = (
            (therapy_class == "NSAIDs" and re.fullmatch(r"M01A[A-Z]\d{2}", code))
            or (therapy_class == "muscle relaxants" and re.fullmatch(r"M03[BC][A-Z]\d{2}", code))
            or (therapy_class == "analgesics" and re.fullmatch(r"N02[A-Z]{2}\d{2}", code))
        )
        if not allowed or not isinstance(entry["aliases"], list):
            raise ValueError("Drug ATC code and Footnote 1 class must agree within allowed groups.")
        for name in [entry["name"], *entry["aliases"]]:
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z]+(?:[ -][A-Za-z]+)*", name):
                raise ValueError("Drug names must be literal words.")
            key = name.lower()
            if key in names:
                raise ValueError("Duplicate drug name or alias.")
            names[key] = therapy_class
    if not names:
        raise ValueError("Empty CPB 0236 drug table.")
    return names


DRUG_CLASSES = load_drug_classes()
# Escaping is for literal token matching only. Membership/class is table data.
DRUG_NAME_PATTERN = r"(?:" + "|".join(re.escape(name) for name in sorted(DRUG_CLASSES, key=lambda name: (-len(name), name))) + r")"
DRUG_NAME_RE = re.compile(rf"\b{DRUG_NAME_PATTERN}\b")


# Accepted date syntax, validated without consulting or changing any clock.
ENGLISH_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
NEW_STUDY_DATE_RE = re.compile(
    r"(?<![\w/.-])(?:"
    r"\d{1,2}[-/]\d{1,2}[-/](?:19|20)\d{2}|"
    r"(?:19|20)\d{2}\.\d{1,2}\.\d{1,2}|"
    rf"{ENGLISH_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+)(?:19|20)\d{{2}}|"
    rf"\d{{1,2}}(?:st|nd|rd|th)?[ -]+{ENGLISH_MONTH}\.?[ -]+(?:19|20)\d{{2}}"
    r")(?![\w/.-]\d)\b"
)


def explicit_study_dates(text: str):
    for match in NEW_STUDY_DATE_RE.finditer(text):
        token = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", match.group(0))
        # Separators in named dates are grammatical punctuation, not a date
        # lookup table. strptime supplies calendar and leap-year validation.
        named = bool(re.search(r"[a-z]", token))
        if named:
            token = re.sub(r"[.,-]", " ", token)
            token = re.sub(r"\bsept\b", "sep", token)
            token = " ".join(token.split())
            formats = ("%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y")
        else:
            formats = ("%m/%d/%Y", "%m-%d-%Y", "%Y.%m.%d")
        for format_string in formats:
            try:
                datetime.strptime(token, format_string)
            except ValueError:
                continue
            yield match
            break
