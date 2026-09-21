"""Transport-neutral MCP tool application service.

This module performs state and logging adaptation only. Deterministic match,
gap and path calculations remain owned by MatchService and PathService through
their existing Agents.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from ..orchestrator import AgentLog, CareerOrchestrator, CareerState, ToolCallLog
from ..repositories.job_repository import (
    JobRepositoryDataError,
    JobRepositoryUnavailableError,
)
from ..repositories.career_graph_repository import (
    CareerGraphProviderDataError,
    PostgresCareerGraphProviderError,
)
from ..repositories.student_profile_repository import (
    StudentProfileDataError,
    StudentProfileRepositoryError,
)
from ..schemas.career_profile_schema import StudentProfile
from ..schemas.database_tool_schema import (
    ReadCareerGraphEdgesData,
    ReadCareerGraphEdgesRequest,
    ReadCareerGraphEdgesResult,
    ReadJobContextData,
    ReadJobContextRequest,
    ReadJobContextResult,
    ReadStudentProfileData,
    ReadStudentProfileRequest,
    ReadStudentProfileResult,
    SearchJobsData,
    SearchJobsRequest,
    SearchJobsResult,
)
from ..schemas.job_schema import JobProfile, TrendResult
from ..schemas.match_schema import MatchResult
from ..schemas.internal_tool_schema import (
    GenerateAndScoreTrainingData,
    GenerateAndScoreTrainingRequest,
    GenerateAndScoreTrainingResult,
    RecommendLearningAndJobResourcesData,
    RecommendLearningAndJobResourcesRequest,
    RecommendLearningAndJobResourcesResult,
    ResourceRecommendation,
    SaveGrowthFeedbackData,
    SaveGrowthFeedbackRequest,
    SaveGrowthFeedbackResult,
)
from ..schemas.mcp_tool_schema import (
    AnalyzeJobMatchMCPData,
    AnalyzeJobMatchMCPRequest,
    AnalyzeJobMatchMCPResult,
    AnalyzeTargetJobData,
    AnalyzeTargetJobRequest,
    AnalyzeTargetJobResult,
    BuildStudentProfileData,
    BuildStudentProfileRequest,
    BuildStudentProfileResult,
    GenerateCareerPathMCPData,
    GenerateCareerPathMCPRequest,
    GenerateCareerPathMCPResult,
    MCPToolResult,
)
from ..schemas.path_schema import PathResult
from ..schemas.feedback_schema import FeedbackAgentResult
from ..schemas.training_schema import TrainingScore, TrainingTask
from ..services.resource_service import ResourceService
from ..services.job_context_service import (
    JobContextMappingError,
    JobContextNotFoundError,
)
from ..services.career_graph_repository import (
    ConfiguredCareerGraphProvider,
    DemoCareerGraphProviderError,
)
from ..services.student_profile_persistence_service import (
    StudentProfileMappingError,
    StudentProfileNotFoundError,
    StudentProfilePersistenceService,
)
from ..tools.database_tools import DatabaseToolError, DatabaseTools


ResultT = TypeVar("ResultT", bound=MCPToolResult)
DatabaseDataT = TypeVar(
    "DatabaseDataT",
    ReadStudentProfileData,
    SearchJobsData,
    ReadJobContextData,
    ReadCareerGraphEdgesData,
)


class MCPToolFailure(RuntimeError):
    """Private, content-free failure used to construct a safe MCP result."""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        missing_fields: list[str] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.message = message
        self.missing_fields = missing_fields or []
        self.retryable = retryable


class CareerMCPToolService:
    """Run CareerPulse MCP tools against the real orchestrator and ledger."""

    def __init__(
        self,
        orchestrator: CareerOrchestrator,
        *,
        timeout_seconds: float = 25.0,
        resource_service: ResourceService | None = None,
        database_tools: DatabaseTools | None = None,
        profile_persistence_service: StudentProfilePersistenceService | None = None,
        demo_mode: bool = False,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("MCP tool timeout must be in (0, 60]")
        self.orchestrator = orchestrator
        self.timeout_seconds = timeout_seconds
        self.resource_service = resource_service or ResourceService()
        environment_demo_mode = os.getenv("A02_DEMO_MODE", "").strip().lower()
        if environment_demo_mode not in {
            "",
            "0",
            "1",
            "false",
            "true",
            "no",
            "yes",
            "off",
            "on",
        }:
            raise ValueError("A02_DEMO_MODE must be a boolean")
        configured_demo_mode = environment_demo_mode in {"1", "true", "yes", "on"}
        self.database_tools = database_tools or DatabaseTools(
            student_service=profile_persistence_service,
            demo_mode=configured_demo_mode,
        )
        self.profile_persistence_service = profile_persistence_service
        self.demo_mode = demo_mode or self.database_tools.demo_mode
        if self.database_tools.authorize_student is None:
            # Competition trust boundary: user_id is accepted as the logical
            # identity, but access still requires the exact persisted session
            # and student reference to match.  Production SSO can replace this
            # callback without changing the Tool contract.
            self.database_tools.authorize_student = (
                self._authorize_session_student_reference
            )
        graph_provider = ConfiguredCareerGraphProvider(
            self.database_tools.graph_selector,
            demo_mode=self.database_tools.demo_mode,
            fallback_to_demo=self.database_tools.fallback_to_demo,
        )
        for agent in self.orchestrator.agents:
            if agent.name == "PathAgent":
                configure = getattr(agent, "configure_graph_provider", None)
                if configure is not None:
                    configure(graph_provider)

    def _authorize_session_student_reference(
        self,
        session_id: str,
        user_id: str,
        student_id: int,
    ) -> bool:
        """Authorize a student reference using the persisted competition session."""

        try:
            state = self.orchestrator.get_session(session_id)
        except Exception:
            return False
        return bool(
            state is not None
            and state.user_id == user_id
            and state.student_profile_id == student_id
        )

    async def read_student_profile(
        self,
        request: ReadStudentProfileRequest,
    ) -> ReadStudentProfileResult:
        return await self._run_database_read(
            request=request,
            tool_name="read_student_profile",
            result_type=ReadStudentProfileResult,
            operation=lambda: self.database_tools.read_student_profile(request),
            result_field="student_profile",
            success_message="Authorized student profile loaded.",
        )

    async def search_database_jobs(
        self,
        request: SearchJobsRequest,
    ) -> SearchJobsResult:
        return await self._run_database_read(
            request=request,
            tool_name="search_jobs",
            result_type=SearchJobsResult,
            operation=lambda: self.database_tools.search_jobs(request),
            result_field="jobs",
            success_message="Job search completed.",
        )

    async def read_job_context(
        self,
        request: ReadJobContextRequest,
    ) -> ReadJobContextResult:
        return await self._run_database_read(
            request=request,
            tool_name="read_job_context",
            result_type=ReadJobContextResult,
            operation=lambda: self.database_tools.read_job_context(request),
            result_field="job_context",
            success_message="Job context loaded.",
        )

    async def read_career_graph_edges(
        self,
        request: ReadCareerGraphEdgesRequest,
    ) -> ReadCareerGraphEdgesResult:
        return await self._run_database_read(
            request=request,
            tool_name="read_career_graph_edges",
            result_type=ReadCareerGraphEdgesResult,
            operation=lambda: self.database_tools.read_career_graph_edges(request),
            result_field="career_graph_edges",
            success_message="Career graph edges loaded.",
        )

    async def build_student_profile(
        self, request: BuildStudentProfileRequest
    ) -> BuildStudentProfileResult:
        trace_id = request.trace_id or f"tool-{uuid4().hex}"
        started = perf_counter()
        state: CareerState | None = None
        postgres_checkpointed = False
        try:
            record, created = self._begin_call(
                "build_student_profile", request, trace_id
            )
            if not created:
                self._require_replayable(record)
                return self._replay_profile(request, trace_id, record)
            state = self._load_or_create(request)
            incoming = request.student_input.model_dump(mode="json", exclude_none=True)
            if (
                self.profile_persistence_service is not None
                and state.student_profile_id is not None
                and state.student_profile is None
            ):
                restored = self.profile_persistence_service.get_profile(
                    state.student_profile_id,
                    user_id=request.user_id,
                )
                state.student_profile = restored.profile.model_dump(mode="json")
                state.student_profile_snapshot_id = restored.student_id
                state.student_profile_updated_at = restored.profile.updated_at

            if state.student_profile is None or state.student_input != incoming:
                state.student_input = incoming
                await self._run_profile_agent_without_persist(state, trace_id)
            profile = StudentProfile.model_validate(state.student_profile)
            fallback_used = self._agent_fallback(state, "ProfileAgent")
            student_id = state.student_profile_id
            data_source = "demo_json" if self.demo_mode else "session"
            if (
                self.profile_persistence_service is not None
                and not self.demo_mode
                and self.profile_persistence_service.can_persist(profile)
            ):
                db_started = perf_counter()
                persisted = self.profile_persistence_service.save_profile(
                    profile,
                    student_id=student_id,
                )
                student_id = persisted.student_id
                state.student_profile_id = student_id
                state.student_profile_snapshot_id = student_id
                state.student_profile_updated_at = persisted.profile.updated_at
                data_source = "postgresql"
                self._append_profile_persistence_log(
                    state,
                    student_id=student_id,
                    duration_ms=self._duration(db_started),
                )
                self._finish_success(
                    trace_id,
                    request.session_id,
                    "student_profile",
                    "ProfileAgent",
                    started,
                    result_metadata={
                        "phase": "postgres_committed",
                        "student_id": student_id,
                        "profile_updated_at": persisted.profile.updated_at.isoformat(),
                        "fallback_used": fallback_used,
                        "data_source": data_source,
                    },
                )
                postgres_checkpointed = True

            state.set_status("PROFILE_COMPLETED")
            self.orchestrator.persist(state)
            data = BuildStudentProfileData(
                agent_run_id=f"{request.session_id}:ProfileAgent",
                fallback_used=fallback_used,
                student_id=student_id,
                data_source=data_source,
                demo_mode=self.demo_mode,
                student_profile=profile,
            )
            self._finish_success(
                trace_id,
                request.session_id,
                "student_profile",
                "ProfileAgent",
                started,
                result_metadata={
                    "phase": "complete",
                    "student_id": student_id,
                    "profile_updated_at": (
                        state.student_profile_updated_at.isoformat()
                        if state.student_profile_updated_at is not None
                        else None
                    ),
                    "fallback_used": fallback_used,
                    "data_source": data_source,
                    "demo_mode": self.demo_mode,
                },
            )
            return BuildStudentProfileResult(
                success=True,
                message=(
                    "Student profile is ready using deterministic fallback."
                    if fallback_used
                    else "Student profile is ready."
                ),
                trace_id=trace_id,
                session_id=request.session_id,
                status=state.status,
                data=data,
            )
        except Exception as exc:
            return self._failure_result(
                BuildStudentProfileResult,
                request,
                trace_id,
                state,
                exc,
                started,
                finish_call=not postgres_checkpointed,
            )

    async def analyze_target_job(
        self, request: AnalyzeTargetJobRequest
    ) -> AnalyzeTargetJobResult:
        trace_id = request.trace_id or f"tool-{uuid4().hex}"
        started = perf_counter()
        state: CareerState | None = None
        try:
            record, created = self._begin_call(
                "analyze_target_job", request, trace_id
            )
            if not created:
                self._require_replayable(record)
                return self._replay_job(request, trace_id, record)
            state = self._load_or_create(request)
            incoming = request.target_job_input.model_dump(mode="json", exclude_none=True)
            if state.job_profile is not None:
                if state.target_job_input not in (None, incoming):
                    raise MCPToolFailure(
                        "SESSION_PAYLOAD_CONFLICT",
                        "This session already contains a different target job.",
                    )
            else:
                state.target_job_input = incoming
                database_read_started: float | None = None
                if self.database_tools.demo_mode:
                    state.job_data_source = "demo_json"
                elif (
                    request.target_job_input.job_id is not None
                    or request.target_job_input.type_key is not None
                ):
                    database_read_started = perf_counter()
                    context = self._load_job_context(request.target_job_input)
                    state.job_profile = context.profile.model_dump(mode="json")
                    state.job_record_id = context.profile.job_id
                    state.job_type_key = context.profile.normalized_title
                    state.job_profile_snapshot_id = context.profile.job_id
                    state.job_profile_snapshot_type_key = (
                        context.profile.normalized_title
                    )
                    state.job_data_source = "postgresql"
                else:
                    state.job_record_id = None
                    state.job_type_key = None
                    state.job_profile_snapshot_id = None
                    state.job_profile_snapshot_type_key = None
                    state.job_data_source = "session"
                await self._run_agent(state, "JobAgent", trace_id)
                if database_read_started is not None:
                    self._append_job_database_log(
                        state,
                        duration_ms=self._duration(database_read_started),
                    )
            job_profile = JobProfile.model_validate(state.job_profile)
            trend_result = TrendResult.model_validate(state.trend_result)
            if state.status != "JOB_COMPLETED":
                state.set_status("JOB_COMPLETED")
            self.orchestrator.persist(state)
            fallback_used = self._agent_fallback(state, "JobAgent")
            data_source = state.job_data_source or "session"
            data = AnalyzeTargetJobData(
                agent_run_id=f"{request.session_id}:JobAgent",
                fallback_used=fallback_used,
                job_id=state.job_record_id or job_profile.job_id,
                type_key=state.job_type_key or job_profile.normalized_title,
                data_source=data_source,
                demo_mode=data_source == "demo_json",
                job_profile=job_profile,
                trend_result=trend_result,
            )
            self._finish_success(
                trace_id,
                request.session_id,
                "job_profile",
                "JobAgent",
                started,
                result_metadata={
                    "job_id": data.job_id,
                    "type_key": data.type_key,
                    "data_source": data.data_source,
                    "fallback_used": fallback_used,
                    "demo_mode": data.demo_mode,
                },
            )
            return AnalyzeTargetJobResult(
                success=True,
                message=(
                    "Target job is ready using validated fallback data."
                    if fallback_used
                    else "Target job is ready."
                ),
                trace_id=trace_id,
                session_id=request.session_id,
                status=state.status,
                data=data,
            )
        except Exception as exc:
            return self._failure_result(
                AnalyzeTargetJobResult, request, trace_id, state, exc, started
            )

    def _load_job_context(self, target: Any) -> Any:
        try:
            if target.job_id is not None:
                return self.database_tools.job_service.get_context_by_job_id(
                    target.job_id
                )
            assert target.type_key is not None
            service = self.database_tools.job_service
            loader = getattr(service, "get_context_by_type_key", None)
            if loader is None:
                loader = service.get_context_by_normalized_title
            return loader(target.type_key)
        except JobContextNotFoundError:
            raise MCPToolFailure(
                "JOB_CONTEXT_NOT_FOUND",
                "The requested PostgreSQL job context was not found.",
            ) from None
        except (JobContextMappingError, JobRepositoryDataError):
            raise MCPToolFailure(
                "JOB_CONTEXT_INVALID",
                "The stored PostgreSQL job context failed validation.",
            ) from None
        except JobRepositoryUnavailableError:
            raise MCPToolFailure(
                "JOB_DATABASE_UNAVAILABLE",
                "The PostgreSQL job context is unavailable.",
                retryable=True,
            ) from None

    async def analyze_job_match(
        self, request: AnalyzeJobMatchMCPRequest
    ) -> AnalyzeJobMatchMCPResult:
        trace_id = request.trace_id or f"tool-{uuid4().hex}"
        started = perf_counter()
        state: CareerState | None = None
        try:
            record, created = self._begin_call(
                "analyze_job_match", request, trace_id
            )
            if not created:
                self._require_replayable(record)
                return self._replay_match(request, trace_id)
            state = self._load_required(request)
            hydration_logs = self._hydrate_match_context(
                state,
                user_id=request.user_id,
            )
            if hydration_logs:
                self._append_match_hydration_log(state, hydration_logs)
                self.orchestrator.persist(state)
            missing = [
                name
                for name in ("student_profile", "job_profile")
                if getattr(state, name) is None
            ]
            if missing:
                raise MCPToolFailure(
                    "MATCH_PREREQUISITES_NOT_READY",
                    "Build the student profile and analyze the target job first.",
                    missing_fields=missing,
                )
            student = StudentProfile.model_validate(state.student_profile)
            job = JobProfile.model_validate(state.job_profile)
            if not student.ability_dimensions or not any(
                dimension.tags for dimension in student.ability_dimensions
            ):
                raise MCPToolFailure(
                    "STUDENT_PROFILE_INCOMPLETE",
                    "The student profile has no evidence-backed ability dimensions.",
                    missing_fields=["student_profile.ability_dimensions"],
                )
            if not job.required_abilities:
                raise MCPToolFailure(
                    "JOB_ABILITY_DIMENSIONS_EMPTY",
                    "The target job has no required ability dimensions.",
                    missing_fields=["job_profile.required_abilities"],
                )
            if state.match_result is None:
                await self._run_agent(state, "MatchAgent", trace_id)
            if state.status == "FAILED" or state.match_result is None:
                raise MCPToolFailure(
                    state.error_type or "MATCH_FAILED",
                    "CareerPulse could not produce a validated match result.",
                    retryable=True,
                )
            match_result = MatchResult.model_validate(state.match_result)
            data = AnalyzeJobMatchMCPData(
                agent_run_id=f"{request.session_id}:MatchAgent",
                match_result=match_result,
            )
            self._finish_success(
                trace_id, request.session_id, "match_result", "MatchAgent", started
            )
            return AnalyzeJobMatchMCPResult(
                success=True,
                message="Deterministic job match is complete.",
                trace_id=trace_id,
                session_id=request.session_id,
                status=state.status,
                data=data,
            )
        except Exception as exc:
            return self._failure_result(
                AnalyzeJobMatchMCPResult, request, trace_id, state, exc, started
            )

    def _hydrate_match_context(
        self,
        state: CareerState,
        *,
        user_id: str,
    ) -> list[ToolCallLog]:
        """Load trusted business references before MatchAgent sees the state."""

        self._validate_match_snapshot_references(state)
        logs: list[ToolCallLog] = []

        if state.student_profile is None and state.student_profile_id is not None:
            started = perf_counter()
            requested_student_id = state.student_profile_id
            service = (
                self.profile_persistence_service
                or self.database_tools.student_service
            )
            try:
                restored = service.get_profile(
                    state.student_profile_id,
                    user_id=user_id,
                )
                profile = StudentProfile.model_validate(restored.profile)
            except StudentProfileNotFoundError:
                raise MCPToolFailure(
                    "MATCH_STUDENT_PROFILE_NOT_FOUND",
                    "The referenced student profile was not found.",
                    missing_fields=["student_profile"],
                ) from None
            except (StudentProfileDataError, StudentProfileMappingError, ValidationError):
                raise MCPToolFailure(
                    "MATCH_STUDENT_PROFILE_INVALID",
                    "The referenced student profile failed its fixed schema.",
                    missing_fields=["student_profile"],
                ) from None
            except StudentProfileRepositoryError:
                raise MCPToolFailure(
                    "MATCH_DATABASE_UNAVAILABLE",
                    "The business database is unavailable.",
                    retryable=True,
                ) from None
            if restored.student_id != requested_student_id:
                raise MCPToolFailure(
                    "MATCH_CONTEXT_ID_CONFLICT",
                    "The loaded student profile does not match its business reference.",
                )
            state.student_profile = profile.model_dump(mode="json")
            state.student_profile_snapshot_id = restored.student_id
            state.student_profile_updated_at = profile.updated_at
            logs.append(
                self._match_hydration_tool_log(
                    tool_name="hydrate_student_profile",
                    service_name="StudentProfilePersistenceService",
                    reference_kind="student_id",
                    reference=restored.student_id,
                    duration_ms=self._duration(started),
                )
            )

        if state.job_profile is None and (
            state.job_record_id is not None or state.job_type_key is not None
        ):
            started = perf_counter()
            requested_job_id = state.job_record_id
            requested_type_key = state.job_type_key
            try:
                if state.job_record_id is not None:
                    context = self.database_tools.job_service.get_context_by_job_id(
                        state.job_record_id
                    )
                    reference_kind = "job_id"
                    reference: int | str = state.job_record_id
                else:
                    assert state.job_type_key is not None
                    service = self.database_tools.job_service
                    loader = getattr(service, "get_context_by_type_key", None)
                    if loader is None:
                        loader = service.get_context_by_normalized_title
                    context = loader(state.job_type_key)
                    reference_kind = "type_key"
                    reference = state.job_type_key
                profile = JobProfile.model_validate(context.profile)
            except JobContextNotFoundError:
                raise MCPToolFailure(
                    "MATCH_JOB_PROFILE_NOT_FOUND",
                    "The referenced job profile was not found.",
                    missing_fields=["job_profile"],
                ) from None
            except (JobContextMappingError, JobRepositoryDataError, ValidationError):
                raise MCPToolFailure(
                    "MATCH_JOB_PROFILE_INVALID",
                    "The referenced job profile failed its fixed schema.",
                    missing_fields=["job_profile"],
                ) from None
            except JobRepositoryUnavailableError:
                raise MCPToolFailure(
                    "MATCH_DATABASE_UNAVAILABLE",
                    "The business database is unavailable.",
                    retryable=True,
                ) from None
            if (
                requested_job_id is not None
                and profile.job_id != requested_job_id
            ) or (
                requested_type_key is not None
                and profile.normalized_title != requested_type_key
            ):
                raise MCPToolFailure(
                    "MATCH_CONTEXT_ID_CONFLICT",
                    "The loaded job profile does not match its business reference.",
                )
            state.job_profile = profile.model_dump(mode="json")
            state.job_record_id = profile.job_id
            state.job_type_key = profile.normalized_title
            state.job_profile_snapshot_id = profile.job_id
            state.job_profile_snapshot_type_key = profile.normalized_title
            state.job_data_source = "postgresql"
            logs.append(
                self._match_hydration_tool_log(
                    tool_name="hydrate_job_context",
                    service_name="JobContextService",
                    reference_kind=reference_kind,
                    reference=reference,
                    duration_ms=self._duration(started),
                )
            )

        self._validate_match_snapshot_references(state)
        return logs

    @staticmethod
    def _validate_match_snapshot_references(state: CareerState) -> None:
        if state.student_profile is not None and state.student_profile_id is not None:
            if state.student_profile_snapshot_id != state.student_profile_id:
                raise MCPToolFailure(
                    "MATCH_CONTEXT_ID_CONFLICT",
                    "The student profile snapshot does not match its business reference.",
                )

        if state.job_profile is None:
            return
        if not state.job_profile.get("required_abilities"):
            raise MCPToolFailure(
                "JOB_ABILITY_DIMENSIONS_EMPTY",
                "The target job has no required ability dimensions.",
                missing_fields=["job_profile.required_abilities"],
            )
        try:
            profile = JobProfile.model_validate(state.job_profile)
        except ValidationError:
            raise MCPToolFailure(
                "MATCH_JOB_PROFILE_INVALID",
                "The target job profile failed its fixed schema.",
                missing_fields=["job_profile"],
            ) from None
        conflicts = (
            state.job_record_id is not None
            and (
                state.job_profile_snapshot_id != state.job_record_id
                or (profile.job_id is not None and profile.job_id != state.job_record_id)
            )
        ) or (
            state.job_type_key is not None
            and (
                state.job_profile_snapshot_type_key != state.job_type_key
                or profile.normalized_title != state.job_type_key
            )
        )
        if conflicts:
            raise MCPToolFailure(
                "MATCH_CONTEXT_ID_CONFLICT",
                "The job profile snapshot does not match its business reference.",
            )

    @staticmethod
    def _match_hydration_tool_log(
        *,
        tool_name: str,
        service_name: str,
        reference_kind: str,
        reference: int | str,
        duration_ms: int,
    ) -> ToolCallLog:
        reference_hash = hashlib.sha256(
            str(reference).encode("utf-8")
        ).hexdigest()[:12]
        return ToolCallLog(
            tool_name=tool_name,
            service_name=service_name,
            input_summary=f"reference={reference_kind}",
            output_summary=(
                "source=postgresql; record_count=1; "
                f"reference_hash={reference_hash}"
            ),
            duration_ms=duration_ms,
            status="success",
        )

    @staticmethod
    def _append_match_hydration_log(
        state: CareerState,
        tool_calls: list[ToolCallLog],
    ) -> None:
        state.agent_logs.append(
            AgentLog(
                session_id=state.session_id,
                agent_name="MatchContextHydration",
                service_name=None,
                status="success",
                summary="Match context hydrated from validated business records.",
                duration_ms=sum(item.duration_ms for item in tool_calls),
                tool_calls=tool_calls,
                fallback_used=False,
                error=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

    async def generate_career_path(
        self, request: GenerateCareerPathMCPRequest
    ) -> GenerateCareerPathMCPResult:
        trace_id = request.trace_id or f"tool-{uuid4().hex}"
        started = perf_counter()
        state: CareerState | None = None
        try:
            record, created = self._begin_call(
                "generate_career_path", request, trace_id
            )
            if not created:
                self._require_replayable(record)
                return self._replay_path(request, trace_id)
            state = self._load_required(request)
            if state.match_result is None or state.status not in {
                "MATCH_COMPLETED",
                "PATH_COMPLETED",
            }:
                raise MCPToolFailure(
                    "MATCH_NOT_COMPLETED",
                    "Run analyze_job_match successfully before generating a path.",
                    missing_fields=["match_result"],
                )
            if state.career_roadmap is None:
                await self._run_agent(state, "PathAgent", trace_id)
            if state.status == "FAILED" or state.career_roadmap is None:
                if state.error_type == PostgresCareerGraphProviderError.__name__:
                    raise MCPToolFailure(
                        "PATH_GRAPH_DATABASE_UNAVAILABLE",
                        "The PostgreSQL career graph is unavailable.",
                        retryable=True,
                    )
                if state.error_type == CareerGraphProviderDataError.__name__:
                    raise MCPToolFailure(
                        "PATH_GRAPH_INVALID",
                        "The career graph failed whole-graph validation.",
                    )
                if state.error_type == DemoCareerGraphProviderError.__name__:
                    raise MCPToolFailure(
                        "DEMO_DATA_INVALID",
                        "The configured Demo career graph is unavailable.",
                    )
                raise MCPToolFailure(
                    state.error_type or "PATH_FAILED",
                    "CareerPulse could not produce a validated career path.",
                    retryable=True,
                )
            roadmap = PathResult.model_validate(state.career_roadmap)
            data = GenerateCareerPathMCPData(
                agent_run_id=f"{request.session_id}:PathAgent",
                career_roadmap=roadmap,
            )
            self._finish_success(
                trace_id, request.session_id, "career_roadmap", "PathAgent", started
            )
            return GenerateCareerPathMCPResult(
                success=True,
                message="Deterministic career path is complete.",
                trace_id=trace_id,
                session_id=request.session_id,
                status=state.status,
                data=data,
            )
        except Exception as exc:
            return self._failure_result(
                GenerateCareerPathMCPResult, request, trace_id, state, exc, started
            )

    async def generate_and_score_training(
        self,
        request: GenerateAndScoreTrainingRequest,
    ) -> GenerateAndScoreTrainingResult:
        """Run the real TrainingAgent without persisting transient user input."""

        trace_id = request.trace_id or f"tool-{uuid4().hex}"
        started = perf_counter()
        state: CareerState | None = None
        try:
            record, created = self._begin_call(
                "generate_and_score_training", request, trace_id
            )
            if not created:
                self._require_replayable(record)
                return self._replay_training(request, trace_id, record)

            state = self._load_required(request)
            missing = [
                name
                for name in ("student_profile", "job_profile")
                if getattr(state, name) is None
            ]
            if request.mode == "generate" and state.match_result is None:
                missing.append("match_result")
            if missing:
                raise MCPToolFailure(
                    "TRAINING_PREREQUISITES_NOT_READY",
                    "Complete the profile, target job, and match context first.",
                    missing_fields=missing,
                )

            if request.mode == "generate":
                stage_input = {"training_type": request.training_type}
            else:
                task_value = state.get_training_task(request.training_id)
                if task_value is None:
                    raise MCPToolFailure(
                        "TRAINING_NOT_FOUND",
                        "The requested training task is not available in this session.",
                        missing_fields=["training_plan"],
                    )
                task = TrainingTask.model_validate(task_value)
                if (
                    request.training_type is not None
                    and request.training_type != task.type
                ):
                    raise MCPToolFailure(
                        "TRAINING_TYPE_MISMATCH",
                        "The supplied training type does not match the stored task.",
                    )
                stage_input = {
                    "training_type": task.type,
                    "training_id": request.training_id,
                    "user_answer": request.user_answer,
                }

            await self._run_agent(
                state,
                "TrainingAgent",
                trace_id,
                stage_input=stage_input,
                tool_name="generate_and_score_training",
            )
            if state.status == "FAILED":
                raise MCPToolFailure(
                    "TRAINING_FAILED",
                    "CareerPulse could not produce a validated training result.",
                    retryable=True,
                )

            if request.mode == "generate":
                task_value = state.get_training_task()
                if task_value is None:
                    raise MCPToolFailure(
                        "TRAINING_RESULT_NOT_FOUND",
                        "TrainingAgent completed without a training task.",
                        retryable=True,
                    )
                task = TrainingTask.model_validate(task_value)
                data = GenerateAndScoreTrainingData(
                    agent_run_id=f"{request.session_id}:TrainingAgent",
                    mode="generate",
                    training_task=task,
                )
                result_metadata = {
                    "mode": "generate",
                    "training_id": task.training_id,
                }
            else:
                score_value = state.get_latest_training_score()
                if (
                    score_value is None
                    or score_value.get("training_id") != request.training_id
                ):
                    raise MCPToolFailure(
                        "TRAINING_RESULT_NOT_FOUND",
                        "TrainingAgent completed without the requested score.",
                        retryable=True,
                    )
                score = TrainingScore.model_validate(score_value)
                data = GenerateAndScoreTrainingData(
                    agent_run_id=f"{request.session_id}:TrainingAgent",
                    mode="score",
                    training_score=score,
                )
                result_metadata = {
                    "mode": "score",
                    "training_id": score.training_id,
                }

            self._finish_success(
                trace_id,
                request.session_id,
                "training_plan",
                "TrainingAgent",
                started,
                result_metadata=result_metadata,
            )
            return GenerateAndScoreTrainingResult(
                success=True,
                message=(
                    "Training task generated."
                    if request.mode == "generate"
                    else "Training answer scored."
                ),
                trace_id=trace_id,
                session_id=request.session_id,
                status=state.status,
                data=data,
            )
        except Exception as exc:
            return self._failure_result(
                GenerateAndScoreTrainingResult,
                request,
                trace_id,
                state,
                exc,
                started,
            )

    async def recommend_learning_and_job_resources(
        self,
        request: RecommendLearningAndJobResourcesRequest,
    ) -> RecommendLearningAndJobResourcesResult:
        """Recommend real resources from ordered match gaps without an LLM."""

        trace_id = request.trace_id or f"tool-{uuid4().hex}"
        started = perf_counter()
        state: CareerState | None = None
        try:
            record, created = self._begin_call(
                "recommend_learning_and_job_resources", request, trace_id
            )
            if not created:
                self._require_replayable(record)
                return self._replay_resources(request, trace_id)

            state = self._load_required(request)
            if state.match_result is None:
                raise MCPToolFailure(
                    "MATCH_RESULT_NOT_FOUND",
                    "Run job matching before requesting learning resources.",
                    missing_fields=["match_result"],
                )

            ability_gaps = []
            for item in state.get_skill_gaps() or []:
                if not isinstance(item, Mapping):
                    continue
                dimension = item.get("dimension")
                if isinstance(dimension, str) and dimension.strip():
                    ability_gaps.append(dimension)
            title = (state.job_profile or {}).get("title")
            target_job = title if isinstance(title, str) and title.strip() else None
            raw_result = self.resource_service.recommend_resources(
                ability_gaps=ability_gaps,
                target_job=target_job,
            )
            if not isinstance(raw_result, Mapping):
                raise MCPToolFailure(
                    "RESOURCE_SERVICE_ERROR",
                    "ResourceService returned an invalid result.",
                    retryable=True,
                )
            if isinstance(raw_result.get("error"), str):
                raise MCPToolFailure(
                    "RESOURCE_SERVICE_ERROR",
                    "ResourceService could not produce recommendations.",
                    retryable=True,
                )
            resource_result = ResourceRecommendation.model_validate(raw_result)
            state.apply_agent_data(
                {"resource_result": resource_result.model_dump(mode="json")}
            )
            self.orchestrator.persist(state)

            self._finish_success(
                trace_id,
                request.session_id,
                "resource_result",
                None,
                started,
            )
            return RecommendLearningAndJobResourcesResult(
                success=True,
                message="Learning and job resources recommended.",
                trace_id=trace_id,
                session_id=request.session_id,
                status=state.status,
                data=RecommendLearningAndJobResourcesData(
                    resource_result=resource_result,
                ),
            )
        except Exception as exc:
            return self._failure_result(
                RecommendLearningAndJobResourcesResult,
                request,
                trace_id,
                state,
                exc,
                started,
            )

    async def save_growth_feedback(
        self,
        request: SaveGrowthFeedbackRequest,
    ) -> SaveGrowthFeedbackResult:
        """Save real feedback while State supplies match/training context."""

        trace_id = request.trace_id or f"tool-{uuid4().hex}"
        started = perf_counter()
        state: CareerState | None = None
        try:
            record, created = self._begin_call(
                "save_growth_feedback", request, trace_id
            )
            if not created:
                self._require_replayable(record)
                return self._replay_feedback(request, trace_id)

            state = self._load_required(request)
            stage_input = request.model_dump(
                mode="json",
                exclude={"session_id", "user_id", "trace_id"},
                exclude_none=True,
            )
            await self._run_agent(
                state,
                "FeedbackAgent",
                trace_id,
                stage_input=stage_input,
                tool_name="save_growth_feedback",
            )
            if state.status == "FAILED" or state.feedback_result is None:
                raise MCPToolFailure(
                    "FEEDBACK_FAILED",
                    "CareerPulse could not save validated feedback.",
                    retryable=True,
                )
            feedback_result = FeedbackAgentResult.model_validate(
                state.feedback_result
            )
            self._finish_success(
                trace_id,
                request.session_id,
                "feedback_result",
                "FeedbackAgent",
                started,
            )
            return SaveGrowthFeedbackResult(
                success=True,
                message="Feedback saved and growth snapshot updated.",
                trace_id=trace_id,
                session_id=request.session_id,
                status=state.status,
                data=SaveGrowthFeedbackData(
                    agent_run_id=f"{request.session_id}:FeedbackAgent",
                    feedback_result=feedback_result,
                ),
            )
        except Exception as exc:
            return self._failure_result(
                SaveGrowthFeedbackResult,
                request,
                trace_id,
                state,
                exc,
                started,
            )

    async def _run_database_read(
        self,
        *,
        request: BaseModel,
        tool_name: str,
        result_type: type[ResultT],
        operation: Callable[[], DatabaseDataT],
        result_field: str,
        success_message: str,
    ) -> ResultT:
        trace_id = getattr(request, "trace_id") or f"tool-{uuid4().hex}"
        started = perf_counter()
        state: CareerState | None = None
        ledger_created = False
        try:
            record, ledger_created = self._begin_call(tool_name, request, trace_id)
            if not ledger_created:
                self._require_replayable(record)
            state = self._load_or_create(request)
            try:
                data = await asyncio.wait_for(
                    asyncio.to_thread(operation),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise MCPToolFailure(
                    "MCP_TOOL_TIMEOUT",
                    "CareerPulse cancelled the database Tool at its configured timeout.",
                    retryable=True,
                ) from exc
            if ledger_created:
                self._finish_success(
                    trace_id,
                    getattr(request, "session_id"),
                    result_field,
                    None,
                    started,
                    result_metadata=self._database_log_metadata(
                        tool_name,
                        request,
                        data,
                    ),
                )
            return result_type(
                success=True,
                message=success_message,
                trace_id=trace_id,
                session_id=getattr(request, "session_id"),
                status=state.status,
                data=data,
            )
        except DatabaseToolError as exc:
            failure = MCPToolFailure(
                exc.error_code,
                exc.message,
                retryable=exc.retryable,
            )
            return self._failure_result(
                result_type,
                request,
                trace_id,
                state,
                failure,
                started,
                finish_call=ledger_created,
            )
        except Exception as exc:
            return self._failure_result(
                result_type,
                request,
                trace_id,
                state,
                exc,
                started,
                finish_call=ledger_created,
            )

    @staticmethod
    def _database_log_metadata(
        tool_name: str,
        request: BaseModel,
        data: DatabaseDataT,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "data_source": data.data_source,
            "fallback_used": data.fallback_used,
        }
        if tool_name == "read_student_profile":
            metadata.update(
                {
                    "student_id": getattr(request, "student_id"),
                    "record_count": 1,
                }
            )
        elif tool_name == "search_jobs":
            metadata.update(
                {
                    "keyword_present": bool(getattr(request, "keyword")),
                    "city_present": bool(getattr(request, "city")),
                    "industry_present": bool(getattr(request, "industry")),
                    "page": getattr(request, "page"),
                    "page_size": getattr(request, "page_size"),
                    "record_count": len(data.items),
                }
            )
        elif tool_name == "read_job_context":
            metadata.update(
                {
                    "job_id": getattr(request, "job_id"),
                    "normalized_title_present": bool(
                        getattr(request, "normalized_title")
                    ),
                    "record_count": 1,
                }
            )
        else:
            metadata.update(
                {
                    "source_type_present": bool(
                        getattr(request, "source_type_key")
                    ),
                    "relation_type": getattr(request, "relation_type"),
                    "limit": getattr(request, "limit"),
                    "record_count": len(data.edges),
                }
            )
        return metadata

    def _begin_call(
        self, tool_name: str, request: BaseModel, trace_id: str
    ) -> tuple[dict[str, Any], bool]:
        body = request.model_dump(mode="json", exclude={"trace_id"})
        canonical = json.dumps(
            {"tool_name": tool_name, "payload": body},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        try:
            record, created = self.orchestrator.repository.create_tool_call(
                tool_call_id=trace_id,
                tool_name=tool_name,
                idempotency_key=trace_id,
                request_fingerprint=fingerprint,
                session_id=getattr(request, "session_id"),
                platform_session_id=None,
                user_id_hash=hashlib.sha256(
                    getattr(request, "user_id").encode("utf-8")
                ).hexdigest(),
            )
        except Exception as exc:
            raise MCPToolFailure(
                "TOOL_LOG_WRITE_FAILED",
                "The MCP call ledger is unavailable.",
                retryable=True,
            ) from exc
        if record["request_fingerprint"] != fingerprint:
            raise MCPToolFailure(
                "TRACE_ID_CONFLICT",
                "The trace_id was already used with different arguments.",
            )
        return record, created

    @staticmethod
    def _require_replayable(record: dict[str, Any]) -> None:
        if record["status"] != "succeeded":
            raise MCPToolFailure(
                "PREVIOUS_CALL_NOT_SUCCESSFUL",
                "This trace_id belongs to a call that did not succeed.",
                retryable=record["status"] in {"running", "timed_out"},
            )

    def _load_or_create(self, request: BaseModel) -> CareerState:
        state = self.orchestrator.get_session(getattr(request, "session_id"))
        if state is None:
            state = CareerState(
                session_id=getattr(request, "session_id"),
                user_id=getattr(request, "user_id"),
            )
            self.orchestrator.persist(state)
        self._check_identity(state, getattr(request, "user_id"))
        return state

    def _load_required(self, request: BaseModel) -> CareerState:
        state = self.orchestrator.get_session(getattr(request, "session_id"))
        if state is None:
            raise MCPToolFailure(
                "SESSION_NOT_FOUND",
                "The CareerPulse session does not exist.",
                missing_fields=["student_profile", "job_profile"],
            )
        self._check_identity(state, getattr(request, "user_id"))
        return state

    @staticmethod
    def _check_identity(state: CareerState, user_id: str) -> None:
        if state.user_id is not None and state.user_id != user_id:
            raise MCPToolFailure(
                "SESSION_USER_MISMATCH",
                "The supplied user_id does not own this session.",
            )
        if state.user_id is None:
            state.user_id = user_id

    async def _run_agent(
        self,
        state: CareerState,
        agent_name: str,
        trace_id: str,
        *,
        stage_input: dict[str, Any] | None = None,
        tool_name: str | None = None,
    ) -> None:
        try:
            await asyncio.wait_for(
                self.orchestrator.run_stage(
                    state,
                    agent_name,
                    stage_input=stage_input,
                ),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            self._append_timeout_log(state, agent_name, tool_name=tool_name)
            state.set_status("FAILED", error_type="MCP_TOOL_TIMEOUT")
            self.orchestrator.persist(state)
            raise MCPToolFailure(
                "MCP_TOOL_TIMEOUT",
                "CareerPulse cancelled the MCP tool at its configured timeout.",
                retryable=True,
            ) from exc

    async def _run_profile_agent_without_persist(
        self,
        state: CareerState,
        trace_id: str,
    ) -> None:
        """Run ProfileAgent before the PostgreSQL-first commit boundary."""

        agent = next(
            (
                candidate
                for candidate in self.orchestrator.agents
                if candidate.name == "ProfileAgent"
            ),
            None,
        )
        if agent is None:
            raise MCPToolFailure(
                "AGENT_NOT_CONFIGURED",
                "ProfileAgent is not configured.",
            )
        try:
            await asyncio.wait_for(agent.run(state), timeout=self.timeout_seconds)
        except asyncio.TimeoutError as exc:
            self._append_timeout_log(
                state,
                "ProfileAgent",
                tool_name="build_student_profile",
            )
            state.set_status("FAILED", error_type="MCP_TOOL_TIMEOUT")
            raise MCPToolFailure(
                "MCP_TOOL_TIMEOUT",
                "CareerPulse cancelled the MCP tool at its configured timeout.",
                retryable=True,
            ) from exc

    @staticmethod
    def _append_profile_persistence_log(
        state: CareerState,
        *,
        student_id: int,
        duration_ms: int,
    ) -> None:
        if not state.agent_logs:
            return
        reference = hashlib.sha256(str(student_id).encode("ascii")).hexdigest()[:12]
        state.agent_logs[-1].tool_calls.append(
            ToolCallLog(
                tool_name="persist_student_profile",
                service_name="StudentProfilePersistenceService",
                input_summary="validated_profile=true; identity_fields=excluded",
                output_summary=(
                    "source=postgresql; record_count=1; "
                    f"student_ref_hash={reference}"
                ),
                duration_ms=duration_ms,
                status="success",
            )
        )

    @staticmethod
    def _append_job_database_log(
        state: CareerState,
        *,
        duration_ms: int,
    ) -> None:
        if not state.agent_logs:
            return
        reference = state.job_record_id or state.job_type_key or "unknown"
        reference_hash = hashlib.sha256(
            str(reference).encode("utf-8")
        ).hexdigest()[:12]
        state.agent_logs[-1].tool_calls.append(
            ToolCallLog(
                tool_name="read_job_context",
                service_name="JobContextService",
                input_summary=(
                    "reference=job_id"
                    if state.job_record_id is not None
                    else "reference=type_key"
                ),
                output_summary=(
                    "source=postgresql; record_count=1; "
                    f"job_ref_hash={reference_hash}"
                ),
                duration_ms=duration_ms,
                status="success",
            )
        )

    def _finish_success(
        self,
        trace_id: str,
        session_id: str,
        result_field: str,
        agent_name: str | None,
        started: float,
        *,
        result_metadata: dict[str, Any] | None = None,
    ) -> None:
        result_data = {"result_field": result_field}
        if result_metadata:
            result_data.update(result_metadata)
        self.orchestrator.repository.finish_tool_call(
            trace_id,
            status="succeeded",
            result_data=result_data,
            agent_run_key=(
                f"{session_id}:{agent_name}" if agent_name is not None else None
            ),
            duration_ms=self._duration(started),
        )

    def _failure_result(
        self,
        result_type: type[ResultT],
        request: BaseModel,
        trace_id: str,
        state: CareerState | None,
        exc: Exception,
        started: float,
        *,
        finish_call: bool = True,
    ) -> ResultT:
        if isinstance(exc, MCPToolFailure):
            failure = exc
        elif isinstance(exc, ValidationError):
            failure = MCPToolFailure(
                "RESULT_SCHEMA_INVALID",
                "CareerPulse produced data that failed its fixed schema.",
                retryable=True,
            )
        else:
            failure = MCPToolFailure(
                "MCP_TOOL_EXECUTION_FAILED",
                "CareerPulse failed without returning private exception content.",
                retryable=True,
            )
        if finish_call and failure.error_code != "TRACE_ID_CONFLICT":
            try:
                self.orchestrator.repository.finish_tool_call(
                    trace_id,
                    status=(
                        "timed_out"
                        if failure.error_code == "MCP_TOOL_TIMEOUT"
                        else "failed"
                    ),
                    error_code=-6 if failure.error_code == "MCP_TOOL_TIMEOUT" else -1,
                    error_type=failure.error_code,
                    duration_ms=self._duration(started),
                )
            except Exception:
                failure = MCPToolFailure(
                    "TOOL_LOG_WRITE_FAILED",
                    "The MCP call failed and its terminal log could not be persisted.",
                    retryable=True,
                )
        return result_type(
            success=False,
            error_code=failure.error_code,
            message=failure.message,
            missing_fields=failure.missing_fields,
            retryable=failure.retryable,
            trace_id=trace_id,
            session_id=getattr(request, "session_id"),
            status=state.status if state is not None else "INITIALIZED",
            data=None,
        )

    def _replay_profile(
        self,
        request: BuildStudentProfileRequest,
        trace_id: str,
        record: dict[str, Any],
    ) -> BuildStudentProfileResult:
        state = self._load_required(request)
        metadata = record.get("result_data") or {}
        student_id = metadata.get("student_id") or state.student_profile_id
        data_source = metadata.get("data_source") or "session"
        fallback_used = bool(
            metadata.get("fallback_used", self._agent_fallback(state, "ProfileAgent"))
        )
        if (
            data_source == "postgresql"
            and student_id is not None
            and self.profile_persistence_service is not None
            and (
                state.student_profile is None
                or state.student_profile_id != student_id
                or metadata.get("phase") == "postgres_committed"
            )
        ):
            restored = self.profile_persistence_service.get_profile(
                int(student_id),
                user_id=request.user_id,
            )
            state.student_profile_id = restored.student_id
            state.student_profile_snapshot_id = restored.student_id
            state.student_profile_updated_at = restored.profile.updated_at
            state.student_profile = restored.profile.model_dump(mode="json")
            state.set_status("PROFILE_COMPLETED")
            self.orchestrator.persist(state)
            self._finish_success(
                trace_id,
                request.session_id,
                "student_profile",
                "ProfileAgent",
                perf_counter(),
                result_metadata={
                    **metadata,
                    "phase": "complete",
                    "student_id": restored.student_id,
                    "profile_updated_at": restored.profile.updated_at.isoformat(),
                    "data_source": "postgresql",
                },
            )
        data = BuildStudentProfileData(
            agent_run_id=f"{request.session_id}:ProfileAgent",
            fallback_used=fallback_used,
            student_id=student_id,
            data_source=data_source,
            demo_mode=bool(metadata.get("demo_mode", False)),
            student_profile=StudentProfile.model_validate(state.student_profile),
        )
        return BuildStudentProfileResult(
            success=True, message="Student profile replayed.", trace_id=trace_id,
            session_id=request.session_id, status=state.status, data=data
        )

    def _replay_job(
        self,
        request: AnalyzeTargetJobRequest,
        trace_id: str,
        record: dict[str, Any],
    ) -> AnalyzeTargetJobResult:
        state = self._load_required(request)
        metadata = record.get("result_data") or {}
        profile = JobProfile.model_validate(state.job_profile)
        data_source = metadata.get("data_source") or state.job_data_source or "session"
        data = AnalyzeTargetJobData(
            agent_run_id=f"{request.session_id}:JobAgent",
            fallback_used=bool(
                metadata.get("fallback_used", self._agent_fallback(state, "JobAgent"))
            ),
            job_id=metadata.get("job_id") or state.job_record_id or profile.job_id,
            type_key=(
                metadata.get("type_key")
                or state.job_type_key
                or profile.normalized_title
            ),
            data_source=data_source,
            demo_mode=bool(metadata.get("demo_mode", data_source == "demo_json")),
            job_profile=profile,
            trend_result=TrendResult.model_validate(state.trend_result),
        )
        return AnalyzeTargetJobResult(
            success=True, message="Target job replayed.", trace_id=trace_id,
            session_id=request.session_id, status=state.status, data=data
        )

    def _replay_match(
        self, request: AnalyzeJobMatchMCPRequest, trace_id: str
    ) -> AnalyzeJobMatchMCPResult:
        state = self._load_required(request)
        data = AnalyzeJobMatchMCPData(
            agent_run_id=f"{request.session_id}:MatchAgent",
            match_result=MatchResult.model_validate(state.match_result),
        )
        return AnalyzeJobMatchMCPResult(
            success=True, message="Job match replayed.", trace_id=trace_id,
            session_id=request.session_id, status=state.status, data=data
        )

    def _replay_path(
        self, request: GenerateCareerPathMCPRequest, trace_id: str
    ) -> GenerateCareerPathMCPResult:
        state = self._load_required(request)
        data = GenerateCareerPathMCPData(
            agent_run_id=f"{request.session_id}:PathAgent",
            career_roadmap=PathResult.model_validate(state.career_roadmap),
        )
        return GenerateCareerPathMCPResult(
            success=True, message="Career path replayed.", trace_id=trace_id,
            session_id=request.session_id, status=state.status, data=data
        )

    def _replay_training(
        self,
        request: GenerateAndScoreTrainingRequest,
        trace_id: str,
        record: dict[str, Any],
    ) -> GenerateAndScoreTrainingResult:
        state = self._load_required(request)
        metadata = record.get("result_data") or {}
        training_id = metadata.get("training_id") or request.training_id
        if request.mode == "generate":
            task_value = state.get_training_task(training_id)
            task = TrainingTask.model_validate(task_value)
            data = GenerateAndScoreTrainingData(
                agent_run_id=f"{request.session_id}:TrainingAgent",
                mode="generate",
                training_task=task,
            )
        else:
            score_value = state.get_latest_training_score()
            if (
                score_value is None
                or score_value.get("training_id") != request.training_id
            ):
                raise MCPToolFailure(
                    "TRAINING_RESULT_NOT_FOUND",
                    "The persisted score is no longer available.",
                )
            data = GenerateAndScoreTrainingData(
                agent_run_id=f"{request.session_id}:TrainingAgent",
                mode="score",
                training_score=TrainingScore.model_validate(score_value),
            )
        return GenerateAndScoreTrainingResult(
            success=True,
            message="Training result replayed.",
            trace_id=trace_id,
            session_id=request.session_id,
            status=state.status,
            data=data,
        )

    def _replay_resources(
        self,
        request: RecommendLearningAndJobResourcesRequest,
        trace_id: str,
    ) -> RecommendLearningAndJobResourcesResult:
        state = self._load_required(request)
        resource_result = ResourceRecommendation.model_validate(
            state.resource_result
        )
        return RecommendLearningAndJobResourcesResult(
            success=True,
            message="Resource recommendations replayed.",
            trace_id=trace_id,
            session_id=request.session_id,
            status=state.status,
            data=RecommendLearningAndJobResourcesData(
                resource_result=resource_result,
            ),
        )

    def _replay_feedback(
        self,
        request: SaveGrowthFeedbackRequest,
        trace_id: str,
    ) -> SaveGrowthFeedbackResult:
        state = self._load_required(request)
        feedback_result = FeedbackAgentResult.model_validate(state.feedback_result)
        return SaveGrowthFeedbackResult(
            success=True,
            message="Feedback result replayed.",
            trace_id=trace_id,
            session_id=request.session_id,
            status=state.status,
            data=SaveGrowthFeedbackData(
                agent_run_id=f"{request.session_id}:FeedbackAgent",
                feedback_result=feedback_result,
            ),
        )

    @staticmethod
    def _agent_fallback(state: CareerState, agent_name: str) -> bool:
        return any(
            log.agent_name == agent_name and log.fallback_used
            for log in state.agent_logs
        )

    def _append_timeout_log(
        self,
        state: CareerState,
        agent_name: str,
        *,
        tool_name: str | None = None,
    ) -> None:
        if any(log.agent_name == agent_name for log in state.agent_logs):
            return
        service_name = {
            "MatchAgent": "MatchService",
            "PathAgent": "PathService",
            "TrainingAgent": "TrainingService",
            "FeedbackAgent": "FeedbackService",
        }.get(agent_name)
        state.agent_logs.append(
            AgentLog(
                session_id=state.session_id,
                agent_name=agent_name,
                service_name=service_name,
                status="failed",
                summary=f"{agent_name} MCP 调用超时",
                duration_ms=round(self.timeout_seconds * 1000),
                tool_calls=[
                    ToolCallLog(
                        tool_name=tool_name or agent_name,
                        service_name=service_name,
                        input_summary="已提供结构化会话字段",
                        output_summary="未生成结果",
                        duration_ms=round(self.timeout_seconds * 1000),
                        status="error",
                    )
                ],
                fallback_used=False,
                error="TimeoutError: MCP tool execution timed out",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

    @staticmethod
    def _duration(started: float) -> int:
        return max(0, round((perf_counter() - started) * 1000))


__all__ = ["CareerMCPToolService", "MCPToolFailure"]
