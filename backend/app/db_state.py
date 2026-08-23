"""Durable persistence for CareerState snapshots and AgentRunLog rows.

Local/demo runs use a real SQLite file by default. Deployments can set
``A02_DATABASE_URL`` to use the PostgreSQL schema created by V003. Database
errors are never converted to an in-memory success: callers receive the error
after the transaction has been rolled back.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import psycopg2


DatabaseKind = Literal["sqlite", "postgresql"]
_DEFAULT_SQLITE_PATH = (
    Path(__file__).resolve().parents[1] / ".runtime" / "career_state.sqlite3"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateRepository:
    """Persist one latest state and one idempotent log per Agent/session."""

    def __init__(
        self,
        database_url: str | None = None,
        sqlite_path: str | Path | None = None,
    ) -> None:
        configured_url = database_url or os.getenv("A02_DATABASE_URL")
        configured_path = sqlite_path or os.getenv("A02_STATE_DB_PATH")
        if configured_url and configured_path:
            raise ValueError(
                "configure only one of A02_DATABASE_URL or A02_STATE_DB_PATH"
            )
        if configured_url:
            if not configured_url.startswith(("postgres://", "postgresql://")):
                raise ValueError("A02_DATABASE_URL must be a PostgreSQL URL")
            self.database_kind: DatabaseKind = "postgresql"
            self._database_url = configured_url
            self._sqlite_path: Path | None = None
        else:
            self.database_kind = "sqlite"
            self._database_url = None
            self._sqlite_path = Path(configured_path or _DEFAULT_SQLITE_PATH).resolve()

    @property
    def location(self) -> str:
        """Return a safe database location without credentials."""

        if self.database_kind == "postgresql":
            return "postgresql://configured"
        assert self._sqlite_path is not None
        return str(self._sqlite_path)

    def _connect(self):
        if self.database_kind == "postgresql":
            assert self._database_url is not None
            return psycopg2.connect(self._database_url)
        assert self._sqlite_path is not None
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self._sqlite_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        """Initialize local SQLite or validate the PostgreSQL migration."""

        connection = self._connect()
        try:
            if self.database_kind == "sqlite":
                self._ensure_sqlite_schema(connection)
                connection.commit()
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT to_regclass('public.career_state'),
                               to_regclass('public.agent_logs'),
                               to_regclass('public.platform_tool_calls')
                        """
                    )
                    state_table, log_table, tool_call_table = cursor.fetchone()
                if (
                    state_table is None
                    or log_table is None
                    or tool_call_table is None
                ):
                    raise RuntimeError(
                        "stage-3 persistence migrations V003/V004 have not been applied"
                    )
        finally:
            connection.close()

    @staticmethod
    def _ensure_sqlite_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS career_state (
                session_id TEXT PRIMARY KEY,
                platform_session_id TEXT,
                user_id TEXT,
                status TEXT NOT NULL,
                error_type TEXT,
                state_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_career_state_user
                ON career_state(user_id);

            CREATE TABLE IF NOT EXISTS agent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_key TEXT NOT NULL UNIQUE,
                session_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                service_name TEXT,
                status TEXT NOT NULL,
                summary TEXT,
                duration_ms INTEGER NOT NULL,
                tool_calls TEXT NOT NULL,
                fallback_used INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                demo INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_agent_logs_session
                ON agent_logs(session_id);
            CREATE INDEX IF NOT EXISTS idx_agent_logs_agent
                ON agent_logs(agent_name);

            CREATE TABLE IF NOT EXISTS platform_tool_calls (
                tool_call_id TEXT PRIMARY KEY,
                tool_name TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                request_fingerprint TEXT NOT NULL,
                session_id TEXT NOT NULL,
                platform_session_id TEXT,
                user_id_hash TEXT,
                status TEXT NOT NULL,
                result_data TEXT,
                error_code INTEGER,
                error_type TEXT,
                agent_run_key TEXT,
                duration_ms INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(tool_name, idempotency_key)
            );
            CREATE INDEX IF NOT EXISTS idx_platform_tool_calls_session
                ON platform_tool_calls(session_id);
            CREATE INDEX IF NOT EXISTS idx_platform_tool_calls_status
                ON platform_tool_calls(status);
            """
        )

    def create_tool_call(
        self,
        *,
        tool_call_id: str,
        tool_name: str,
        idempotency_key: str,
        request_fingerprint: str,
        session_id: str,
        platform_session_id: str | None,
        user_id_hash: str | None,
    ) -> tuple[dict[str, Any], bool]:
        """Create a running call or return the existing idempotent call."""

        connection = self._connect()
        now = _now()
        values = (
            tool_call_id,
            tool_name,
            idempotency_key,
            request_fingerprint,
            session_id,
            platform_session_id,
            user_id_hash,
            "running",
            now,
            now,
        )
        try:
            if self.database_kind == "sqlite":
                self._ensure_sqlite_schema(connection)
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO platform_tool_calls
                      (tool_call_id, tool_name, idempotency_key,
                       request_fingerprint, session_id, platform_session_id,
                       user_id_hash, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                created = cursor.rowcount == 1
                row = connection.execute(
                    """
                    SELECT tool_call_id, tool_name, idempotency_key,
                           request_fingerprint, session_id, platform_session_id,
                           user_id_hash, status, result_data, error_code,
                           error_type, agent_run_key, duration_ms, created_at,
                           updated_at
                    FROM platform_tool_calls
                    WHERE tool_name = ? AND idempotency_key = ?
                    """,
                    (tool_name, idempotency_key),
                ).fetchone()
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO platform_tool_calls
                          (tool_call_id, tool_name, idempotency_key,
                           request_fingerprint, session_id, platform_session_id,
                           user_id_hash, status, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                                %s::timestamptz, %s::timestamptz)
                        ON CONFLICT (tool_name, idempotency_key) DO NOTHING
                        """,
                        values,
                    )
                    created = cursor.rowcount == 1
                    cursor.execute(
                        """
                        SELECT tool_call_id, tool_name, idempotency_key,
                               request_fingerprint, session_id,
                               platform_session_id, user_id_hash, status,
                               result_data, error_code, error_type,
                               agent_run_key, duration_ms, created_at, updated_at
                        FROM platform_tool_calls
                        WHERE tool_name = %s AND idempotency_key = %s
                        """,
                        (tool_name, idempotency_key),
                    )
                    row = cursor.fetchone()
            connection.commit()
            if row is None:
                raise RuntimeError("platform tool call insert returned no row")
            return self._tool_call_row(row), created
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def finish_tool_call(
        self,
        tool_call_id: str,
        *,
        status: str,
        result_data: dict[str, Any] | None = None,
        error_code: int | None = None,
        error_type: str | None = None,
        agent_run_key: str | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        """Persist a terminal platform call without retaining its raw input."""

        connection = self._connect()
        now = _now()
        serialized = (
            json.dumps(result_data, ensure_ascii=False, default=str)
            if result_data is not None
            else None
        )
        try:
            if self.database_kind == "sqlite":
                self._ensure_sqlite_schema(connection)
                connection.execute(
                    """
                    UPDATE platform_tool_calls
                    SET status = ?, result_data = ?, error_code = ?,
                        error_type = ?, agent_run_key = ?, duration_ms = ?,
                        updated_at = ?
                    WHERE tool_call_id = ?
                    """,
                    (
                        status,
                        serialized,
                        error_code,
                        error_type,
                        agent_run_key,
                        duration_ms,
                        now,
                        tool_call_id,
                    ),
                )
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE platform_tool_calls
                        SET status = %s, result_data = %s::jsonb,
                            error_code = %s, error_type = %s,
                            agent_run_key = %s, duration_ms = %s,
                            updated_at = %s::timestamptz
                        WHERE tool_call_id = %s
                        """,
                        (
                            status,
                            serialized,
                            error_code,
                            error_type,
                            agent_run_key,
                            duration_ms,
                            now,
                            tool_call_id,
                        ),
                    )
            connection.commit()
            record = self.get_tool_call(tool_call_id)
            if record is None:
                raise RuntimeError("platform tool call not found after update")
            return record
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_tool_call(self, tool_call_id: str) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            if self.database_kind == "sqlite":
                self._ensure_sqlite_schema(connection)
                row = connection.execute(
                    """
                    SELECT tool_call_id, tool_name, idempotency_key,
                           request_fingerprint, session_id, platform_session_id,
                           user_id_hash, status, result_data, error_code,
                           error_type, agent_run_key, duration_ms, created_at,
                           updated_at
                    FROM platform_tool_calls WHERE tool_call_id = ?
                    """,
                    (tool_call_id,),
                ).fetchone()
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT tool_call_id, tool_name, idempotency_key,
                               request_fingerprint, session_id,
                               platform_session_id, user_id_hash, status,
                               result_data, error_code, error_type,
                               agent_run_key, duration_ms, created_at, updated_at
                        FROM platform_tool_calls WHERE tool_call_id = %s
                        """,
                        (tool_call_id,),
                    )
                    row = cursor.fetchone()
            return None if row is None else self._tool_call_row(row)
        finally:
            connection.close()

    @staticmethod
    def _tool_call_row(row: Any) -> dict[str, Any]:
        result_data = row[8]
        if isinstance(result_data, str):
            result_data = json.loads(result_data)
        return {
            "tool_call_id": row[0],
            "tool_name": row[1],
            "idempotency_key": row[2],
            "request_fingerprint": row[3],
            "session_id": row[4],
            "platform_session_id": row[5],
            "user_id_hash": row[6],
            "status": row[7],
            "result_data": result_data,
            "error_code": row[9],
            "error_type": row[10],
            "agent_run_key": row[11],
            "duration_ms": row[12],
            "created_at": row[13],
            "updated_at": row[14],
        }

    def save_state_and_logs(
        self,
        state: dict[str, Any],
        logs: list[dict[str, Any]] | None = None,
    ) -> None:
        """Atomically upsert a state snapshot and idempotent Agent logs."""

        connection = self._connect()
        try:
            if self.database_kind == "sqlite":
                self._ensure_sqlite_schema(connection)
                connection.commit()
                connection.execute("BEGIN")
            self._upsert_state(connection, state)
            self._upsert_logs(connection, state["session_id"], logs or [])
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def save_state(self, state: dict[str, Any]) -> None:
        self.save_state_and_logs(state, [])

    def _upsert_state(self, connection, state: dict[str, Any]) -> None:
        serialized = json.dumps(state, ensure_ascii=False, default=str)
        now = _now()
        values = (
            state["session_id"],
            state.get("platform_session_id"),
            state.get("user_id"),
            state.get("status") or "INITIALIZED",
            state.get("error_type"),
            serialized,
            now,
            now,
        )
        if self.database_kind == "sqlite":
            connection.execute(
                """
                INSERT INTO career_state
                  (session_id, platform_session_id, user_id, status, error_type,
                   state_data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                  platform_session_id = excluded.platform_session_id,
                  user_id = excluded.user_id,
                  status = excluded.status,
                  error_type = excluded.error_type,
                  state_data = excluded.state_data,
                  updated_at = excluded.updated_at
                """,
                values,
            )
            return
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO career_state
                  (session_id, platform_session_id, user_id, status, error_type,
                   state_data, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb,
                        %s::timestamptz, %s::timestamptz)
                ON CONFLICT (session_id) DO UPDATE SET
                  platform_session_id = EXCLUDED.platform_session_id,
                  user_id = EXCLUDED.user_id,
                  status = EXCLUDED.status,
                  error_type = EXCLUDED.error_type,
                  state_data = EXCLUDED.state_data,
                  updated_at = EXCLUDED.updated_at
                """,
                values,
            )

    def _upsert_logs(
        self,
        connection,
        session_id: str,
        logs: list[dict[str, Any]],
    ) -> None:
        for log in logs:
            agent_name = log["agent_name"]
            run_key = f"{session_id}:{agent_name}"
            values = (
                run_key,
                session_id,
                agent_name,
                log.get("service_name"),
                log["status"],
                log.get("summary", ""),
                log.get("duration_ms", 0),
                json.dumps(log.get("tool_calls") or [], ensure_ascii=False),
                bool(log.get("fallback_used", False)),
                log.get("error"),
                bool(log.get("demo", False)),
                log.get("timestamp") or _now(),
            )
            if self.database_kind == "sqlite":
                connection.execute(
                    """
                    INSERT INTO agent_logs
                      (run_key, session_id, agent_name, service_name, status,
                       summary, duration_ms, tool_calls, fallback_used, error,
                       demo, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_key) DO UPDATE SET
                      service_name = excluded.service_name,
                      status = excluded.status,
                      summary = excluded.summary,
                      duration_ms = excluded.duration_ms,
                      tool_calls = excluded.tool_calls,
                      fallback_used = excluded.fallback_used,
                      error = excluded.error,
                      demo = excluded.demo,
                      created_at = excluded.created_at
                    """,
                    values,
                )
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO agent_logs
                          (run_key, session_id, agent_name, service_name, status,
                           summary, duration_ms, tool_calls, fallback_used, error,
                           demo, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                                %s, %s, %s, %s::timestamptz)
                        ON CONFLICT (run_key) DO UPDATE SET
                          service_name = EXCLUDED.service_name,
                          status = EXCLUDED.status,
                          summary = EXCLUDED.summary,
                          duration_ms = EXCLUDED.duration_ms,
                          tool_calls = EXCLUDED.tool_calls,
                          fallback_used = EXCLUDED.fallback_used,
                          error = EXCLUDED.error,
                          demo = EXCLUDED.demo,
                          created_at = EXCLUDED.created_at
                        """,
                        values,
                    )

    def get_state(self, session_id: str) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            if self.database_kind == "sqlite":
                self._ensure_sqlite_schema(connection)
                row = connection.execute(
                    "SELECT state_data FROM career_state WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT state_data FROM career_state WHERE session_id = %s",
                        (session_id,),
                    )
                    row = cursor.fetchone()
            if row is None:
                return None
            value = row[0]
            return value if isinstance(value, dict) else json.loads(value)
        finally:
            connection.close()

    def list_agent_logs(
        self,
        session_id: str,
        agent_name: str | None = None,
    ) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            if self.database_kind == "sqlite":
                self._ensure_sqlite_schema(connection)
                sql = (
                    "SELECT session_id, agent_name, service_name, status, summary, "
                    "duration_ms, tool_calls, fallback_used, error, created_at "
                    "FROM agent_logs WHERE session_id = ?"
                )
                params: tuple[Any, ...] = (session_id,)
                if agent_name:
                    sql += " AND agent_name = ?"
                    params += (agent_name,)
                sql += " ORDER BY created_at ASC, id ASC"
                rows = connection.execute(sql, params).fetchall()
            else:
                sql = (
                    "SELECT session_id, agent_name, service_name, status, summary, "
                    "duration_ms, tool_calls, fallback_used, error, created_at "
                    "FROM agent_logs WHERE session_id = %s"
                )
                params = (session_id,)
                if agent_name:
                    sql += " AND agent_name = %s"
                    params += (agent_name,)
                sql += " ORDER BY created_at ASC, id ASC"
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
            return [self._log_row(row) for row in rows]
        finally:
            connection.close()

    @staticmethod
    def _log_row(row: Any) -> dict[str, Any]:
        tool_calls = row[6]
        if isinstance(tool_calls, str):
            tool_calls = json.loads(tool_calls)
        created_at = row[9]
        return {
            "session_id": row[0],
            "agent_name": row[1],
            "service_name": row[2],
            "status": row[3],
            "summary": row[4] or "",
            "duration_ms": row[5] or 0,
            "tool_calls": tool_calls or [],
            "fallback_used": bool(row[7]),
            "error": row[8],
            "timestamp": (
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at)
            ),
        }


__all__ = ["StateRepository"]
