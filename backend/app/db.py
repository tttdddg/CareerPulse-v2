"""

本模块只放“跨业务可复用”的能力：
1) 建立数据库连接
2) 检查表是否存在
3) 业务表初始化
4) 常见字段标准化函数
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg2

from .config import get_postgres_config


def get_db_conn():
    config = get_postgres_config()
    return psycopg2.connect(
        host=config["host"],
        port=config["port"],
        database=config["database"],
        user=config["user"],
        password=config["password"],
        connect_timeout=config["connect_timeout"],
    )


def table_exists(conn, table_name: str) -> bool:
    """Check whether a table exists in public schema."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            (table_name,),
        )
        return bool(cur.fetchone()[0])


def ensure_business_tables(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS career_report (
                id BIGSERIAL PRIMARY KEY,
                student_id BIGINT NOT NULL,
                job_id INTEGER NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'ready',
                content JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS matching_history (
                id BIGSERIAL PRIMARY KEY,
                user_id VARCHAR(64) NOT NULL DEFAULT 'default',
                student_id BIGINT NOT NULL,
                job_id INTEGER NOT NULL,
                overall_score NUMERIC(5,2),
                analysis JSONB NOT NULL,
                report_id BIGINT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    conn.commit()


def normalize_industry(industry: str | None) -> str:
    """Normalize industry text to the first label for stable type-key grouping."""
    if not industry:
        return "未知行业"
    first = str(industry).split(",")[0].strip()
    return first or "未知行业"


def make_type_key(normalized_job_title: str | None, industry: str | None) -> str:
    """Build deterministic key used to map instance -> job type profile.

    聚合改为仅按岗位标准名，避免同名岗位被行业拆散。
    """
    _ = industry
    return (normalized_job_title or "未知岗位").strip()


def to_iso(dt: Any) -> str | None:
    """Convert datetime to ISO-8601 string, passthrough None/others."""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return None
