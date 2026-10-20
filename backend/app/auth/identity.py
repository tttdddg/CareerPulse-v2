"""Canonical owner identifiers for isolated authentication channels."""

from __future__ import annotations

import hashlib
import re


WEB_OWNER_PREFIX = "web:"
EXTERNAL_OWNER_PREFIX = "external:"
_EXTERNAL_OWNER_PATTERN = re.compile(r"^external:[0-9a-f]{64}$")


def web_owner_id(user_id: str) -> str:
    """Return the owner stored for a verified CareerPulse Web account."""

    normalized = user_id.strip()
    if not normalized:
        raise ValueError("web user id must not be empty")
    return f"{WEB_OWNER_PREFIX}{normalized}"


def external_owner_id(subject_id: str) -> str:
    """Return an opaque owner for a trusted platform/MCP logical subject."""

    normalized = subject_id.strip()
    if not normalized:
        raise ValueError("external subject id must not be empty")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{EXTERNAL_OWNER_PREFIX}{digest}"


def ensure_external_owner_id(subject_id: str) -> str:
    """Canonicalize an internal value once without double hashing it."""

    normalized = subject_id.strip()
    if _EXTERNAL_OWNER_PATTERN.fullmatch(normalized):
        return normalized
    return external_owner_id(normalized)


def normalize_stored_owner(owner_id: str | None) -> str | None:
    """Upgrade pre-M2 raw owners while preserving canonical persisted owners."""

    if owner_id is None:
        return None
    normalized = owner_id.strip()
    if not normalized:
        return None
    if normalized.startswith((WEB_OWNER_PREFIX, EXTERNAL_OWNER_PREFIX)):
        return normalized
    return external_owner_id(normalized)


__all__ = [
    "EXTERNAL_OWNER_PREFIX",
    "WEB_OWNER_PREFIX",
    "ensure_external_owner_id",
    "external_owner_id",
    "normalize_stored_owner",
    "web_owner_id",
]
