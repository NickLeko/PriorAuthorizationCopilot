"""Audit regression: unused settings cannot break startup; no deprecated clock call."""

import re
import warnings
from pathlib import Path

import cli
from engine.config import AppConfig, load_app_config
from engine.policy_monitor import utc_now_iso

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_unused_api_port_variable_cannot_break_configuration_loading(monkeypatch, capsys):
    monkeypatch.setenv("PA_COPILOT_API_PORT", "not-a-port")
    monkeypatch.setenv("PA_COPILOT_API_HOST", " ")

    load_app_config(REPO_ROOT)
    assert cli.main(["status"]) == 0
    assert capsys.readouterr().err == ""


def test_configuration_declares_no_settings_that_nothing_reads():
    assert not {"api_host", "api_port"} & set(AppConfig.model_fields)
    assert "PA_COPILOT_API_" not in (REPO_ROOT / ".env.example").read_text(encoding="utf-8")


def test_monitor_timestamp_keeps_its_format_without_deprecated_utcnow():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        stamp = utc_now_iso()

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp)
