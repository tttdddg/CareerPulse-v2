"""Password and opaque-token security helpers."""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type


class AuthSecurity:
    def __init__(self) -> None:
        self._password_hasher = PasswordHasher(type=Type.ID)
        self._dummy_hash = self._password_hasher.hash(
            "CareerPulse-dummy-password-never-used"
        )

    def hash_password(self, password: str) -> str:
        return self._password_hasher.hash(password)

    def verify_password(self, password_hash: str, password: str) -> bool:
        try:
            return self._password_hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    def consume_dummy_verification(self, password: str) -> None:
        self.verify_password(self._dummy_hash, password)

    @staticmethod
    def new_session_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def new_csrf_token() -> str:
        return secrets.token_urlsafe(24)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def rate_limit_key(identifier: str, client_host: str) -> str:
        canonical = f"{identifier.strip().lower()}|{client_host.strip()}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["AuthSecurity"]

