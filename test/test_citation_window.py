"""Bounded reviewer context; canonical/API citation context stays unchanged."""

from unittest.mock import patch

import pytest

from engine.citation_context import CitationWindowTooLarge, citation_context, citation_window
from engine.extract import extract_facts
from engine.note_context import NoteIndex, indexed_note


@pytest.mark.parametrize(
    "note,quote,expected",
    [
        ("First. Second. Third.", "First", "⟦First⟧. Second."),
        ("First. Second. Third.", "Third", "Second. ⟦Third⟧."),
        ("One sentence only.", "sentence", "One ⟦sentence⟧ only."),
        ("First. Second. Third.", "Second", "First. ⟦Second⟧. Third."),
        ("First.\nSecond. Third.", "First", "⟦First⟧.\nSecond."),
        ("First.\u00a0\nSecond. Third.", "First", "⟦First⟧.\u00a0\nSecond."),
        ("First...\n\nSecond. Third.", "First", "⟦First⟧...\n\nSecond."),
        (
            "Before. First sentence. Second sentence. After. Beyond.",
            "sentence. Second",
            "Before. First ⟦sentence. Second⟧ sentence. After.",
        ),
        ("Prior. AHI 3.5 documented. Today: asymptomatic. Later.", "AHI 3.5", "Prior. ⟦AHI 3.5⟧ documented. Today: asymptomatic."),
        ("First. Last.", "Last.", "First. ⟦Last.⟧"),
        # Reuse the existing citation-context Unicode regression fixture.
        ("İ. OSA confirmed.", "OSA", "İ. ⟦OSA⟧ confirmed."),
    ],
)
def test_citation_window_sentence_boundaries(note, quote, expected):
    start = note.index(quote)
    assert citation_window(note, start, start + len(quote)) == expected


@pytest.mark.parametrize("prefix", ["İ", "İİİ", "😀İ\n", "É\tİ\n", "ΟΣ İ "])
def test_citation_window_uses_original_unicode_fixture_offsets(prefix):
    # Same note/prefix cases as TestExtractionContractAlignment's Unicode checks.
    note = prefix + " OSA. Sleep study completed 2024-05-18. AHI 22."
    _, evidence = extract_facts(note)
    span = evidence["osa_diagnosis"][0]
    window = citation_window(note, span["start"], span["end"])
    assert "⟦OSA⟧" in window
    assert prefix.strip() in window
    assert "Sleep study completed 2024-05-18." in window


@pytest.mark.parametrize(
    "side,expected",
    [
        ("before", "[truncated]…" + "a" * 973 + "⟦完整 😀 citation⟧"),
        ("after", "⟦完整 😀 citation⟧" + "b" * 973 + "…[truncated]"),
        ("both", "[truncated]…" + "a" * 480 + "⟦完整 😀 citation⟧" + "b" * 481 + "…[truncated]"),
    ],
    ids=("left-only", "right-only", "both-sides"),
)
def test_citation_window_caps_context_and_preserves_the_complete_span(side, expected):
    before = "a" * 1500 if side in {"before", "both"} else ""
    after = "b" * 1500 if side in {"after", "both"} else ""
    quote = "完整 😀 citation"
    note = before + quote + after
    window = citation_window(note, len(before), len(before) + len(quote))
    assert len(window) == 1000
    assert window == expected
    assert "⟦" + quote + "⟧" in window
    assert window.count("⟦") == window.count("⟧") == 1


@pytest.mark.parametrize(
    "before,after,expected",
    [
        ("a", "b" * 100, "a⟦" + "x" * 984 + "⟧b…[truncated]"),
        ("a" * 100, "b", "[truncated]…a⟦" + "x" * 984 + "⟧b"),
    ],
)
def test_citation_window_uses_only_one_marker_when_the_other_side_fits(before, after, expected):
    quote = "x" * 984
    assert citation_window(before + quote + after, len(before), len(before) + len(quote)) == expected
    assert len(expected) == 1000


def test_citation_window_rejects_when_two_required_markers_cannot_fit():
    with pytest.raises(CitationWindowTooLarge, match="truncation markers"):
        citation_window("a" * 100 + "x" * 984 + "b" * 100, 100, 1084)


@pytest.mark.parametrize("quote,context", [("x" * 999, ""), ("x" * 987, "y" * 100)])
def test_citation_window_rejects_a_span_that_cannot_fit_with_required_markers(quote, context):
    with pytest.raises(CitationWindowTooLarge):
        citation_window(quote + context, 0, len(quote))


def test_citation_window_exact_limit_needs_no_truncation_marker():
    note = "x" * 998
    assert citation_window(note, 0, len(note)) == "⟦" + note + "⟧"


@pytest.mark.parametrize("start,end", [(-1, 2), (0, 0), (2, 1), (0, 20)])
def test_citation_window_rejects_invalid_ranges(start, end):
    with pytest.raises(ValueError, match="Citation range"):
        citation_window("A note.", start, end)


@pytest.mark.parametrize("neighbors", (-1, 1.0, True))
def test_citation_window_rejects_invalid_neighbor_counts(neighbors):
    with pytest.raises(ValueError, match="neighbors"):
        citation_window("A note.", 0, 1, neighbors=neighbors)


def test_citation_window_reuses_one_index_without_changing_original_context():
    note = "First. Second. Third."
    with patch("engine.note_context.NoteIndex", wraps=NoteIndex) as constructor, indexed_note(note):
        expected = citation_context(note, 7, 13)
        for _ in range(120):
            assert citation_window(note, 7, 13) == "First. ⟦Second⟧. Third."
        assert citation_context(note, 7, 13) == expected == "⟦Second⟧."
        assert constructor.call_count == 1
        assert citation_window(note, 7, 13, neighbors=0) == expected
