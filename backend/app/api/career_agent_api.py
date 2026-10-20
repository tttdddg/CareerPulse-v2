"""HTTP adapters for the local A02 Agent chain and stage-3 E2E flow."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..orchestrator import (
    AgentLog,
    CareerOrchestrator,
    CareerState,
    StateOwnershipError,
    StatePersistenceError,
)
from ..auth.dependencies import (
    AuthenticatedRequest,
    require_web_authenticated_request,
    require_web_csrf,
)
from ..auth.identity import external_owner_id, web_owner_id
from ..schemas.career_profile_schema import StudentProfile as UnifiedStudentProfile
from ..schemas.job_schema import JobProfile as StageTwoJobProfile


_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class ApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CareerAgentRunRequest(ApiRequest):
    session_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    platform_session_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    user_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    student_input: dict[str, Any] | None = None
    target_job_input: dict[str, Any] | None = None


class PrepareStageThreeRequest(ApiRequest):
    """Ingest already validated stage-2 profiles for local stage-3 execution."""

    session_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    platform_session_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    user_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    student_profile: UnifiedStudentProfile | None = None
    job_profile: StageTwoJobProfile | None = None

    @model_validator(mode="after")
    def require_a_profile(self) -> "PrepareStageThreeRequest":
        if self.student_profile is None and self.job_profile is None:
            raise ValueError("student_profile or job_profile must be provided")
        return self


class StageExecutionRequest(ApiRequest):
    session_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    user_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )


orchestrator = CareerOrchestrator()
router = APIRouter(prefix="/api/career-agent", tags=["career-agent"])
agent_log_router = APIRouter(prefix="/api/agent", tags=["career-agent"])


def _get_orchestrator(request: Request) -> CareerOrchestrator:
    return getattr(request.app.state, "career_orchestrator", orchestrator)


def _database_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": -5,
            "type": "DATABASE_WRITE_FAILED",
            "message": "CareerState database transaction failed",
        },
    )


def _load_state(
    career_orchestrator: CareerOrchestrator,
    session_id: str,
) -> CareerState:
    try:
        state_value = career_orchestrator.get_session(session_id)
    except Exception as exc:
        raise _database_error() from exc
    if state_value is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": -3, "type": "SESSION_NOT_FOUND"},
        )
    return state_value


def _owner_id(
    authenticated: AuthenticatedRequest | None,
    *,
    session_id: str,
    legacy_user_id: str | None = None,
) -> str | None:
    if authenticated is not None:
        return web_owner_id(authenticated.user.id)
    if legacy_user_id:
        return external_owner_id(legacy_user_id)
    return None


def _check_owner(state_value: CareerState, owner_id: str | None) -> None:
    if owner_id is not None and state_value.user_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": -3, "type": "SESSION_NOT_FOUND"},
        )


def _ownership_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": -2, "type": "SESSION_OWNERSHIP_CONFLICT"},
    )


def _persist_failure(
    career_orchestrator: CareerOrchestrator,
    state_value: CareerState,
    *,
    error_type: str,
    status_code: int,
) -> None:
    state_value.set_status("FAILED", error_type=error_type)
    try:
        career_orchestrator.persist(state_value)
    except StatePersistenceError as exc:
        raise _database_error() from exc
    raise HTTPException(
        status_code=status_code,
        detail={"code": -2, "type": error_type},
    )


@router.post("/run", response_model=CareerState)
async def run_career_agent(
    payload: CareerAgentRunRequest,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
    _csrf: None = Depends(require_web_csrf),
) -> CareerState:
    owner_id = _owner_id(
        authenticated,
        session_id=payload.session_id,
        legacy_user_id=payload.user_id,
    )
    career_orchestrator = _get_orchestrator(request)
    try:
        existing = career_orchestrator.get_session(payload.session_id)
        if existing is not None:
            _check_owner(existing, owner_id)
        state_data = payload.model_dump(exclude={"user_id"})
        return await career_orchestrator.run(
            CareerState(**state_data, user_id=owner_id)
        )
    except StateOwnershipError as exc:
        raise _ownership_error() from exc
    except StatePersistenceError as exc:
        raise _database_error() from exc


@router.post("/stage3/prepare", response_model=CareerState)
def prepare_stage_three(
    payload: PrepareStageThreeRequest,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
    _csrf: None = Depends(require_web_csrf),
) -> CareerState:
    career_orchestrator = _get_orchestrator(request)
    owner_id = _owner_id(
        authenticated,
        session_id=payload.session_id,
        legacy_user_id=payload.user_id,
    )
    try:
        existing = career_orchestrator.get_session(payload.session_id)
    except Exception as exc:
        raise _database_error() from exc
    supplied_student = (
        payload.student_profile.model_dump(mode="json")
        if payload.student_profile is not None
        else None
    )
    supplied_job = (
        payload.job_profile.model_dump(mode="json")
        if payload.job_profile is not None
        else None
    )
    if existing is not None:
        conflict = (
            supplied_student is not None
            and existing.student_profile is not None
            and existing.student_profile != supplied_student
        ) or (
            supplied_job is not None
            and existing.job_profile is not None
            and existing.job_profile != supplied_job
        )
        _check_owner(existing, owner_id)
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": -2, "type": "SESSION_PAYLOAD_CONFLICT"},
            )
        if existing.student_profile is None:
            existing.student_profile = supplied_student
        if existing.job_profile is None:
            existing.job_profile = supplied_job
        state_value = existing
    else:
        state_value = CareerState(
            session_id=payload.session_id,
            platform_session_id=payload.platform_session_id,
            user_id=owner_id,
            student_profile=supplied_student,
            job_profile=supplied_job,
        )
    try:
        career_orchestrator.persist(state_value)
    except StateOwnershipError as exc:
        raise _ownership_error() from exc
    except StatePersistenceError as exc:
        raise _database_error() from exc
    return state_value


@router.post("/stage3/match", response_model=CareerState)
async def run_stage_three_match(
    payload: StageExecutionRequest,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
    _csrf: None = Depends(require_web_csrf),
) -> CareerState:
    career_orchestrator = _get_orchestrator(request)
    state_value = _load_state(career_orchestrator, payload.session_id)
    _check_owner(
        state_value,
        _owner_id(
            authenticated,
            session_id=payload.session_id,
            legacy_user_id=payload.user_id,
        ),
    )
    if state_value.match_result is not None and state_value.status in {
        "MATCH_COMPLETED",
        "PATH_COMPLETED",
    }:
        return state_value
    if state_value.student_profile is None:
        _persist_failure(
            career_orchestrator,
            state_value,
            error_type="STUDENT_PROFILE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if state_value.job_profile is None:
        _persist_failure(
            career_orchestrator,
            state_value,
            error_type="JOB_PROFILE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    try:
        student = UnifiedStudentProfile.model_validate(state_value.student_profile)
        job = StageTwoJobProfile.model_validate(state_value.job_profile)
    except ValueError:
        _persist_failure(
            career_orchestrator,
            state_value,
            error_type="PROFILE_SCHEMA_INVALID",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    if not student.ability_dimensions or not any(
        dimension.tags for dimension in student.ability_dimensions
    ):
        _persist_failure(
            career_orchestrator,
            state_value,
            error_type="STUDENT_PROFILE_INCOMPLETE",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    if not job.required_abilities:
        _persist_failure(
            career_orchestrator,
            state_value,
            error_type="JOB_ABILITY_DIMENSIONS_EMPTY",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    try:
        await career_orchestrator.run_stage(state_value, "MatchAgent")
    except StateOwnershipError as exc:
        raise _ownership_error() from exc
    except StatePersistenceError as exc:
        raise _database_error() from exc
    if state_value.status == "FAILED" or state_value.match_result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": -1, "type": state_value.error_type or "MATCH_FAILED"},
        )
    return state_value


@router.post("/stage3/path", response_model=CareerState)
async def run_stage_three_path(
    payload: StageExecutionRequest,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
    _csrf: None = Depends(require_web_csrf),
) -> CareerState:
    career_orchestrator = _get_orchestrator(request)
    state_value = _load_state(career_orchestrator, payload.session_id)
    _check_owner(
        state_value,
        _owner_id(
            authenticated,
            session_id=payload.session_id,
            legacy_user_id=payload.user_id,
        ),
    )
    if state_value.career_roadmap is not None and state_value.status == "PATH_COMPLETED":
        return state_value
    if state_value.match_result is None or state_value.status != "MATCH_COMPLETED":
        _persist_failure(
            career_orchestrator,
            state_value,
            error_type="MATCH_NOT_COMPLETED",
            status_code=status.HTTP_409_CONFLICT,
        )
    try:
        await career_orchestrator.run_stage(state_value, "PathAgent")
    except StateOwnershipError as exc:
        raise _ownership_error() from exc
    except StatePersistenceError as exc:
        raise _database_error() from exc
    if state_value.status == "FAILED" or state_value.career_roadmap is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": -1, "type": state_value.error_type or "PATH_FAILED"},
        )
    return state_value


@router.get("/session/{session_id}", response_model=CareerState)
async def get_career_session(
    session_id: str,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
) -> CareerState:
    state_value = _load_state(_get_orchestrator(request), session_id)
    _check_owner(
        state_value,
        _owner_id(authenticated, session_id=session_id),
    )
    return state_value


@agent_log_router.get("/logs/{session_id}", response_model=list[AgentLog])
async def get_agent_logs(
    session_id: str,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
) -> list[AgentLog]:
    career_orchestrator = _get_orchestrator(request)
    state_value = _load_state(career_orchestrator, session_id)
    _check_owner(
        state_value,
        _owner_id(authenticated, session_id=session_id),
    )
    try:
        return [
            AgentLog.model_validate(item)
            for item in career_orchestrator.get_agent_logs(session_id)
        ]
    except Exception as exc:
        raise _database_error() from exc


# Standalone entry point retained for focused Agent API testing.
app = FastAPI(title="CareerPulse A02 Agent API")
app.state.career_orchestrator = orchestrator
app.include_router(router)
app.include_router(agent_log_router)


__all__ = [
    "CareerAgentRunRequest",
    "PrepareStageThreeRequest",
    "StageExecutionRequest",
    "agent_log_router",
    "app",
    "router",
]
