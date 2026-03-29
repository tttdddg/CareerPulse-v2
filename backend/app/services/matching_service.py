"""Matching service.

实现人岗匹配评分（主逻辑为 LLM 语义评分），并保留规则法作为兜底。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from ..db import ensure_business_tables, get_db_conn
from .job_service import get_job_profile
from .student_service import get_student_profile

CERT_SKILL_MAP = {
    "软考": {"java", "python", "sql", "数据库", "后端", "前端"},
    "计算机二级": {"python", "c++", "数据库", "sql"},
    "pmp": {"项目管理", "沟通", "协作"},
    "ccna": {"网络", "运维", "云计算"},
    "hcia": {"网络", "运维", "云计算"},
    "hcip": {"网络", "运维", "云计算"},
    "aws": {"云计算", "docker", "kubernetes", "linux"},
    "azure": {"云计算", "docker", "kubernetes", "linux"},
}


def _extract_student_skills(parsed_data: dict[str, Any]) -> list[str]:
    raw = parsed_data.get("skills") or []
    if isinstance(raw, str):
        raw = re.split(r"[,，/、\s]+", raw)
    return [str(x).strip() for x in raw if str(x).strip()]


def _extract_student_certs(parsed_data: dict[str, Any]) -> list[str]:
    raw = parsed_data.get("certificates") or []
    if isinstance(raw, str):
        raw = re.split(r"[,，/、\s]+", raw)
    return [str(x).strip().lower() for x in raw if str(x).strip()]


def _extract_student_soft_text(parsed_data: dict[str, Any]) -> str:
    texts = []
    for k in ["self_evaluation", "summary", "objective"]:
        v = parsed_data.get(k)
        if v:
            texts.append(str(v))
    return " ".join(texts)


def _cert_assist_hits(required_skills: set[str], certs: list[str]) -> float:
    """Use certificates as skill-level proxies and grant partial assisted hits."""
    if not required_skills or not certs:
        return 0.0

    assisted = 0.0
    for cert in certs:
        for cert_name, mapped_skills in CERT_SKILL_MAP.items():
            if cert_name in cert:
                overlap = sum(1 for s in required_skills if any(ms in s for ms in mapped_skills))
                assisted += overlap * 0.2

    return min(assisted, max(1.0, len(required_skills) * 0.35))


def _parse_llm_json(result_text: str) -> dict[str, Any]:
    start = result_text.find("{")
    end = result_text.rfind("}") + 1
    if start == -1 or end <= start:
        raise ValueError("模型返回不包含有效 JSON")
    return json.loads(result_text[start:end])


def _clamp_score(value: Any, default: float) -> float:
    try:
        v = float(value)
    except Exception:
        v = default
    return max(0.0, min(100.0, round(v, 2)))


def _rule_fallback_analysis(student_data: dict[str, Any], job_data: dict[str, Any]) -> dict[str, Any]:
    """Original rule-based scoring kept as safe fallback."""
    student_skills = {x.lower() for x in _extract_student_skills(student_data)}
    student_certs = _extract_student_certs(student_data)
    required_skills = {str(x).lower() for x in (job_data.get("required_skills") or [])}

    if required_skills:
        direct_hit = student_skills & required_skills
        assisted_hit = _cert_assist_hits(required_skills - direct_hit, student_certs)
        effective_hit = min(len(required_skills), len(direct_hit) + assisted_hit)
        skill_score = round(effective_hit / len(required_skills) * 100, 2)
    else:
        direct_hit = set()
        skill_score = 60.0

    internships = student_data.get("internships") or []
    projects = student_data.get("projects") or []

    cert_learning_bonus = min(20.0, len(student_certs) * 6.0)
    practice_score = min(95.0, 55.0 + len(internships) * 10 + len(projects) * 8)
    learning_score = min(95.0, 60.0 + cert_learning_bonus + len(projects) * 3)

    soft_requirements = [str(x) for x in (job_data.get("soft_skills") or [])]
    soft_text = _extract_student_soft_text(student_data).lower()
    if soft_requirements:
        soft_hit = sum(1 for s in soft_requirements if str(s).lower() in soft_text)
        soft_score = round((soft_hit / len(soft_requirements)) * 100, 2)
    else:
        soft_score = 70.0

    dimensions = [
        {"name": "专业技能", "student_score": skill_score, "job_required": 85, "gap": round(skill_score - 85, 2)},
        {"name": "学习能力", "student_score": learning_score, "job_required": 75, "gap": round(learning_score - 75, 2)},
        {"name": "实践能力", "student_score": practice_score, "job_required": 75, "gap": round(practice_score - 75, 2)},
        {"name": "通用素养", "student_score": soft_score, "job_required": 70, "gap": round(soft_score - 70, 2)},
    ]

    overall = round(skill_score * 0.5 + learning_score * 0.2 + practice_score * 0.2 + soft_score * 0.1, 2)

    missing_skills = [s for s in required_skills if s not in student_skills]
    gap_analysis = [
        {
            "item": s,
            "status": "missing",
            "suggestion": f"建议补充 {s} 的项目实战并形成作品。",
        }
        for s in sorted(missing_skills)[:8]
    ]

    return {
        "overall_score": overall,
        "dimensions": dimensions,
        "gap_analysis": gap_analysis,
    }


def build_matching_analysis(student_data: dict[str, Any], job_data: dict[str, Any]) -> dict[str, Any]:
    """Build matching result using LLM semantic scoring."""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _rule_fallback_analysis(student_data, job_data)

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    client = OpenAI(api_key=api_key, base_url=base_url)

    system_prompt = (
        "你是资深人岗匹配评估专家。"
        "请基于学生画像与岗位画像做语义级评分，允许同义词、上下位词、项目经历和迁移能力匹配。"
        "只返回 JSON。"
        "字段必须为 overall_score、dimensions、gap_analysis。"
        "overall_score 为 0-100 数值。"
        "dimensions 必须包含四项：专业技能、学习能力、实践能力、通用素养；"
        "每项包含 name、student_score、job_required、gap。"
        "gap_analysis 为数组，每项包含 item、status、suggestion。"
        "重要：在评估学生技能与岗位要求的匹配度时，应采用语义相似度而非严格匹配。对于语义相关的技能，即使不完全匹配，也应给予部分分数，并确保分数不会过低。请注意，岗位技能需求通常较为广泛，旨在覆盖多个同类岗位，但实际工作中未必全部用到；且入门级岗位对技能水平要求不高，除非是高级岗位。"
    )

    user_payload = {
        "student_profile": student_data,
        "job_profile": {
            "title": job_data.get("title"),
            "required_skills": job_data.get("required_skills") or [],
            "soft_skills": job_data.get("soft_skills") or [],
            "job_description": job_data.get("job_description") or "",
            "industry": job_data.get("industry"),
        },
    }

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=1200,
        )
        content = resp.choices[0].message.content or ""
        parsed = _parse_llm_json(content)

        overall = _clamp_score(parsed.get("overall_score"), default=0.0)

        dimensions: list[dict[str, Any]] = []
        for item in parsed.get("dimensions") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            student_score = _clamp_score(item.get("student_score"), default=0.0)
            job_required = _clamp_score(item.get("job_required"), default=75.0)
            dimensions.append(
                {
                    "name": name,
                    "student_score": student_score,
                    "job_required": job_required,
                    "gap": round(student_score - job_required, 2),
                }
            )

        if not dimensions:
            raise ValueError("模型返回 dimensions 为空")

        gap_analysis_raw = parsed.get("gap_analysis") or []
        gap_analysis: list[dict[str, str]] = []
        for item in gap_analysis_raw:
            if not isinstance(item, dict):
                continue
            gap_analysis.append(
                {
                    "item": str(item.get("item") or "未命名项"),
                    "status": str(item.get("status") or "missing"),
                    "suggestion": str(item.get("suggestion") or "建议补充相关能力证据。"),
                }
            )

        return {
            "overall_score": overall,
            "dimensions": dimensions,
            "gap_analysis": gap_analysis,
        }
    except Exception:
        return _rule_fallback_analysis(student_data, job_data)


def analyze_matching(student_id: int, job_id: int, user_id: str = "default") -> dict[str, Any]:
    """Analyze matching and persist one history record."""
    student = get_student_profile(student_id)
    job = get_job_profile(job_id)
    analysis = build_matching_analysis(student["profile"], job)

    conn = get_db_conn()
    try:
        ensure_business_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO matching_history (user_id, student_id, job_id, overall_score, analysis)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id or "default", student_id, job_id, analysis["overall_score"], json.dumps(analysis, ensure_ascii=False)),
            )
            history_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    analysis["history_id"] = history_id
    return analysis
