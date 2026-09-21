"""Read-only business tools over the parameterized database services."""

from __future__ import annotations

from collections.abc import Callable

from ..repositories.career_graph_repository import (
    CareerGraphProviderDataError,
    CareerGraphProviderError,
    CareerGraphQuery,
    PostgresCareerGraphProvider,
    PostgresCareerGraphProviderError,
)
from ..repositories.job_repository import (
    JobRepositoryDataError,
    JobRepositoryUnavailableError,
)
from ..repositories.student_profile_repository import (
    StudentProfileDataError,
    StudentProfileRepositoryError,
)
from ..schemas.database_tool_schema import (
    JobSearchItem,
    ReadCareerGraphEdgesData,
    ReadCareerGraphEdgesRequest,
    ReadJobContextData,
    ReadJobContextRequest,
    ReadStudentProfileData,
    ReadStudentProfileRequest,
    SearchJobsData,
    SearchJobsRequest,
)
from ..schemas.job_context_schema import JobSearchFilters
from ..services.career_graph_repository import (
    CareerGraphProviderSelector,
    DemoCareerGraphProviderError,
    JsonCareerGraphProvider,
)
from ..services.job_context_service import (
    JobContextMappingError,
    JobContextNotFoundError,
    JobContextService,
)
from ..services.student_profile_persistence_service import (
    StudentProfileMappingError,
    StudentProfileNotFoundError,
    StudentProfilePersistenceService,
)


StudentAuthorization = Callable[[str, str, int], bool]


class DatabaseToolError(RuntimeError):
    """Safe classified error consumed by the MCP application service."""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.message = message
        self.retryable = retryable


class DatabaseTools:
    """Expose business parameters only; never accept SQL or schema identifiers."""

    def __init__(
        self,
        *,
        student_service: StudentProfilePersistenceService | None = None,
        job_service: JobContextService | None = None,
        graph_selector: CareerGraphProviderSelector | None = None,
        authorize_student: StudentAuthorization | None = None,
        demo_mode: bool = False,
        fallback_to_demo: bool = False,
    ) -> None:
        if fallback_to_demo and not demo_mode:
            raise ValueError("database Tool Demo fallback requires Demo Mode")
        self.student_service = student_service or StudentProfilePersistenceService()
        self.job_service = job_service or JobContextService()
        self.authorize_student = authorize_student
        self.demo_mode = demo_mode
        self.fallback_to_demo = fallback_to_demo
        if graph_selector is None:
            demo_provider = (
                JsonCareerGraphProvider(demo_mode=True) if demo_mode else None
            )
            graph_selector = CareerGraphProviderSelector(
                PostgresCareerGraphProvider(),
                demo_provider,
            )
        self.graph_selector = graph_selector

    def read_student_profile(
        self,
        request: ReadStudentProfileRequest,
    ) -> ReadStudentProfileData:
        if self.authorize_student is None or not self.authorize_student(
            request.session_id,
            request.user_id,
            request.student_id,
        ):
            raise DatabaseToolError(
                "STUDENT_PROFILE_ACCESS_DENIED",
                "The student profile reference is not authorized for this session.",
            )
        try:
            profile = self.student_service.get_profile(
                request.student_id,
                user_id=request.user_id,
            )
            return ReadStudentProfileData(
                student_profile=profile,
                data_source="postgresql",
                fallback_used=False,
            )
        except StudentProfileNotFoundError:
            raise self._not_found("student profile") from None
        except (StudentProfileDataError, StudentProfileMappingError):
            raise self._invalid_data("student profile") from None
        except StudentProfileRepositoryError:
            raise self._database_unavailable() from None

    def search_jobs(self, request: SearchJobsRequest) -> SearchJobsData:
        try:
            page = self.job_service.search_jobs(
                JobSearchFilters(
                    keyword=request.keyword,
                    city=request.city,
                    industry=request.industry,
                    page=request.page,
                    page_size=request.page_size,
                )
            )
            return SearchJobsData(
                items=[
                    JobSearchItem(
                        job_id=item.job_id,
                        title=item.job_title,
                        normalized_title=item.normalized_job_title,
                        city=item.city,
                        salary_range=item.salary_range,
                        industry=item.industry,
                    )
                    for item in page.items
                ],
                page=page.page,
                page_size=page.page_size,
                has_more=page.has_more,
                data_source="postgresql",
                fallback_used=False,
            )
        except JobRepositoryDataError:
            raise self._invalid_data("job search") from None
        except JobRepositoryUnavailableError:
            raise self._database_unavailable() from None

    def read_job_context(
        self,
        request: ReadJobContextRequest,
    ) -> ReadJobContextData:
        try:
            if request.job_id is not None:
                context = self.job_service.get_context_by_job_id(request.job_id)
            else:
                assert request.normalized_title is not None
                context = self.job_service.get_context_by_normalized_title(
                    request.normalized_title
                )
            return ReadJobContextData(
                context=context,
                data_source="postgresql",
                fallback_used=False,
            )
        except JobContextNotFoundError:
            raise self._not_found("job context") from None
        except (JobRepositoryDataError, JobContextMappingError):
            raise self._invalid_data("job context") from None
        except JobRepositoryUnavailableError:
            raise self._database_unavailable() from None

    def read_career_graph_edges(
        self,
        request: ReadCareerGraphEdgesRequest,
    ) -> ReadCareerGraphEdgesData:
        try:
            result = self.graph_selector.load(
                CareerGraphQuery(
                    source_type_key=request.source_type_key,
                    relation_type=request.relation_type,
                    limit=request.limit,
                ),
                demo_mode=self.demo_mode,
                fallback_to_demo=self.fallback_to_demo,
            )
            return ReadCareerGraphEdgesData(
                edges=result.edges,
                data_source=result.data_source,
                fallback_used=result.fallback_used,
            )
        except DemoCareerGraphProviderError:
            raise DatabaseToolError(
                "DEMO_DATA_INVALID",
                "The configured Demo career graph is unavailable.",
            ) from None
        except CareerGraphProviderDataError:
            raise self._invalid_data("career graph") from None
        except PostgresCareerGraphProviderError:
            raise self._database_unavailable() from None
        except CareerGraphProviderError:
            raise DatabaseToolError(
                "DATABASE_TOOL_EXECUTION_FAILED",
                "The career graph could not be loaded.",
                retryable=True,
            ) from None

    @staticmethod
    def _not_found(resource: str) -> DatabaseToolError:
        return DatabaseToolError(
            "BUSINESS_RECORD_NOT_FOUND",
            f"The requested {resource} was not found.",
        )

    @staticmethod
    def _invalid_data(resource: str) -> DatabaseToolError:
        return DatabaseToolError(
            "BUSINESS_RECORD_SCHEMA_INVALID",
            f"The stored {resource} failed its fixed schema.",
        )

    @staticmethod
    def _database_unavailable() -> DatabaseToolError:
        return DatabaseToolError(
            "DATABASE_UNAVAILABLE",
            "The business database is unavailable.",
            retryable=True,
        )


__all__ = ["DatabaseToolError", "DatabaseTools", "StudentAuthorization"]
