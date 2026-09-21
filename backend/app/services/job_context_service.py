"""Deterministically assemble PostgreSQL job rows into a job context."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from ..repositories.job_repository import JobRepository
from ..schemas.job_context_schema import (
    JobCleanRecord,
    JobContext,
    JobSearchFilters,
    JobSearchPage,
    JobTypeProfileRecord,
)
from ..schemas.job_schema import JobProfile, RequiredJobAbility


_ABILITY_TAGS_FILE = Path(__file__).resolve().parents[1] / "data" / "ability_tags.json"


class JobContextError(RuntimeError):
    """Safe domain error for job context retrieval and conversion."""


class JobContextNotFoundError(JobContextError):
    """The requested job instance or type profile does not exist."""


class JobContextMappingError(JobContextError):
    """Stored job rows cannot form a valid frozen job context."""


@lru_cache(maxsize=1)
def _soft_skill_tags() -> frozenset[str]:
    try:
        with _ABILITY_TAGS_FILE.open(encoding="utf-8") as source:
            records = json.load(source)
        return frozenset(
            record["tag"]
            for record in records
            if record.get("category") == "soft_skill"
            and not record.get("deprecated", False)
        )
    except (OSError, TypeError, ValueError, KeyError):
        raise JobContextMappingError("ability taxonomy is unavailable") from None


class JobContextService:
    """Read job facts and perform deterministic field composition only."""

    def __init__(self, repository: JobRepository | None = None) -> None:
        self.repository = repository or JobRepository()

    def get_job(self, job_id: int) -> JobCleanRecord:
        job = self.repository.get_job_by_id(job_id)
        if job is None:
            raise JobContextNotFoundError("job not found")
        return job

    def get_job_type(self, type_key: str) -> JobTypeProfileRecord:
        job_type = self.repository.get_job_type_by_key(type_key)
        if job_type is None:
            raise JobContextNotFoundError("job type profile not found")
        return job_type

    def get_context_by_job_id(self, job_id: int) -> JobContext:
        job = self.get_job(job_id)
        if job.normalized_job_title is None:
            raise JobContextMappingError("job has no normalized type")
        job_type = self.get_job_type(job.normalized_job_title)
        return self._assemble(job, job_type)

    def get_context_by_normalized_title(self, normalized_title: str) -> JobContext:
        job_type = self.get_job_type(normalized_title)
        if job_type.exemplar_job_id is not None:
            job = self.repository.get_job_by_id(job_type.exemplar_job_id)
            if job is None:
                raise JobContextMappingError("job type exemplar is unavailable")
        else:
            job = self.repository.get_first_job_by_normalized_title(
                job_type.type_key
            )
            if job is None:
                raise JobContextNotFoundError(
                    "job instance for normalized title not found"
                )
        return self._assemble(job, job_type)

    def get_context_by_type_key(self, type_key: str) -> JobContext:
        """Load an exact type profile and its deterministic representative job."""

        return self.get_context_by_normalized_title(type_key)

    def search_jobs(self, filters: JobSearchFilters) -> JobSearchPage:
        return self.repository.search_jobs(filters)

    @staticmethod
    def _assemble(
        job: JobCleanRecord,
        job_type: JobTypeProfileRecord,
    ) -> JobContext:
        if job.normalized_job_title != job_type.type_key:
            raise JobContextMappingError("job and type profile do not match")
        industry = job_type.industry or job.industry
        description = job_type.profile_summary or job.job_description
        if industry is None or description is None:
            raise JobContextMappingError("job context lacks required facts")

        try:
            requirements = [
                RequiredJobAbility(
                    tag=item.tag,
                    required_level=item.required_level,
                    weight=item.weight,
                    importance=item.importance,
                    evidence=None,
                )
                for item in job_type.skill_requirements
            ]
            soft_tags = _soft_skill_tags()
            profile = JobProfile(
                job_id=job.job_id,
                title=job.job_title,
                normalized_title=job_type.type_key,
                industry=industry,
                required_abilities=requirements,
                soft_skills=[
                    item.tag
                    for item in job_type.skill_requirements
                    if item.tag in soft_tags
                ],
                salary_range=job.salary_range or job_type.salary_desc_p50,
                job_description=description,
            )
            return JobContext(job=job, job_type=job_type, profile=profile)
        except ValidationError:
            raise JobContextMappingError(
                "stored job context failed output validation"
            ) from None


__all__ = [
    "JobContextError",
    "JobContextMappingError",
    "JobContextNotFoundError",
    "JobContextService",
]
