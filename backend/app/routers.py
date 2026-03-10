"""Application-level router aggregator.

将按业务拆分的子路由统一挂载到一个入口，保持 app.main 兼容：
`from .routers import router`
"""

from fastapi import APIRouter

from .routes import (
    history_router,
    jobs_router,
    matching_router,
    recommendations_router,
    reports_router,
    students_router,
)

router = APIRouter()

# 统一注册顺序：先基础数据，再业务动作。
router.include_router(jobs_router)
router.include_router(students_router)
router.include_router(matching_router)
router.include_router(reports_router)
router.include_router(history_router)
router.include_router(recommendations_router)
