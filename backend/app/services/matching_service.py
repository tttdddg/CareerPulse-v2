"""Matching service.

实现人岗匹配评分（主逻辑为 LLM 语义评分），并保留规则法作为兜底。
"""

from __future__ import annotations

import json
import re
from typing import Any

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
    """Build a deterministic matching result.

    Match scores are business calculations and must not be invented by an LLM.
    A future semantic-normalization step may use the unified client, but its
    output must be validated and passed into deterministic score calculation.
    """

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
