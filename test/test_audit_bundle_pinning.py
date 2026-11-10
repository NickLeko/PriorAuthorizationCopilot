"""Audit regression: a public read is served from one rulebook bundle snapshot."""

import pytest

from engine.service import GovernanceConfigError, ReadinessService

READS = {
    "get_status": lambda service: service.get_status(),
    "list_supported_procedures": lambda service: service.list_supported_procedures(),
    "get_supported_procedure": lambda service: service.get_supported_procedure("Aetna", "CPAP_DEVICE"),
    "get_drift_status": lambda service: service.get_drift_status(),
}


@pytest.mark.parametrize("name", READS)
def test_public_read_takes_exactly_one_bundle_snapshot(monkeypatch, name):
    service = ReadinessService()
    expected = READS[name](service)
    snapshots = []
    take_snapshot = service._bundle_snapshot
    monkeypatch.setattr(service, "_bundle_snapshot", lambda: snapshots.append(1) or take_snapshot())

    assert READS[name](service) == expected
    assert len(snapshots) == 1


def test_pinning_does_not_outlive_the_call():
    service = ReadinessService()
    service.get_status()

    assert service._evaluation_bundle.get() is None


def test_pinning_is_released_when_the_read_fails():
    service = ReadinessService()
    with pytest.raises(Exception):
        service.get_supported_procedure("Aetna", "NOT_A_PROCEDURE")

    assert service._evaluation_bundle.get() is None


def test_evaluate_still_rechecks_the_bundle_at_the_end(monkeypatch):
    """The end-of-evaluation change detection must keep reading fresh state."""
    service = ReadinessService()
    request = service.get_demo_case_request("MRI-01-complete")
    original = service._bundle_digest
    calls = []

    def digest():
        calls.append(1)
        # First call pins the evaluation; the final call simulates a concurrent edit.
        return original() if len(calls) == 1 else "changed-after-start"

    monkeypatch.setattr(service, "_bundle_digest", digest)
    with pytest.raises(GovernanceConfigError, match="Rulebook changed during evaluation"):
        service.evaluate(request)
