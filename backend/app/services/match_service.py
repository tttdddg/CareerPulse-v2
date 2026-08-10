"""Deterministic ability matching for A02 stage 2.

This module deliberately contains no LLM integration or career-path generation.
Both inputs must already use the normalized ability tags produced by stage 2.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .ability_normalization import AbilityTagNormalizer


_ABILITY_TAGS_FILE = Path(__file__).resolve().parents[1] / "data" / "ability_tags.json"
_ALGORITHM_VERSION = "deterministic-v1"
_WEIGHT_TOLERANCE = 1e-6


class MatchService:
    """Calculate the frozen MatchResult schema using deterministic arithmetic."""

    def __init__(self, ability_tags_file: Path | str = _ABILITY_TAGS_FILE) -> None:
        self._abilities = self._load_ability_tags(Path(ability_tags_file))
        self._normalizer = AbilityTagNormalizer(canonical_tags=self._abilities)

    def calculate(
        self,
        student_profile: Mapping[str, Any] | Any,
        job_profile: Mapping[str, Any] | Any,
    ) -> dict[str, Any]:
        """Return a deterministic MatchResult for normalized profile inputs."""

        student = self._as_mapping(student_profile, "student_profile")
        job = self._as_mapping(job_profile, "job_profile")
        student_levels = self._student_levels(student.get("abilities", []))
        requirements = self._requirements(job.get("required_abilities", []))

        overall_score = 0.0
        dimensions: list[dict[str, Any]] = []
        ranked_gaps: list[tuple[float, str, dict[str, Any]]] = []
        gap_analysis: list[dict[str, str]] = []
        strengths: list[str] = []

        for requirement in requirements:
            tag = requirement["tag"]
            current = student_levels.get(tag, 0)
            required = requirement["required_level"]
            weight = requirement["weight"]
            ratio = min(current / required, 1.0)
            student_score = round(ratio * 100.0, 2)
            gap = max(required - current, 0)

            overall_score += weight * ratio * 100.0
            dimensions.append(
                {
                    "name": tag,
                    "student_score": student_score,
                    "job_required": 100.0,
                    "gap": round(student_score - 100.0, 2),
                    "weight": weight,
                }
            )

            status = "adequate"
            if gap:
                status = "missing" if current == 0 else "insufficient"
                priority_score = gap * weight / self._abilities[tag]
                ranked_gaps.append(
                    (
                        priority_score,
                        tag,
                        {
                            "tag": tag,
                            "current_level": current,
                            "required_level": required,
                            "gap": gap,
                            "priority": 0,
                        },
                    )
                )
            else:
                strengths.append(tag)
            gap_analysis.append({"item": tag, "status": status, "suggestion": ""})

        ranked_gaps.sort(key=lambda entry: (-entry[0], entry[1]))
        ability_gaps: list[dict[str, Any]] = []
        for rank, (_, _, item) in enumerate(ranked_gaps, start=1):
            item["priority"] = rank
            ability_gaps.append(item)

        return {
            "overall_score": round(overall_score, 2),
            "dimensions": dimensions,
            "ability_gaps": ability_gaps,
            "gap_analysis": gap_analysis,
            "strengths": strengths,
            "matching_algorithm_version": _ALGORITHM_VERSION,
        }

    @staticmethod
    def _as_mapping(value: Mapping[str, Any] | Any, name: str) -> Mapping[str, Any]:
        if isinstance(value, Mapping):
            return value
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            if isinstance(dumped, Mapping):
                return dumped
        raise TypeError(f"{name} must be a mapping or Pydantic model")

    @staticmethod
    def _load_ability_tags(path: Path) -> dict[str, float]:
        with path.open(encoding="utf-8") as tag_file:
            records = json.load(tag_file)
        abilities: dict[str, float] = {}
        for record in records:
            if record.get("deprecated", False):
                continue
            tag = record.get("tag")
            difficulty = record.get("difficulty")
            if not isinstance(tag, str) or not tag.strip() or tag in abilities:
                raise ValueError("ability tag data contains an invalid or duplicate tag")
            if not MatchService._is_number(difficulty) or not math.isfinite(difficulty):
                raise ValueError(f"difficulty for ability tag {tag!r} must be finite")
            if not 1.0 <= float(difficulty) <= 3.0:
                raise ValueError(f"difficulty for ability tag {tag!r} must be between 1.0 and 3.0")
            abilities[tag] = float(difficulty)
        return abilities

    def _student_levels(self, abilities: Any) -> dict[str, int]:
        items = self._list_of_mappings(abilities, "student abilities")
        levels: dict[str, int] = {}
        for item in items:
            tag = self._tag(item.get("tag"), "student ability")
            if tag in levels:
                raise ValueError(f"student abilities contain duplicate tag: {tag}")
            levels[tag] = self._level(item.get("level"), f"level for {tag}")
        return levels

    def _requirements(self, abilities: Any) -> list[dict[str, Any]]:
        items = self._list_of_mappings(abilities, "job required_abilities")
        requirements: list[dict[str, Any]] = []
        seen: set[str] = set()
        total_weight = 0.0
        for item in items:
            tag = self._tag(item.get("tag"), "job requirement")
            if tag in seen:
                raise ValueError(f"job requirements contain duplicate tag: {tag}")
            seen.add(tag)
            required_level = self._level(
                item.get("required_level"), f"required_level for {tag}"
            )
            weight = item.get("weight")
            if not self._is_number(weight) or not math.isfinite(weight):
                raise ValueError(f"weight for {tag} must be a finite number")
            weight = float(weight)
            if not 0.0 <= weight <= 1.0:
                raise ValueError(f"weight for {tag} must be between 0.0 and 1.0")
            total_weight += weight
            requirements.append(
                {"tag": tag, "required_level": required_level, "weight": weight}
            )
        if requirements and not math.isclose(
            total_weight, 1.0, rel_tol=0.0, abs_tol=_WEIGHT_TOLERANCE
        ):
            raise ValueError("job requirement weights must sum to 1.0")
        return requirements

    def _tag(self, value: Any, location: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{location} tag must be a non-empty string")
        try:
            return self._normalizer.normalize_or_raise(value)
        except ValueError as error:
            raise ValueError(
                f"{location} tag {value!r} cannot be mapped; "
                "use a normalized active ability tag"
            ) from error

    @staticmethod
    def _level(value: Any, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise ValueError(f"{name} must be an integer between 1 and 5")
        return value

    @staticmethod
    def _list_of_mappings(value: Any, name: str) -> list[Mapping[str, Any]]:
        if not isinstance(value, list):
            raise TypeError(f"{name} must be a list")
        if not all(isinstance(item, Mapping) for item in value):
            raise TypeError(f"{name} must contain only mappings")
        return value

    @staticmethod
    def _is_number(value: Any) -> bool:
        return not isinstance(value, bool) and isinstance(value, (int, float))


__all__ = ["MatchService"]
