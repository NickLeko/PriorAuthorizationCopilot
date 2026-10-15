"""Derived reviewer context; never used as extraction evidence or fingerprint input."""

from __future__ import annotations

from bisect import bisect_left, bisect_right

from .note_context import indexed_note, note_index

MAX_CITATION_WINDOW_CHARACTERS = 1_000
_TRUNCATION_MARKER = "…[truncated]"


class CitationWindowTooLarge(ValueError):
    """A complete marked citation cannot fit in the bounded context window."""


def citation_context(note: str, start: int, end: int) -> str:
    """Full containing sentences with the original cited range marked by ⟦…⟧.

    Newlines also delimit note sentences. Semicolons and decimal points between
    digits do not. For a range spanning sentences, keep every containing sentence.
    """
    if not 0 <= start < end <= len(note):
        raise ValueError("Citation range must belong to the note.")
    index = note_index(note)
    left, _ = index.containing(start, end)
    i = bisect_left(index.starts, end)
    right = index.ends[i] if i < len(index.ends) else len(note)
    if end and note[end - 1] in ".!?\n" and bisect_right(index.ends, end) != bisect_left(index.ends, end):
        right = end
    return (note[left:start] + "⟦" + note[start:end] + "⟧" + note[end:right]).strip()


def citation_window(note: str, start: int, end: int, neighbors: int = 1) -> str:
    """Containing sentences and adjacent context, bounded in Unicode characters.

    Reuse indexed_note for a batch of citations. Empty boundary segments do not
    consume a neighbor. Clipped context has one trailing truncation marker;
    the complete cited span is retained or CitationWindowTooLarge is raised.
    """
    if not 0 <= start < end <= len(note):
        raise ValueError("Citation range must belong to the note.")
    if type(neighbors) is not int or neighbors < 0:
        raise ValueError("Citation neighbors must be a non-negative integer.")
    marked_length = end - start + 2
    if marked_length > MAX_CITATION_WINDOW_CHARACTERS:
        raise CitationWindowTooLarge("The cited span exceeds the 1,000-character context window.")

    index = note_index(note)
    if "citation_window" not in index.spans:
        starts, ends = [], []
        left = 0
        for right in [*index.ends, len(note)]:
            if any(not char.isspace() and char not in ".!?" for char in note[left:right]):
                starts.append(left)
                ends.append(right)
            left = right
        index.spans["citation_window"] = (starts, ends)
    starts, ends = index.spans["citation_window"]
    if starts:
        first = min(bisect_right(ends, start), len(starts) - 1)
        last = max(first, bisect_left(starts, end) - 1)
        left = min(start, starts[max(0, first - neighbors)])
        right = max(end, ends[min(len(ends) - 1, last + neighbors)])
    else:
        left, right = 0, len(note)

    before, after = note[left:start].lstrip(), note[end:right].rstrip()
    citation = "⟦" + note[start:end] + "⟧"
    if len(before) + marked_length + len(after) <= MAX_CITATION_WINDOW_CHARACTERS:
        return before + citation + after

    budget = MAX_CITATION_WINDOW_CHARACTERS - marked_length - len(_TRUNCATION_MARKER)
    if budget < 0:
        raise CitationWindowTooLarge("The complete citation and truncation marker exceed the context window.")
    keep_before = min(len(before), budget // 2)
    keep_after = min(len(after), budget - keep_before)
    keep_before = min(len(before), budget - keep_after)
    return (before[-keep_before:] if keep_before else "") + citation + after[:keep_after] + _TRUNCATION_MARKER


def evaluation_citation_context(evaluation) -> dict[str, list[str]]:
    with indexed_note(evaluation.request.note_text):
        return {
            result.key: [citation_context(evaluation.request.note_text, span.start, span.end) for span in result.evidence_spans]
            for result in evaluation.results
        }
