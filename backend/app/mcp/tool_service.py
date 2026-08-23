"""Transport-neutral MCP tool application service.

This module performs state and logging adaptation only. Deterministic match,
gap and path calculations remain owned by MatchService and PathService through
their existing Agents.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from ..orchestrator import AgentLog, CareerOrchestrator, CareerState, ToolCallLog
from ..schemas.career_profile_schema import StudentProfile
from ..schemas.job_schema import JobProfile, TrendResult
from ..schemas.match_schema import MatchResult
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


ResultT = TypeVar("ResultT", bound=MCPToolResult)


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
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("MCP tool timeout must be in (0, 60]")
        self.orchestrator = orchestrator
        self.timeout_seconds = timeout_seconds

    async def build_student_profile(
        self, request: BuildStudentProfileRequest
    ) -> BuildStudentProfileResult:
        trace_id = request.trace_id or f"tool-{uuid4().hex}"
        started = perf_counter()
        state: CareerState | None = None
        try:
            record, created = self._begin_call(
                "build_student_profile", request, trace_id
            )
            if not created:
                self._require_replayable(record)
                return self._replay_profile(request, trace_id)
            state = self._load_or_create(request)
            incoming = request.student_input.model_dump(mode="json", exclude_none=True)
            if state.student_profile is not None:
                if state.student_input not in (None, incoming):
                    raise MCPToolFailure(
                        "SESSION_PAYLOAD_CONFLICT",
                        "This session already contains different student evidence.",
                    )
            else:
                state.student_input = incoming
                await self._run_agent(state, "ProfileAgent", trace_id)
            profile = StudentProfile.model_validate(state.student_profile)
            if state.status != "PROFILE_COMPLETED":
                state.set_status("PROFILE_COMPLETED")
                self.orchestrator.persist(state)
            fallback_used = self._agent_fallback(state, "ProfileAgent")
            data = BuildStudentProfileData(
                agent_run_id=f"{request.session_id}:ProfileAgent",
                fallback_used=fallback_used,
                student_profile=profile,
            )
            self._finish_success(
                trace_id, request.session_id, "student_profile", "ProfileAgent", started
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
                BuildStudentProfileResult, request, trace_id, state, exc, started
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
                return self._replay_job(request, trace_id)
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
                await self._run_agent(state, "JobAgent", trace_id)
            job_profile = JobProfile.model_validate(state.job_profile)
            trend_result = TrendResult.model_validate(state.trend_result)
            if state.status != "JOB_COMPLETED":
                state.set_status("JOB_COMPLETED")
                self.orchestrator.persist(state)
            fallback_used = self._agent_fallback(state, "JobAgent")
            data = AnalyzeTargetJobData(
                agent_run_id=f"{request.session_id}:JobAgent",
                fallback_used=fallback_used,
                job_profile=job_profile,
                trend_result=trend_result,
            )
            self._finish_success(
                trace_id, request.session_id, "job_profile", "JobAgent", started
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
        self, state: CareerState, agent_name: str, trace_id: str
    ) -> None:
        try:
            await asyncio.wait_for(
                self.orchestrator.run_stage(state, agent_name),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            self._append_timeout_log(state, agent_name)
            state.set_status("FAILED", error_type="MCP_TOOL_TIMEOUT")
            self.orchestrator.persist(state)
            raise MCPToolFailure(
                "MCP_TOOL_TIMEOUT",
                "CareerPulse cancelled the MCP tool at its configured timeout.",
                retryable=True,
            ) from exc

    def _finish_success(
        self,
        trace_id: str,
        session_id: str,
        result_field: str,
        agent_name: str,
        started: float,
    ) -> None:
        self.orchestrator.repository.finish_tool_call(
            trace_id,
            status="succeeded",
            result_data={"result_field": result_field},
            agent_run_key=f"{session_id}:{agent_name}",
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
        if failure.error_code != "TRACE_ID_CONFLICT":
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
        self, request: BuildStudentProfileRequest, trace_id: str
    ) -> BuildStudentProfileResult:
        state = self._load_required(request)
        data = BuildStudentProfileData(
            agent_run_id=f"{request.session_id}:ProfileAgent",
            fallback_used=self._agent_fallback(state, "ProfileAgent"),
            student_profile=StudentProfile.model_validate(state.student_profile),
        )
        return BuildStudentProfileResult(
            success=True, message="Student profile replayed.", trace_id=trace_id,
            session_id=request.session_id, status=state.status, data=data
        )

    def _replay_job(
        self, request: AnalyzeTargetJobRequest, trace_id: str
    ) -> AnalyzeTargetJobResult:
        state = self._load_required(request)
        data = AnalyzeTargetJobData(
            agent_run_id=f"{request.session_id}:JobAgent",
            fallback_used=self._agent_fallback(state, "JobAgent"),
            job_profile=JobProfile.model_validate(state.job_profile),
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

    @staticmethod
    def _agent_fallback(state: CareerState, agent_name: str) -> bool:
        return any(
            log.agent_name == agent_name and log.fallback_used
            for log in state.agent_logs
        )

    def _append_timeout_log(self, state: CareerState, agent_name: str) -> None:
        if any(log.agent_name == agent_name for log in state.agent_logs):
            return
        service_name = {
            "MatchAgent": "MatchService",
            "PathAgent": "PathService",
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
                        tool_name=agent_name,
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
