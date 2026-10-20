"""Application-level router aggregator.

将按业务拆分的子路由统一挂载到一个入口，保持 app.main 兼容：
`from .routers import router`
"""

from fastapi import APIRouter

from .api.career_agent_api import router as career_agent_router
from .api.career_agent_api import agent_log_router
from .api.platform_tool_api import router as platform_tool_router
from .api.auth_api import router as auth_router
from .api.web_business_api import router as web_business_router
from .platform.tbox.router import router as tbox_chat_router

router = APIRouter()

# A02 新 Agent 链路 API（先注册，与旧路由无前缀冲突）
router.include_router(career_agent_router)
router.include_router(agent_log_router)
router.include_router(platform_tool_router)
router.include_router(tbox_chat_router)
router.include_router(auth_router)
router.include_router(web_business_router)

# Legacy REST routes were detached with their standalone database helpers.
# A02 Agent, platform Tool, TBox and MCP are the supported backend entries.
