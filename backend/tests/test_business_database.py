"""Business PostgreSQL infrastructure tests; no real database is contacted."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

import psycopg2

from app import db
from app.config import get_postgres_pool_config
from app.repositories.base import BaseRepository, BusinessDatabaseQueryError


class FakeCursor:
    def __init__(self) -> None:
        self.executions: list[tuple[str, object]] = []
        self.one = (1,)
        self.all = [(1,), (2,)]
        self.rowcount = 2
        self.execute_error: Exception | None = None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str, parameters: object) -> None:
        self.executions.append((statement, parameters))
        if self.execute_error is not None:
            raise self.execute_error

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.all


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False
        self.server_version = 160000
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self.cursor_value = FakeCursor()
        self.rollback_error: Exception | None = None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1
        if self.rollback_error is not None:
            raise self.rollback_error

    def close(self) -> None:
        self.closes += 1
        self.closed = True

    def cursor(self) -> FakeCursor:
        return self.cursor_value


class FakePool:
    def __init__(self, connection: FakeConnection | None = None) -> None:
        self.connection = connection or FakeConnection()
        self.get_error: Exception | None = None
        self.get_count = 0
        self.put_calls: list[tuple[FakeConnection, bool]] = []
        self.close_count = 0

    def getconn(self) -> FakeConnection:
        self.get_count += 1
        if self.get_error is not None:
            raise self.get_error
        return self.connection

    def putconn(self, connection: FakeConnection, *, close: bool = False) -> None:
        self.put_calls.append((connection, close))

    def closeall(self) -> None:
        self.close_count += 1


class BusinessDatabaseInfrastructureTests(unittest.TestCase):
    def setUp(self) -> None:
        db._business_pool = None

    def tearDown(self) -> None:
        db._business_pool = None

    def test_pool_is_lazy_and_uses_only_postgres_configuration(self) -> None:
        environment = {
            "POSTGRES_HOST": "business.internal",
            "POSTGRES_PORT": "5544",
            "POSTGRES_DATABASE": "careerpulse_micro",
            "POSTGRES_USER": "business_user",
            "POSTGRES_PASSWORD": "business-secret",
            "POSTGRES_CONNECT_TIMEOUT": "7",
            "POSTGRES_POOL_MIN_SIZE": "2",
            "POSTGRES_POOL_MAX_SIZE": "8",
            "A02_DATABASE_URL": "postgresql://state:state-secret@state/db",
            "A02_STATE_DB_PATH": "ignored-state.sqlite3",
        }
        pool = Mock()
        pooled_connection = FakeConnection()
        pool.getconn.return_value = pooled_connection
        with patch.dict(os.environ, environment, clear=True), patch.object(
            db, "ThreadedConnectionPool", return_value=pool
        ) as pool_type:
            self.assertIsNone(db._business_pool)
            pool_type.assert_not_called()

            first = db.get_business_database_pool()
            second = db.get_business_database_pool()

        self.assertIs(first, pool)
        self.assertIs(second, pool)
        pool_type.assert_called_once_with(
            2,
            8,
            host="business.internal",
            port=5544,
            database="careerpulse_micro",
            user="business_user",
            password="business-secret",
            connect_timeout=7,
        )
        pool.getconn.assert_called_once_with()
        pool.putconn.assert_called_once_with(pooled_connection)

    def test_pool_configuration_validates_bounds(self) -> None:
        with patch.dict(
            os.environ,
            {
                "POSTGRES_POOL_MIN_SIZE": "4",
                "POSTGRES_POOL_MAX_SIZE": "3",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "POSTGRES_POOL_MAX_SIZE"):
                get_postgres_pool_config()

    def test_pool_rejects_non_postgres_16_and_closes(self) -> None:
        pool = Mock()
        connection = FakeConnection()
        connection.server_version = 180000
        pool.getconn.return_value = connection
        with patch.dict(os.environ, {}, clear=True), patch.object(
            db, "ThreadedConnectionPool", return_value=pool
        ):
            with self.assertRaisesRegex(
                db.BusinessDatabaseUnavailable,
                "PostgreSQL 16",
            ):
                db.get_business_database_pool()

        pool.putconn.assert_called_once_with(connection)
        pool.closeall.assert_called_once_with()

    def test_legacy_standalone_helpers_are_not_exported(self) -> None:
        for name in (
            "get_db_conn",
            "table_exists",
            "ensure_business_tables",
            "normalize_industry",
            "make_type_key",
            "to_iso",
        ):
            self.assertFalse(hasattr(db, name), name)

    def test_connection_context_rolls_back_and_returns_connection(self) -> None:
        connection = FakeConnection()
        pool = FakePool(connection)
        with patch.object(db, "get_business_database_pool", return_value=pool):
            with db.business_connection() as leased:
                self.assertIs(leased, connection)

        self.assertEqual(1, connection.rollbacks)
        self.assertEqual([(connection, False)], pool.put_calls)

    def test_connection_is_returned_when_body_raises(self) -> None:
        connection = FakeConnection()
        pool = FakePool(connection)
        with patch.object(db, "get_business_database_pool", return_value=pool):
            with self.assertRaisesRegex(RuntimeError, "application failure"):
                with db.business_connection():
                    raise RuntimeError("application failure")

        self.assertEqual(1, connection.rollbacks)
        self.assertEqual([(connection, False)], pool.put_calls)

    def test_transaction_commits_success_and_returns_connection(self) -> None:
        connection = FakeConnection()
        pool = FakePool(connection)
        with patch.object(db, "get_business_database_pool", return_value=pool):
            with db.business_transaction() as leased:
                self.assertIs(leased, connection)

        self.assertEqual(1, connection.commits)
        self.assertEqual(0, connection.rollbacks)
        self.assertEqual([(connection, False)], pool.put_calls)

    def test_transaction_rolls_back_error_and_returns_connection(self) -> None:
        connection = FakeConnection()
        pool = FakePool(connection)
        with patch.object(db, "get_business_database_pool", return_value=pool):
            with self.assertRaisesRegex(ValueError, "bad input"):
                with db.business_transaction():
                    raise ValueError("bad input")

        self.assertEqual(0, connection.commits)
        self.assertEqual(1, connection.rollbacks)
        self.assertEqual([(connection, False)], pool.put_calls)

    def test_acquisition_failure_is_sanitized(self) -> None:
        pool = FakePool()
        pool.get_error = RuntimeError(
            "password=do-not-log; profile=private-student-content"
        )
        with patch.object(db, "get_business_database_pool", return_value=pool):
            with self.assertRaises(db.BusinessDatabaseUnavailable) as caught:
                with db.business_connection():
                    pass

        message = str(caught.exception)
        self.assertNotIn("do-not-log", message)
        self.assertNotIn("private-student-content", message)

    def test_pool_creation_failure_is_sanitized(self) -> None:
        with patch.object(
            db,
            "ThreadedConnectionPool",
            side_effect=RuntimeError("postgresql://user:secret@host/database"),
        ):
            with self.assertRaises(db.BusinessDatabaseUnavailable) as caught:
                db.get_business_database_pool()

        self.assertNotIn("secret", str(caught.exception))
        self.assertIsNone(db._business_pool)

    def test_close_pool_releases_all_connections_and_allows_recreation(self) -> None:
        pool = FakePool()
        db._business_pool = pool  # type: ignore[assignment]

        db.close_business_database_pool()

        self.assertEqual(1, pool.close_count)
        self.assertIsNone(db._business_pool)


class BaseRepositoryTests(unittest.TestCase):
    @staticmethod
    @contextmanager
    def _connection_context(connection: FakeConnection):
        yield connection

    def test_fetch_and_execute_keep_parameters_separate_from_sql(self) -> None:
        connection = FakeConnection()
        repository = BaseRepository()
        with patch(
            "app.repositories.base.business_connection",
            side_effect=lambda: self._connection_context(connection),
        ):
            result = repository.fetch_one(
                "SELECT value FROM fixed_table WHERE id = %s",
                ("private-value",),
            )

        self.assertEqual((1,), result)
        self.assertEqual(
            [
                (
                    "SELECT value FROM fixed_table WHERE id = %s",
                    ("private-value",),
                )
            ],
            connection.cursor_value.executions,
        )

        connection.cursor_value.executions.clear()
        with patch(
            "app.repositories.base.business_transaction",
            side_effect=lambda: self._connection_context(connection),
        ):
            affected = repository.execute(
                "UPDATE fixed_table SET value = %s WHERE id = %s",
                ("private-value", 7),
            )

        self.assertEqual(2, affected)
        self.assertEqual(
            [
                (
                    "UPDATE fixed_table SET value = %s WHERE id = %s",
                    ("private-value", 7),
                )
            ],
            connection.cursor_value.executions,
        )

    def test_query_failure_does_not_expose_statement_or_parameters(self) -> None:
        connection = FakeConnection()
        connection.cursor_value.execute_error = psycopg2.DatabaseError(
            "private-value from private_table"
        )
        repository = BaseRepository()
        with patch(
            "app.repositories.base.business_connection",
            side_effect=lambda: self._connection_context(connection),
        ):
            with self.assertRaises(BusinessDatabaseQueryError) as caught:
                repository.fetch_all(
                    "SELECT secret FROM private_table WHERE profile = %s",
                    ("private-value",),
                )

        message = str(caught.exception)
        self.assertNotIn("private_table", message)
        self.assertNotIn("private-value", message)

    def test_blank_statement_is_rejected_before_connection(self) -> None:
        repository = BaseRepository()
        with patch("app.repositories.base.business_connection") as connection:
            with self.assertRaisesRegex(ValueError, "non-empty"):
                repository.fetch_one("   ")
        connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
