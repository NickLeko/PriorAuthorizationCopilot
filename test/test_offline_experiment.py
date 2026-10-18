import json
import shutil
from hashlib import sha256

import pytest

from engine.decision_store import DecisionStore
from experiments.dual_extraction import runner
from experiments.dual_extraction.errors import ExperimentFailure


def test_default_coverage_and_three_mode_outputs_are_explicit_and_reproducible():
    report = runner.build_report()
    assert report == runner.build_report()
    coverage = report["coverage"]
    assert coverage["eligible_synthetic_cases"] == 177
    assert coverage["policy_supported_cases"] == 148
    assert coverage["incomplete_policy_scope_cases"] == 29
    assert coverage["valid_recordings"] == 4
    assert coverage["without_recordings"] == 173
    assert coverage["rejected_recordings"] == 0
    assert coverage["successful_three_mode_cases"] == 3
    assert coverage["extraction_only_compared_cases"] == 1
    assert len(report["cases"]) == 177
    for record in report["cases"]:
        if record["recording_status"] == "ABSENT":
            assert record["comparison"] is None and record["evaluations"] is None
        elif record["scope"] == "INCOMPLETE":
            assert record["comparison"] is not None and record["evaluations"] is None
        else:
            assert set(record["evaluations"]) == {"regex_only", "llm_only", "dual"}
            assert record["downstream"] is not None
            for result in record["evaluations"].values():
                assert not result["request"]["fact_verifications"]
                assert all(item["verification"]["state"] == "UNVERIFIED" for item in result["results"])
    assert report["metrics"]["value_agreement_rate"]["denominator"] > 0
    assert report["metrics"]["state_disagreement_rate"]["denominator"] == 48
    assert report["metrics"]["downstream_requirement_status_difference_rate"]["denominator"] == 11


def test_shared_error_is_labeled_and_never_automatically_ready():
    report = runner.build_report()
    case = next(case for case in report["cases"] if case["demonstration"] == "known_shared_error")
    key = "back_pain_with_radiculopathy"
    item = next(item for item in case["comparison"]["comparisons"] if item["key"] == key)
    assert item["reason"] == "AGREED_CAPTURE"
    assert case["comparison"]["dual"]["facts"][key] is True
    assert case["comparison"]["clinical_verification"] is False
    assert case["known_failure"]
    assert all(result["overall_status"] == "PENDING_VERIFICATION" for result in case["evaluations"].values())
    assert report["coverage"]["known_shared_error_demonstrations"] == 1


def test_no_recapture_no_archive_writes_and_same_captures_reused(monkeypatch):
    import engine.extract
    import engine.service
    import experiments.dual_extraction.recorded as recorded

    def forbidden(*args, **kwargs):
        raise AssertionError("Source recapture or archive write is forbidden.")

    monkeypatch.setattr(engine.extract, "extract_facts", forbidden)
    monkeypatch.setattr(engine.service, "extract_facts", forbidden)
    monkeypatch.setattr(recorded, "adapt_recorded_response", forbidden)
    monkeypatch.setattr(DecisionStore, "record", forbidden)
    counts = {"load": 0, "reconcile": 0}
    load, reconcile = runner.load_recording, runner.reconcile

    def counted_load(*args):
        counts["load"] += 1
        return load(*args)

    def counted_reconcile(*args):
        counts["reconcile"] += 1
        return reconcile(*args)

    monkeypatch.setattr(runner, "load_recording", counted_load)
    monkeypatch.setattr(runner, "reconcile", counted_reconcile)
    assert runner.build_report()["coverage"]["successful_three_mode_cases"] == 3
    assert counts == {"load": 4, "reconcile": 4}


def test_missing_malformed_and_integrity_coverage_do_not_become_clinical_missingness(tmp_path):
    root = tmp_path / "fixtures"
    shutil.copytree(runner.DEFAULT_MANIFEST.parent, root)
    path = root / "manifest.json"
    manifest = json.loads(path.read_text())
    entries = manifest["recordings"]
    (root / entries[0]["path"]).unlink()
    (root / entries[1]["path"]).write_text("tampered")
    malformed = root / entries[3]["path"]
    malformed.write_text("not JSON")
    entries[3]["stored_sha256"] = sha256(malformed.read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest))
    report = runner.build_report(manifest_path=path)
    coverage = report["coverage"]
    assert coverage["valid_recordings"] == 1
    assert coverage["without_recordings"] == 174
    assert coverage["missing_recording_files"] == 1
    assert coverage["malformed_recordings"] == coverage["integrity_failures"] == 1
    assert coverage["rejected_recordings"] == 2
    assert coverage["successful_three_mode_cases"] == 1
    for case in report["cases"]:
        if case["recording_status"] != "VALID":
            assert case["comparison"] is None and case["evaluations"] is None
    legacy = report["response_accounting"]["hand_authored_adapted"]
    assert legacy["malformed_recordings"] == legacy["integrity_failures"] == 1
    assert report["response_accounting"]["actual_model"]["invalid_recorded_response_rate"]["denominator"] == 0


def test_inputs_and_sources_are_not_mutated_and_case_order_is_frozen():
    paths = [runner.BASELINE_PATH, runner.DEFAULT_MANIFEST, *runner.DEFAULT_MANIFEST.parent.glob("recordings/*.json")]
    before = {path: path.read_bytes() for path in paths}
    report = runner.build_report()
    assert before == {path: path.read_bytes() for path in paths}
    expected = [json.loads(line)["case_id"] for line in runner.BASELINE_PATH.read_text().splitlines()[1:]]
    assert [case["case_id"] for case in report["cases"]] == expected


def test_frozen_baseline_tamper_is_not_accepted(tmp_path, monkeypatch):
    path = tmp_path / "baseline.jsonl"
    path.write_bytes(runner.BASELINE_PATH.read_bytes() + b"\n")
    monkeypatch.setattr(runner, "BASELINE_PATH", path)
    with pytest.raises(ExperimentFailure, match="INVALID_FROZEN_BASELINE"):
        runner.build_report()


def test_note_bound_reuse_and_unsupported_scope_are_explicit():
    report = runner.build_report()
    row = next(row for row in report["cases"] if row["recording_status"] == "VALID")
    frozen = next(row for row in runner.load_frozen_baseline()[1:] if row["case_id"] == row_id(report))
    proposal = runner.baseline_proposal(frozen)
    with pytest.raises(ExperimentFailure, match="NOTE_MISMATCH"):
        runner.bound_extraction(proposal)(proposal.note_text + " ")
    assert row["note_sha256"]
    assert runner.policy_scope({"request_metadata": {"payer": "Aetna"}}) == "INCOMPLETE"
    modified = dict(frozen)
    modified["request_metadata"] = frozen["request_metadata"] | {"procedure_code": "UNSUPPORTED"}
    assert runner.policy_scope(modified) == "UNSUPPORTED"


def row_id(report):
    return next(case["case_id"] for case in report["cases"] if case["recording_status"] == "VALID" and case["scope"] == "SUPPORTED")


def test_explicit_regeneration_check_and_no_partial_writes_on_failure(tmp_path, capsys):
    output = tmp_path / "results"
    assert runner.main(["--write", "--output-dir", str(output)]) == 0
    assert runner.main(["--check", "--output-dir", str(output)]) == 0
    assert "Hand-authored" in (output / "summary.md").read_text()
    assert (output / "three-mode-example.json").exists()
    assert (output / "correlated-error-example.json").exists()
    (output / "comparisons.json").write_text("{}\n")
    assert runner.main(["--check", "--output-dir", str(output)]) == 1
    missing = tmp_path / "missing-manifest.json"
    assert runner.main(["--write", "--manifest", str(missing), "--output-dir", str(tmp_path / "untouched")]) == 1
    assert not (tmp_path / "untouched").exists()
    assert "INVALID_RECORDING_MANIFEST" in capsys.readouterr().out


def test_zero_coverage_has_no_fake_agreement_or_stale_examples(tmp_path):
    manifest = json.loads(runner.DEFAULT_MANIFEST.read_text())
    manifest["recordings"] = []
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    report = runner.build_report(manifest_path=path)
    assert report["coverage"]["without_recordings"] == 177
    assert report["coverage"]["successful_three_mode_cases"] == 0
    assert all(metric["percent"] is None for metric in report["metrics"].values())
    output = tmp_path / "results"
    assert runner.main(["--write", "--output-dir", str(output)]) == 0
    assert runner.main(["--write", "--manifest", str(path), "--output-dir", str(output)]) == 0
    assert json.loads((output / "three-mode-example.json").read_text()) is None
    assert json.loads((output / "correlated-error-example.json").read_text()) is None


def test_changed_bundle_context_aborts_before_artifact_writes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner.ReadinessService, "_bundle_digest", lambda self: "0" * 64)
    assert runner.main(["--write", "--output-dir", str(tmp_path / "results")]) == 1
    assert not (tmp_path / "results").exists()
    assert "EXPERIMENT_CONTEXT_CHANGED" in capsys.readouterr().out


def test_manifest_unknown_case_is_not_assigned_invented_scope(tmp_path):
    manifest = json.loads(runner.DEFAULT_MANIFEST.read_text())
    manifest["recordings"][0]["case_id"] = "invented-case"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ExperimentFailure, match="INVALID_RECORDING_MANIFEST"):
        runner.build_report(manifest_path=path)
