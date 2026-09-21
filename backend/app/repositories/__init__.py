"""Shared infrastructure for future business-data repositories."""

from .base import BaseRepository, BusinessDatabaseQueryError
from .career_graph_repository import (
    CareerGraphProvider,
    CareerGraphProviderDataError,
    CareerGraphProviderError,
    CareerGraphProviderResult,
    CareerGraphQuery,
    PostgresCareerGraphProvider,
    PostgresCareerGraphProviderError,
)
from .job_repository import (
    JobRepository,
    JobRepositoryDataError,
    JobRepositoryError,
    JobRepositoryUnavailableError,
)
from .student_profile_repository import (
    StudentProfileDataError,
    StudentProfileRepository,
    StudentProfileRepositoryError,
)

__all__ = [
    "BaseRepository",
    "BusinessDatabaseQueryError",
    "CareerGraphProvider",
    "CareerGraphProviderDataError",
    "CareerGraphProviderError",
    "CareerGraphProviderResult",
    "CareerGraphQuery",
    "JobRepository",
    "JobRepositoryDataError",
    "JobRepositoryError",
    "JobRepositoryUnavailableError",
    "PostgresCareerGraphProvider",
    "PostgresCareerGraphProviderError",
    "StudentProfileDataError",
    "StudentProfileRepository",
    "StudentProfileRepositoryError",
]
