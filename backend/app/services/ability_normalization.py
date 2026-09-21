"""Deterministic normalization of stage-2 ability tags."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any


_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_ABILITY_TAGS_FILE = _DATA_DIR / "ability_tags.json"
_ALIASES_FILE = _DATA_DIR / "ability_tag_aliases.json"
_WHITESPACE = re.compile(r"\s+")


class AbilityTagNormalizer:
    """Map explicit aliases to stable canonical tags without semantic guessing."""

    def __init__(
        self,
        ability_tags_file: Path | str = _ABILITY_TAGS_FILE,
        aliases_file: Path | str = _ALIASES_FILE,
        *,
        canonical_tags: Iterable[str] | None = None,
    ) -> None:
        self._canonical_tags = (
            set(canonical_tags)
            if canonical_tags is not None
            else self._load_canonical_tags(Path(ability_tags_file))
        )
        self._canonical_lookup = self._build_canonical_lookup(self._canonical_tags)
        self._aliases = self._load_aliases(Path(aliases_file))

    def normalize(self, raw_tag: Any) -> dict[str, Any]:
        """Return a fixed result; unknown inputs are preserved but never guessed."""

        if not isinstance(raw_tag, str) or not raw_tag.strip():
            return {
                "original_tag": raw_tag,
                "standard_tag": None,
                "mapped": False,
                "rule_basis": "无效输入：能力标签必须是非空字符串",
            }

        normalized = self._key(raw_tag)
        canonical = self._canonical_lookup.get(normalized)
        if canonical is not None:
            basis = (
                "标准标签精确匹配"
                if raw_tag == canonical
                else "标准名称的Unicode、空白或大小写归一化"
            )
            return self._result(raw_tag, canonical, basis)

        alias = self._aliases.get(normalized)
        if alias is not None:
            return self._result(raw_tag, alias["standard_tag"], alias["rule_basis"])

        return {
            "original_tag": raw_tag,
            "standard_tag": None,
            "mapped": False,
            "rule_basis": "未命中标准名称或显式别名；保留原始标签并交由人工维护，不做语义猜测",
        }

    def normalize_or_raise(self, raw_tag: Any) -> str:
        result = self.normalize(raw_tag)
        if not result["mapped"]:
            raise ValueError(
                f"ability tag {raw_tag!r} cannot be mapped deterministically: "
                f"{result['rule_basis']}"
            )
        return result["standard_tag"]

    def explicit_aliases(self) -> dict[str, str]:
        """Return the authoritative alias-to-standard mapping as a safe copy."""

        return {
            item["alias"]: item["standard_tag"]
            for item in self._aliases.values()
        }

    def aliases_for(self, standard_tag: str) -> tuple[str, ...]:
        """Return every explicit alias registered for one canonical tag."""

        return tuple(
            sorted(
                item["alias"]
                for item in self._aliases.values()
                if item["standard_tag"] == standard_tag
            )
        )

    @staticmethod
    def _result(original_tag: str, standard_tag: str, basis: str) -> dict[str, Any]:
        return {
            "original_tag": original_tag,
            "standard_tag": standard_tag,
            "mapped": True,
            "rule_basis": basis,
        }

    @staticmethod
    def _key(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).strip()
        return _WHITESPACE.sub(" ", normalized).casefold()

    @staticmethod
    def _load_canonical_tags(path: Path) -> set[str]:
        with path.open(encoding="utf-8") as tag_file:
            records = json.load(tag_file)
        tags = {
            record["tag"]
            for record in records
            if not record.get("deprecated", False)
        }
        if not tags:
            raise ValueError("ability tag dictionary must contain active tags")
        return tags

    def _build_canonical_lookup(self, tags: set[str]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for tag in tags:
            key = self._key(tag)
            if key in lookup and lookup[key] != tag:
                raise ValueError("canonical ability tags collide after normalization")
            lookup[key] = tag
        return lookup

    def _load_aliases(self, path: Path) -> dict[str, dict[str, str]]:
        with path.open(encoding="utf-8") as alias_file:
            records = json.load(alias_file)
        aliases: dict[str, dict[str, str]] = {}
        for record in records:
            alias = record.get("alias")
            standard_tag = record.get("standard_tag")
            rule_basis = record.get("rule_basis")
            if not all(isinstance(value, str) and value.strip() for value in (alias, standard_tag, rule_basis)):
                raise ValueError("ability alias records require non-empty alias, standard_tag, and rule_basis")
            if standard_tag not in self._canonical_tags:
                raise ValueError(f"alias {alias!r} targets unknown standard tag {standard_tag!r}")
            key = self._key(alias)
            canonical = self._canonical_lookup.get(key)
            if canonical is not None and canonical != standard_tag:
                raise ValueError(f"alias {alias!r} conflicts with canonical tag {canonical!r}")
            existing = aliases.get(key)
            if existing is not None and existing["standard_tag"] != standard_tag:
                raise ValueError(f"alias {alias!r} maps to multiple standard tags")
            aliases[key] = {
                "alias": alias,
                "standard_tag": standard_tag,
                "rule_basis": rule_basis,
            }
        return aliases


__all__ = ["AbilityTagNormalizer"]
