"""Deterministic learning resource recommendation service."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .ability_normalization import AbilityTagNormalizer

_RESOURCES_FILE = Path(__file__).resolve().parents[1] / "data" / "resources.json"

RESOURCE_LIMIT = 10

FLAG_NO_RESOURCE_FOR_TAG = "no_resource_for_tag"
FLAG_UNKNOWN_TAG = "unknown_tag"
FLAG_JOB_RESOURCES_UNAVAILABLE = "job_resources_unavailable"

_OUTPUT_FIELD_NAMES = ("title", "type", "url", "target_ability", "description")


class ResourceService:
    """Recommend learning resources against ordered ability gaps."""

    def __init__(
        self,
        resources_file: Path | str | None = None,
        resources: list[dict[str, Any]] | None = None,
    ) -> None:
        if resources is not None:
            self._resources = resources
        else:
            path = Path(resources_file) if resources_file else _RESOURCES_FILE
            with path.open(encoding="utf-8") as handle:
                self._resources = json.load(handle)
        if not all(isinstance(item, Mapping) for item in self._resources):
            raise TypeError("resources must be a list of mappings")
        self._normalizer = AbilityTagNormalizer()
        self._by_tag: dict[str, list[dict[str, Any]]] = {}
        for item in self._resources:
            normalized = self._normalizer.normalize(item.get("target_ability"))
            tag = normalized["standard_tag"] or ""
            if not tag:
                continue
            self._by_tag.setdefault(tag, []).append(item)
        for group in self._by_tag.values():
            group.sort(key=lambda item: item.get("resource_id", ""))
        self._all = sorted(self._resources, key=lambda item: item.get("resource_id", ""))

    def recommend_resources(
        self,
        ability_gaps: list[str],
        target_job: str | None = None,
    ) -> dict[str, Any]:
        """Return ordered learning resources, flags, and certificate suggestions."""
        gaps = list(ability_gaps or [])
        flags: list[str] = []
        ordered: list[dict[str, Any]] = []

        if not gaps:
            ordered = [self._to_output(item) for item in self._all]
        else:
            for gap in gaps:
                if not isinstance(gap, str):
                    flags.append(f"{FLAG_UNKNOWN_TAG}:{gap}")
                    continue
                normalized = self._normalizer.normalize(gap)
                if not normalized["mapped"]:
                    flags.append(f"{FLAG_UNKNOWN_TAG}:{gap}")
                    continue
                matched = self._by_tag.get(normalized["standard_tag"], [])
                if not matched:
                    flags.append(f"{FLAG_NO_RESOURCE_FOR_TAG}:{gap}")
                    continue
                ordered.extend(self._to_output(item) for item in matched)

        flags.append(FLAG_JOB_RESOURCES_UNAVAILABLE)

        certificates = [
            item["target_ability"] for item in ordered if item["type"] == "certificate"
        ]
        return {
            "learning_resources": ordered[:RESOURCE_LIMIT],
            "job_resources": [],
            "certificate_suggestions": certificates,
            "data_quality_flags": flags,
        }

    @staticmethod
    def _to_output(item: Mapping[str, Any]) -> dict[str, Any]:
        return {name: item.get(name) for name in _OUTPUT_FIELD_NAMES}


__all__ = [
    "FLAG_JOB_RESOURCES_UNAVAILABLE",
    "FLAG_NO_RESOURCE_FOR_TAG",
    "FLAG_UNKNOWN_TAG",
    "RESOURCE_LIMIT",
    "ResourceService",
]