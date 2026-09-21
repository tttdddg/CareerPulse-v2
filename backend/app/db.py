"""

本模块只保留新业务 Repository 共用的 PostgreSQL 基础设施：
1) PostgreSQL 16 连接池
2) 只读连接上下文
3) 写事务上下文

旧 REST 的独立连接、运行时建表和字段转换辅助函数已移除；数据库
Schema 只允许通过版本化 migration 管理。
"""

from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from typing import Any, Iterator

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

from .config import get_postgres_config, get_postgres_pool_config


class BusinessDatabaseError(RuntimeError):
    """Safe base error that never exposes credentials or query parameters."""


class BusinessDatabaseUnavailable(BusinessDatabaseError):
    """The pool or a business connection is unavailable."""


class BusinessDatabaseTransactionError(BusinessDatabaseError):
    """A commit, rollback, or connection cleanup failed."""


_business_pool: ThreadedConnectionPool | None = None
_business_pool_lock = RLock()
_REQUIRED_POSTGRES_MAJOR_VERSION = 16


def _validate_business_connection(connection: Any) -> None:
    """Fail closed when the business connection is not PostgreSQL 16."""

    try:
        server_version = int(connection.server_version)
    except (AttributeError, TypeError, ValueError):
        raise BusinessDatabaseUnavailable(
            "business database server version is unavailable"
        ) from None
    if server_version // 10_000 != _REQUIRED_POSTGRES_MAJOR_VERSION:
        raise BusinessDatabaseUnavailable(
            "business database must use PostgreSQL 16"
        )


def _new_business_pool() -> ThreadedConnectionPool:
    connection_config = get_postgres_config()
    pool_config = get_postgres_pool_config()
    try:
        pool = ThreadedConnectionPool(
            pool_config["minconn"],
            pool_config["maxconn"],
            **connection_config,
        )
        connection = pool.getconn()
        try:
            _validate_business_connection(connection)
        finally:
            pool.putconn(connection)
        return pool
    except BusinessDatabaseUnavailable:
        if "pool" in locals():
            try:
                pool.closeall()
            except Exception:
                pass
        raise
    except Exception:
        if "pool" in locals():
            try:
                pool.closeall()
            except Exception:
                pass
        raise BusinessDatabaseUnavailable(
            "business database connection pool is unavailable"
        ) from None


def get_business_database_pool() -> ThreadedConnectionPool:
    """Return the process-wide thread-safe pool, creating it on first use."""

    global _business_pool
    with _business_pool_lock:
        if _business_pool is None:
            _business_pool = _new_business_pool()
        return _business_pool


def close_business_database_pool() -> None:
    """Close the current pool during application shutdown or test cleanup."""

    global _business_pool
    with _business_pool_lock:
        pool = _business_pool
        _business_pool = None
    if pool is None:
        return
    try:
        pool.closeall()
    except Exception:
        raise BusinessDatabaseError(
            "business database connection pool could not be closed"
        ) from None


def _lease_connection() -> tuple[ThreadedConnectionPool, Any]:
    pool = get_business_database_pool()
    try:
        connection = pool.getconn()
    except Exception:
        raise BusinessDatabaseUnavailable(
            "business database connection could not be acquired"
        ) from None
    if connection is None:
        raise BusinessDatabaseUnavailable(
            "business database connection could not be acquired"
        )
    return pool, connection


def _return_connection(
    pool: ThreadedConnectionPool,
    connection: Any,
    *,
    discard: bool = False,
) -> None:
    if getattr(connection, "closed", False):
        discard = True
    try:
        pool.putconn(connection, close=discard)
    except Exception:
        try:
            connection.close()
        except Exception:
            pass
        raise BusinessDatabaseError(
            "business database connection could not be returned"
        ) from None


@contextmanager
def business_connection() -> Iterator[Any]:
    """Lease a pooled connection and return it without an open transaction.

    This context never commits. It rolls back before returning the connection,
    making it suitable for reads and explicit lower-level control. Use
    :func:`business_transaction` for writes.
    """

    pool, connection = _lease_connection()
    discard = False
    active_error = False
    returned = False
    try:
        yield connection
    except BaseException:
        active_error = True
        raise
    finally:
        if not getattr(connection, "closed", False):
            try:
                connection.rollback()
            except Exception:
                discard = True
                if not active_error:
                    _return_connection(pool, connection, discard=True)
                    returned = True
                    raise BusinessDatabaseTransactionError(
                        "business database connection cleanup failed"
                    ) from None
        if not returned:
            _return_connection(pool, connection, discard=discard)


@contextmanager
def business_transaction() -> Iterator[Any]:
    """Commit a successful pooled transaction and roll back an exception."""

    pool, connection = _lease_connection()
    discard = False
    try:
        try:
            yield connection
            connection.commit()
        except BaseException as exc:
            try:
                connection.rollback()
            except Exception:
                discard = True
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                raise BusinessDatabaseTransactionError(
                    "business database transaction rollback failed"
                ) from None
            if isinstance(exc, psycopg2.Error):
                raise BusinessDatabaseTransactionError(
                    "business database transaction failed"
                ) from None
            raise
    finally:
        _return_connection(pool, connection, discard=discard)


__all__ = [
    "BusinessDatabaseError",
    "BusinessDatabaseTransactionError",
    "BusinessDatabaseUnavailable",
    "business_connection",
    "business_transaction",
    "close_business_database_pool",
    "get_business_database_pool",
]
