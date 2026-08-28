"""Official MCP SDK server for CareerPulse Streamable HTTP tools."""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field

from ..orchestrator import CareerOrchestrator
from ..schemas.internal_tool_schema import (
    GenerateAndScoreTrainingRequest,
    GenerateAndScoreTrainingResult,
    RecommendLearningAndJobResourcesRequest,
    RecommendLearningAndJobResourcesResult,
    SaveGrowthFeedbackRequest,
    SaveGrowthFeedbackResult,
)
from ..schemas.mcp_tool_schema import (
    AnalyzeJobMatchMCPRequest,
    AnalyzeJobMatchMCPResult,
    AnalyzeTargetJobRequest,
    AnalyzeTargetJobResult,
    BuildStudentProfileRequest,
    BuildStudentProfileResult,
    GenerateCareerPathMCPRequest,
    GenerateCareerPathMCPResult,
    StudentProfileInput,
    TargetJobInput,
)
from ..schemas.training_schema import TrainingType
from .input_normalization import (
    normalize_enum_text,
    parse_optional_float,
    parse_optional_int,
    parse_optional_list,
)
from .tool_service import CareerMCPToolService


ASGIApp = Callable[
    [dict[str, Any], Callable[[], Awaitable[dict[str, Any]]], Callable[[dict[str, Any]], Awaitable[None]]],
    Awaitable[None],
]

SessionIdInput = Annotated[
    str,
    Field(
        description=(
            "Stable CareerPulse session identifier. Reuse the same value for "
            "every tool in one conversation."
        )
    ),
]
UserIdInput = Annotated[
    str,
    Field(
        description=(
            "Stable user identifier for the session. Reuse the same value with "
            "the same session_id."
        )
    ),
]
TraceIdInput = Annotated[
    str | None,
    Field(
        description=(
            "Optional unique call identifier for tracing and idempotent replay."
        )
    ),
]

_TRAINING_TYPE_ALIASES: dict[str, TrainingType] = {
    "remote_collaboration": "remote_collaboration",
    "remote collaboration": "remote_collaboration",
    "远程协作": "remote_collaboration",
    "远程办公协作": "remote_collaboration",
    "异步协作": "remote_collaboration",
    "跨时区协作": "remote_collaboration",
    "ai_office_task": "ai_office_task",
    "ai office task": "ai_office_task",
    "AI办公": "ai_office_task",
    "AI 办公": "ai_office_task",
    "AI办公任务": "ai_office_task",
    "人工智能办公": "ai_office_task",
    "cross_role_communication": "cross_role_communication",
    "cross role communication": "cross_role_communication",
    "跨角色沟通": "cross_role_communication",
    "跨岗沟通": "cross_role_communication",
    "跨岗位沟通": "cross_role_communication",
    "跨部门沟通": "cross_role_communication",
}
_TRAINING_TYPE_SUPPORT = (
    "当前仅支持 remote_collaboration（远程协作）、"
    "ai_office_task（AI办公任务）或 "
    "cross_role_communication（跨角色沟通）；"
    "当前不支持面试自我介绍类训练"
)


class BearerTokenASGI:
    """Protect only the MCP transport with a configured static Bearer token."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        if not token:
            raise ValueError("MCP_API_TOKEN is required when MCP auth is enabled")
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        supplied = headers.get("authorization", "")
        expected = f"Bearer {self.token}"
        if not secrets.compare_digest(supplied, expected):
            body = b'{"error":"authentication_failed"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode("ascii")),
                        (b"www-authenticate", b"Bearer"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


def create_career_mcp_server(
    orchestrator: CareerOrchestrator,
    *,
    timeout_seconds: float = 25.0,
) -> MCPServer:
    """Create one MCP server bound to the application's real orchestrator."""

    service = CareerMCPToolService(
        orchestrator,
        timeout_seconds=timeout_seconds,
    )
    server = MCPServer(
        name="CareerPulse-A02",
        title="CareerPulse A02 Career Navigation",
        version="stage4-mcp-v1",
        description=(
            "Session-based CareerPulse tools. Profile and job steps store state; "
            "match, path, training, resource and feedback steps reuse validated "
            "session state and never accept client-supplied business results."
        ),
        instructions=(
            "Call build_student_profile and analyze_target_job before "
            "analyze_job_match. Call generate_career_path only after a successful "
            "match. Then call generate_and_score_training, "
            "recommend_learning_and_job_resources or save_growth_feedback as "
            "needed. Reuse the same session_id and user_id for every step."
        ),
    )

    @server.tool(
        name="build_student_profile",
        description=(
            "Build and store a student profile when the user provides resume, "
            "education, skills, project or experience evidence. Send flat fields, "
            "not a nested profile object. Multi-value fields accept either a "
            "comma/Chinese-comma/dunhao/newline-delimited string or a string array. "
            "Requires session_id and user_id and at least one evidence field; never "
            "include credentials or invent unsupported abilities."
        ),
        structured_output=True,
    )
    async def build_student_profile(
        session_id: SessionIdInput,
        user_id: UserIdInput,
        resume_text: Annotated[
            str | None,
            Field(description="Optional resume or profile evidence text."),
        ] = None,
        education_level: Annotated[
            str | None,
            Field(description="Optional education level, for example 本科 or 硕士."),
        ] = None,
        major: Annotated[
            str | None,
            Field(description="Optional academic major."),
        ] = None,
        graduation_year: Annotated[
            str | int | None,
            Field(description="Optional graduation year as an integer or numeric text."),
        ] = None,
        city: Annotated[
            str | None,
            Field(description="Optional current or preferred city."),
        ] = None,
        target_job: Annotated[
            str | None,
            Field(description="Optional target job named by the user."),
        ] = None,
        target_industry: Annotated[
            str | None,
            Field(description="Optional target industry."),
        ] = None,
        years_of_experience: Annotated[
            str | int | float | None,
            Field(description="Optional years of experience as a number or numeric text."),
        ] = None,
        skills: Annotated[
            str | list[str] | None,
            Field(description="Skills as delimited text or a string array."),
        ] = None,
        projects: Annotated[
            str | list[str] | None,
            Field(description="Projects as delimited text or a string array."),
        ] = None,
        internships: Annotated[
            str | list[str] | None,
            Field(description="Internships as delimited text or a string array."),
        ] = None,
        work_experience: Annotated[
            str | list[str] | None,
            Field(description="Work experience as delimited text or a string array."),
        ] = None,
        competitions: Annotated[
            str | list[str] | None,
            Field(description="Competitions as delimited text or a string array."),
        ] = None,
        certificates: Annotated[
            str | list[str] | None,
            Field(description="Certificates as delimited text or a string array."),
        ] = None,
        supplementary_info: Annotated[
            str | None,
            Field(description="Optional additional profile evidence."),
        ] = None,
        trace_id: TraceIdInput = None,
    ) -> BuildStudentProfileResult:
        form_fields = {
            key: value
            for key, value in {
                "education_level": education_level,
                "major": major,
                "graduation_year": parse_optional_int(
                    graduation_year, field_name="graduation_year"
                ),
                "city": city,
                "target_job": target_job,
                "target_industry": target_industry,
                "years_of_experience": parse_optional_float(
                    years_of_experience, field_name="years_of_experience"
                ),
            }.items()
            if value is not None
        }
        student_input = StudentProfileInput(
            resume_text=resume_text,
            form_fields=form_fields or None,
            skills=parse_optional_list(skills, field_name="skills"),
            projects=parse_optional_list(projects, field_name="projects"),
            internships=parse_optional_list(internships, field_name="internships"),
            work_experience=parse_optional_list(
                work_experience, field_name="work_experience"
            ),
            competitions=parse_optional_list(competitions, field_name="competitions"),
            certificates=parse_optional_list(certificates, field_name="certificates"),
            supplementary_info=supplementary_info,
        )
        request = BuildStudentProfileRequest(
            session_id=session_id,
            user_id=user_id,
            trace_id=trace_id,
            student_input=student_input,
        )
        return await service.build_student_profile(request)

    @server.tool(
        name="analyze_target_job",
        description=(
            "Analyze and store the target role after the user identifies it. Reuse "
            "the profile session_id and user_id, send job_title plus optional flat "
            "job evidence, and do not send a nested target_job object. Returns "
            "JOB_COMPLETED when the same CareerState is ready for matching."
        ),
        structured_output=True,
    )
    async def analyze_target_job(
        session_id: SessionIdInput,
        user_id: UserIdInput,
        job_title: Annotated[
            str,
            Field(description="Required target job title stated by the user."),
        ],
        job_id: Annotated[
            str | int | None,
            Field(description="Optional job identifier as an integer or numeric text."),
        ] = None,
        industry: Annotated[
            str | None,
            Field(description="Optional target-job industry."),
        ] = None,
        city: Annotated[
            str | None,
            Field(description="Optional target-job city."),
        ] = None,
        job_description: Annotated[
            str | None,
            Field(description="Optional job description evidence."),
        ] = None,
        trend_context: Annotated[
            str | None,
            Field(description="Optional user-supplied job trend context."),
        ] = None,
        trace_id: TraceIdInput = None,
    ) -> AnalyzeTargetJobResult:
        target_job_input = TargetJobInput(
            job_id=parse_optional_int(job_id, field_name="job_id"),
            job_title=job_title,
            industry=industry,
            city=city,
            job_description=job_description,
            trend_context=trend_context,
        )
        request = AnalyzeTargetJobRequest(
            session_id=session_id,
            user_id=user_id,
            trace_id=trace_id,
            target_job_input=target_job_input,
        )
        return await service.analyze_target_job(request)

    @server.tool(
        name="analyze_job_match",
        description=(
            "Call only after build_student_profile and analyze_target_job both "
            "succeeded in this same session. Pass only session_id and user_id; the "
            "tool loads the stored profile and target job. Do not pass profile JSON, "
            "scores or gaps. Deterministic MatchService owns all scores and returns "
            "MATCH_COMPLETED."
        ),
        structured_output=True,
    )
    async def analyze_job_match(
        session_id: SessionIdInput,
        user_id: UserIdInput,
        trace_id: TraceIdInput = None,
    ) -> AnalyzeJobMatchMCPResult:
        request = AnalyzeJobMatchMCPRequest(
            session_id=session_id,
            user_id=user_id,
            trace_id=trace_id,
        )
        return await service.analyze_job_match(request)

    @server.tool(
        name="generate_career_path",
        description=(
            "Call only after analyze_job_match succeeded in this same session. Pass "
            "only session_id and user_id; the tool loads the stored match result. Do "
            "not pass match JSON, nodes or path scores. Deterministic PathService "
            "owns path scoring and returns PATH_COMPLETED."
        ),
        structured_output=True,
    )
    async def generate_career_path(
        session_id: SessionIdInput,
        user_id: UserIdInput,
        trace_id: TraceIdInput = None,
    ) -> GenerateCareerPathMCPResult:
        request = GenerateCareerPathMCPRequest(
            session_id=session_id,
            user_id=user_id,
            trace_id=trace_id,
        )
        return await service.generate_career_path(request)

    @server.tool(
        name="generate_and_score_training",
        description=(
            "Generate one supported workplace training task after profile, target "
            "job and match are ready, or score a task stored in the same session. "
            "Generate mode: send training_type only; supported intents are remote "
            "collaboration/远程协作, AI office tasks/AI办公任务, and cross-role "
            "communication/跨角色沟通. Interview introductions are not supported. "
            "Score mode: send training_id and user_answer. Never send scores, "
            "criteria or ability updates because TrainingService owns them."
        ),
        structured_output=True,
    )
    async def generate_and_score_training(
        session_id: SessionIdInput,
        user_id: UserIdInput,
        training_type: Annotated[
            str | None,
            Field(
                description=(
                    "Generate-mode type: remote_collaboration/远程协作, "
                    "ai_office_task/AI办公任务, or "
                    "cross_role_communication/跨角色沟通."
                )
            ),
        ] = None,
        training_id: Annotated[
            str | None,
            Field(description="Stored training task ID; required only in score mode."),
        ] = None,
        user_answer: Annotated[
            str | None,
            Field(description="User-authored answer; required only in score mode."),
        ] = None,
        trace_id: TraceIdInput = None,
    ) -> GenerateAndScoreTrainingResult:
        normalized_training_type = normalize_enum_text(
            training_type,
            field_name="training_type",
            aliases=_TRAINING_TYPE_ALIASES,
            supported_message=_TRAINING_TYPE_SUPPORT,
        )
        request = GenerateAndScoreTrainingRequest(
            session_id=session_id,
            user_id=user_id,
            trace_id=trace_id,
            training_type=normalized_training_type,
            training_id=training_id,
            user_answer=user_answer,
        )
        return await service.generate_and_score_training(request)

    @server.tool(
        name="recommend_learning_and_job_resources",
        description=(
            "Recommend learning and job resources only after analyze_job_match has "
            "stored a target job and ordered skill gaps in this same session. Pass "
            "only session_id and user_id; callers cannot override gaps, target job "
            "or resource ranking inputs."
        ),
        structured_output=True,
    )
    async def recommend_learning_and_job_resources(
        session_id: SessionIdInput,
        user_id: UserIdInput,
        trace_id: TraceIdInput = None,
    ) -> RecommendLearningAndJobResourcesResult:
        request = RecommendLearningAndJobResourcesRequest(
            session_id=session_id,
            user_id=user_id,
            trace_id=trace_id,
        )
        return await service.recommend_learning_and_job_resources(request)

    @server.tool(
        name="save_growth_feedback",
        description=(
            "Save user-authored feedback after this session has a student profile "
            "and target job, typically after a planning or training round. "
            "satisfaction is required from 1 to 5 and may be an integer or numeric "
            "text; optional path, training and resource ratings use the same range. "
            "Existing match/training context is loaded from CareerState."
        ),
        structured_output=True,
    )
    async def save_growth_feedback(
        session_id: SessionIdInput,
        user_id: UserIdInput,
        satisfaction: Annotated[
            str | int,
            Field(description="Required satisfaction rating from 1 to 5."),
        ],
        path_rating: Annotated[
            str | int | None,
            Field(description="Optional career-path rating from 1 to 5."),
        ] = None,
        training_rating: Annotated[
            str | int | None,
            Field(description="Optional training rating from 1 to 5."),
        ] = None,
        resource_rating: Annotated[
            str | int | None,
            Field(description="Optional resource rating from 1 to 5."),
        ] = None,
        comments: Annotated[
            str | None,
            Field(description="Optional user-authored feedback comments."),
        ] = None,
        trace_id: TraceIdInput = None,
    ) -> SaveGrowthFeedbackResult:
        request = SaveGrowthFeedbackRequest(
            session_id=session_id,
            user_id=user_id,
            trace_id=trace_id,
            satisfaction=parse_optional_int(
                satisfaction, field_name="satisfaction"
            ),
            path_rating=parse_optional_int(
                path_rating, field_name="path_rating"
            ),
            training_rating=parse_optional_int(
                training_rating, field_name="training_rating"
            ),
            resource_rating=parse_optional_int(
                resource_rating, field_name="resource_rating"
            ),
            comments=comments,
        )
        return await service.save_growth_feedback(request)

    # MCP SDK 2.0 builds a dynamic root argument model with its default
    # extra="ignore" policy. The project contract requires unknown tool
    # arguments to be rejected and advertised as such. The SDK version is
    # pinned, and these regenerated schemas are covered by tools/list and
    # tools/call tests so a future SDK migration cannot silently loosen them.
    for registered_tool in server._tool_manager._tools.values():
        argument_model = registered_tool.fn_metadata.arg_model
        argument_model.model_config["extra"] = "forbid"
        argument_model.model_rebuild(force=True)
        registered_tool.parameters = argument_model.model_json_schema(by_alias=True)

    return server


def create_streamable_http_app(
    server: MCPServer,
    *,
    path: str = "/mcp",
    host: str = "127.0.0.1",
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
    auth_enabled: bool = True,
    token: str = "",
) -> ASGIApp:
    """Build the remote Streamable HTTP ASGI app with deployment safeguards."""

    if not path.startswith("/") or path == "/" or path.endswith("/"):
        raise ValueError("MCP_PATH must start with '/', not be '/', and have no trailing slash")
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts
        or ["127.0.0.1:*", "localhost:*", "[::1]:*"],
        allowed_origins=allowed_origins
        or ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
    )
    app: ASGIApp = server.streamable_http_app(
        streamable_http_path=path,
        json_response=True,
        stateless_http=True,
        transport_security=security,
        host=host,
    )
    if auth_enabled:
        app = BearerTokenASGI(app, token)
    return app


__all__ = [
    "BearerTokenASGI",
    "create_career_mcp_server",
    "create_streamable_http_app",
]
