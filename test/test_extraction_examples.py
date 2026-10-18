import json

from experiments.dual_extraction import examples


def test_examples_match_and_show_both_original_sources_and_dispositions():
    assert examples.main(["--check"]) == 0
    records = examples.build_examples()
    proposal = records["phase2-recorded-proposal-example.json"]
    record = records["phase2-reconciliation-example.json"]
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
    assert calls == {"regex": 1, "recorded": 1}
    assert examples.main(["--write", "--output-dir", str(tmp_path)]) == 0
    assert examples.main(["--check", "--output-dir", str(tmp_path)]) == 0
    path = tmp_path / "phase2-reconciliation-example.json"
    assert json.loads(path.read_text()) == result[path.name]
    path.write_text("{}\n")
    assert examples.main(["--check", "--output-dir", str(tmp_path)]) == 1
