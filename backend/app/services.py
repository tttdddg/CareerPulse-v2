"""Compatibility service facade.

历史代码可能仍在 `from app.services import ...`。
这里保留同名导出，实际实现已拆分到 app/services/*。
"""

from .services.history_service import get_history_snapshot, get_user_histories
from .services.job_service import get_job_graph, get_job_profile, search_jobs
from .services.matching_service import analyze_matching
from .services.recommendation_service import get_recommendations
from .services.report_service import export_report, generate_report, get_report, polish_report
from .services.resume_service import extract_all_content, parse_llm_json
from .services.student_service import get_student_profile, save_resume_profile

__all__ = [
    "search_jobs",
    "get_job_profile",
    "get_job_graph",
    "save_resume_profile",
    "get_student_profile",
    "analyze_matching",
    "generate_report",
    "get_report",
    "polish_report",
    "export_report",
    "get_user_histories",
    "get_history_snapshot",
    "get_recommendations",
    "extract_all_content",
    "parse_llm_json",
]
