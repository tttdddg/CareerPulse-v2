"""PostgreSQL repository for users and opaque browser sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from ..db import (
    BusinessDatabaseError,
    BusinessDatabaseTransactionError,
    BusinessDatabaseUnavailable,
    business_connection,
    business_transaction,
)


class AuthRepositoryError(RuntimeError):
    pass


class AuthRepositoryUnavailable(AuthRepositoryError):
    pass


class AuthIdentityConflict(AuthRepositoryError):
    pass


@dataclass(frozen=True, slots=True)
class AuthUserRecord:
    id: str
    username: str
    email: str
    password_hash: str
    role: str
    status: str
    created_at: datetime


class AuthRepositoryProtocol(Protocol):
    def create_user(self, username: str, email: str, password_hash: str) -> AuthUserRecord: ...
    def find_user_by_identifier(self, identifier: str) -> AuthUserRecord | None: ...
    def create_session(self, token_hash: str, user_id: str, expires_at: datetime) -> None: ...
    def find_user_by_session(self, token_hash: str, now: datetime) -> AuthUserRecord | None: ...
    def revoke_session(self, token_hash: str, revoked_at: datetime) -> None: ...
    def is_login_limited(self, rate_key: str, since: datetime, maximum: int) -> bool: ...
    def record_login_failure(self, rate_key: str, attempted_at: datetime) -> None: ...
    def clear_login_failures(self, rate_key: str) -> None: ...


class AuthRepository:
    @staticmethod
    def _row_to_user(row: tuple) -> AuthUserRecord:
        return AuthUserRecord(
            id=row[0],
            username=row[1],
            email=row[2],
            password_hash=row[3],
            role=row[4],
            status=row[5],
            created_at=row[6],
        )

    @staticmethod
    def _translate_database_error(exc: Exception) -> AuthRepositoryUnavailable:
        del exc
        return AuthRepositoryUnavailable("authentication database is unavailable")

    def create_user(self, username: str, email: str, password_hash: str) -> AuthUserRecord:
        user_id = str(uuid4())
        try:
            with business_transaction() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO identity.app_user (
                        id, username, username_normalized, email,
                        email_normalized, password_hash
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id, username, email, password_hash, role, status, created_at
                    """,
                    (user_id, username, username.lower(), email, email.lower(), password_hash),
                )
                row = cursor.fetchone()
                if row is None:
                    raise AuthIdentityConflict("username or email already exists")
                return self._row_to_user(row)
        except AuthIdentityConflict:
            raise
        except (BusinessDatabaseError, BusinessDatabaseTransactionError, BusinessDatabaseUnavailable) as exc:
            raise self._translate_database_error(exc) from None

    def find_user_by_identifier(self, identifier: str) -> AuthUserRecord | None:
        normalized = identifier.strip().lower()
        try:
            with business_connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, username, email, password_hash, role, status, created_at
                    FROM identity.app_user
                    WHERE username_normalized = %s OR email_normalized = %s
                    LIMIT 1
                    """,
                    (normalized, normalized),
                )
                row = cursor.fetchone()
                return self._row_to_user(row) if row is not None else None
        except (BusinessDatabaseError, BusinessDatabaseTransactionError, BusinessDatabaseUnavailable) as exc:
            raise self._translate_database_error(exc) from None

    def create_session(self, token_hash: str, user_id: str, expires_at: datetime) -> None:
        try:
            with business_transaction() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO identity.auth_session (session_token_hash, user_id, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (token_hash, user_id, expires_at),
                )
        except (BusinessDatabaseError, BusinessDatabaseTransactionError, BusinessDatabaseUnavailable) as exc:
            raise self._translate_database_error(exc) from None

    def find_user_by_session(self, token_hash: str, now: datetime) -> AuthUserRecord | None:
        try:
            with business_transaction() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT u.id, u.username, u.email, u.password_hash,
                           u.role, u.status, u.created_at
                    FROM identity.auth_session AS s
                    JOIN identity.app_user AS u ON u.id = s.user_id
                    WHERE s.session_token_hash = %s
                      AND s.revoked_at IS NULL
                      AND s.expires_at > %s
                      AND u.status = 'active'
                    """,
                    (token_hash, now),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute(
                    """
                    UPDATE identity.auth_session
                    SET last_seen_at = %s
                    WHERE session_token_hash = %s
                    """,
                    (now, token_hash),
                )
                return self._row_to_user(row)
        except (BusinessDatabaseError, BusinessDatabaseTransactionError, BusinessDatabaseUnavailable) as exc:
            raise self._translate_database_error(exc) from None

    def revoke_session(self, token_hash: str, revoked_at: datetime) -> None:
        try:
            with business_transaction() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE identity.auth_session
                    SET revoked_at = COALESCE(revoked_at, %s)
                    WHERE session_token_hash = %s
                    """,
                    (revoked_at, token_hash),
                )
        except (BusinessDatabaseError, BusinessDatabaseTransactionError, BusinessDatabaseUnavailable) as exc:
            raise self._translate_database_error(exc) from None

    def is_login_limited(self, rate_key: str, since: datetime, maximum: int) -> bool:
        try:
            with business_connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM identity.auth_login_attempt
                    WHERE rate_key = %s AND attempted_at >= %s
                    """,
                    (rate_key, since),
                )
                return int(cursor.fetchone()[0]) >= maximum
        except (BusinessDatabaseError, BusinessDatabaseTransactionError, BusinessDatabaseUnavailable) as exc:
            raise self._translate_database_error(exc) from None

    def record_login_failure(self, rate_key: str, attempted_at: datetime) -> None:
        try:
            with business_transaction() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM identity.auth_login_attempt WHERE attempted_at < %s - INTERVAL '1 day'",
                    (attempted_at,),
                )
                cursor.execute(
                    "INSERT INTO identity.auth_login_attempt (rate_key, attempted_at) VALUES (%s, %s)",
                    (rate_key, attempted_at),
                )
        except (BusinessDatabaseError, BusinessDatabaseTransactionError, BusinessDatabaseUnavailable) as exc:
            raise self._translate_database_error(exc) from None

    def clear_login_failures(self, rate_key: str) -> None:
        try:
            with business_transaction() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM identity.auth_login_attempt WHERE rate_key = %s",
                    (rate_key,),
                )
        except (BusinessDatabaseError, BusinessDatabaseTransactionError, BusinessDatabaseUnavailable) as exc:
            raise self._translate_database_error(exc) from None


__all__ = [
    "AuthIdentityConflict",
    "AuthRepository",
    "AuthRepositoryProtocol",
    "AuthRepositoryUnavailable",
    "AuthUserRecord",
]

