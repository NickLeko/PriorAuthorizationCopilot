"""Audit regression: an unknown release ID is a caller error, not a server fault."""

import pytest
from fastapi.testclient import TestClient

import cli
from api import app
from engine.service import InvalidRequestError, ReadinessService

client = TestClient(app)
ACTIVE = "2026-08-22-active-v1.0"
MARKER = "CALLER_SUPPLIED_RELEASE_MARKER"


@pytest.mark.parametrize(
    "params", [{"from_release_id": MARKER, "to_release_id": ACTIVE}, {"from_release_id": ACTIVE, "to_release_id": MARKER}]
)
def test_unknown_release_id_is_a_client_error_and_is_not_reflected(params):
    response = client.get("/rulebook/diff", params=params)

    assert response.status_code == 400
    assert response.json() == {"error": "invalid_request", "detail": "Invalid request."}
    assert MARKER not in response.text


def test_service_reports_unknown_release_as_invalid_request():
    with pytest.raises(InvalidRequestError, match="Unknown rulebook release"):
        ReadinessService().get_rulebook_diff(MARKER, ACTIVE)


def test_cli_still_names_the_unknown_release_for_the_local_operator(capsys):
    assert cli.main(["rulebook-diff", "--from-release", MARKER, "--to-release", ACTIVE]) == 2
    assert f"Unknown rulebook release: {MARKER}" in capsys.readouterr().err
