"""Audit regression: malformed review projections raise ValidationError, never raw lookups."""

import copy

import pytest
from pydantic import ValidationError

from engine.rendering import export_evaluation_payload
from engine.schemas import EvaluationResult, PARequest
from engine.service import ReadinessService


@pytest.fixture(scope="module")
def projection():
    # 500 mentions exceed the stored-evidence cap, so the projection carries evidence_counts.
    result = ReadinessService().evaluate(PARequest(payer="Aetna", procedure_code="CPAP_DEVICE", note_text="osa " * 500))
    payload = export_evaluation_payload(result, include_citation_context=True)
    assert "evidence_counts" in payload
    EvaluationResult.model_validate(payload)
    return payload


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.pop("original_snapshot"),
        lambda payload: payload.pop("request"),
        lambda payload: payload.pop("results"),
        lambda payload: payload.__setitem__("results", [{}]),
        lambda payload: payload.__setitem__("results", [1]),
        lambda payload: payload.__setitem__("results", 5),
        lambda payload: payload.__setitem__("results", [{"key": {"unhashable": True}}]),
    ],
)
def test_malformed_projection_with_evidence_counts_is_a_validation_error(projection, mutate):
    payload = copy.deepcopy(projection)
    mutate(payload)

    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(payload)
