"""Label schema, harness accounting and the committed baseline report."""

import json
from hashlib import sha256

import pytest
from pydantic import ValidationError

from evaluation import report as report_module
from evaluation.harness import evaluate_dataset
from evaluation.schema import DATASET_DIR, REPO_ROOT, Dataset, HoldoutSealedError, RequirementLabel, load_dataset, note_sha256

NOTE = "Low back pain with radiculopathy. NSAIDs for 8 weeks with no improvement."
PROVENANCE = {
    "author_type": "agent",
    "author": "test",
    "authored_on": "2026-11-16",
    "blind_to_extractor_output": True,
    "basis": "test",
}
HOLDOUT_NOTE_DIGEST = "906f1f6809f177fae75ade4cbc2ec2ab6edd02516815a8364c4cd07a6a8591d5"


def label(**overrides):
    base = {
        "requirement_key": "a",
        "review_status": "provisional",
        "expected_state": "MET",
        "evidence_quote": "NSAIDs for 8 weeks",
        "rationale": "r",
        "uncertainty": "low",
    }
    return {**base, **overrides}


def dataset(labels, **overrides):
    payload = {
        "dataset_id": "t",
        "dataset_version": 1,
        "split": "challenge",
        "description": "d",
        "note_authorship": "synthetic",
        "selection": "hand-picked",
        "label_defaults": PROVENANCE,
        "cases": [
            {
                "case_id": "c1",
                "payer": "Aetna",
                "procedure_code": "X",
                "note_sha256": note_sha256(NOTE),
                "note_text": NOTE,
                "labels": labels,
            }
        ],
    }
    return {**payload, **overrides}


def write(tmp_path, payload):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_an_agent_cannot_mark_a_label_verified():
    with pytest.raises(ValidationError):
        RequirementLabel.model_validate(label(review_status="verified"))
    with pytest.raises(ValidationError):
        RequirementLabel.model_validate(
            label(review_status="provisional", reviewer="Someone", reviewer_type="human", reviewed_on="2026-11-16")
        )
    verified = RequirementLabel.model_validate(
        label(review_status="verified", reviewer="A Reviewer", reviewer_type="human", reviewed_on="2026-11-17")
    )
    assert verified.acceptable_states == ["MET"]


def test_scored_labels_need_a_state_and_cited_text_and_review_labels_need_a_question():
    with pytest.raises(ValidationError):
        RequirementLabel.model_validate(label(expected_state=None))
    with pytest.raises(ValidationError):
        RequirementLabel.model_validate(label(evidence_quote=None))
    with pytest.raises(ValidationError):
        RequirementLabel.model_validate(label(acceptable_states=["NOT_MET"]))
    with pytest.raises(ValidationError):
        RequirementLabel.model_validate(label(review_status="needs_review"))
    with pytest.raises(ValidationError):
        RequirementLabel.model_validate(label(review_status="needs_review", uncertainty_note="q", acceptable_states=["MET"]))
    assert RequirementLabel.model_validate(label(expected_state="NOT_DOCUMENTED", evidence_quote=None)).acceptable_states == [
        "NOT_DOCUMENTED"
    ]
    assert Dataset.model_validate(dataset([])).independent_clinical_ground_truth is False
    with pytest.raises(ValidationError):
        Dataset.model_validate(dataset([], independent_clinical_ground_truth=True))


def test_labels_are_bound_to_the_exact_note_text(tmp_path):
    with pytest.raises(ValueError, match="not an exact substring"):
        load_dataset(write(tmp_path, dataset([label(evidence_quote="NSAIDs for 9 weeks")])))
    changed = dataset([label()])
    changed["cases"][0]["note_text"] = NOTE + " Addendum."
    with pytest.raises(ValueError, match="changed since labeling"):
        load_dataset(write(tmp_path, changed))


def test_a_holdout_is_sealed_unlabeled_and_refused_by_default(tmp_path):
    sealed = dataset([], split="holdout", sealed=True)
    with pytest.raises(HoldoutSealedError):
        load_dataset(write(tmp_path, sealed))
    assert len(load_dataset(write(tmp_path, sealed), allow_sealed_holdout=True).cases) == 1
    with pytest.raises(ValidationError):
        Dataset.model_validate(dataset([], split="holdout", sealed=False))
    with pytest.raises(ValidationError):
        Dataset.model_validate(dataset([label()], split="holdout", sealed=True))


def test_the_committed_holdout_is_unchanged_unlabeled_and_absent_from_the_report():
    path = DATASET_DIR / "holdout_v1.json"
    with pytest.raises(HoldoutSealedError):
        load_dataset(path)
    holdout = load_dataset(path, allow_sealed_holdout=True)
    assert len(holdout.cases) == 10 and not any(case.labels for case in holdout.cases)
    assert sha256("".join(case.note_sha256 for case in holdout.cases).encode()).hexdigest() == HOLDOUT_NOTE_DIGEST
    committed = json.loads((report_module.OUTPUT_DIR / "requirement_level_baseline.json").read_text(encoding="utf-8"))
    assert committed["sealed_holdouts"]["holdout_v1"]["evaluated"] is False
    assert "holdout_v1" not in committed["datasets"]
    assert "HO-01" not in json.dumps(committed["datasets"])


def fake_predictor(statuses, overall="CANNOT_DETERMINE"):
    def predict(case):
        return {
            "overall_status": overall,
            "requirements": {key: {"status": status, "fact_value": None, "evidence_spans": []} for key, status in statuses.items()},
        }

    return predict


def test_missing_and_unreviewed_labels_are_never_counted_as_agreement(tmp_path):
    labels = [
        label(requirement_key="a"),
        label(requirement_key="b", review_status="needs_review", uncertainty_note="Which course?"),
        label(requirement_key="orphan"),
    ]
    data = load_dataset(write(tmp_path, dataset(labels)))
    result = evaluate_dataset(data, fake_predictor({"a": "MET", "b": "MET", "c": "MET"}, overall="PENDING_VERIFICATION"))
    assert result["requirement_slots"] == 3
    assert result["tiers"]["provisional"]["aggregate"]["scored_labels"] == 1
    assert result["tiers"]["verified"]["aggregate"]["scored_labels"] == 0
    assert result["tiers"]["verified"]["aggregate"]["utility_flags"] == ["NO_SCORED_LABELS"]
    assert result["unlabeled_requirements"] == [{"case_id": "c1", "requirement_key": "c"}]
    assert [row["requirement_key"] for row in result["unscored_needs_review"]] == ["b"]
    assert result["labels_without_matching_requirement"] == [{"case_id": "c1", "requirement_key": "orphan"}]
    # A case with any unscored requirement cannot count toward case-level results.
    assert result["case_level"]["fully_scored_cases"] == 0
    assert result["case_level"]["missed_all_met"]["denominator"] == 0


def test_a_false_met_is_reported_even_when_another_blocker_hides_it_at_case_level(tmp_path):
    labels = [label(requirement_key="a", expected_state="NOT_DOCUMENTED", evidence_quote=None), label(requirement_key="b")]
    data = load_dataset(write(tmp_path, dataset(labels)))
    result = evaluate_dataset(data, fake_predictor({"a": "MET", "b": "NOT_DOCUMENTED"}))
    aggregate = result["tiers"]["provisional"]["aggregate"]
    assert (aggregate["false_met"]["numerator"], aggregate["missed_met"]["numerator"]) == (1, 1)
    assert result["case_level"]["false_met_hidden_by_another_blocker"]["case_ids"] == ["c1"]
    assert result["case_level"]["false_all_met"]["numerator"] == 0
    assert {row["error_class"] for row in result["observed_failures"]} == {"FALSE_MET", "MISSED_MET"}


def test_ready_is_reported_as_unreachable_not_as_a_zero_rate(tmp_path):
    data = load_dataset(write(tmp_path, dataset([label()])))
    ready = evaluate_dataset(data, fake_predictor({"a": "MET"}, overall="PENDING_VERIFICATION"))["case_level"]["ready"]
    assert ready["reachable"] is False and ready["observed"] == 0
    assert "rate" not in ready and "denominator" not in ready


@pytest.fixture(scope="module")
def baseline():
    return report_module.build_report()


def test_committed_reports_match_the_current_extractor_and_labels():
    for path, content in report_module.outputs().items():
        assert path.read_text(encoding="utf-8") == content, f"Run: python -m evaluation.report ({path.name})"


def test_baseline_states_its_limits_and_makes_no_population_estimate(baseline):
    assert baseline["population_error_rate_estimate"] is None
    text = report_module.render_markdown(baseline)
    for phrase in ("No label has been reviewed by a human", "synthetic", "no population-level error rate", "READY: not reachable"):
        assert phrase in text
    for data in baseline["datasets"].values():
        assert data["independent_clinical_ground_truth"] is False
        assert data["label_counts"]["verified"] == 0
        assert data["tiers"]["verified"]["aggregate"]["scored_labels"] == 0
        assert not data["unlabeled_requirements"] and not data["labels_without_matching_requirement"]
        assert data["case_level"]["ready"]["observed"] == 0


def test_bundled_corpus_baseline_is_scored_per_requirement(baseline):
    corpus = baseline["datasets"]["corpus52"]
    assert (corpus["cases"], corpus["requirement_slots"]) == (52, 197)
    assert corpus["label_counts"] == {"verified": 0, "provisional": 193, "needs_review": 4}
    aggregate = corpus["tiers"]["provisional"]["aggregate"]
    assert (aggregate["false_met"]["numerator"], aggregate["false_met"]["denominator"]) == (0, 94)
    assert (aggregate["met_recall"]["numerator"], aggregate["met_recall"]["denominator"]) == (96, 96)
    # Zero false MET does not distinguish the extractor from one that asserts nothing; recall does.
    abstain = corpus["tiers"]["provisional"]["controls"]["ALWAYS_NOT_DOCUMENTED"]
    assert abstain["false_met"]["numerator"] == aggregate["false_met"]["numerator"] == 0
    assert abstain["met_recall"]["numerator"] == 0 and abstain["meets_minimum_utility"] is False
    assert aggregate["meets_minimum_utility"] is True


def test_known_lumbar_failures_are_represented_as_measured_baseline_failures(baseline):
    """Pins the pre-fix baseline. A Phase 2 extraction change is expected to update these deliberately."""
    challenge = baseline["datasets"]["challenge_v1"]
    observed = {(row["case_id"], row["requirement_key"]): row["error_class"] for row in challenge["observed_failures"]}
    weeks, response = "cpb_0236_conservative_therapy_weeks", "cpb_0236_conservative_therapy_no_improvement"
    exam = "objective_motor_or_reflex_change_in_root_distribution"
    expected = {
        ("CH-02-missed-nsaids", weeks): "FALSE_MET",
        ("CH-02-missed-nsaids", response): "FALSE_MET",
        ("CH-03-nsaids-2019", weeks): "FALSE_MET",
        ("CH-04-initially-none-now-improved", response): "FALSE_MET",
        ("CH-05-intermittent-adherence", weeks): "FALSE_MET",
        ("CH-06-historical-exam", exam): "FALSE_MET",
        ("CH-07-natural-two-months", weeks): "MISSED_MET",
        ("CH-08-natural-x-8-wks-failed", weeks): "MISSED_MET",
        ("CH-10-natural-dorsiflexion-l5", exam): "MISSED_MET",
    }
    assert {key: observed.get(key) for key in expected} == expected
    unscored = {(row["case_id"], row["requirement_key"]): row["observed_state"] for row in challenge["unscored_needs_review"]}
    assert unscored[("CH-09-natural-ehl", exam)] == "NOT_DOCUMENTED"
    aggregate = challenge["tiers"]["provisional"]["aggregate"]
    assert (aggregate["false_met"]["numerator"], aggregate["false_met"]["denominator"]) == (13, 17)
    assert (aggregate["missed_met"]["numerator"], aggregate["missed_met"]["denominator"]) == (11, 59)
    assert challenge["case_level"]["false_all_met"]["numerator"] == 7


def test_a_case_added_to_the_note_file_cannot_go_silently_unlabeled(tmp_path, monkeypatch):
    notes = tmp_path / "notes.json"
    notes.write_text(json.dumps([{"id": "c1", "note_text": NOTE}, {"id": "c2", "note_text": "New case."}]), encoding="utf-8")
    payload = dataset([label()], notes_source="notes.json")
    del payload["cases"][0]["note_text"]
    data = load_dataset(write(tmp_path, payload), repo_root=tmp_path)
    monkeypatch.setattr("evaluation.harness.source_case_ids", lambda dataset: ["c1", "c2"])
    assert evaluate_dataset(data, fake_predictor({"a": "MET"}))["unlabeled_source_cases"] == ["c2"]


def test_blocker_depth_shows_where_a_single_false_met_would_stay_hidden(baseline):
    depth = baseline["datasets"]["corpus52"]["case_level"]["blocker_depth"]
    assert (depth["single_blocker_cases"], depth["denominator"]) == (19, 42)
    assert sum(depth["cases_by_blocking_requirements"].values()) == depth["denominator"]
    assert baseline["datasets"]["corpus52"]["unlabeled_source_cases"] == []


def test_challenge_results_are_never_rendered_as_percentages(baseline):
    text = report_module.render_markdown(baseline)
    challenge = text.split("## Dataset `challenge_v1`")[1].split("## Sealed holdouts")[0]
    assert "%" not in challenge
    assert "13 of 17" in challenge and "known failures, not rates" in challenge
    assert "say nothing about real-world or clinical performance" in text


def test_decision_packet_is_compact_blind_and_quotes_the_stored_policy(baseline):
    spec = json.loads((DATASET_DIR / "decision_packet_v1.json").read_text(encoding="utf-8"))
    selected = {(entry["dataset"], entry["case_id"], entry["requirement_key"]) for entry in spec["entries"]}
    assert len(selected) == len(spec["entries"]) == 37
    # Every baseline failure and every open question is in the first review pass.
    for dataset_id, data in baseline["datasets"].items():
        for row in data["observed_failures"] + data["unscored_needs_review"]:
            assert (dataset_id, row["case_id"], row["requirement_key"]) in selected
    assert not any(entry["dataset"] == "holdout_v1" for entry in spec["entries"])
    packet = report_module.render_decision_packet()
    for forbidden in ("observed", "Observed", "FALSE_MET", "MISSED_MET", "predicted", "HO-0"):
        assert forbidden not in packet
    assert packet.count("- Decision: state") == 37
    assert "not clinical validation" in packet
    snapshot = json.loads((REPO_ROOT / "policy_snapshots/aetna_mri_lumbar/latest.json").read_text(encoding="utf-8"))["normalized_text"]
    for wording in (report_module.CPB_0236_CRITERION, report_module.CPB_0236_FOOTNOTE_1):
        assert wording in snapshot and wording in packet


def test_labeling_packet_keeps_the_reviewer_blind_to_extractor_output():
    rows = report_module.build_packet_rows()
    assert not any("observed" in column or "predicted" in column for column in report_module.PACKET_COLUMNS)
    assert sum(1 for row in rows if row["priority"] == "1-decide") == 6
    assert sum(1 for row in rows if row["dataset"] == "holdout_v1") == 10
    assert all(row["reviewer_state"] == "" and row["reviewer_name"] == "" for row in rows)
    assert (REPO_ROOT / "docs/evaluation/labeling_packet.csv").exists()
