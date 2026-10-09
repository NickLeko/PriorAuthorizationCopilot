"""Per-operation sentence indexes; no notes retained in shared caches."""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from contextlib import contextmanager
from contextvars import ContextVar

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
