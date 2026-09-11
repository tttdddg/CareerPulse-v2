"""Environment-backed configuration for legacy CareerPulse services."""

from __future__ import annotations

import os
from typing import Any


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name)
    try:
        value = default if raw_value in (None, "") else int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def get_postgres_config() -> dict[str, Any]:
    """Read the legacy PostgreSQL connection settings from the environment."""

    return {
        "host": os.getenv("POSTGRES_HOST", "localhost").strip() or "localhost",
        "port": _env_int("POSTGRES_PORT", 5432, minimum=1, maximum=65535),
        "database": os.getenv("POSTGRES_DATABASE", "postgres").strip()
        or "postgres",
        "user": os.getenv("POSTGRES_USER", "postgres").strip() or "postgres",
        # Intentionally empty by default. Production credentials belong only in
        # the protected systemd EnvironmentFile, never in source control.
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "connect_timeout": _env_int(
            "POSTGRES_CONNECT_TIMEOUT", 5, minimum=1, maximum=60
        ),
    }


# Retain the historical name for compatibility with any external imports. The
# database helper reads fresh settings per connection so deployment tooling and
# tests can override the process environment safely.
POSTGRES_CONFIG = get_postgres_config()


__all__ = ["POSTGRES_CONFIG", "get_postgres_config"]
