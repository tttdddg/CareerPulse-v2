"""Route package exports."""

from .history import router as history_router
from .jobs import router as jobs_router
from .matching import router as matching_router
from .recommendations import router as recommendations_router
from .reports import router as reports_router
from .students import router as students_router

__all__ = [
    "jobs_router",
    "students_router",
    "matching_router",
    "reports_router",
    "history_router",
    "recommendations_router",
]
