from pydantic import BaseModel, Field


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
