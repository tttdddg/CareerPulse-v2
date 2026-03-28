from __future__ import annotations

from typing import Any

from ..db import get_db_conn, make_type_key, table_exists


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _normalize_relation(relation_type: str | None) -> tuple[str, str]:
    """将数据库关系类型映射到前端友好的标签/类型。

    Returns:
      (label, edge_type)
      - label: 晋升 or 换岗
      - edge_type: vertical or lateral
    """
    rt = (relation_type or "").strip()
    if rt == "晋升":
        return "晋升", "vertical"
    if rt in {"平移", "换岗"}:
        return "换岗", "lateral"
    return "换岗", "lateral"


def _compute_match_score(
    keyword: str,
    job_title: str | None,
    normalized_job_title: str | None,
    industry: str | None,
    location: str | None,
    company_name: str | None,
    salary_desc: str | None,
    title_level: int | None,
) -> float:
    """暂时用于列表显示的匹配分数，后续根据需要替换成更实际的逻辑"""
    k = (keyword or "").strip().lower()
    score = 70.0

    jt = (job_title or "").lower()
    nt = (normalized_job_title or "").lower()
    ind = (industry or "").lower()
    loc = (location or "").lower()
    comp = (company_name or "").lower()
 
    if k:
        if k == nt:
            score += 20
        elif k in nt:
            score += 15
        elif k in jt:
            score += 12

        if k in ind:
            score += 8
        if k in loc:
            score += 4
        if k in comp:
            score += 3

    if salary_desc:
        score += 2

    if title_level is not None:
        try:
            score += min(int(title_level) * 2, 6)
        except Exception:
            pass

    return round(_clamp(score, 55.0, 99.0), 1)


def _infer_required_certs(required_skills: list[str], title: str, industry: str | None) -> list[str]:
    """推断岗位所需证书，暂时基于简单的关键词规则，后续可替换成大模型逻辑"""
    text = " ".join(required_skills + [title or "", industry or ""]).lower()

    certs: list[str] = []

    def add(cert: str) -> None:
        if cert not in certs:
            certs.append(cert)

    if any(x in text for x in ["java", "spring", "后端"]):
        add("软考中级（软件设计师）")
    if any(x in text for x in ["python"]):
        add("计算机二级（Python）")
    if any(x in text for x in ["前端", "javascript", "typescript", "vue", "react"]):
        add("1+X Web前端开发（可选）")
    if any(x in text for x in ["sql", "mysql", "postgres", "数据库"]):
        add("数据库认证（可选）")
    if any(x in text for x in ["网络", "运维", "云"]):
        add("HCIA/HCIP（可选）")
    if any(x in text for x in ["产品", "项目管理", "需求"]):
        add("PMP（可选）")

    if not certs:
        certs = ["暂无硬性证书要求"]

    return certs[:3]


def _build_ability_dimensions(required_skills: list[str], soft_skills: list[str], optional_skills: list[str]) -> dict[str, int]:
    rs = len(required_skills)
    ss = len(soft_skills)
    osz = len(optional_skills)

    communication_hit = sum(
        1 for s in soft_skills if any(k in str(s) for k in ["沟通", "协作", "表达", "跨部门", "团队"])
    )

    dimensions = {
        "innovation": int(round(_clamp(62 + osz * 3, 50, 95))),
        "learning": int(round(_clamp(65 + min(rs, 10) * 2, 50, 95))),
        "stress_tolerance": int(round(_clamp(63 + min(ss, 8) * 3, 50, 95))),
        "communication": int(round(_clamp(60 + communication_hit * 8 + min(ss, 4) * 2, 50, 95))),
        "internship": int(round(_clamp(58 + min(rs, 12) * 2, 50, 95))),
    }
    return dimensions


def search_jobs(keyword: str, page: int, size: int) -> dict[str, Any]:
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        if not table_exists(conn, "job_clean"):
            raise RuntimeError("缺少 job_clean 表")

        page = max(int(page or 1), 1)
        size = min(max(int(size or 10), 1), 100)
        offset = (page - 1) * size

        kw_raw = (keyword or "").strip()
        has_kw = bool(kw_raw)
        kw = f"%{kw_raw}%"

        if has_kw:
            cur.execute(
                """
                SELECT job_id, job_title, normalized_job_title,
                       location_raw, salary_desc, company_name, industry,
                       job_description_clean, title_level
                FROM job_clean
                WHERE job_title ILIKE %s
                   OR normalized_job_title ILIKE %s
                   OR industry ILIKE %s
                   OR city ILIKE %s
                   OR company_name ILIKE %s
                ORDER BY
                    CASE WHEN normalized_job_title ILIKE %s THEN 0 ELSE 1 END,
                    job_id ASC
                LIMIT %s OFFSET %s
                """,
                (kw, kw, kw, kw, kw, kw, size, offset),
            )
        else:
            cur.execute(
                """
                SELECT job_id, job_title, normalized_job_title,
                       location_raw, salary_desc, company_name, industry,
                       job_description_clean, title_level
                FROM job_clean
                ORDER BY updated_at DESC NULLS LAST, job_id ASC
                LIMIT %s OFFSET %s
                """,
                (size, offset),
            )

        jobs = []
        for row in cur.fetchall():
            match_score = _compute_match_score(
                kw_raw,
                row[1],
                row[2],
                row[6],
                row[3],
                row[5],
                row[4],
                row[8],
            )
            jobs.append(
                {
                    "job_id": row[0],
                    "title": row[1],
                    "company": row[5] or "",
                    "company_name": row[5] or "",
                    "industry": row[6] or "",
                    "salary_range": row[4] or "",
                    "match_score": match_score,
                    "location": row[3],
                    "job_detail": row[7],
                }
            )

        if has_kw:
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
        else:
            cur.execute("SELECT COUNT(*) FROM job_clean")

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

        fallback_required_skills: list[str] = []
        fallback_optional_skills: list[str] = []
        fallback_soft_skills: list[str] = []

        fallback = {
            "job_id": base[0],
            "title": base[1],
            "required_skills": fallback_required_skills,
            "required_certs": _infer_required_certs(fallback_required_skills, base[1], base[4]),
            "soft_skills": fallback_soft_skills,
            "ability_dimensions": _build_ability_dimensions(
                fallback_required_skills,
                fallback_soft_skills,
                fallback_optional_skills,
            ),
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

        core_skills = row[0] or []
        optional_skills = row[1] or []
        soft_skills = row[2] or []
        required_skills = core_skills + optional_skills

        return {
            "job_id": base[0],
            "title": base[1],
            "required_skills": required_skills,
            "required_certs": _infer_required_certs(required_skills, base[1], row[4] or base[4]),
            "soft_skills": soft_skills,
            "ability_dimensions": _build_ability_dimensions(required_skills, soft_skills, optional_skills),
            "salary_range": row[3] or base[3],
            "industry": row[4] or base[4],
            "job_description": row[5] or base[5],
        }
    finally:
        cur.close()
        conn.close()


def _load_node_detail(
    cur,
    node_job_id: int | None,
    node_type_key: str | None,
    node_name_fallback: str | None,
) -> dict[str, Any]:
    """Load node detail from job_clean first, then job_type_profile fallback."""
    if node_job_id is not None:
        cur.execute(
            """
            SELECT job_id, job_title, normalized_job_title, salary_desc, industry, job_description_clean
            FROM job_clean
            WHERE job_id = %s
            """,
            (node_job_id,),
        )
        row = cur.fetchone()
        if row:
            core_skills: list[str] = []
            optional_skills: list[str] = []
            summary = row[5]
            salary_range = row[3]
            key = make_type_key(row[2], row[4])

            if table_exists(cur.connection, "job_type_profile"):
                cur.execute(
                    """
                    SELECT core_skills, optional_skills, salary_desc_p50, profile_summary
                    FROM job_type_profile
                    WHERE type_key = %s
                    """,
                    (key,),
                )
                p = cur.fetchone()
                if p:
                    core_skills = p[0] or []
                    optional_skills = p[1] or []
                    salary_range = p[2] or salary_range
                    summary = p[3] or summary

            return {
                "id": str(row[0]),
                "name": row[1] or node_name_fallback or node_type_key or "",
                "job_description": summary or "",
                "core_skills": (core_skills + optional_skills)[:12],
                "salary_range": salary_range or "",
            }

    if node_type_key and table_exists(cur.connection, "job_type_profile"):
        cur.execute(
            """
            SELECT type_key, normalized_job_title, core_skills, optional_skills,
                   salary_desc_p50, profile_summary, exemplar_job_id, exemplar_job_title
            FROM job_type_profile
            WHERE type_key = %s
            """,
            (node_type_key,),
        )
        p = cur.fetchone()
        if p:
            node_id = str(p[6]) if p[6] is not None else f"type:{p[0]}"
            node_name = p[1] or p[7] or node_name_fallback or p[0]
            return {
                "id": node_id,
                "name": node_name,
                "job_description": p[5] or "",
                "core_skills": ((p[2] or []) + (p[3] or []))[:12],
                "salary_range": p[4] or "",
            }

    fallback_id = str(node_job_id) if node_job_id is not None else f"type:{node_type_key or (node_name_fallback or 'unknown')}"
    return {
        "id": fallback_id,
        "name": node_name_fallback or node_type_key or "",
        "job_description": "",
        "core_skills": [],
        "salary_range": "",
    }


def get_job_graph(job_id: int) -> dict[str, Any]:
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
        center_row = cur.fetchone()
        if not center_row:
            raise ValueError("岗位不存在")

        center_type_key = make_type_key(center_row[2], center_row[4])
        center_core: list[str] = []
        center_optional: list[str] = []
        center_salary = center_row[3]
        center_desc = center_row[5]

        if table_exists(conn, "job_type_profile"):
            cur.execute(
                """
                SELECT core_skills, optional_skills, salary_desc_p50, profile_summary
                FROM job_type_profile
                WHERE type_key = %s
                """,
                (center_type_key,),
            )
            p = cur.fetchone()
            if p:
                center_core = p[0] or []
                center_optional = p[1] or []
                center_salary = p[2] or center_salary
                center_desc = p[3] or center_desc

        center = {
            "id": str(center_row[0]),
            "name": center_row[1],
            "job_description": center_desc or "",
            "core_skills": (center_core + center_optional)[:12],
            "salary_range": center_salary or "",
        }

        result = {
            "center": center,
            "vertical": [],
            "lateral": [],
            "relations": [],
        }

        if not table_exists(conn, "job_type_graph_edge"):
            return result

        cur.execute(
            """
            SELECT target_type_key, target_job_id, target_job_title, relation_type, reason, score
            FROM job_type_graph_edge
            WHERE source_type_key = %s
            ORDER BY score DESC NULLS LAST, id ASC
            LIMIT 50
            """,
            (center_type_key,),
        )

        seen_vertical: set[str] = set()
        seen_lateral: set[str] = set()

        for target_type_key, target_job_id, target_job_title, relation_type, reason, score in cur.fetchall():
            label, edge_type = _normalize_relation(relation_type)

            node = _load_node_detail(
                cur,
                node_job_id=target_job_id,
                node_type_key=target_type_key,
                node_name_fallback=target_job_title,
            )
            node["relation"] = label
            node["reason"] = reason
            node["score"] = float(score) if score is not None else None

            node_id = str(node["id"])
            if edge_type == "vertical":
                if node_id in seen_vertical:
                    continue
                seen_vertical.add(node_id)
                result["vertical"].append(node)
                result["relations"].append(
                    {
                        "source": node_id,
                        "target": str(center["id"]),
                        "type": "vertical",
                        "label": "晋升",
                    }
                )
            else:
                if node_id in seen_lateral:
                    continue
                seen_lateral.add(node_id)
                result["lateral"].append(node)
                result["relations"].append(
                    {
                        "source": str(center["id"]),
                        "target": node_id,
                        "type": "lateral",
                        "label": "换岗",
                    }
                )

        return result
    finally:
        cur.close()
        conn.close()
