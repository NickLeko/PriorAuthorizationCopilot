from __future__ import annotations

import json
import math

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from engine import __version__
from engine.schemas import (
    DemoCase,
    DriftStatusReport,
    ErrorResponse,
    EvaluationResult,
    PARequest,
    RulebookDiffResponse,
    RulebookStatusResponse,
    StatusResponse,
    SupportedProcedure,
)
from engine.service import InvalidRequestError, ReadinessService, ServiceError, UnsupportedScopeError

app = FastAPI(
    title="Prior Authorization Readiness Copilot API",
    version=__version__,
    description=(
        "Deterministic administrative readiness review with typed, source-located reviewer corrections for synthetic demo cases. "
        "No clinical judgment, approval prediction, or autonomous action."
    ),
)

service = ReadinessService()


class NonfiniteJSONNumber(ValueError):
    pass


def finite_json_number(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise NonfiniteJSONNumber("JSON numbers must be finite; overflow is not permitted.")
    return value


def reject_nonfinite_constant(token: str):
    raise NonfiniteJSONNumber(f"Non-finite JSON number {token} is not permitted.")


@app.middleware("http")
async def reject_nonfinite_json(request: Request, call_next):
    # Inspect raw JSON before Pydantic can put an infinity/NaN in an error input.
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if not media_type or media_type == "application/json" or (media_type.startswith("application/") and media_type.endswith("+json")):
        try:
            json.loads(await request.body(), parse_float=finite_json_number, parse_constant=reject_nonfinite_constant)
        except NonfiniteJSONNumber as exc:
            return JSONResponse(status_code=422, content=ErrorResponse(error="invalid_request", detail=str(exc)).model_dump())
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass  # Ordinary malformed JSON retains FastAPI's normal 422 handling.
    return await call_next(request)


@app.exception_handler(UnsupportedScopeError)
@app.exception_handler(InvalidRequestError)
@app.exception_handler(ServiceError)
async def handle_service_error(_: Request, exc: ServiceError) -> JSONResponse:
    error = ErrorResponse(error=exc.code, detail=str(exc))
    status_code = 400 if isinstance(exc, InvalidRequestError) else 422 if isinstance(exc, UnsupportedScopeError) else 500
    return JSONResponse(status_code=status_code, content=error.model_dump())


@app.get("/", response_model=StatusResponse, tags=["status"])
def root_status() -> StatusResponse:
    return service.get_status()


@app.get("/health", response_model=StatusResponse, tags=["status"])
@app.get("/status", response_model=StatusResponse, tags=["status"])
def health_status() -> StatusResponse:
    return service.get_status()


@app.get("/supported-procedures", response_model=list[SupportedProcedure], tags=["catalog"])
def supported_procedures() -> list[SupportedProcedure]:
    return service.list_supported_procedures()


@app.get("/demo-cases", response_model=list[DemoCase], tags=["catalog"])
def demo_cases() -> list[DemoCase]:
    return service.list_demo_case_summaries()


@app.post("/evaluate", response_model=EvaluationResult, tags=["evaluation"])
def evaluate(request: PARequest) -> EvaluationResult:
    return service.evaluate(request)


@app.get("/drift-status", response_model=DriftStatusReport, tags=["governance"])
def drift_status() -> DriftStatusReport:
    return service.get_drift_status()


@app.get("/rulebook", response_model=RulebookStatusResponse, tags=["governance"])
def rulebook_status() -> RulebookStatusResponse:
    return service.get_rulebook_status()


@app.get("/rulebook/diff", response_model=RulebookDiffResponse, tags=["governance"])
def rulebook_diff(from_release_id: str, to_release_id: str) -> RulebookDiffResponse:
    return service.get_rulebook_diff(from_release_id, to_release_id)
