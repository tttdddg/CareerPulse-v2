"""History query service."""

from __future__ import annotations

from typing import Any

from ..db import ensure_business_tables, get_db_conn, to_iso
from .job_service import get_job_profile
from .student_service import get_student_profile


def get_user_histories(user_id: str) -> list[dict[str, Any]]:
    """List user's matching/report history summary."""
    conn = get_db_conn()
    try:
        ensure_business_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT h.id, h.job_id, COALESCE(c.job_title, '未知岗位'), h.overall_score, h.created_at
                FROM matching_history h
                LEFT JOIN job_clean c ON c.job_id = h.job_id
                WHERE h.user_id = %s
                ORDER BY h.created_at DESC
                LIMIT 100
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            return [
                {
                    "history_id": r[0],
                    "job_title": r[2],
                    "created_at": to_iso(r[4]),
                    "match_score": float(r[3]) if r[3] is not None else None,
                }
                for r in rows
            ]
    finally:
        conn.close()


def get_history_snapshot(history_id: int) -> dict[str, Any]:
    """Return full snapshot: analysis + student/job/report."""
    conn = get_db_conn()
    try:
        ensure_business_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, student_id, job_id, overall_score, analysis, report_id, created_at
                FROM matching_history
                WHERE id = %s
                """,
                (history_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("历史记录不存在")

            report_content = None
            if row[6]:
                cur.execute("SELECT content FROM career_report WHERE id = %s", (row[6],))
                rr = cur.fetchone()
                report_content = rr[0] if rr else None

        student = get_student_profile(row[2])
        job = get_job_profile(row[3])
        return {
            "history_id": row[0],
            "user_id": row[1],
            "created_at": to_iso(row[7]),
            "overall_score": float(row[4]) if row[4] is not None else None,
            "analysis": row[5],
            "student_profile": student,
            "job_profile": job,
            "report": report_content,
        }
    finally:
        conn.close()
