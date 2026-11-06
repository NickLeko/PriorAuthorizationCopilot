from __future__ import annotations

import json
import math
from types import UnionType
from typing import Union, get_args, get_origin

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, computed_field
from pydantic_core import ErrorType

from engine import __version__
from engine.citation_context import evaluation_citation_context
from engine.note_context import MAX_REQUEST_BYTES
from engine.rendering import export_evaluation_payload
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


class RequestBodyLimit:
    """Bound bytes before either JSON decoder, including chunked requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0
        body = bytearray()
        if declared <= MAX_REQUEST_BYTES:
            while True:
                event = await receive()
                if event["type"] == "http.disconnect":
                    return
                body.extend(event.get("body", b""))
                if len(body) > MAX_REQUEST_BYTES or not event.get("more_body", False):
                    break
        if declared > MAX_REQUEST_BYTES or len(body) > MAX_REQUEST_BYTES:
            response = JSONResponse(status_code=413, content={"error": "invalid_request", "detail": "Request body exceeds 1048576 bytes."})
            return await response(scope, receive, send)
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


service = ReadinessService()

MAX_VALIDATION_ERRORS = 20
MAX_VALIDATION_LOCATION_DEPTH = 8
VALIDATION_ERROR_TYPES = frozenset(get_args(ErrorType)) | {"json_invalid"}


def validation_error_location(request: Request, location) -> list[str | int]:
    """Keep declared field names and bounded indices, never caller-defined keys."""
    if not isinstance(location, (tuple, list)) or not location:
        return []
    source = location[0]
    if source not in {"body", "query", "path", "header", "cookie"}:
        return []
    safe = [source]
    if source != "body":
        route = request.scope.get("route")
        parameters = getattr(getattr(route, "dependant", None), f"{source}_params", ())
        if len(location) > 1:
            safe.append(location[1] if location[1] in {parameter.alias for parameter in parameters} else "<field>")
        return safe

    annotation = PARequest
    for segment in location[1:MAX_VALIDATION_LOCATION_DEPTH]:
        if get_origin(annotation) in {Union, UnionType}:
            members = [member for member in get_args(annotation) if member is not type(None)]
            annotation = members[0] if len(members) == 1 else None
        origin, members = get_origin(annotation), get_args(annotation)
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if isinstance(segment, str) and segment in annotation.model_fields:
                safe.append(segment)
                annotation = annotation.model_fields[segment].annotation
            else:
                safe.append("<field>")
                break
        elif origin in {list, tuple} and type(segment) is int and 0 <= segment <= MAX_REQUEST_BYTES:
            safe.append(segment)
            annotation = members[0]
        elif origin is dict:
            safe.append("<key>")
            annotation = members[1]
        else:
            safe.append("<field>")
            break
    return safe


def validation_error_response(request: Request, errors) -> JSONResponse:
    # Do not encode whole error dictionaries: input/ctx/msg and even loc keys can
    # contain submitted data. Raw nested inputs also break recursive encoders.
    detail = []
    for error in errors[:MAX_VALIDATION_ERRORS]:
        code = error.get("type")
        code = code if isinstance(code, str) and code in VALIDATION_ERROR_TYPES else "validation_error"
        location = ("body",) if code == "json_invalid" else error.get("loc", ())
        detail.append({"type": code, "loc": validation_error_location(request, location), "msg": "Invalid request."})
    return JSONResponse(status_code=422, content={"error": "invalid_request", "detail": detail})


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return validation_error_response(request, exc.errors())


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
            pass  # FastAPI reports ordinary malformed JSON through the sanitized handler.
        except (RecursionError, ValueError):
            # Decoder depth/integer limits are client errors; never echo decoder diagnostics.
            return validation_error_response(request, [{"type": "json_invalid", "loc": ("body",)}])
    return await call_next(request)


app.add_middleware(RequestBodyLimit)


@app.exception_handler(UnsupportedScopeError)
@app.exception_handler(InvalidRequestError)
@app.exception_handler(ServiceError)
async def handle_service_error(_: Request, exc: ServiceError) -> JSONResponse:
    # Service-level client rejections can also quote caller-controlled keys/scope.
    detail = str(exc)
    if isinstance(exc, InvalidRequestError):
        detail = "Invalid request."
    elif isinstance(exc, UnsupportedScopeError):
        detail = "Unsupported request scope. See /supported-procedures for supported inputs."
    error = ErrorResponse(error=exc.code, detail=detail)
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


class EvaluationReviewResponse(EvaluationResult):
    """HTTP review projection; canonical stored records remain schema 2.0.0."""

    @computed_field
    @property
    def citation_context(self) -> dict[str, list[str]]:
        return evaluation_citation_context(self)


@app.post("/evaluate", response_model=EvaluationReviewResponse, tags=["evaluation"])
def evaluate(request: PARequest) -> JSONResponse:
    return JSONResponse(export_evaluation_payload(service.evaluate(request), include_citation_context=True))


@app.get("/drift-status", response_model=DriftStatusReport, tags=["governance"])
def drift_status() -> DriftStatusReport:
    return service.get_drift_status()


@app.get("/rulebook", response_model=RulebookStatusResponse, tags=["governance"])
def rulebook_status() -> RulebookStatusResponse:
    return service.get_rulebook_status()


@app.get("/rulebook/diff", response_model=RulebookDiffResponse, tags=["governance"])
def rulebook_diff(from_release_id: str, to_release_id: str) -> RulebookDiffResponse:
    return service.get_rulebook_diff(from_release_id, to_release_id)
