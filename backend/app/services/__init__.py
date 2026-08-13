"""Lazy service exports.

Database-backed services are imported only when requested, so deterministic
services and unit tests do not require a live PostgreSQL driver at import time.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "get_history_snapshot": ("history_service", "get_history_snapshot"),
    "get_user_histories": ("history_service", "get_user_histories"),
    "get_job_graph": ("job_service", "get_job_graph"),
    "get_job_profile": ("job_service", "get_job_profile"),
    "search_jobs": ("job_service", "search_jobs"),
    "analyze_matching": ("matching_service", "analyze_matching"),
    "build_matching_analysis": ("matching_service", "build_matching_analysis"),
    "get_recommendations": ("recommendation_service", "get_recommendations"),
    "ProfileEvidenceExtraction": ("profile_service", "ProfileEvidenceExtraction"),
    "ProfileService": ("profile_service", "ProfileService"),
    "export_report": ("report_service", "export_report"),
    "generate_report": ("report_service", "generate_report"),
    "get_report": ("report_service", "get_report"),
    "polish_report": ("report_service", "polish_report"),
    "extract_all_content": ("resume_service", "extract_all_content"),
    "parse_llm_json": ("resume_service", "parse_llm_json"),
    "get_student_profile": ("student_service", "get_student_profile"),
    "save_resume_profile": ("student_service", "save_resume_profile"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value


__all__ = sorted(_EXPORTS)
