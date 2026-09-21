"""Application schema package.

Legacy API request/response models are re-exported here so existing imports such
as ``from app.schemas import ProfileUploadRequest`` remain compatible after the
structured schema modules became an importable package.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .database_tool_schema import (
    JobSearchItem,
    ReadCareerGraphEdgesData,
    ReadCareerGraphEdgesRequest,
    ReadCareerGraphEdgesResult,
    ReadJobContextData,
    ReadJobContextRequest,
    ReadJobContextResult,
    ReadStudentProfileData,
    ReadStudentProfileRequest,
    ReadStudentProfileResult,
    SearchJobsData,
    SearchJobsRequest,
    SearchJobsResult,
)
from .job_context_schema import (
    JobCleanRecord,
    JobContext,
    JobSearchFilters,
    JobSearchPage,
    JobSkillRequirement,
    JobTypeProfileRecord,
)
from .student_persistence_schema import (
    StoredStudentAbility,
    StoredStudentBasicInfo,
    StudentProfilePersistenceResult,
    StudentProfileRecord,
    StudentProfileWrite,
)


class ProfileUploadRequest(BaseModel):
    name: str | None = Field(default=None, description="学生姓名，可选")
    skills: str = Field(..., description="专业技能字符串")
    certificates: str = Field(..., description="证书资质字符串")
    internships: str = Field(..., description="实习经历字符串")
    self_evaluation: str = Field(..., description="自我评价字符串")


class MatchingAnalyzeRequest(BaseModel):
    student_id: int
    job_id: int
    user_id: str | None = Field(default="default")


class ReportGenerateRequest(BaseModel):
    student_id: int
    job_id: int
    custom_instructions: str | None = None
    user_id: str | None = Field(default="default")


class ReportPolishRequest(BaseModel):
    paragraph_index: int = 0
    text: str


class StudentUploadResponseData(BaseModel):
    student_id: int
    student_name: str
    profile: dict[str, Any]


class StudentUploadResponse(BaseModel):
    code: int
    msg: str
    data: StudentUploadResponseData


__all__ = [
    "JobSearchItem",
    "JobCleanRecord",
    "JobContext",
    "JobSearchFilters",
    "JobSearchPage",
    "JobSkillRequirement",
    "JobTypeProfileRecord",
    "MatchingAnalyzeRequest",
    "ProfileUploadRequest",
    "ReadCareerGraphEdgesData",
    "ReadCareerGraphEdgesRequest",
    "ReadCareerGraphEdgesResult",
    "ReadJobContextData",
    "ReadJobContextRequest",
    "ReadJobContextResult",
    "ReadStudentProfileData",
    "ReadStudentProfileRequest",
    "ReadStudentProfileResult",
    "ReportGenerateRequest",
    "ReportPolishRequest",
    "StudentUploadResponse",
    "StudentUploadResponseData",
    "SearchJobsData",
    "SearchJobsRequest",
    "SearchJobsResult",
    "StoredStudentAbility",
    "StoredStudentBasicInfo",
    "StudentProfilePersistenceResult",
    "StudentProfileRecord",
    "StudentProfileWrite",
]
