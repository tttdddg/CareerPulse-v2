"""Student profile persistence service."""

from __future__ import annotations

import json
import re
from typing import Any

from ..db import get_db_conn, to_iso


_EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_MOBILE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")
_LANDLINE_PATTERN = re.compile(r"(?<!\d)0\d{2,3}[-\s]?\d{7,8}(?!\d)")
_IDENTITY_CARD_PATTERN = re.compile(r"(?<!\w)\d{17}[\dXx](?!\w)")


def _sanitize_text(value: str, student_name: str | None) -> str:
    sanitized = value.strip()
    for pattern in (
        _EMAIL_PATTERN,
        _MOBILE_PATTERN,
        _LANDLINE_PATTERN,
        _IDENTITY_CARD_PATTERN,
    ):
        sanitized = pattern.sub("***", sanitized)
    name = (student_name or "").strip()
    if len(name) >= 2 and name not in {"未知", "匿名"}:
        sanitized = sanitized.replace(name, "***")
    return sanitized


def _string_list(value: Any, student_name: str | None) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [
            cleaned
            for item in value
            if (cleaned := _sanitize_text(str(item), student_name))
        ]
    if isinstance(value, str) and value.strip():
        return [_sanitize_text(value, student_name)]
    return []


def _education_object(value: Any, student_name: str | None) -> dict[str, Any]:
    if isinstance(value, dict):
        education: dict[str, Any] = {}
        for key in ("degree", "major", "graduation_year"):
            item = value.get(key)
            if isinstance(item, str):
                education[key] = _sanitize_text(item, student_name)
            elif isinstance(item, int) and not isinstance(item, bool):
                education[key] = item
        return education
    if isinstance(value, str) and value.strip():
        return {"degree": _sanitize_text(value, student_name)}
    return {}


def _normalize_parsed_data(
    parsed_data: dict[str, Any], student_name: str | None = None
) -> dict[str, Any]:
    """Map legacy parser output to the finalized anonymous JSON structure."""
    if not isinstance(parsed_data, dict):
        raise ValueError("parsed_data 必须是对象")

    normalized: dict[str, Any] = {
        "skills": _string_list(parsed_data.get("skills"), student_name),
        "education": _education_object(parsed_data.get("education"), student_name),
        "target_job": (
            _sanitize_text(parsed_data["target_job"], student_name)
            if isinstance(parsed_data.get("target_job"), str)
            else ""
        ),
        "projects": _string_list(parsed_data.get("projects"), student_name),
        "internships": _string_list(parsed_data.get("internships"), student_name),
        "certificates": _string_list(parsed_data.get("certificates"), student_name),
    }
    for key in ("target_industry", "city", "supplementary_info"):
        value = parsed_data.get(key)
        if isinstance(value, str):
            normalized[key] = _sanitize_text(value, student_name)
    return normalized


def save_resume_profile(student_name: str, parsed_data: dict[str, Any]):
    """Persist an anonymous, schema-compatible profile JSON document."""
    conn = None
    cur = None
    try:
        normalized = _normalize_parsed_data(parsed_data, student_name)
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO student_profile (parsed_data) VALUES (%s::jsonb) RETURNING id",
            (json.dumps(normalized, ensure_ascii=False),),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id
    except Exception as exc:
        if conn:
            conn.rollback()
        raise RuntimeError("数据库操作失败") from exc
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_student_profile(student_id: int) -> dict[str, Any]:
    """Load one student profile by id."""
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, parsed_data, created_at, updated_at
            FROM student_profile
            WHERE id = %s
            """,
            (student_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("学生画像不存在")
        return {
            "student_id": row[0],
            "student_name": None,
            "profile": row[1] or {},
            "created_at": to_iso(row[2]),
            "updated_at": to_iso(row[3]),
        }
    finally:
        cur.close()
        conn.close()
