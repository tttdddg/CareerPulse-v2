"""Deterministic job matching over the stage-2 ability vocabulary.

The Service performs arithmetic and rule evaluation only.  It never calls an
LLM and never interprets an absent student ability as a measured level of zero.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..schemas.match_schema import MatchResult
from .ability_normalization import AbilityTagNormalizer
from .match_config import (
    CALCULATION_VERSION,
    CONFIDENCE_COMPONENT_WEIGHTS,
    CONFIDENCE_FLOOR,
    IMPORTANCE_ORDER,
    LEGACY_ALGORITHM_VERSION,
    MATCH_LEVEL_THRESHOLDS,
    SCORING_COVERAGE_FLOOR,
    WEIGHT_TOLERANCE,
)


_ABILITY_TAGS_FILE = Path(__file__).resolve().parents[1] / "data" / "ability_tags.json"


class MatchService:
    """Calculate a validated, deterministic match and ability-gap result."""

    def __init__(self, ability_tags_file: Path | str = _ABILITY_TAGS_FILE) -> None:
        self._abilities = self._load_ability_tags(Path(ability_tags_file))
        self._normalizer = AbilityTagNormalizer(
            canonical_tags={tag: item["difficulty"] for tag, item in self._abilities.items()}
        )

    def calculate(
        self,
        student_profile: Mapping[str, Any] | Any,
        job_profile: Mapping[str, Any] | Any,
    ) -> dict[str, Any]:
        """Return the strict MatchResult as a backwards-compatible dictionary."""

        student = self._as_mapping(student_profile, "student_profile")
        job = self._as_mapping(job_profile, "job_profile")
        student_abilities = self._student_abilities(student.get("abilities", []))
        requirements = self._requirements(job.get("required_abilities", []))

        weighted_score = 0.0
        known_positive_weight = 0.0
        known_required_weight = 0.0
        evidence_weighted_confidence = 0.0
        evidence_confidence_weight = 0.0
        dimension_matches: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        matched_skills: list[str] = []
        missing_skills: list[str] = []
        ranked_gaps: list[tuple[float, int, str, dict[str, Any]]] = []
        hard_constraints: list[dict[str, Any]] = []
        data_quality_flags: list[str] = []

        for requirement in requirements:
            tag = requirement["tag"]
            required = requirement["required_level"]
            weight = requirement["weight"]
            importance = requirement["importance"]
            job_evidence = requirement["evidence"]
            student_ability = student_abilities.get(tag)

            if student_ability is None:
                if weight > 0.0:
                    missing_skills.append(tag)
                    data_quality_flags.append(f"required_ability_not_provided:{tag}")
                dimension_matches.append(
                    {
                        "dimension": tag,
                        "student_level": None,
                        "required_level": required,
                        "gap": None,
                        "score": None,
                        "weight": weight,
                        "student_evidence": None,
                        "job_evidence": job_evidence,
                        "confidence": None,
                        "importance": importance,
                        "status": "unknown" if weight > 0.0 else "excluded",
                    }
                )
                if importance == "critical" and weight > 0.0:
                    hard_constraints.append(
                        self._hard_constraint(tag, required, None, "unknown")
                    )
                evidence.append(
                    {
                        "dimension": tag,
                        "student_evidence": None,
                        "job_evidence": job_evidence,
                        "confidence": None,
                    }
                )
                continue

            current = student_ability["level"]
            confidence = student_ability["confidence"]
            student_evidence = student_ability["evidence"]
            ratio = min(current / required, 1.0)
            dimension_score = round(ratio * 100.0, 2)
            gap = max(required - current, 0)
            weighted_score += weight * ratio * 100.0

            if weight > 0.0:
                known_positive_weight += weight
                known_required_weight += weight
                if confidence is not None:
                    evidence_weighted_confidence += weight * confidence
                    evidence_confidence_weight += weight
            status = "excluded" if weight == 0.0 else ("matched" if gap == 0 else "gap")
            if gap == 0 and weight > 0.0:
                matched_skills.append(tag)
            elif gap > 0 and weight > 0.0:
                priority_score = gap * weight / self._abilities[tag]["difficulty"]
                ranked_gaps.append(
                    (
                        priority_score,
                        IMPORTANCE_ORDER[importance],
                        tag,
                        {
                            "dimension": tag,
                            "student_level": current,
                            "required_level": required,
                            "gap": gap,
                            "score": dimension_score,
                            "weight": weight,
                            "priority": 0,
                            "importance": importance,
                            "difficulty": self._abilities[tag]["difficulty"],
                            "student_evidence": student_evidence,
                            "job_evidence": job_evidence,
                            "confidence": confidence,
                        },
                    )
                )

            if confidence is not None and confidence < CONFIDENCE_FLOOR:
                data_quality_flags.append(f"low_student_evidence_confidence:{tag}")
            dimension_matches.append(
                {
                    "dimension": tag,
                    "student_level": current,
                    "required_level": required,
                    "gap": gap,
                    "score": dimension_score,
                    "weight": weight,
                    "student_evidence": student_evidence,
                    "job_evidence": job_evidence,
                    "confidence": confidence,
                    "importance": importance,
                    "status": status,
                }
            )
            if importance == "critical":
                hard_constraints.append(
                    self._hard_constraint(
                        tag, required, current, "passed" if gap == 0 else "failed"
                    )
                )
            evidence.append(
                {
                    "dimension": tag,
                    "student_evidence": student_evidence,
                    "job_evidence": job_evidence,
                    "confidence": confidence,
                }
            )

        ranked_gaps.sort(key=lambda item: (-item[0], item[1], item[2]))
        skill_gaps: list[dict[str, Any]] = []
        for priority, (_, _, _, item) in enumerate(ranked_gaps, start=1):
            item["priority"] = priority
            skill_gaps.append(item)

        completeness = self._optional_probability(student.get("completeness"), "completeness")
        if completeness is None:
            data_quality_flags.append("profile_completeness_not_provided")
        elif completeness < 0.5:
            data_quality_flags.append("profile_completeness_below_0.5")
        missing_fields = student.get("missing_fields")
        if missing_fields is not None:
            if not isinstance(missing_fields, list) or not all(
                isinstance(item, str) and item.strip() for item in missing_fields
            ):
                raise TypeError("missing_fields must be a list of non-empty strings")
            if missing_fields:
                data_quality_flags.append("profile_declares_missing_fields")

        required_positive_weight = sum(item["weight"] for item in requirements if item["weight"] > 0)
        coverage = (
            known_required_weight / required_positive_weight
            if required_positive_weight > 0.0
            else None
        )
        evidence_quality = (
            evidence_weighted_confidence / evidence_confidence_weight
            if evidence_confidence_weight > 0.0
            else None
        )
        result_confidence = self._result_confidence(
            evidence_quality=evidence_quality,
            required_skill_coverage=coverage,
            profile_completeness=completeness,
        )
        overall_score = (
            round(weighted_score / known_positive_weight, 2)
            if known_positive_weight > 0.0
            else 0.0
        )
        match_level = (
            self._match_level(overall_score)
            if known_positive_weight > 0.0
            and coverage is not None
            and coverage >= SCORING_COVERAGE_FLOOR
            else "insufficient_data"
        )

        legacy = self._legacy_projection(
            dimension_matches, skill_gaps, requirements, self._abilities
        )
        result = MatchResult.model_validate(
            {
                "overall_score": overall_score,
                "match_level": match_level,
                "dimension_matches": dimension_matches,
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "skill_gaps": skill_gaps,
                "strengths": list(matched_skills),
                "hard_constraint_results": hard_constraints,
                "confidence": result_confidence,
                "evidence": evidence,
                "calculation_version": CALCULATION_VERSION,
                "data_quality_flags": data_quality_flags,
                **legacy,
            }
        )
        return result.model_dump()

    @staticmethod
    def _legacy_projection(
        dimensions: list[dict[str, Any]],
        skill_gaps: list[dict[str, Any]],
        requirements: list[dict[str, Any]],
        ability_metadata: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Retain D2 field names; level 0 is only an explicit legacy sentinel."""

        legacy_dimensions = []
        gap_analysis = []
        skill_gap_by_tag = {item["dimension"]: item for item in skill_gaps}
        requirement_by_tag = {item["tag"]: item for item in requirements}
        ranked_legacy_gaps: list[tuple[float, str, dict[str, Any]]] = []
        for dimension in dimensions:
            unknown = dimension["student_level"] is None
            score = 0.0 if unknown else dimension["score"]
            legacy_dimensions.append(
                {
                    "name": dimension["dimension"],
                    "student_score": score,
                    "job_required": 100.0,
                    "gap": round(score - 100.0, 2),
                    "weight": dimension["weight"],
                }
            )
            if unknown:
                required = requirement_by_tag[dimension["dimension"]]
                legacy_item = {
                    "tag": dimension["dimension"],
                    "current_level": 0,
                    "required_level": dimension["required_level"],
                    "gap": dimension["required_level"],
                    "priority": 0,
                }
                ranked_legacy_gaps.append(
                    (
                        legacy_item["gap"]
                        * required["weight"]
                        / ability_metadata[dimension["dimension"]]["difficulty"],
                        dimension["dimension"],
                        legacy_item,
                    )
                )
                gap_analysis.append(
                    {"item": dimension["dimension"], "status": "missing", "suggestion": ""}
                )
            elif dimension["dimension"] in skill_gap_by_tag:
                item = skill_gap_by_tag[dimension["dimension"]]
                legacy_item = {
                    "tag": item["dimension"],
                    "current_level": item["student_level"],
                    "required_level": item["required_level"],
                    "gap": item["gap"],
                    "priority": 0,
                }
                ranked_legacy_gaps.append(
                    (
                        item["gap"]
                        * item["weight"]
                        / ability_metadata[item["dimension"]]["difficulty"],
                        item["dimension"],
                        legacy_item,
                    )
                )
                gap_analysis.append(
                    {"item": dimension["dimension"], "status": "insufficient", "suggestion": ""}
                )
            else:
                gap_analysis.append(
                    {"item": dimension["dimension"], "status": "adequate", "suggestion": ""}
                )
        ranked_legacy_gaps.sort(key=lambda entry: (-entry[0], entry[1]))
        ability_gaps = []
        for priority, (_, _, item) in enumerate(ranked_legacy_gaps, start=1):
            item["priority"] = priority
            ability_gaps.append(item)
        return {
            "dimensions": legacy_dimensions,
            "ability_gaps": ability_gaps,
            "gap_analysis": gap_analysis,
            "matching_algorithm_version": LEGACY_ALGORITHM_VERSION,
        }

    @staticmethod
    def _hard_constraint(
        tag: str, required: int, current: int | None, status: str
    ) -> dict[str, Any]:
        if status == "unknown":
            reason = "学生画像未提供该关键能力，无法判定是否满足硬性条件"
            passed = None
        elif status == "passed":
            reason = "学生能力等级达到岗位关键能力要求"
            passed = True
        else:
            reason = "学生能力等级低于岗位关键能力要求"
            passed = False
        return {
            "constraint": tag,
            "required_level": required,
            "student_level": current,
            "status": status,
            "passed": passed,
            "reason": reason,
        }

    @staticmethod
    def _result_confidence(**components: float | None) -> float:
        numerator = 0.0
        denominator = 0.0
        for name, value in components.items():
            if value is None:
                continue
            weight = CONFIDENCE_COMPONENT_WEIGHTS[name]
            numerator += weight * value
            denominator += weight
        return round(numerator / denominator, 4) if denominator else 0.0

    @staticmethod
    def _match_level(score: float) -> str:
        return next(level for threshold, level in MATCH_LEVEL_THRESHOLDS if score >= threshold)

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
    def _load_ability_tags(path: Path) -> dict[str, dict[str, Any]]:
        with path.open(encoding="utf-8") as tag_file:
            records = json.load(tag_file)
        if not isinstance(records, list):
            raise TypeError("ability tag data must be a list")
        abilities: dict[str, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, Mapping) or record.get("deprecated", False):
                continue
            tag = record.get("tag")
            difficulty = record.get("difficulty")
            if not isinstance(tag, str) or not tag.strip() or tag in abilities:
                raise ValueError("ability tag data contains an invalid or duplicate tag")
            if not MatchService._is_number(difficulty) or not math.isfinite(difficulty):
                raise ValueError(f"difficulty for ability tag {tag!r} must be finite")
            if not 1.0 <= float(difficulty) <= 3.0:
                raise ValueError(
                    f"difficulty for ability tag {tag!r} must be between 1.0 and 3.0"
                )
            abilities[tag] = {
                "difficulty": float(difficulty),
                "category": record.get("category"),
            }
        return abilities

    def _student_abilities(self, abilities: Any) -> dict[str, dict[str, Any]]:
        items = self._list_of_mappings(abilities, "student abilities")
        normalized: dict[str, dict[str, Any]] = {}
        for item in items:
            tag = self._tag(item.get("tag"), "student ability")
            if tag in normalized:
                raise ValueError(f"student abilities contain duplicate tag: {tag}")
            confidence = self._optional_probability(
                item.get("confidence"), f"confidence for {tag}"
            )
            evidence = item.get("evidence")
            if evidence is not None and (
                not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 500
            ):
                raise ValueError(f"evidence for {tag} must be a non-empty string up to 500 chars")
            normalized[tag] = {
                "level": self._level(item.get("level"), f"level for {tag}"),
                "confidence": confidence,
                "evidence": evidence.strip() if isinstance(evidence, str) else None,
            }
        return normalized

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
            importance = item.get("importance", "important")
            if importance not in IMPORTANCE_ORDER:
                raise ValueError(
                    f"importance for {tag} must be critical, important, or nice_to_have"
                )
            evidence = item.get("evidence")
            if evidence is not None and (
                not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 1000
            ):
                raise ValueError(
                    f"job evidence for {tag} must be a non-empty string up to 1000 chars"
                )
            total_weight += weight
            requirements.append(
                {
                    "tag": tag,
                    "required_level": required_level,
                    "weight": weight,
                    "importance": importance,
                    "evidence": evidence.strip() if isinstance(evidence, str) else None,
                }
            )
        if requirements and not math.isclose(
            total_weight, 1.0, rel_tol=0.0, abs_tol=WEIGHT_TOLERANCE
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
    def _optional_probability(value: Any, name: str) -> float | None:
        if value is None:
            return None
        if not MatchService._is_number(value) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number between 0.0 and 1.0")
        probability = float(value)
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"{name} must be between 0.0 and 1.0")
        return probability

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
