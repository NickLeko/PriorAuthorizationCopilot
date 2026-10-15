"""Reviewer context is visible, literal, and separate from decision semantics."""

from streamlit.testing.v1 import AppTest
from test_v200_surfaces import load_request

from engine.citation_context import citation_window

N1B = (
    "Prior visit note (2019): low back pain with radiculopathy, right L5 distribution strength 4/5, "
    "NSAIDs for 8 weeks with no improvement. Today: asymptomatic."
)
N1 = (
    "PREVIOUS NOTE (2019): low back pain with radiculopathy, right L5 distribution strength 4/5, "
    "NSAIDs for 8 weeks with no improvement. TODAY: asymptomatic."
)
CAPTION = "Context shown is an aid; read the full note before attesting."


def evaluated_app(note):
    at = AppTest.from_file("app.py", default_timeout=30).run()
    load_request(at, "MRI-01-complete", note)
    return at


def verification_form(at):
    return next(form for form in at.get("form") if form.proto.form.form_id == "fact_verification_form")


def test_n1b_shows_following_contradiction_for_all_four_attestations():
    at = evaluated_app(N1B)
    payload = at.session_state["last_eval_payload"]
    assert len(payload["results"]) == 4
    assert all(result["status"] == "MET" for result in payload["results"])
    assert payload["overall_status"] == "PENDING_VERIFICATION"
    form = verification_form(at)
    contexts = [text.value for text in form.text if "⟦" in text.value]
    assert len(contexts) == 4
    for result, context in zip(payload["results"], contexts, strict=True):
        span = result["evidence_spans"][0]
        assert context == citation_window(N1B, span["start"], span["end"])
        assert "Today: asymptomatic." in context
    assert len(form.checkbox) == 4
    children = list(form.children.values())
    for i, element in enumerate(children):
        if element.type == "checkbox":
            assert children[i - 1].type == "caption"
            assert children[i - 1].value == CAPTION
    original = next(expander for expander in at.expander if expander.label == "Original note for this evaluation")
    assert original.proto.expanded is True
    assert [text.value for text in original.text] == [N1B]
    for expander in at.expander:
        if expander.label.startswith("Correct "):
            windows = [text.value for text in expander.text if "⟦" in text.value]
            assert len(windows) == 2  # effective and original citations
            assert all("Today: asymptomatic." in window for window in windows)


def test_original_n1_attestation_view_renders_review_required_facts():
    at = evaluated_app(N1)
    assert at.session_state["last_eval_payload"]["overall_status"] == "NEEDS_REVIEW"
    contexts = [text.value for text in verification_form(at).text if "⟦" in text.value]
    assert len(contexts) == 4
    assert all("TODAY: asymptomatic." in context for context in contexts)


def test_markdown_link_in_citation_window_is_literal_text():
    link = "[link](https://example.com)"
    note = N1B.replace("no improvement.", f"no improvement {link}.")
    at = evaluated_app(note)
    contexts = [text.value for text in verification_form(at).text if "⟦" in text.value]
    assert contexts
    assert all(link in context.replace("⟦", "").replace("⟧", "") for context in contexts)
    assert not any(link in markdown.value for markdown in at.markdown)


def test_oversized_citation_shows_literal_notice_and_expanded_full_note():
    note = N1B.replace("no improvement.", "no improvement" + " x" * 600 + ".")
    at = evaluated_app(note)
    form = verification_form(at)
    notices = [text.value for text in form.text if "too long for the context window" in text.value]
    assert len(notices) == 4
    original = next(expander for expander in at.expander if expander.label == "Original note for this evaluation")
    assert original.proto.expanded is True
    assert [text.value for text in original.text] == [note]
