"""Platform-friendly input normalization for the CareerPulse MCP adapter.

The public MCP signature accepts the simple scalar forms commonly produced by
AntBox tool calling.  These helpers convert those values before the existing
strict request models validate the internal business boundary.
"""

from __future__ import annotations

import json
import math
import re
from decimal import Decimal, InvalidOperation
from typing import TypeVar


EnumValueT = TypeVar("EnumValueT", bound=str)

_LIST_SEPARATOR = re.compile(r"[,，、\r\n]+")
_ENUM_KEY_SEPARATOR = re.compile(r"[\s_-]+")


def parse_optional_list(
    value: str | list[str] | None,
    *,
    field_name: str,
) -> list[str] | None:
    """Normalize a delimited string or native string list without rewriting text."""

    if value is None:
        return None
    if isinstance(value, str):
        stripped_value = value.strip()
        if stripped_value.startswith("["):
            try:
                decoded = json.loads(stripped_value)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{field_name} JSON array text is invalid"
                ) from exc
            if not isinstance(decoded, list):
                raise ValueError(
                    f"{field_name} JSON text must contain an array"
                )
            candidates = decoded
        else:
            candidates = _LIST_SEPARATOR.split(value)
    elif isinstance(value, list):
        candidates = value
    else:
        raise ValueError(
            f"{field_name} must be text or a list of text values"
        )

    normalized: list[str] = []
    for item in candidates:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} items must be text")
        stripped = item.strip()
        if stripped:
            normalized.append(stripped)
    return normalized


def parse_optional_int(
    value: str | int | None,
    *,
    field_name: str,
) -> int | None:
    """Parse an integer-compatible platform value without inventing a default."""

    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, int):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be an integer")
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if not parsed.is_finite() or parsed != parsed.to_integral_value():
        raise ValueError(f"{field_name} must be an integer")
    return int(parsed)


def parse_optional_float(
    value: str | int | float | None,
    *,
    field_name: str,
) -> float | None:
    """Parse a finite floating-point platform value without a silent fallback."""

    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite number")
    if not isinstance(value, (str, int, float)):
        raise ValueError(f"{field_name} must be a finite number")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{field_name} must be a finite number")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite number") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name} must be a finite number")
    return parsed


def normalize_enum_text(
    value: str | None,
    *,
    field_name: str,
    aliases: dict[str, EnumValueT],
    supported_message: str,
) -> EnumValueT | None:
    """Map only explicit aliases; unknown natural-language requests stay invalid."""

    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required; {supported_message}")
    normalized_aliases = {
        _enum_key(alias): canonical for alias, canonical in aliases.items()
    }
    canonical = normalized_aliases.get(_enum_key(value))
    if canonical is None:
        raise ValueError(f"{field_name} is unsupported; {supported_message}")
    return canonical


def _enum_key(value: str) -> str:
    return _ENUM_KEY_SEPARATOR.sub("", value.strip().casefold())


__all__ = [
    "normalize_enum_text",
    "parse_optional_float",
    "parse_optional_int",
    "parse_optional_list",
]
