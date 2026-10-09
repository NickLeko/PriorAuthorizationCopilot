"""Deployment update regressions, isolated from pytest's engine imports."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def test_retained_service_survives_mixed_engine_module_loads():
    script = textwrap.dedent(
        """
        import importlib
        import sys
        from unittest.mock import patch
        from pydantic import ValidationError
        from engine.service import ReadinessService

        cached = ReadinessService()
        request = cached.get_demo_case_request("MRI-01-complete")
        baseline = cached.evaluate(request)
        for name in list(sys.modules):
            if name == "engine" or name.startswith("engine."):
                del sys.modules[name]
        current = importlib.import_module("engine.service")
        equal_values = current.EvaluationMetrics(**baseline.metrics.model_dump())
        assert type(baseline.metrics) is not type(equal_values)
        assert baseline.metrics != equal_values
        assert baseline.metrics.model_dump() == equal_values.model_dump()
        result = cached.evaluate(request)
        assert result.overall_status == "PENDING_VERIFICATION"
        assert result.metrics.model_dump() == baseline.metrics.model_dump()
        note = (
            "Low back pain with right leg radiculopathy. NSAIDs for 8 weeks with no improvement in sleep "
            "but significant improvement in pain. Ankle dorsiflexion strength 4/5 in the right L5 distribution."
        )
        assert cached.evaluate(request.model_copy(update={"note_text": note})).overall_status == "NEEDS_REVIEW"
        fresh = current.ReadinessService()
        assert fresh.evaluate(fresh.get_demo_case_request("MRI-01-complete")).overall_status == "PENDING_VERIFICATION"
        compute = current._compute_metrics
        with patch.object(current, "_compute_metrics", side_effect=lambda summary:
                compute(summary).model_copy(update={"criteria_met_count": -1})):
            try:
                cached.evaluate(request)
            except ValidationError as exc:
                assert "Metrics disagree with validated requirement results" in str(exc)
            else:
                raise AssertionError("Different metric values must still be rejected")
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_streamlit_version_guard_checks_disk_on_every_rerun(monkeypatch):
    at = AppTest.from_file("app.py").run(timeout=15)
    assert not at.exception
    next(button for button in at.button if button.key == "case_MRI-01-complete").click().run(timeout=15)
    assert not at.exception
    assert at.session_state["last_eval_payload"]["overall_status"] == "PENDING_VERIFICATION"
    read_text = Path.read_text

    def newer_release(path, *args, **kwargs):
        if path == Path("engine/__init__.py").resolve():
            # Simulate a newer release than the version under test.
            return '__version__ = "2.1.4"\n'
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", newer_release)
    with patch("engine.service.ReadinessService.evaluate") as evaluate:
        at.run(timeout=15)
        assert not at.exception
        assert [item.value for item in at.error] == ["App code was updated; the server needs a restart"]
        assert not at.button  # Stop before any evaluation or review controls render.
        evaluate.assert_not_called()
        fresh_session = AppTest.from_file("app.py").run(timeout=15)
        assert not fresh_session.exception
        assert [item.value for item in fresh_session.error] == ["App code was updated; the server needs a restart"]
        assert not fresh_session.button
        evaluate.assert_not_called()
