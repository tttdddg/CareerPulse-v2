"""Authenticated stage-3 HTTP tools for the Ant TBox minimal integration."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.exceptions import RequestValidationError

from ..auth.identity import external_owner_id
from ..orchestrator import (
    AgentLog,
    CareerOrchestrator,
    CareerState,
    StatePersistenceError,
    ToolCallLog,
)
from ..schemas.match_schema import MatchResult
from ..schemas.path_schema import PathResult
from ..schemas.platform_tool_schema import (
    AnalyzeJobMatchData,
    AnalyzeJobMatchRequest,
    AnalyzeJobMatchResponse,
    GenerateCareerPathData,
    GenerateCareerPathRequest,
    GenerateCareerPathResponse,
    ToolErrorDetail,
    ToolErrorResponse,
    ToolResultData,
    ToolResultResponse,
    ToolStatusData,
    ToolStatusResponse,
)


_TOOL_CALL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$"
_security = HTTPBearer(
    auto_error=False,
    bearerFormat="API token",
    scheme_name="TBoxBearerAuth",
)


class PlatformToolException(Exception):
    """Stable platform-facing error independent of internal exceptions."""

    def __init__(
        self,
        *,
        code: int,
        http_status: int,
        error_type: str,
        message: str,
        detail: str,
        retryable: bool,
        request_id: str | None = None,
    ) -> None:
        super().__init__(error_type)
        self.code = code
        self.http_status = http_status
        self.error_type = error_type
        self.message = message
        self.detail = detail
        self.retryable = retryable
        self.request_id = request_id or _new_tool_call_id()


def _new_tool_call_id() -> str:
    return f"tool-{uuid4().hex}"


def _error_response(exc: PlatformToolException) -> JSONResponse:
    body = ToolErrorResponse(
        code=exc.code,
        message=exc.message,
        request_id=exc.request_id,
        data=None,
        error=ToolErrorDetail(
            type=exc.error_type,
            detail=exc.detail,
            retryable=exc.retryable,
        ),
    )
    return JSONResponse(status_code=exc.http_status, content=body.model_dump(mode="json"))


async def platform_tool_exception_handler(
    request: Request, exc: PlatformToolException
) -> JSONResponse:
    del request
    return _error_response(exc)


async def platform_request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    if not request.url.path.startswith("/api/platform/v1/tools"):
        from fastapi.exception_handlers import request_validation_exception_handler

        return await request_validation_exception_handler(request, exc)
    return _error_response(
        PlatformToolException(
            code=-2,
            http_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_type="REQUEST_VALIDATION_FAILED",
            message="request validation failed",
            detail="The request does not match the fixed stage3-tool-v1 JSON schema",
            retryable=False,
        )
    )


async def require_platform_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> None:
    configured = getattr(request.app.state, "tbox_api_token", "")
    if not configured:
        raise PlatformToolException(
            code=-1,
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="TOOL_AUTH_NOT_CONFIGURED",
            message="tool authentication is not configured",
            detail="CareerPulse must configure A02_TBOX_API_TOKEN before publishing tools",
            retryable=False,
        )
    supplied = credentials.credentials if credentials is not None else ""
    if credentials is None or credentials.scheme.lower() != "bearer" or not secrets.compare_digest(
        supplied, configured
    ):
        raise PlatformToolException(
            code=-7,
            http_status=status.HTTP_401_UNAUTHORIZED,
            error_type="AUTHENTICATION_FAILED",
            message="authentication failed",
            detail="Provide the configured Bearer token",
            retryable=False,
        )


router = APIRouter(
    prefix="/api/platform/v1/tools",
    tags=["tbox-stage3-tools"],
    dependencies=[Depends(require_platform_token)],
)


_ERROR_RESPONSES = {
    401: {"model": ToolErrorResponse, "description": "Bearer authentication failed"},
    404: {"model": ToolErrorResponse, "description": "Session or tool call not found"},
    409: {"model": ToolErrorResponse, "description": "Idempotency or prerequisite conflict"},
    422: {"model": ToolErrorResponse, "description": "Fixed request schema validation failed"},
    500: {"model": ToolErrorResponse, "description": "Tool execution failed"},
    503: {"model": ToolErrorResponse, "description": "Persistence or configuration unavailable"},
    504: {"model": ToolErrorResponse, "description": "CareerPulse tool timeout"},
}


def _orchestrator(request: Request) -> CareerOrchestrator:
    return request.app.state.career_orchestrator


def _timeout_seconds(request: Request) -> float:
    return float(getattr(request.app.state, "tbox_tool_timeout_seconds", 25.0))


def _fingerprint(tool_name: str, payload: Any) -> str:
    body = payload.model_dump(mode="json", exclude={"idempotency_key"})
    canonical = json.dumps(
        {"tool_name": tool_name, "payload": body},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hash_user_id(user_id: str | None) -> str | None:
    if user_id is None:
        return None
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def _trusted_external_payload(payload: Any) -> Any:
    """Replace caller identity strings with one isolated external owner."""

    raw_subject = payload.user_id or payload.platform_session_id or payload.session_id
    owner_id = external_owner_id(raw_subject)
    updates: dict[str, Any] = {"user_id": owner_id}
    student_profile = getattr(payload, "student_profile", None)
    if student_profile is not None:
        updates["student_profile"] = student_profile.model_copy(
            update={"user_id": owner_id}
        )
    return payload.model_copy(update=updates)


def _validate_tool_call_id(tool_call_id: str) -> None:
    if re.fullmatch(_TOOL_CALL_PATTERN, tool_call_id):
        return
    raise PlatformToolException(
        code=-2,
        http_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        error_type="REQUEST_VALIDATION_FAILED",
        message="invalid tool_call_id",
        detail="tool_call_id does not match the fixed identifier schema",
        retryable=False,
    )


def _begin_call(
    career_orchestrator: CareerOrchestrator,
    *,
    tool_name: str,
    payload: Any,
) -> tuple[dict[str, Any], bool]:
    tool_call_id = _new_tool_call_id()
    fingerprint = _fingerprint(tool_name, payload)
    try:
        record, created = career_orchestrator.repository.create_tool_call(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            idempotency_key=payload.idempotency_key,
            request_fingerprint=fingerprint,
            session_id=payload.session_id,
            platform_session_id=payload.platform_session_id,
            user_id_hash=_hash_user_id(payload.user_id),
        )
    except Exception as exc:
        raise PlatformToolException(
            code=-5,
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="TOOL_LOG_WRITE_FAILED",
            message="tool persistence unavailable",
            detail="The platform tool call ledger could not be written",
            retryable=True,
            request_id=tool_call_id,
        ) from exc
    if record["request_fingerprint"] != fingerprint:
        raise PlatformToolException(
            code=-8,
            http_status=status.HTTP_409_CONFLICT,
            error_type="IDEMPOTENCY_KEY_CONFLICT",
            message="idempotency key conflict",
            detail="The idempotency key was already used with a different request",
            retryable=False,
            request_id=record["tool_call_id"],
        )
    return record, created


def _replayed_error(record: dict[str, Any]) -> PlatformToolException:
    call_status = record["status"]
    if call_status == "running":
        return PlatformToolException(
            code=-8,
            http_status=status.HTTP_409_CONFLICT,
            error_type="TOOL_CALL_IN_PROGRESS",
            message="tool call is already running",
            detail="Query the status endpoint with this request_id",
            retryable=True,
            request_id=record["tool_call_id"],
        )
    return PlatformToolException(
        code=record.get("error_code") or -1,
        http_status=(
            status.HTTP_504_GATEWAY_TIMEOUT
            if call_status == "timed_out"
            else status.HTTP_409_CONFLICT
        ),
        error_type=record.get("error_type") or "TOOL_CALL_FAILED",
        message="idempotent tool call previously failed",
        detail="Use a new idempotency key only after correcting the failure",
        retryable=call_status == "timed_out",
        request_id=record["tool_call_id"],
    )


def _finish_call(
    career_orchestrator: CareerOrchestrator,
    tool_call_id: str,
    *,
    call_status: str,
    result_data: dict[str, Any] | None = None,
    error_code: int | None = None,
    error_type: str | None = None,
    agent_run_key: str | None = None,
    duration_ms: int | None = None,
) -> None:
    try:
        career_orchestrator.repository.finish_tool_call(
            tool_call_id,
            status=call_status,
            result_data=result_data,
            error_code=error_code,
            error_type=error_type,
            agent_run_key=agent_run_key,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        raise PlatformToolException(
            code=-5,
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="TOOL_LOG_WRITE_FAILED",
            message="tool persistence unavailable",
            detail="The terminal tool status could not be persisted",
            retryable=True,
            request_id=tool_call_id,
        ) from exc


def _load_session(
    career_orchestrator: CareerOrchestrator,
    session_id: str,
    request_id: str,
) -> CareerState:
    try:
        state_value = career_orchestrator.get_session(session_id)
    except Exception as exc:
        raise PlatformToolException(
            code=-5,
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="DATABASE_READ_FAILED",
            message="tool persistence unavailable",
            detail="CareerState could not be read",
            retryable=True,
            request_id=request_id,
        ) from exc
    if state_value is None:
        raise PlatformToolException(
            code=-3,
            http_status=status.HTTP_404_NOT_FOUND,
            error_type="SESSION_NOT_FOUND",
            message="session not found",
            detail="Run analyze_job_match before generate_career_path",
            retryable=False,
            request_id=request_id,
        )
    return state_value


def _check_session_identity(state_value: CareerState, payload: Any, request_id: str) -> None:
    if payload.user_id and state_value.user_id and payload.user_id != state_value.user_id:
        raise PlatformToolException(
            code=-9,
            http_status=status.HTTP_409_CONFLICT,
            error_type="SESSION_USER_MISMATCH",
            message="session identity mismatch",
            detail="The supplied user_id does not own this CareerPulse session",
            retryable=False,
            request_id=request_id,
        )
    if (
        payload.platform_session_id
        and state_value.platform_session_id
        and payload.platform_session_id != state_value.platform_session_id
    ):
        raise PlatformToolException(
            code=-9,
            http_status=status.HTTP_409_CONFLICT,
            error_type="PLATFORM_SESSION_MISMATCH",
            message="session identity mismatch",
            detail="The supplied platform_session_id does not match this session",
            retryable=False,
            request_id=request_id,
        )


def _append_timeout_agent_log(
    state_value: CareerState,
    *,
    agent_name: str,
    service_name: str,
    tool_name: str,
    duration_ms: int,
) -> None:
    if any(log.agent_name == agent_name for log in state_value.agent_logs):
        return
    state_value.agent_logs.append(
        AgentLog(
            session_id=state_value.session_id,
            agent_name=agent_name,
            service_name=service_name,
            status="failed",
            summary=f"{agent_name} 平台调用超时",
            duration_ms=duration_ms,
            tool_calls=[
                ToolCallLog(
                    tool_name=tool_name,
                    service_name=service_name,
                    input_summary="已提供阶段3结构化字段",
                    output_summary="未生成结果",
                    duration_ms=duration_ms,
                    status="error",
                )
            ],
            fallback_used=False,
            error="TimeoutError: platform tool execution timed out",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    )


def _persist_terminal_failure(
    career_orchestrator: CareerOrchestrator,
    record: dict[str, Any],
    exc: PlatformToolException,
    *,
    agent_run_key: str | None,
    duration_ms: int,
) -> None:
    call_status = "timed_out" if exc.code == -6 else "failed"
    _finish_call(
        career_orchestrator,
        record["tool_call_id"],
        call_status=call_status,
        error_code=exc.code,
        error_type=exc.error_type,
        agent_run_key=agent_run_key,
        duration_ms=duration_ms,
    )


def _agent_run_link(
    state_value: CareerState | None,
    *,
    agent_name: str,
    agent_run_key: str,
) -> str | None:
    """Link only when an AgentRunLog actually exists in the state snapshot."""

    if state_value is None:
        return None
    if any(log.agent_name == agent_name for log in state_value.agent_logs):
        return agent_run_key
    return None


@router.post(
    "/analyze_job_match",
    response_model=AnalyzeJobMatchResponse,
    responses=_ERROR_RESPONSES,
    operation_id="analyze_job_match",
    summary="Analyze deterministic job match and ability gaps",
    description=(
        "Accepts validated stage-2 student/job profiles. Match scores and gaps "
        "are calculated only by CareerPulse MatchService."
    ),
)
async def analyze_job_match(
    payload: AnalyzeJobMatchRequest,
    request: Request,
) -> AnalyzeJobMatchResponse:
    payload = _trusted_external_payload(payload)
    career_orchestrator = _orchestrator(request)
    record, created = _begin_call(
        career_orchestrator, tool_name="analyze_job_match", payload=payload
    )
    if not created:
        if record["status"] != "succeeded":
            raise _replayed_error(record)
        state_value = _load_session(
            career_orchestrator, record["session_id"], record["tool_call_id"]
        )
        if state_value.match_result is None:
            raise PlatformToolException(
                code=-3,
                http_status=status.HTTP_404_NOT_FOUND,
                error_type="TOOL_RESULT_NOT_FOUND",
                message="tool result not found",
                detail="The persisted CareerState no longer contains match_result",
                retryable=False,
                request_id=record["tool_call_id"],
            )
        data = AnalyzeJobMatchData(
            tool_call_id=record["tool_call_id"],
            session_id=record["session_id"],
            idempotent_replay=True,
            agent_run_id=record["agent_run_key"],
            match_result=state_value.match_result,
        )
        return AnalyzeJobMatchResponse(request_id=record["tool_call_id"], data=data)

    started = perf_counter()
    agent_run_key = f"{payload.session_id}:MatchAgent"
    try:
        existing = career_orchestrator.get_session(payload.session_id)
        student_data = payload.student_profile.model_dump(mode="json")
        job_data = payload.job_profile.model_dump(mode="json")
        if existing is None:
            state_value = CareerState(
                session_id=payload.session_id,
                platform_session_id=payload.platform_session_id,
                user_id=payload.user_id,
                student_profile=student_data,
                job_profile=job_data,
            )
            career_orchestrator.persist(state_value)
        else:
            state_value = existing
            _check_session_identity(state_value, payload, record["tool_call_id"])
            if (
                state_value.student_profile != student_data
                or state_value.job_profile != job_data
            ):
                raise PlatformToolException(
                    code=-8,
                    http_status=status.HTTP_409_CONFLICT,
                    error_type="SESSION_PAYLOAD_CONFLICT",
                    message="session payload conflict",
                    detail="This session already contains different stage-2 profiles",
                    retryable=False,
                    request_id=record["tool_call_id"],
                )
        if state_value.match_result is None:
            await asyncio.wait_for(
                career_orchestrator.run_stage(state_value, "MatchAgent"),
                timeout=_timeout_seconds(request),
            )
        if state_value.status == "FAILED" or state_value.match_result is None:
            raise PlatformToolException(
                code=-1,
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_type=state_value.error_type or "MATCH_FAILED",
                message="job match analysis failed",
                detail="CareerPulse did not produce a validated match result",
                retryable=True,
                request_id=record["tool_call_id"],
            )
        match_result = MatchResult.model_validate(state_value.match_result)
        duration_ms = max(0, round((perf_counter() - started) * 1000))
        stored_result = {"result_field": "match_result"}
        _finish_call(
            career_orchestrator,
            record["tool_call_id"],
            call_status="succeeded",
            result_data=stored_result,
            agent_run_key=agent_run_key,
            duration_ms=duration_ms,
        )
        data = AnalyzeJobMatchData(
            tool_call_id=record["tool_call_id"],
            session_id=payload.session_id,
            idempotent_replay=False,
            agent_run_id=agent_run_key,
            match_result=match_result,
        )
        return AnalyzeJobMatchResponse(request_id=record["tool_call_id"], data=data)
    except asyncio.TimeoutError as exc:
        duration_ms = max(0, round((perf_counter() - started) * 1000))
        timeout_error = PlatformToolException(
            code=-6,
            http_status=status.HTTP_504_GATEWAY_TIMEOUT,
            error_type="TOOL_TIMEOUT",
            message="tool execution timed out",
            detail="CareerPulse cancelled the match tool at its configured timeout",
            retryable=True,
            request_id=record["tool_call_id"],
        )
        state_value = locals().get("state_value")
        if isinstance(state_value, CareerState):
            state_value.set_status("FAILED", error_type="TOOL_TIMEOUT")
            _append_timeout_agent_log(
                state_value,
                agent_name="MatchAgent",
                service_name="MatchService",
                tool_name="analyze_job_match",
                duration_ms=duration_ms,
            )
            career_orchestrator.persist(state_value)
        _persist_terminal_failure(
            career_orchestrator,
            record,
            timeout_error,
            agent_run_key=agent_run_key,
            duration_ms=duration_ms,
        )
        raise timeout_error from exc
    except PlatformToolException as exc:
        duration_ms = max(0, round((perf_counter() - started) * 1000))
        _persist_terminal_failure(
            career_orchestrator,
            record,
            exc,
            agent_run_key=_agent_run_link(
                locals().get("state_value"),
                agent_name="MatchAgent",
                agent_run_key=agent_run_key,
            ),
            duration_ms=duration_ms,
        )
        raise
    except Exception as exc:
        duration_ms = max(0, round((perf_counter() - started) * 1000))
        persistence_error = isinstance(exc, StatePersistenceError)
        tool_error = PlatformToolException(
            code=-5 if persistence_error else -1,
            http_status=(
                status.HTTP_503_SERVICE_UNAVAILABLE
                if persistence_error
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            error_type=(
                "DATABASE_WRITE_FAILED"
                if persistence_error
                else "MATCH_EXECUTION_FAILED"
            ),
            message="job match analysis failed",
            detail="CareerPulse failed without retaining request content",
            retryable=True,
            request_id=record["tool_call_id"],
        )
        _persist_terminal_failure(
            career_orchestrator,
            record,
            tool_error,
            agent_run_key=_agent_run_link(
                locals().get("state_value"),
                agent_name="MatchAgent",
                agent_run_key=agent_run_key,
            ),
            duration_ms=duration_ms,
        )
        raise tool_error from exc


@router.post(
    "/generate_career_path",
    response_model=GenerateCareerPathResponse,
    responses=_ERROR_RESPONSES,
    operation_id="generate_career_path",
    summary="Generate deterministic 3-year and 5-year career paths",
    description=(
        "Uses the completed backend match in CareerState. The request cannot "
        "supply or override match scores, ability gaps, path nodes, or path scores."
    ),
)
async def generate_career_path(
    payload: GenerateCareerPathRequest,
    request: Request,
) -> GenerateCareerPathResponse:
    payload = _trusted_external_payload(payload)
    career_orchestrator = _orchestrator(request)
    record, created = _begin_call(
        career_orchestrator, tool_name="generate_career_path", payload=payload
    )
    if not created:
        if record["status"] != "succeeded":
            raise _replayed_error(record)
        state_value = _load_session(
            career_orchestrator, record["session_id"], record["tool_call_id"]
        )
        if state_value.career_roadmap is None:
            raise PlatformToolException(
                code=-3,
                http_status=status.HTTP_404_NOT_FOUND,
                error_type="TOOL_RESULT_NOT_FOUND",
                message="tool result not found",
                detail="The persisted CareerState no longer contains career_roadmap",
                retryable=False,
                request_id=record["tool_call_id"],
            )
        data = GenerateCareerPathData(
            tool_call_id=record["tool_call_id"],
            session_id=record["session_id"],
            idempotent_replay=True,
            agent_run_id=record["agent_run_key"],
            career_roadmap=state_value.career_roadmap,
        )
        return GenerateCareerPathResponse(request_id=record["tool_call_id"], data=data)

    started = perf_counter()
    agent_run_key = f"{payload.session_id}:PathAgent"
    try:
        state_value = _load_session(
            career_orchestrator, payload.session_id, record["tool_call_id"]
        )
        _check_session_identity(state_value, payload, record["tool_call_id"])
        if state_value.match_result is None or state_value.status not in {
            "MATCH_COMPLETED",
            "PATH_COMPLETED",
        }:
            raise PlatformToolException(
                code=-9,
                http_status=status.HTTP_409_CONFLICT,
                error_type="MATCH_NOT_COMPLETED",
                message="career path prerequisite not met",
                detail="Run analyze_job_match successfully before generating a path",
                retryable=False,
                request_id=record["tool_call_id"],
            )
        if state_value.career_roadmap is None:
            await asyncio.wait_for(
                career_orchestrator.run_stage(state_value, "PathAgent"),
                timeout=_timeout_seconds(request),
            )
        if state_value.status == "FAILED" or state_value.career_roadmap is None:
            raise PlatformToolException(
                code=-1,
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_type=state_value.error_type or "PATH_FAILED",
                message="career path generation failed",
                detail="CareerPulse did not produce a validated path result",
                retryable=True,
                request_id=record["tool_call_id"],
            )
        career_roadmap = PathResult.model_validate(state_value.career_roadmap)
        duration_ms = max(0, round((perf_counter() - started) * 1000))
        stored_result = {"result_field": "career_roadmap"}
        _finish_call(
            career_orchestrator,
            record["tool_call_id"],
            call_status="succeeded",
            result_data=stored_result,
            agent_run_key=agent_run_key,
            duration_ms=duration_ms,
        )
        data = GenerateCareerPathData(
            tool_call_id=record["tool_call_id"],
            session_id=payload.session_id,
            idempotent_replay=False,
            agent_run_id=agent_run_key,
            career_roadmap=career_roadmap,
        )
        return GenerateCareerPathResponse(request_id=record["tool_call_id"], data=data)
    except asyncio.TimeoutError as exc:
        duration_ms = max(0, round((perf_counter() - started) * 1000))
        timeout_error = PlatformToolException(
            code=-6,
            http_status=status.HTTP_504_GATEWAY_TIMEOUT,
            error_type="TOOL_TIMEOUT",
            message="tool execution timed out",
            detail="CareerPulse cancelled the path tool at its configured timeout",
            retryable=True,
            request_id=record["tool_call_id"],
        )
        state_value = locals().get("state_value")
        if isinstance(state_value, CareerState):
            state_value.set_status("FAILED", error_type="TOOL_TIMEOUT")
            _append_timeout_agent_log(
                state_value,
                agent_name="PathAgent",
                service_name="PathService",
                tool_name="generate_career_path",
                duration_ms=duration_ms,
            )
            career_orchestrator.persist(state_value)
        _persist_terminal_failure(
            career_orchestrator,
            record,
            timeout_error,
            agent_run_key=agent_run_key,
            duration_ms=duration_ms,
        )
        raise timeout_error from exc
    except PlatformToolException as exc:
        duration_ms = max(0, round((perf_counter() - started) * 1000))
        _persist_terminal_failure(
            career_orchestrator,
            record,
            exc,
            agent_run_key=_agent_run_link(
                locals().get("state_value"),
                agent_name="PathAgent",
                agent_run_key=agent_run_key,
            ),
            duration_ms=duration_ms,
        )
        raise
    except Exception as exc:
        duration_ms = max(0, round((perf_counter() - started) * 1000))
        persistence_error = isinstance(exc, StatePersistenceError)
        tool_error = PlatformToolException(
            code=-5 if persistence_error else -1,
            http_status=(
                status.HTTP_503_SERVICE_UNAVAILABLE
                if persistence_error
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            error_type=(
                "DATABASE_WRITE_FAILED"
                if persistence_error
                else "PATH_EXECUTION_FAILED"
            ),
            message="career path generation failed",
            detail="CareerPulse failed without retaining request content",
            retryable=True,
            request_id=record["tool_call_id"],
        )
        _persist_terminal_failure(
            career_orchestrator,
            record,
            tool_error,
            agent_run_key=_agent_run_link(
                locals().get("state_value"),
                agent_name="PathAgent",
                agent_run_key=agent_run_key,
            ),
            duration_ms=duration_ms,
        )
        raise tool_error from exc


@router.get(
    "/calls/{tool_call_id}/status",
    response_model=ToolStatusResponse,
    responses=_ERROR_RESPONSES,
    operation_id="get_stage3_tool_call_status",
    summary="Query a stage-3 platform tool call status",
)
async def get_tool_call_status(
    tool_call_id: str,
    request: Request,
) -> ToolStatusResponse:
    _validate_tool_call_id(tool_call_id)
    career_orchestrator = _orchestrator(request)
    try:
        record = career_orchestrator.repository.get_tool_call(tool_call_id)
    except Exception as exc:
        raise PlatformToolException(
            code=-5,
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="DATABASE_READ_FAILED",
            message="tool persistence unavailable",
            detail="The tool call ledger could not be read",
            retryable=True,
            request_id=tool_call_id,
        ) from exc
    if record is None:
        raise PlatformToolException(
            code=-3,
            http_status=status.HTTP_404_NOT_FOUND,
            error_type="TOOL_CALL_NOT_FOUND",
            message="tool call not found",
            detail="No platform tool call exists for this identifier",
            retryable=False,
            request_id=tool_call_id,
        )
    data = ToolStatusData(
        tool_call_id=tool_call_id,
        tool_name=record["tool_name"],
        session_id=record["session_id"],
        status=record["status"],
        result_available=record["status"] == "succeeded",
        agent_run_id=record["agent_run_key"],
        updated_at=record["updated_at"],
    )
    return ToolStatusResponse(request_id=tool_call_id, data=data)


@router.get(
    "/calls/{tool_call_id}/result",
    response_model=ToolResultResponse,
    responses=_ERROR_RESPONSES,
    operation_id="get_stage3_tool_call_result",
    summary="Query a completed stage-3 platform tool result",
)
async def get_tool_call_result(
    tool_call_id: str,
    request: Request,
) -> ToolResultResponse:
    _validate_tool_call_id(tool_call_id)
    career_orchestrator = _orchestrator(request)
    try:
        record = career_orchestrator.repository.get_tool_call(tool_call_id)
    except Exception as exc:
        raise PlatformToolException(
            code=-5,
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="DATABASE_READ_FAILED",
            message="tool persistence unavailable",
            detail="The tool call ledger could not be read",
            retryable=True,
            request_id=tool_call_id,
        ) from exc
    if record is None:
        raise PlatformToolException(
            code=-3,
            http_status=status.HTTP_404_NOT_FOUND,
            error_type="TOOL_CALL_NOT_FOUND",
            message="tool call not found",
            detail="No platform tool call exists for this identifier",
            retryable=False,
            request_id=tool_call_id,
        )
    if record["status"] != "succeeded" or record["result_data"] is None:
        raise PlatformToolException(
            code=-9,
            http_status=status.HTTP_409_CONFLICT,
            error_type="TOOL_RESULT_NOT_AVAILABLE",
            message="tool result is not available",
            detail="Query status before requesting the result",
            retryable=record["status"] in {"running", "timed_out"},
            request_id=tool_call_id,
        )
    state_value = _load_session(
        career_orchestrator, record["session_id"], tool_call_id
    )
    match_result = (
        state_value.match_result
        if record["tool_name"] == "analyze_job_match"
        else None
    )
    career_roadmap = (
        state_value.career_roadmap
        if record["tool_name"] == "generate_career_path"
        else None
    )
    if match_result is None and career_roadmap is None:
        raise PlatformToolException(
            code=-3,
            http_status=status.HTTP_404_NOT_FOUND,
            error_type="TOOL_RESULT_NOT_FOUND",
            message="tool result not found",
            detail="The persisted CareerState no longer contains this tool result",
            retryable=False,
            request_id=tool_call_id,
        )
    data = ToolResultData(
        tool_call_id=tool_call_id,
        tool_name=record["tool_name"],
        session_id=record["session_id"],
        agent_run_id=record["agent_run_key"],
        match_result=match_result,
        career_roadmap=career_roadmap,
    )
    return ToolResultResponse(request_id=tool_call_id, data=data)


__all__ = [
    "PlatformToolException",
    "platform_request_validation_exception_handler",
    "platform_tool_exception_handler",
    "router",
]
