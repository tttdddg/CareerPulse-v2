"""Student-related API routes: upload & profile query."""

from __future__ import annotations

import json

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI

from ..schemas import ProfileUploadRequest
from ..services.resume_service import extract_all_content, parse_llm_json
from ..services.student_service import get_student_profile, save_resume_profile

router = APIRouter()


client = AsyncOpenAI(
    # api_key=os.environ.get("DEEPSEEK_API_KEY"),
    api_key="sk-cd8d792d6874441188c983a81c4b5d84",
    base_url="https://api.deepseek.com",
)


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


@router.post("/student/upload/resume")
async def upload_resume(file: UploadFile = File(...)):
    """Upload resume file and parse to structured student profile."""
    allowed_types = [".txt", ".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg"]
    if not file.filename or not any(file.filename.lower().endswith(ext) for ext in allowed_types):
        raise HTTPException(status_code=400, detail="仅支持 TXT/PDF/Word/图片 文件")

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
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=_build_resume_messages(text),
            temperature=0.3,
            max_tokens=1500,
            stream=False,
        )
        data = parse_llm_json(response.choices[0].message.content)
        student_name = data.get("name") or "未知"
        save_resume_profile(student_name=student_name, parsed_data=data)
        return JSONResponse(content={"code": 1, "msg": "success", "data": data})
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"解析模型返回 JSON 失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分析请求失败: {str(e)}")


@router.post("/student/upload/profile")
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
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=_build_manual_profile_messages(user_text),
            temperature=0.3,
            max_tokens=1500,
            stream=False,
        )
        data = parse_llm_json(response.choices[0].message.content)

        if profile.name and not data.get("name"):
            data["name"] = profile.name

        student_name = data.get("name") or profile.name or "未知"
        save_resume_profile(student_name=student_name, parsed_data=data)
        return JSONResponse(content={"code": 1, "msg": "success", "data": data})
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"解析模型返回 JSON 失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分析请求失败: {str(e)}")
