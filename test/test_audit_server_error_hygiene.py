"""Audit regression: broken governance files fail closed without leaking server paths."""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api
import cli
from engine.config import load_app_config
from engine.service import ReadinessService

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUEST = {"payer": "Aetna", "procedure_code": "CPAP_DEVICE", "note_text": "OSA."}


def copied_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for name in ("rules", "rulebook", "policy_snapshots", "inputs"):
        shutil.copytree(REPO_ROOT / name, root / name)
    return root


@pytest.fixture
def client_for(monkeypatch):
    def build(root: Path) -> TestClient:
        monkeypatch.setattr(api, "service", ReadinessService(load_app_config(root)))
        return TestClient(api.app, raise_server_exceptions=False)

    return build


@pytest.mark.parametrize(
    ("relative_path", "content"),
    [
        ("rules/payer_rules.yaml", "rules: [unclosed\n"),  # yaml.YAMLError
        ("rules/payer_rules.yaml", "- a list\n- not a mapping\n"),  # RulebookError carrying a path
        ("rules/policy_sources.yaml", "sources: 5\n"),  # ValueError
        ("rulebook/manifest.yaml", "a: [b\n"),
    ],
)
@pytest.mark.parametrize("path", ["/status", "/supported-procedures", "/rulebook", "/drift-status", "/evaluate"])
def test_broken_governance_files_return_the_error_envelope_without_paths(tmp_path, client_for, relative_path, content, path):
    root = copied_root(tmp_path)
    (root / relative_path).write_text(content, encoding="utf-8")
    client = client_for(root)

    response = client.post(path, json=REQUEST) if path == "/evaluate" else client.get(path)

    assert response.status_code == 500
    body = response.json()
    assert set(body) == {"error", "detail"}
    assert body["error"] in {"governance_config_error", "internal_error"}
    assert str(tmp_path) not in response.text and str(root.resolve()) not in response.text
    assert "Traceback" not in response.text


def test_rulebook_status_names_a_missing_release_file_relative_to_the_repository(tmp_path, client_for):
    root = copied_root(tmp_path)
    shutil.rmtree(root / "rulebook" / "releases" / "2026-04-09-reviewed-v0.4")

    response = client_for(root).get("/rulebook")

    assert response.status_code == 200
    errors = response.json()["validation_errors"]
    assert any("rulebook/releases/2026-04-09-reviewed-v0.4/" in error for error in errors)
    assert str(tmp_path) not in response.text and str(root.resolve()) not in response.text


def test_unreadable_drift_log_requires_review_without_exposing_its_location(tmp_path, client_for):
    root = copied_root(tmp_path)
    (root / "policy_snapshots" / "drift_log.jsonl").mkdir()

    response = client_for(root).get("/drift-status")

    assert response.status_code == 200
    source = response.json()["sources"][0]
    assert source["status"] == "INVALID_DRIFT_LOG"  # unchanged fail-closed status
    assert "Policy drift log could not be read" in source["review_reason"]
    assert str(tmp_path) not in response.text and str(root.resolve()) not in response.text


def test_cli_reports_malformed_yaml_as_a_controlled_error(tmp_path, monkeypatch, capsys):
    bad_rules = tmp_path / "bad_rules.yaml"
    bad_rules.write_text("rules: [unclosed\n", encoding="utf-8")
    monkeypatch.setenv("PA_COPILOT_RULES_PATH", str(bad_rules))

    assert cli.main(["status"]) == 2
    assert capsys.readouterr().err.strip()
