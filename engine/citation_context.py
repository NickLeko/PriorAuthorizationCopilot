"""Derived reviewer context; never used as extraction evidence or fingerprint input."""

from __future__ import annotations

import re


def citation_context(note: str, start: int, end: int) -> str:
    """Full containing sentences with the original cited range marked by ⟦…⟧.

    Newlines and semicolons also delimit note sentences. Decimal points between
    digits do not. For a range spanning sentences, keep every containing sentence.
    """
    if not 0 <= start < end <= len(note):
        raise ValueError("Citation range must belong to the note.")
    boundaries = list(re.finditer(r"(?<!\d)[.!?]|[.!?](?!\d)|[;\n]", note))
    left = max((match.end() for match in boundaries if match.end() <= start), default=0)
    right = min((match.end() for match in boundaries if match.start() >= end), default=len(note))
    # A span may include its sentence's final punctuation.
    if end and note[end - 1] in ".!?;\n" and any(match.end() == end for match in boundaries):
        right = end
    return (note[left:start] + "⟦" + note[start:end] + "⟧" + note[end:right]).strip()


def evaluation_citation_context(evaluation) -> dict[str, list[str]]:
    return {
        result.key: [citation_context(evaluation.request.note_text, span.start, span.end) for span in result.evidence_spans]
        for result in evaluation.results
    }
