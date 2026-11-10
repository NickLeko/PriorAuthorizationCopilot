"""Audit regression D3: the "<token> no longer" review trigger is linear and search-equivalent.

The trigger is used only through re.search truthiness (_finding_is_uncertain), so equivalence
means the same match/no-match outcome on every input, not the same span.
"""

import random
import re
import subprocess
import sys

import pytest

from engine.extract import PERSISTENCE_REVIEW_TRIGGER, REVIEW_TRIGGER, extract_facts

# The pre-audit branch, retained only as the reference for the differential test.
REFERENCE = r"\b[\w/-]+\s+no\s+longer\b(?!\s+than\b)"
CURRENT = PERSISTENCE_REVIEW_TRIGGER.rsplit("|", 1)[1]
PIECES = ["a", "B", "1", "_", "é", "٣", "-", "/", "/-", " ", "  ", "\t", "\n", " ", ".", ",", "(",
          "no", "longer", "than", " no longer", " no  longer ", "no\tlonger", " than", "x-", "-x", "/no", "longers"]  # fmt: skip


def test_current_branch_is_the_linear_form():
    assert CURRENT == r"(?<![\w/-])[/-]*\w[\w/-]*\s+no\s+longer\b(?!\s+than\b)"
    assert REVIEW_TRIGGER.count(CURRENT) == 1


def test_seeded_differential_search_equivalence_with_the_reference():
    reference, current = re.compile(REFERENCE), re.compile(CURRENT)
    rng = random.Random(20261109)
    outcomes = set()
    for _ in range(60_000):
        text = "".join(rng.choice(PIECES) for _ in range(rng.randint(0, 24)))
        found = reference.search(text) is not None
        assert found == (current.search(text) is not None), repr(text)
        outcomes.add(found)
    assert outcomes == {True, False}  # the sample exercises both outcomes


@pytest.mark.parametrize(
    "text,expected",
    [
        ("radicular pain no longer radiates", True),
        ("pain/numbness no longer present", True),
        ("-/x no longer", True),  # first word character after a /- prefix
        ("-/ no longer", False),  # no word character: no \b inside the token
        ("pain no longer than 6 weeks", False),
        ("é-٣ no longer", True),  # Unicode word characters
        ("no longer", False),  # this branch needs a preceding token
        ("pain no longer", True),  # NBSP is whitespace
        ("pain no longers", False),
    ],
)
def test_documented_trigger_cases(text, expected):
    assert (re.search(CURRENT, text) is not None) is expected
    assert (re.search(REFERENCE, text) is not None) is expected


@pytest.mark.parametrize("unit", ["a-", "a/", "é-"])
def test_near_cap_token_runs_extract_promptly(unit):
    note = "osa " + unit * ((20_000 - 4) // len(unit))
    script = (
        "import time; from engine.extract import extract_facts; "
        f"started = time.perf_counter(); extract_facts({note!r}); "
        "elapsed = time.perf_counter() - started; "
        "assert elapsed < 0.5, f'Persistence trigger took {elapsed:.3f}s; per-boundary rescans may have returned'"
    )
    # Measured ~2.0 s before the fix and ~15 ms after; the outer deadline also catches a hang.
    subprocess.run([sys.executable, "-B", "-c", script], check=True, timeout=6.0)


def test_trigger_still_routes_a_persistence_cue_to_review():
    facts, _ = extract_facts("Low back pain 8 weeks. Radiculopathy no longer present. PT 6 weeks.")
    assert facts["back_pain_with_radiculopathy"] != True  # noqa: E712 - a cue must not yield an affirmative fact
