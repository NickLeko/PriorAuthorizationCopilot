from __future__ import annotations

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
        "Deterministic administrative readiness review for synthetic prior authorization demo cases. "
        "No clinical judgment, approval prediction, or autonomous action."
    ),
)

service = ReadinessService()


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
