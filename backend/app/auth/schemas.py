"""Strict public schemas for end-user authentication."""

from __future__ import annotations

from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_USERNAME_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]+$")


class AuthSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RegisterRequest(AuthSchema):
    username: str = Field(min_length=3, max_length=32)
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not _USERNAME_PATTERN.fullmatch(value):
            raise ValueError("username must not contain whitespace or control characters")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.lower()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("email is invalid")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if not 10 <= len(password) <= 128:
            raise ValueError("password must contain 10 to 128 characters")
        if password.isspace():
            raise ValueError("password must not be blank")
        return value


class LoginRequest(AuthSchema):
    identifier: str = Field(min_length=3, max_length=254)
    password: SecretStr

    @field_validator("password")
    @classmethod
    def cap_password_length(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) > 128:
            raise ValueError("password is too long")
        return value


class AuthUser(AuthSchema):
    id: str
    username: str
    email: str
    role: str
    created_at: datetime


class AuthResponse(AuthSchema):
    user: AuthUser


__all__ = ["AuthResponse", "AuthUser", "LoginRequest", "RegisterRequest"]

