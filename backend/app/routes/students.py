"""Student-related API routes: upload & profile query."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..core.llm_client import llm_client
from ..schemas import ProfileUploadRequest, StudentUploadResponse
from ..services.resume_service import extract_all_content
from ..services.student_service import get_student_profile, save_resume_profile

router = APIRouter()


def _build_resume_messages(text: str):
    """Prompt for resume-to-profile parsing."""
    return [
        {
            "role": "system",
            "content": (
                "你是一个简历解析专家。"
                "输出字段必须为：name、skills、certificates、education、internships、projects。"
                "字段缺失时填 null，且只输出 JSON。"
            ),
        },
        {"role": "user", "content": text},
    ]


def _build_manual_profile_messages(text: str):
    """Prompt for manual text-to-profile parsing."""
    return [
        {
            "role": "system",
            "content": (
                "你是学生画像结构化专家。"
                "输出字段必须为：name、skills、certificates、education、internships、projects。"
                "字段缺失时填 null，且只输出 JSON。"
            ),
        },
        {"role": "user", "content": text},
    ]


@router.get("/student/{student_id}/profile")
def get_student_profile_api(student_id: int):
    try:
        data = get_student_profile(student_id)
        return JSONResponse(content={"code": 1, "msg": "success", "data": data})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/student/upload/resume", response_model=StudentUploadResponse)
async def upload_resume(file: UploadFile = File(...)):
    """Upload resume file and parse to structured student profile."""
    allowed_types = [".txt", ".pdf", ".docx", ".png", ".jpg", ".jpeg"]
    if not file.filename or not any(file.filename.lower().endswith(ext) for ext in allowed_types):
        raise HTTPException(status_code=400, detail="仅支持 TXT/PDF/DOCX/图片 文件")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件超过 10MB 限制")

    try:
        text = extract_all_content(content, file.filename)
        if not text.strip():
            raise ValueError("无法提取任何文本内容")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件处理失败: {str(e)}")

    try:
        data = await llm_client.generate_structured(
            _build_resume_messages(text),
            dict,
            temperature=0.3,
            max_tokens=1500,
        )
        student_name = data.get("name") or "未知"
        student_id = save_resume_profile(student_name=student_name, parsed_data=data)
        return JSONResponse(
            content={
                "code": 1,
                "msg": "success",
                "data": {"student_id": student_id, "student_name": student_name, "profile": data},
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分析请求失败: {str(e)}")


@router.post("/student/upload/profile", response_model=StudentUploadResponse)
async def upload_profile(profile: ProfileUploadRequest):
    """Upload manually entered profile text fields and parse to structured JSON."""
    if not any([
        profile.skills.strip(),
        profile.certificates.strip(),
        profile.internships.strip(),
        profile.self_evaluation.strip(),
    ]):
        raise HTTPException(status_code=400, detail="至少提供一项有效内容")

    user_text = (
        f"专业技能：{profile.skills}\n"
        f"证书资质：{profile.certificates}\n"
        f"实习经历：{profile.internships}\n"
        f"自我评价：{profile.self_evaluation}"
    )

    try:
        data = await llm_client.generate_structured(
            _build_manual_profile_messages(user_text),
            dict,
            temperature=0.3,
            max_tokens=1500,
        )

        if profile.name and not data.get("name"):
            data["name"] = profile.name

        student_name = data.get("name") or profile.name or "未知"
        student_id = save_resume_profile(student_name=student_name, parsed_data=data)
        return JSONResponse(
            content={
                "code": 1,
                "msg": "success",
                "data": {"student_id": student_id, "student_name": student_name, "profile": data},
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分析请求失败: {str(e)}")
