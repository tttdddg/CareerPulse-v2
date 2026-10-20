"""End-user authentication primitives for the CareerPulse Web client."""

from .config import AuthSettings
from .identity import (
    ensure_external_owner_id,
    external_owner_id,
    normalize_stored_owner,
    web_owner_id,
)
from .repository import AuthRepository, AuthUserRecord
from .service import AuthService

__all__ = [
    "AuthRepository",
    "AuthService",
    "AuthSettings",
    "AuthUserRecord",
    "ensure_external_owner_id",
    "external_owner_id",
    "normalize_stored_owner",
    "web_owner_id",
]

