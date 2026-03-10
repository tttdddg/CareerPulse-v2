"""Student profile persistence service."""

from __future__ import annotations

import json
from typing import Any

from ..db import get_db_conn, to_iso


def save_resume_profile(student_name: str, parsed_data: dict):
    """Persist parsed student profile JSON into student_profile."""
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO student_profile (student_name, parsed_data) VALUES (%s, %s) RETURNING id",
            (student_name, json.dumps(parsed_data, ensure_ascii=False)),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id
    except Exception as e:
        if conn:
            conn.rollback()
        raise RuntimeError(f"数据库操作失败: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


def get_student_profile(student_id: int) -> dict[str, Any]:
    """Load one student profile by id."""
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, student_name, parsed_data, created_at FROM student_profile WHERE id = %s",
            (student_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("学生画像不存在")
        return {
            "student_id": row[0],
            "student_name": row[1],
            "profile": row[2] or {},
            "created_at": to_iso(row[3]),
        }
    finally:
        cur.close()
        conn.close()
