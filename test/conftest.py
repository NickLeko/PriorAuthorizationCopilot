from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.acceptance import ACCEPTANCE_GOVERNANCE_NOW  # noqa: E402 -- repository path is established above

GOVERNANCE_NOW = ACCEPTANCE_GOVERNANCE_NOW


@pytest.fixture(autouse=True)
def fixed_governance_clock(monkeypatch):
    # Only successful-check freshness is pinned. Runtime defaults to real UTC;
    # audit, correction and attestation timestamps retain their real clocks.
    monkeypatch.setattr("engine.service.utc_now", lambda: GOVERNANCE_NOW)
