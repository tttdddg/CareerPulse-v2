"""Authenticated Web business API for the M3.1 career-analysis workflow.

This router reuses the existing ``CareerMCPToolService`` (which itself drives
``CareerOrchestrator`` / ``CareerState`` and the deterministic services) with a
trusted Web owner, so the browser never supplies or decides ``user_id``. Every
owner is derived from the verified HttpOnly session via ``web_owner_id``.

Ownership rules enforced here:
- A missing or foreign session always returns HTTP 404 so callers cannot probe
  whether another subject's session exists.
- Writes require CSRF in addition to authentication.
- The conditional upsert in ``StateRepository`` remains the final concurrency
  guard; reading-then-writing here is only a fast path, not a security control.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ..auth.dependencies import (
    AuthenticatedRequest,
    require_web_authenticated_request,
    require_web_csrf,
)
from ..auth.identity import web_owner_id
from ..db_state import SessionOwnershipConflict, StateRepository
from ..orchestrator import CareerOrchestrator, CareerState
from ..schemas.database_tool_schema import (
    ReadCareerGraphEdgesRequest,
    ReadJobContextRequest,
    SearchJobsRequest,
)
from ..schemas.mcp_tool_schema import (
    AnalyzeJobMatchMCPRequest,
    AnalyzeTargetJobRequest,
    BuildStudentProfileRequest,
    GenerateCareerPathMCPRequest,
    StudentProfileInput,
    TargetJobInput,
)


_WORKFLOW_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"

STATUS_MESSAGES: dict[str, str] = {
    "PROFILE_COMPLETED": "画像已保存，可选择目标岗位",
    "JOB_COMPLETED": "目标岗位已确认，可执行人岗匹配",
    "MATCH_COMPLETED": "人岗匹配已完成，可生成职业路径",
    "PATH_COMPLETED": "职业路径已生成",
    "TRAINING_COMPLETED": "职场训练已完成",
    "FEEDBACK_COMPLETED": "成长反馈已保存",
}

_WORKFLOW_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "WORKFLOW_NOT_FOUND", "message": "workflow not found"},
)

_PRECONDITION_FAILED = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail={
        "code": "WORKFLOW_PRECONDITION_FAILED",
        "message": "workflow prerequisite is not met",
    },
)

# Read-only business tools still persist an audit CareerState for every tool
# call (MCP ToolService contract). Those rows are execution ledgers rather than
# user workflows, and they carry no private user evidence, so the Web API writes
# them under a dedicated system owner: they stay auditable, stay unreachable for
# users, and never pollute a user's workflow history.
_READ_AUDIT_OWNER = "system:web-read-auditor"

router = APIRouter(prefix="/api/web/v1", tags=["web-business"])


def _repository(request: Request) -> StateRepository:
    return request.app.state.career_state_repository


def _orchestrator(request: Request) -> CareerOrchestrator:
    return request.app.state.career_orchestrator


def _tool_service(request: Request) -> Any:
    return request.app.state.career_web_tool_service


def _owner(authenticated: AuthenticatedRequest | None) -> str:
    """Return the canonical Web owner for this request.

    When Web auth is explicitly disabled (controlled local testing only) the
    anonymous Web owner is used so data still never leaks across subjects.
    """

    if authenticated is not None:
        return web_owner_id(authenticated.user.id)
    return web_owner_id("anonymous")


def _workflow_id(value: str) -> str:
    return value.strip()


def _load_owned_state(
    repository: StateRepository,
    owner_id: str,
    session_id: str,
) -> CareerState:
    """Load a session only when it belongs to ``owner_id``.

    A missing session and a foreign session are deliberately indistinguishable.
    """

    stored = repository.get_state(session_id)
    if stored is None:
        raise _WORKFLOW_NOT_FOUND
    state = CareerState.model_validate(stored)
    if state.user_id != owner_id:
        raise _WORKFLOW_NOT_FOUND
    return state


def _persist_state(
    orchestrator: CareerOrchestrator, state: CareerState
) -> None:
    try:
        orchestrator.persist(state)
    except SessionOwnershipConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "WORKFLOW_OWNER_CONFLICT",
                "message": "workflow was claimed by another subject",
            },
        ) from exc


def _require_tool_success(result: Any) -> Any:
    """Convert a failed MCP-shaped tool result into an HTTP error."""

    if getattr(result, "success", False):
        return result
    error_code = getattr(result, "error_code", None) or "WORKFLOW_EXECUTION_FAILED"
    message = getattr(result, "message", None) or "workflow step failed"
    status_code = status.HTTP_409_CONFLICT
    if error_code in {
        "PROFILE_SCHEMA_INVALID",
        "STUDENT_PROFILE_INCOMPLETE",
        "JOB_ABILITY_DIMENSIONS_EMPTY",
        "REQUEST_VALIDATION_FAILED",
    }:
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    elif error_code in {"DATABASE_UNAVAILABLE", "MCP_TOOL_TIMEOUT"}:
        status_code = (
            status.HTTP_504_GATEWAY_TIMEOUT
            if error_code == "MCP_TOOL_TIMEOUT"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": error_code,
            "message": message,
            "missing_fields": getattr(result, "missing_fields", []),
            "retryable": bool(getattr(result, "retryable", False)),
        },
    )


def _status_message(state: CareerState) -> str:
    return STATUS_MESSAGES.get(state.status, "工作流状态已更新")


def _workflow_summary(state: CareerState) -> dict[str, Any]:
    """Serialize one workflow summary without leaking another subject."""

    job_profile = state.job_profile or {}
    match_result = state.match_result or {}
    return {
        "session_id": state.session_id,
        "status": state.status,
        "status_message": _status_message(state),
        "job_id": state.job_record_id,
        "job_title": job_profile.get("title") or job_profile.get("job_title"),
        "overall_score": match_result.get("overall_score"),
        "has_student_profile": state.student_profile is not None,
        "has_job_profile": state.job_profile is not None,
        "has_match_result": state.match_result is not None,
        "has_career_roadmap": state.career_roadmap is not None,
    }


class WebWorkflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=_WORKFLOW_ID_PATTERN
    )


class WebProfileInput(StudentProfileInput):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class WebTargetJobInput(TargetJobInput):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


@router.post(
    "/workflows",
    status_code=status.HTTP_201_CREATED,
    summary="Create an owned career-analysis workflow",
)
async def create_workflow(
    payload: WebWorkflowInput,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
    _csrf: None = Depends(require_web_csrf),
) -> dict[str, Any]:
    owner_id = _owner(authenticated)
    session_id = _workflow_id(payload.session_id or f"web-{uuid4().hex}")
    repository = _repository(request)
    try:
        existing = repository.get_state(session_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "STATE_DATABASE_UNAVAILABLE",
                "message": "workflow store is unavailable",
            },
        ) from exc
    if existing is not None:
        if existing.get("user_id") == owner_id:
            state = CareerState.model_validate(existing)
            return {**_workflow_summary(state), "created": False}
        # A foreign session id is reported as a conflict rather than revealing
        # that another subject already owns it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "WORKFLOW_ID_TAKEN",
                "message": "choose a different workflow id",
            },
        )
    state = CareerState(session_id=session_id, user_id=owner_id)
    _persist_state(_orchestrator(request), state)
    return {**_workflow_summary(state), "created": True}


@router.get("/workflows", summary="List the current user's workflows")
async def list_workflows(
    request: Request,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=50),
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
) -> dict[str, Any]:
    owner_id = _owner(authenticated)
    items, total = _repository(request).list_states_by_owner(
        owner_id, limit=page_size, offset=(page - 1) * page_size
    )
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_more": page * page_size < total,
    }


@router.get(
    "/workflows/{session_id}",
    summary="Read one owned workflow with its persisted results",
)
async def get_workflow(
    session_id: str,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
) -> dict[str, Any]:
    owner_id = _owner(authenticated)
    state = _load_owned_state(_repository(request), owner_id, _workflow_id(session_id))
    return {
        **_workflow_summary(state),
        "student_profile": state.student_profile,
        "job_profile": state.job_profile,
        "match_result": state.match_result,
        "career_roadmap": state.career_roadmap,
        "trend_result": state.trend_result,
        "agent_logs": [log.model_dump(mode="json") for log in state.agent_logs],
    }


@router.put(
    "/workflows/{session_id}/profile",
    summary="Build and store the current user's student profile",
)
async def put_workflow_profile(
    session_id: str,
    payload: WebProfileInput,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
    _csrf: None = Depends(require_web_csrf),
) -> dict[str, Any]:
    owner_id = _owner(authenticated)
    state = _load_owned_state(_repository(request), owner_id, _workflow_id(session_id))
    orchestrator = _orchestrator(request)
    service = _tool_service(request)
    result = await _run_tool(
        request,
        service.build_student_profile(
            BuildStudentProfileRequest(
                session_id=state.session_id,
                user_id=owner_id,
                student_input=payload,
            )
        ),
    )
    _require_tool_success(result)
    refreshed = _load_owned_state(_repository(request), owner_id, state.session_id)
    _persist_state(orchestrator, refreshed)
    return {
        **_workflow_summary(refreshed),
        "student_profile": refreshed.student_profile,
        "student_id": refreshed.student_profile_id,
    }


@router.put(
    "/workflows/{session_id}/target-job",
    summary="Select or resolve the target job for this workflow",
)
async def put_workflow_target_job(
    session_id: str,
    payload: WebTargetJobInput,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
    _csrf: None = Depends(require_web_csrf),
) -> dict[str, Any]:
    owner_id = _owner(authenticated)
    state = _load_owned_state(_repository(request), owner_id, _workflow_id(session_id))
    orchestrator = _orchestrator(request)
    service = _tool_service(request)
    result = await _run_tool(
        request,
        service.analyze_target_job(
            AnalyzeTargetJobRequest(
                session_id=state.session_id,
                user_id=owner_id,
                target_job_input=payload,
            )
        ),
    )
    _require_tool_success(result)
    refreshed = _load_owned_state(_repository(request), owner_id, state.session_id)
    _persist_state(orchestrator, refreshed)
    return {
        **_workflow_summary(refreshed),
        "job_profile": refreshed.job_profile,
        "job_id": refreshed.job_record_id,
        "trend_result": refreshed.trend_result,
    }


@router.post(
    "/workflows/{session_id}/match",
    summary="Run deterministic person-job matching for this workflow",
)
async def post_workflow_match(
    session_id: str,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
    _csrf: None = Depends(require_web_csrf),
) -> dict[str, Any]:
    owner_id = _owner(authenticated)
    state = _load_owned_state(_repository(request), owner_id, _workflow_id(session_id))
    if state.match_result is not None and state.status in {
        "MATCH_COMPLETED",
        "PATH_COMPLETED",
    }:
        return {
            **_workflow_summary(state),
            "match_result": state.match_result,
            "idempotent_replay": True,
        }
    orchestrator = _orchestrator(request)
    service = _tool_service(request)
    result = await _run_tool(
        request,
        service.analyze_job_match(
            AnalyzeJobMatchMCPRequest(
                session_id=state.session_id, user_id=owner_id
            )
        ),
    )
    _require_tool_success(result)
    refreshed = _load_owned_state(_repository(request), owner_id, state.session_id)
    _persist_state(orchestrator, refreshed)
    return {
        **_workflow_summary(refreshed),
        "match_result": refreshed.match_result,
        "idempotent_replay": False,
    }


@router.post(
    "/workflows/{session_id}/path",
    summary="Generate the deterministic 3/5-year career path",
)
async def post_workflow_path(
    session_id: str,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
    _csrf: None = Depends(require_web_csrf),
) -> dict[str, Any]:
    owner_id = _owner(authenticated)
    state = _load_owned_state(_repository(request), owner_id, _workflow_id(session_id))
    if state.career_roadmap is not None and state.status == "PATH_COMPLETED":
        return {
            **_workflow_summary(state),
            "career_roadmap": state.career_roadmap,
            "idempotent_replay": True,
        }
    orchestrator = _orchestrator(request)
    service = _tool_service(request)
    # PathAgent keeps its default graph source until a real path request binds
    # this service's source policy. The bind mutates the shared orchestrator, so
    # it is applied here instead of at app construction.
    await asyncio.to_thread(service.configure_runtime_graph_provider)
    result = await _run_tool(
        request,
        service.generate_career_path(
            GenerateCareerPathMCPRequest(session_id=state.session_id, user_id=owner_id)
        ),
    )
    _require_tool_success(result)
    refreshed = _load_owned_state(_repository(request), owner_id, state.session_id)
    _persist_state(orchestrator, refreshed)
    return {
        **_workflow_summary(refreshed),
        "career_roadmap": refreshed.career_roadmap,
        "idempotent_replay": False,
    }


@router.get("/jobs", summary="Search stored jobs")
async def search_jobs(
    request: Request,
    keyword: str | None = Query(default=None, max_length=200),
    city: str | None = Query(default=None, max_length=64),
    industry: str | None = Query(default=None, max_length=255),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=50),
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
) -> dict[str, Any]:
    service = _tool_service(request)
    result = await _run_tool(
        request,
        service.search_database_jobs(
            SearchJobsRequest(
                session_id=f"web-jobs-{uuid4().hex}",
                user_id=_READ_AUDIT_OWNER,
                keyword=keyword,
                city=city,
                industry=industry,
                page=page,
                page_size=page_size,
            )
        ),
    )
    _require_tool_success(result)
    data = result.data
    return {
        "items": [item.model_dump(mode="json") for item in data.items],
        "page": data.page,
        "page_size": data.page_size,
        "has_more": data.has_more,
        "data_source": data.data_source,
        "fallback_used": data.fallback_used,
    }


@router.get("/jobs/{job_id}", summary="Read one job context")
async def read_job(
    job_id: int,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
) -> dict[str, Any]:
    service = _tool_service(request)
    result = await _run_tool(
        request,
        service.read_job_context(
            ReadJobContextRequest(
                session_id=f"web-job-{uuid4().hex}",
                user_id=_READ_AUDIT_OWNER,
                job_id=job_id,
            )
        ),
    )
    _require_tool_success(result)
    data = result.data
    return {
        "context": data.context.model_dump(mode="json"),
        "data_source": data.data_source,
        "fallback_used": data.fallback_used,
    }


@router.get("/jobs/{job_id}/graph", summary="Read career-graph edges for a job")
async def read_job_graph(
    job_id: int,
    request: Request,
    relation_type: Literal["vertical", "lateral"] | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
) -> dict[str, Any]:
    context_result = await _run_tool(
        request,
        _tool_service(request).read_job_context(
            ReadJobContextRequest(
                session_id=f"web-graph-{uuid4().hex}",
                user_id=_READ_AUDIT_OWNER,
                job_id=job_id,
            )
        ),
    )
    _require_tool_success(context_result)
    type_key = context_result.data.context.job_type.type_key
    edges_result = await _run_tool(
        request,
        _tool_service(request).read_career_graph_edges(
            ReadCareerGraphEdgesRequest(
                session_id=f"web-graph-{uuid4().hex}",
                user_id=_READ_AUDIT_OWNER,
                source_type_key=type_key,
                relation_type=relation_type,
                limit=limit,
            )
        ),
    )
    _require_tool_success(edges_result)
    data = edges_result.data
    return {
        "source_type_key": type_key,
        "edges": [edge.model_dump(mode="json") for edge in data.edges],
        "data_source": data.data_source,
        "fallback_used": data.fallback_used,
    }


def _tool_timeout(request: Request) -> float:
    return float(getattr(request.app.state, "web_tool_timeout_seconds", 25.0))


async def _run_tool(request: Request, coro: Any) -> Any:
    """Run one tool call with the configured timeout and map failures."""

    try:
        return await asyncio.wait_for(coro, timeout=_tool_timeout(request))
    except (TimeoutError, asyncio.TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "code": "WORKFLOW_TIMEOUT",
                "message": "workflow step timed out",
                "retryable": True,
            },
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "WORKFLOW_UNAVAILABLE",
                "message": "workflow step is temporarily unavailable",
                "retryable": True,
            },
        ) from exc


__all__ = ["router"]
