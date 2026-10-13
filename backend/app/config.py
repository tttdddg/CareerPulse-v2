
"""Environment-backed PostgreSQL configuration for CareerPulse business services."""

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
    """Read business PostgreSQL connection settings from POSTGRES_*."""

    configured_database = os.getenv("POSTGRES_DATABASE")
    if configured_database is None and os.getenv("POSTGRES_DB") not in (None, ""):
        raise ValueError("POSTGRES_DB is not supported; use POSTGRES_DATABASE")

    return {
        "host": os.getenv("POSTGRES_HOST", "localhost").strip() or "localhost",
        "port": _env_int("POSTGRES_PORT", 5433, minimum=1, maximum=65535),
        "database": (configured_database or "careerpulse_micro").strip()
        or "careerpulse_micro",
        "user": os.getenv("POSTGRES_USER", "postgres").strip() or "postgres",
        # Production credentials must be provided through protected
        # environment configuration and never committed to source control.
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "connect_timeout": _env_int(
            "POSTGRES_CONNECT_TIMEOUT", 5, minimum=1, maximum=60
        ),
    }


def get_postgres_pool_config() -> dict[str, int]:
    """Read bounded business connection-pool settings from POSTGRES_*."""

    minimum = _env_int("POSTGRES_POOL_MIN_SIZE", 1, minimum=1, maximum=100)
    maximum = _env_int("POSTGRES_POOL_MAX_SIZE", 10, minimum=1, maximum=100)
    if maximum < minimum:
        raise ValueError(
            "POSTGRES_POOL_MAX_SIZE must be greater than or equal to "
            "POSTGRES_POOL_MIN_SIZE"
        )
    return {"minconn": minimum, "maxconn": maximum}


# Retain the historical name for compatibility with external imports.
# The database helper reads fresh settings per connection so deployment
# tooling and tests can override the process environment safely.
POSTGRES_CONFIG = get_postgres_config()


__all__ = [
    "POSTGRES_CONFIG",
    "get_postgres_config",
    "get_postgres_pool_config",
]
