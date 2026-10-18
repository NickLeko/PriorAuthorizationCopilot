import json

from experiments.dual_extraction import examples


def test_examples_match_and_show_both_original_sources_and_dispositions():
    assert examples.main(["--check"]) == 0
    records = examples.build_examples()
    record = records[examples.CURRENT_EXAMPLE]
    proposal = record["recorded_llm"]
    key = "conservative_therapy_weeks"
    assert proposal["recording"]["origin"] == "hand_authored_synthetic"
    assert record["clinical_verification"] is False
    assert record["regex"]["snapshot"]["facts"][key] == 8
    assert record["recorded_llm"]["proposal"]["snapshot"]["facts"][key] == 6
    assert record["dual"]["snapshot"]["states"][key] == "NEEDS_REVIEW"
    assert next(item for item in record["comparisons"] if item["key"] == key)["reason"] == "VALUE_DISAGREEMENT"


def test_example_generation_is_explicit_repeatable_and_reuses_captures(tmp_path, monkeypatch):
    calls = {"regex": 0, "recorded": 0}
    regex, recorded = examples.extract_regex_proposal, examples.adapt_recorded_response

    def capture_regex(note):
        calls["regex"] += 1
        return regex(note)

    def capture_recorded(note, payload):
        calls["recorded"] += 1
        return recorded(note, payload)

    monkeypatch.setattr(examples, "extract_regex_proposal", capture_regex)
    monkeypatch.setattr(examples, "adapt_recorded_response", capture_recorded)
    result = examples.build_examples()
    assert calls == {"regex": 1, "recorded": 3}
    assert examples.main(["--write", "--output-dir", str(tmp_path)]) == 0
    assert examples.main(["--check", "--output-dir", str(tmp_path)]) == 0
    path = tmp_path / examples.CURRENT_EXAMPLE
    assert json.loads(path.read_text()) == result[examples.CURRENT_EXAMPLE]
    path.write_text("{}\n")
    assert examples.main(["--check", "--output-dir", str(tmp_path)]) == 1


def test_phase2_examples_are_preserved_and_review_examples_keep_both_sources(tmp_path):
    from hashlib import sha256

    before = {name: (examples.DIRECTORY / "artifacts" / name).read_bytes() for name in examples.HISTORICAL_HASHES}
    assert examples.main(["--write", "--output-dir", str(tmp_path)]) == 0
    for name, data in before.items():
        assert (examples.DIRECTORY / "artifacts" / name).read_bytes() == data
        assert sha256(data).hexdigest() == examples.HISTORICAL_HASHES[name]
        assert not (tmp_path / name).exists()
    for role in ("regex", "llm"):
        record = json.loads((tmp_path / f"phase3/review-required-{role}-example.json").read_text())
        cell = next(cell for cell in record["comparisons"] if cell["key"] == "cpb_0236_conservative_therapy_weeks")
        assert cell["reason"] == "REVIEW_REQUIRED"
        assert cell["evidence_source"] == "both"
        assert cell["dual_citation_sources"] == [["regex"], ["llm"]]
        assert not record["clinical_verification"]
