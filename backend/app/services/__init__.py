"""Lazy service exports.

Database-backed services are imported only when requested, so deterministic
services and unit tests do not require a live PostgreSQL driver at import time.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "JobContextError": ("job_context_service", "JobContextError"),
    "JobContextMappingError": ("job_context_service", "JobContextMappingError"),
    "JobContextNotFoundError": ("job_context_service", "JobContextNotFoundError"),
    "JobContextService": ("job_context_service", "JobContextService"),
    "get_recommendations": ("recommendation_service", "get_recommendations"),
    "ProfileEvidenceExtraction": ("profile_service", "ProfileEvidenceExtraction"),
    "ProfileService": ("profile_service", "ProfileService"),
    "StudentProfileMappingError": (
        "student_profile_persistence_service",
        "StudentProfileMappingError",
    ),
    "StudentProfileNotFoundError": (
        "student_profile_persistence_service",
        "StudentProfileNotFoundError",
    ),
    "StudentProfilePersistenceService": (
        "student_profile_persistence_service",
        "StudentProfilePersistenceService",
    ),
    "StudentProfileScoreMismatchError": (
        "student_profile_persistence_service",
        "StudentProfileScoreMismatchError",
    ),
    "extract_all_content": ("resume_service", "extract_all_content"),
    "parse_llm_json": ("resume_service", "parse_llm_json"),
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
