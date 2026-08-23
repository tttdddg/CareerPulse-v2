"""Official MCP SDK server for CareerPulse Streamable HTTP tools."""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from ..orchestrator import CareerOrchestrator
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
from .tool_service import CareerMCPToolService


ASGIApp = Callable[
    [dict[str, Any], Callable[[], Awaitable[dict[str, Any]]], Callable[[dict[str, Any]], Awaitable[None]]],
    Awaitable[None],
]


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
        version="stage3-mcp-v1",
        description=(
            "Session-based CareerPulse tools. Profile and job steps store state; "
            "match and path steps read it and never accept client-supplied scores."
        ),
        instructions=(
            "Call build_student_profile and analyze_target_job before "
            "analyze_job_match. Call generate_career_path only after a successful "
            "match. Reuse the same session_id and user_id for every step."
        ),
    )

    @server.tool(
        name="build_student_profile",
        description=(
            "Call when the user has supplied resume or form evidence. Requires "
            "session_id, user_id and student_input. Stores a validated student "
            "profile in CareerState and returns PROFILE_COMPLETED. Never include "
            "credentials or ask the model to invent unsupported abilities."
        ),
        structured_output=True,
    )
    async def build_student_profile(
        session_id: str,
        user_id: str,
        student_input: StudentProfileInput,
        trace_id: str | None = None,
    ) -> BuildStudentProfileResult:
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
            "Call after the target role is known. Requires session_id, user_id and "
            "target_job_input with job_title. Stores a validated job profile and "
            "trend result in the same CareerState and returns JOB_COMPLETED."
        ),
        structured_output=True,
    )
    async def analyze_target_job(
        session_id: str,
        user_id: str,
        target_job_input: TargetJobInput,
        trace_id: str | None = None,
    ) -> AnalyzeTargetJobResult:
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
            "Call only after this session contains both a completed student profile "
            "and target job. Requires only session_id and user_id; do not pass profile "
            "JSON, scores or gaps. MatchAgent delegates all scores and ability gaps "
            "to the deterministic MatchService and returns MATCH_COMPLETED."
        ),
        structured_output=True,
    )
    async def analyze_job_match(
        session_id: str,
        user_id: str,
        trace_id: str | None = None,
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
            "Call only after analyze_job_match completed for this session. Requires "
            "only session_id and user_id; do not pass match JSON, nodes or path scores. "
            "PathAgent delegates paths and scores to the deterministic PathService "
            "and returns PATH_COMPLETED."
        ),
        structured_output=True,
    )
    async def generate_career_path(
        session_id: str,
        user_id: str,
        trace_id: str | None = None,
    ) -> GenerateCareerPathMCPResult:
        request = GenerateCareerPathMCPRequest(
            session_id=session_id,
            user_id=user_id,
            trace_id=trace_id,
        )
        return await service.generate_career_path(request)

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
