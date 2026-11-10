"""Audit regression: a clean render must not pre-acknowledge later governance issues."""

from datetime import datetime, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from engine.acceptance import ACCEPTANCE_GOVERNANCE_NOW

APPTEST_TIMEOUT_SECONDS = 10
STALE_NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)  # past the monthly window of the bundled baseline


def test_drift_that_appears_mid_session_still_requires_acknowledgement(monkeypatch):
    monkeypatch.setattr("engine.service.utc_now", lambda: ACCEPTANCE_GOVERNANCE_NOW)
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py")
    at.run(timeout=APPTEST_TIMEOUT_SECONDS)
    assert not at.exception
    assert not at.checkbox  # nothing to acknowledge while the baseline is current

    monkeypatch.setattr("engine.service.utc_now", lambda: STALE_NOW)
    at.run(timeout=APPTEST_TIMEOUT_SECONDS)

    assert not at.exception
    assert any("require governance review" in warning.value for warning in at.warning)
    assert [checkbox.value for checkbox in at.checkbox] == [False]
    assert at.session_state["ack_policy_drift"] is False

    lumbar_button = next(button for button in at.button if button.key == "case_MRI-01-complete")
    lumbar_button.click().run(timeout=APPTEST_TIMEOUT_SECONDS)

    assert not at.exception
    assert any("Acknowledge the drift gate" in message.value for message in at.info)
    assert not at.session_state["last_eval_payload"]


def test_explicit_acknowledgement_still_unblocks_the_monitored_case(monkeypatch):
    monkeypatch.setattr("engine.service.utc_now", lambda: STALE_NOW)
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py")
    at.run(timeout=APPTEST_TIMEOUT_SECONDS)
    at.checkbox[0].check().run(timeout=APPTEST_TIMEOUT_SECONDS)
    lumbar_button = next(button for button in at.button if button.key == "case_MRI-01-complete")
    lumbar_button.click().run(timeout=APPTEST_TIMEOUT_SECONDS)

    assert not at.exception
    assert at.session_state["last_eval_payload"]["request"]["procedure_code"] == "MRI_LUMBAR"
