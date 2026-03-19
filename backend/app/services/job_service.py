from __future__ import annotations

from typing import Any

from ..db import get_db_conn, make_type_key, table_exists


def search_jobs(keyword: str, page: int, size: int) -> dict[str, Any]:
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        if not table_exists(conn, "job_clean"):
            raise RuntimeError("缺少 job_clean 表")

        offset = max(page - 1, 0) * size
        kw = f"%{keyword}%"

        cur.execute(
            """
            SELECT job_id, job_title, location_raw, salary_desc, company_name, job_description_clean
            FROM job_clean
            WHERE job_title ILIKE %s
               OR normalized_job_title ILIKE %s
               OR industry ILIKE %s
               OR city ILIKE %s
               OR company_name ILIKE %s
            ORDER BY job_id ASC
            LIMIT %s OFFSET %s
            """,
            (kw, kw, kw, kw, kw, size, offset),
        )

        jobs = [
            {
                "job_id": row[0],
                "title": row[1],
                "location": row[2],
                "salary_range": row[3],
                "company_name": row[4],
                "job_detail": row[5],
            }
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM job_clean
            WHERE job_title ILIKE %s
               OR normalized_job_title ILIKE %s
               OR industry ILIKE %s
               OR city ILIKE %s
               OR company_name ILIKE %s
            """,
            (kw, kw, kw, kw, kw),
        )
        total = cur.fetchone()[0]
        return {"total": total, "jobs": jobs}
    finally:
        cur.close()
        conn.close()


def get_job_profile(job_id: int) -> dict[str, Any]:
    """
    读取 job_clean 的实例基础信息，再映射到 job_type_profile 的聚合画像。
    """
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        if not table_exists(conn, "job_clean"):
            raise RuntimeError("缺少 job_clean 表")

        cur.execute(
            """
            SELECT job_id, job_title, normalized_job_title, salary_desc, industry, job_description_clean
            FROM job_clean
            WHERE job_id = %s
            """,
            (job_id,),
        )
        base = cur.fetchone()
        if not base:
            raise ValueError("岗位不存在")

        fallback = {
            "job_id": base[0],
            "title": base[1],
            "required_skills": [],
            "soft_skills": [],
            "salary_range": base[3],
            "industry": base[4],
            "job_description": base[5],
        }

        if not table_exists(conn, "job_type_profile"):
            return fallback

        key = make_type_key(base[2], base[4])
        cur.execute(
            """
            SELECT core_skills, optional_skills, soft_skills,
                   salary_desc_p50, industry, profile_summary
            FROM job_type_profile
            WHERE type_key = %s
            """,
            (key,),
        )
        row = cur.fetchone()
        if not row:
            return fallback

        return {
            "job_id": base[0],
            "title": base[1],
            "required_skills": (row[0] or []) + (row[1] or []),
            "soft_skills": row[2] or [],
            "salary_range": row[3] or base[3],
            "industry": row[4] or base[4],
            "job_description": row[5] or base[5],
        }
    finally:
        cur.close()
        conn.close()


def get_job_graph(job_id: int) -> dict[str, Any]:
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        if not table_exists(conn, "job_clean"):
            raise RuntimeError("缺少 job_clean 表")

        cur.execute(
            """
            SELECT job_id, job_title, normalized_job_title, industry
            FROM job_clean
            WHERE job_id = %s
            """,
            (job_id,),
        )
        center = cur.fetchone()
        if not center:
            raise ValueError("岗位不存在")

        result = {
            "center": {"id": center[0], "name": center[1]},
            "vertical": [],
            "lateral": [],
        }

        if not table_exists(conn, "job_type_graph_edge"):
            return result

        key = make_type_key(center[2], center[3])
        cur.execute(
            """
            SELECT target_job_id, target_job_title, relation_type, reason, score
            FROM job_type_graph_edge
            WHERE source_type_key = %s
            ORDER BY score DESC NULLS LAST, id ASC
            LIMIT 30
            """,
            (key,),
        )

        for target_job_id, target_title, relation_type, reason, score in cur.fetchall():
            node = {
                "id": target_job_id,
                "name": target_title,
                "relation": relation_type,
                "reason": reason,
                "score": float(score) if score is not None else None,
            }
            if relation_type == "晋升":
                result["vertical"].append(node)
            else:
                result["lateral"].append(node)

        return result
    finally:
        cur.close()
        conn.close()
