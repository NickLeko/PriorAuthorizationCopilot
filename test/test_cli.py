import json
from pathlib import Path

from cli import main


def test_cli_list_procedures(capsys):
    exit_code = main(["list-procedures"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "MRI_LUMBAR" in captured.out
    assert "MRI_CERVICAL" in captured.out
    assert "MRI_KNEE" in captured.out
    assert "category=advanced_imaging" in captured.out


def test_cli_evaluate_json(capsys):
    exit_code = main(["evaluate", "--demo-case", "CPAP-02-borderline", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["overall_status"] == "CANNOT_DETERMINE"


def test_cli_export_report(tmp_path: Path, capsys):
    output_path = tmp_path / "artifact.json"

    exit_code = main(
        [
            "export-report",
            "--demo-case",
            "MRI-01-complete",
            "--output",
            str(output_path),
            "--with-letter",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(output_path) in captured.out
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "READY"
    assert "letter" in payload


def test_cli_validate_demo_case(capsys):
    exit_code = main(["validate-demo-case", "--demo-case", "MRI-05-incomplete"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "demo_case=MRI-05-incomplete" in captured.out


def test_cli_list_demo_cases_includes_scenario_type(capsys):
    exit_code = main(["list-demo-cases"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "MRI-CERV-01-ready" in captured.out
    assert "expected_status=READY" in captured.out
    assert "New procedure coverage" in captured.out
    assert "MRI-KNEE-01-ready" in captured.out
    assert "Non-spine coverage" in captured.out


def test_cli_rulebook_status(capsys):
    exit_code = main(["rulebook-status"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "2026-08-22-active-v1.0" in captured.out


def test_cli_rulebook_diff(capsys):
    exit_code = main(
        [
            "rulebook-diff",
            "--from-release",
            "2026-04-09-reviewed-v0.4",
            "--to-release",
            "2026-08-22-active-v1.0",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Added procedures: Aetna:MRI_KNEE" in captured.out
