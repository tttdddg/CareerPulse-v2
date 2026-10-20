from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager

import os

from fastapi.exceptions import RequestValidationError

from .auth import AuthService
from .api.platform_tool_api import (
    PlatformToolException,
    platform_request_validation_exception_handler,
    platform_tool_exception_handler,
)
from .orchestrator import CareerOrchestrator
from .mcp.tool_service import CareerMCPToolService
from .platform.tbox import (
    TBoxChatException,
    TBoxChatService,
    TBoxClient,
    TBoxClientConfig,
    TBoxSessionMapper,
)
from .platform.tbox.router import (
    tbox_chat_exception_handler,
    tbox_chat_request_validation_exception_handler,
)
from .routers import router


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _env_csv(name: str) -> list[str] | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


async def _request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    if request.url.path.startswith("/api/tbox/chat"):
        return await tbox_chat_request_validation_exception_handler(request, exc)
    return await platform_request_validation_exception_handler(request, exc)


def create_app(
    orchestrator: CareerOrchestrator | None = None,
    *,
    tbox_chat_service: TBoxChatService | None = None,
    tbox_api_token: str | None = None,
    tbox_tool_timeout_seconds: float | None = None,
    mcp_enabled: bool | None = None,
    mcp_expose_database_tools: bool | None = None,
    mcp_auth_enabled: bool | None = None,
    mcp_api_token: str | None = None,
    mcp_host: str | None = None,
    mcp_port: int | None = None,
    mcp_path: str | None = None,
    mcp_tool_timeout_seconds: float | None = None,
    mcp_allowed_hosts: list[str] | None = None,
    mcp_allowed_origins: list[str] | None = None,
    auth_service: AuthService | None = None,
    web_allowed_origins: list[str] | None = None,
    web_auth_enabled: bool | None = None,
) -> FastAPI:
    """Create a fresh application instance for runtime and persistence tests."""

    career_orchestrator = orchestrator or CareerOrchestrator()
    configured_web_tool_timeout = float(os.getenv("WEB_TOOL_TIMEOUT_SECONDS", "25") or 25)
    if configured_web_tool_timeout <= 0 or configured_web_tool_timeout > 60:
        configured_web_tool_timeout = 25.0
    career_web_tool_service = CareerMCPToolService(
        career_orchestrator,
        timeout_seconds=configured_web_tool_timeout,
        # The Web API must not rebind PathAgent's shared graph source; only the
        # MCP/competition service owns that runtime policy.
        bind_runtime_graph_provider=False,
    )
    configured_auth_service = auth_service or AuthService()
    configured_web_auth_enabled = (
        _env_bool("WEB_AUTH_ENABLED", True)
        if web_auth_enabled is None
        else web_auth_enabled
    )
    configured_web_origins = (
        web_allowed_origins
        if web_allowed_origins is not None
        else _env_csv("WEB_ALLOWED_ORIGINS")
        or [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    configured_tbox_chat_service = tbox_chat_service or TBoxChatService(
        TBoxClient(TBoxClientConfig.from_env()),
        TBoxSessionMapper(career_orchestrator),
        career_orchestrator,
    )
    configured_mcp_enabled = (
        _env_bool("MCP_ENABLED", False) if mcp_enabled is None else mcp_enabled
    )
    configured_mcp_expose_database_tools = (
        _env_bool("MCP_EXPOSE_DATABASE_TOOLS", False)
        if mcp_expose_database_tools is None
        else mcp_expose_database_tools
    )
    configured_mcp_auth_enabled = (
        _env_bool("MCP_AUTH_ENABLED", True)
        if mcp_auth_enabled is None
        else mcp_auth_enabled
    )
    configured_mcp_token = (
        os.getenv("MCP_API_TOKEN", "")
        if mcp_api_token is None
        else mcp_api_token
    )
    configured_mcp_host = mcp_host or os.getenv("MCP_HOST", "127.0.0.1")
    configured_mcp_port = int(
        os.getenv("MCP_PORT", "8000") if mcp_port is None else mcp_port
    )
    if configured_mcp_port < 1 or configured_mcp_port > 65535:
        raise ValueError("MCP_PORT must be between 1 and 65535")
    configured_mcp_path = mcp_path or os.getenv("MCP_PATH", "/mcp")
    configured_allowed_hosts = (
        mcp_allowed_hosts
        if mcp_allowed_hosts is not None
        else _env_csv("MCP_ALLOWED_HOSTS")
    )
    configured_allowed_origins = (
        mcp_allowed_origins
        if mcp_allowed_origins is not None
        else _env_csv("MCP_ALLOWED_ORIGINS")
    )
    configured_timeout = (
        float(os.getenv("A02_TBOX_TOOL_TIMEOUT_SECONDS", "25"))
        if tbox_tool_timeout_seconds is None
        else float(tbox_tool_timeout_seconds)
    )
    if configured_timeout <= 0 or configured_timeout > 60:
        raise ValueError("A02_TBOX_TOOL_TIMEOUT_SECONDS must be in (0, 60]")
    configured_mcp_timeout = (
        float(os.getenv("MCP_TOOL_TIMEOUT_SECONDS", "25"))
        if mcp_tool_timeout_seconds is None
        else float(mcp_tool_timeout_seconds)
    )
    if configured_mcp_timeout <= 0 or configured_mcp_timeout > 60:
        raise ValueError("MCP_TOOL_TIMEOUT_SECONDS must be in (0, 60]")

    mcp_server = None
    mcp_asgi_app = None
    if configured_mcp_enabled:
        from .mcp.server import (
            create_career_mcp_server,
            create_streamable_http_app,
        )

        mcp_server = create_career_mcp_server(
            career_orchestrator,
            timeout_seconds=configured_mcp_timeout,
            expose_database_tools=configured_mcp_expose_database_tools,
        )
        mcp_asgi_app = create_streamable_http_app(
            mcp_server,
            path=configured_mcp_path,
            host=configured_mcp_host,
            allowed_hosts=configured_allowed_hosts,
            allowed_origins=configured_allowed_origins,
            auth_enabled=configured_mcp_auth_enabled,
            token=configured_mcp_token,
        )

    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        if mcp_server is None:
            yield
            return
        async with mcp_server.session_manager.run():
            yield

    application = FastAPI(
        title="CareerPulse A02 API",
        version="stage3-tool-v1",
        description=(
            "CareerPulse APIs including the Ant TBox agent chat gateway, "
            "authenticated stage-3 HTTP tools, and optional remote MCP server."
        ),
        lifespan=lifespan,
    )
    application.state.career_orchestrator = career_orchestrator
    application.state.career_state_repository = career_orchestrator.repository
    application.state.career_web_tool_service = career_web_tool_service
    application.state.web_tool_timeout_seconds = configured_web_tool_timeout
    application.state.auth_service = configured_auth_service
    application.state.web_auth_enabled = configured_web_auth_enabled
    application.state.tbox_chat_service = configured_tbox_chat_service
    application.state.tbox_api_token = (
        os.getenv("A02_TBOX_API_TOKEN", "")
        if tbox_api_token is None
        else tbox_api_token
    )
    application.state.tbox_tool_timeout_seconds = configured_timeout
    application.state.mcp_enabled = configured_mcp_enabled
    application.state.mcp_expose_database_tools = (
        configured_mcp_expose_database_tools
    )
    application.state.mcp_auth_enabled = configured_mcp_auth_enabled
    application.state.mcp_host = configured_mcp_host
    application.state.mcp_port = configured_mcp_port
    application.state.mcp_path = configured_mcp_path
    application.state.mcp_tool_timeout_seconds = configured_mcp_timeout
    application.state.mcp_server = mcp_server
    application.add_exception_handler(
        PlatformToolException, platform_tool_exception_handler
    )
    application.add_exception_handler(
        TBoxChatException, tbox_chat_exception_handler
    )
    application.add_exception_handler(
        RequestValidationError, _request_validation_exception_handler
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=configured_web_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "Mcp-Session-Id"],
    )

    @application.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Return minimal process health without probing configuration."""

        return {"status": "ok"}

    application.include_router(router)
    if mcp_asgi_app is not None:
        # Existing FastAPI routes are registered first. The mounted MCP app then
        # serves its exact configured path (default /mcp) without a redirect.
        application.mount("/", mcp_asgi_app)
    return application


app = create_app()


__all__ = ["app", "create_app"]
