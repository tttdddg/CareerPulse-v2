"""Deterministic training task generation and scoring service."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .ability_normalization import AbilityTagNormalizer

_TRAINING_TASKS_FILE = Path(__file__).resolve().parents[1] / "data" / "training_tasks.json"

TRAINING_TYPES = ("remote_collaboration", "ai_office_task", "cross_role_communication")

COVERAGE_LEVELS = ("fully", "mostly", "partial", "barely", "missing")
COVERAGE_SCORE = {
    "fully": 1.0,
    "mostly": 0.75,
    "partial": 0.5,
    "barely": 0.25,
    "missing": 0.0,
}

SHORT_ANSWER_LENGTH_THRESHOLD = 20
SHORT_ANSWER_SCORE_CAP = 80.0
MAX_REASON_LENGTH = 200
NEGATION_WINDOW_RADIUS = 3
NEGATION_WORDS = ("无", "未", "没", "不", "缺少")

ABILITY_UPDATE_UPGRADE_THRESHOLD = 80.0
ABILITY_UPDATE_DOWNGRADE_THRESHOLD = 40.0

ERR_UNSUPPORTED_TRAINING_TYPE = "unsupported_training_type"
ERR_NO_TRAINING_TASK_FOR_TYPE = "no_training_task_for_type"
ERR_TRAINING_NOT_FOUND = "training_not_found"
ERR_PRIVACY_VIOLATION = "privacy_violation"

_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_IDENTITY_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_NEGATION_PATTERN = re.compile("|".join(re.escape(word) for word in NEGATION_WORDS))
_NUMERIC_KEY_PATTERN = re.compile(r"(score|total|level)", re.IGNORECASE)


def _has_private_info(text: str) -> bool:
    return bool(
        _EMAIL_PATTERN.search(text)
        or _PHONE_PATTERN.search(text)
        or _IDENTITY_PATTERN.search(text)
    )


def _error(code: str, detail: str) -> dict[str, str]:
    return {"error": f"{code}:{detail}"}


class TrainingService:
    """Generate training tasks and synthesise deterministic scores."""

    def __init__(
        self,
        training_tasks_file: Path | str | None = None,
        tasks: list[dict[str, Any]] | None = None,
    ) -> None:
        if tasks is not None:
            self._tasks = tasks
        else:
            path = Path(training_tasks_file) if training_tasks_file else _TRAINING_TASKS_FILE
            with path.open(encoding="utf-8") as handle:
                self._tasks = json.load(handle)
        if not all(isinstance(task, Mapping) for task in self._tasks):
            raise TypeError("training tasks must be a list of mappings")
        self._tasks_by_id: dict[str, dict[str, Any]] = {
            task["training_id"]: task for task in self._tasks
        }
        self._tasks_by_type: dict[str, list[dict[str, Any]]] = {}
        for task in self._tasks:
            self._tasks_by_type.setdefault(task["type"], []).append(task)
        self._normalizer = AbilityTagNormalizer()

    def generate(
        self,
        training_type: str,
        ability_gaps: list[str] | None = None,
    ) -> dict[str, Any]:
        """Pick one deterministic training task for the requested type."""
        if training_type not in TRAINING_TYPES:
            return _error(ERR_UNSUPPORTED_TRAINING_TYPE, training_type)
        candidates = self._tasks_by_type.get(training_type, [])
        if not candidates:
            return _error(ERR_NO_TRAINING_TASK_FOR_TYPE, training_type)

        gaps = {
            item
            for item in (ability_gaps or [])
            if isinstance(item, str) and item.strip()
        }

        def overlap(task: dict[str, Any]) -> int:
            return len(gaps & {tag for tag in task.get("target_abilities", [])})

        best = min(candidates, key=lambda item: (-overlap(item), item["training_id"]))
        return {
            "mode": "generate",
            "training_id": best["training_id"],
            "type": best["type"],
            "title": best["title"],
            "scenario": best["scenario"],
            "task_description": best["task_description"],
            "evaluation_criteria": [dict(item) for item in best["evaluation_criteria"]],
            "target_abilities": list(best["target_abilities"]),
            "reference_answer": best["reference_answer"],
        }

    def score(
        self,
        training_id: str,
        user_answer: str,
        agent_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Score one answer deterministically via main or fallback synthesis."""
        task = self._tasks_by_id.get(training_id)
        if task is None:
            return _error(ERR_TRAINING_NOT_FOUND, training_id)
        answer_text = re.sub(r"\s+", "", user_answer or "")
        if _has_private_info(answer_text):
            return _error(ERR_PRIVACY_VIOLATION, "user_answer contains sensitive information")

        criteria = task["evaluation_criteria"]
        weights = [item["weight"] for item in criteria]
        validation = self._validate_signal(agent_analysis, criteria)
        flags: list[str] = []

        if validation is not None and validation["valid"]:
            dim_scores = self._synthesize_main(
                criteria, validation["coverage_by_dim"]
            )
            flags.extend(validation["flags"])
        else:
            if validation is not None:
                flags.extend(validation["problem_flags"])
            dim_scores = self._synthesize_fallback(criteria, answer_text)

        answer_empty = not answer_text
        self._apply_length_correction(dim_scores, answer_text, answer_empty)
        if answer_empty:
            flags.append("empty_answer")

        total = round(sum(w * s for w, s in zip(weights, dim_scores)), 2)
        return self._build_score_output(task, dim_scores, total, flags, answer_empty)

    def _validate_signal(
        self,
        agent_analysis: dict[str, Any] | None,
        criteria: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if agent_analysis is None:
            return None
        if not isinstance(agent_analysis, Mapping):
            return {"valid": False, "problem_flags": ["agent_analysis_rejected:not_object"]}
        if self._signal_has_numeric_fields(agent_analysis):
            return {
                "valid": False,
                "problem_flags": ["agent_analysis_rejected:numeric_field"],
            }

        dimensions = agent_analysis.get("dimensions")
        if not isinstance(dimensions, list):
            return {
                "valid": False,
                "problem_flags": ["agent_analysis_rejected:dimensions_not_list"],
            }

        criteria_dims = [item["dimension"] for item in criteria]
        coverage_by_dim: dict[str, str] = {}
        for item in dimensions:
            if not isinstance(item, Mapping):
                return {
                    "valid": False,
                    "problem_flags": ["agent_analysis_rejected:malformed_item"],
                }
            dim = item.get("dimension")
            coverage = item.get("coverage")
            reason = item.get("reason")
            if not isinstance(dim, str) or not dim.strip():
                return {
                    "valid": False,
                    "problem_flags": ["agent_analysis_rejected:invalid_dimension"],
                }
            if coverage not in COVERAGE_LEVELS:
                return {
                    "valid": False,
                    "problem_flags": [f"agent_analysis_rejected:invalid_coverage:{dim}"],
                }
            if not isinstance(reason, str) or not reason.strip():
                return {
                    "valid": False,
                    "problem_flags": [f"agent_analysis_rejected:empty_reason:{dim}"],
                }
            if len(reason) > MAX_REASON_LENGTH:
                return {
                    "valid": False,
                    "problem_flags": [f"agent_analysis_rejected:long_reason:{dim}"],
                }
            if _has_private_info(reason):
                return {
                    "valid": False,
                    "problem_flags": [f"agent_analysis_rejected:privacy_reason:{dim}"],
                }
            if dim not in criteria_dims:
                return {
                    "valid": False,
                    "problem_flags": [f"agent_analysis_rejected:unrelated_dimension:{dim}"],
                }
            coverage_by_dim[dim] = coverage

        missing_flags = [
            f"incomplete_analysis:{item['dimension']}"
            for item in criteria
            if item["dimension"] not in coverage_by_dim
        ]
        return {"valid": True, "coverage_by_dim": coverage_by_dim, "flags": missing_flags}

    @staticmethod
    def _synthesize_main(
        criteria: list[dict[str, Any]],
        coverage_by_dim: dict[str, str],
    ) -> list[float]:
        dim_scores: list[float] = []
        for item in criteria:
            coverage = coverage_by_dim.get(item["dimension"], "missing")
            dim_scores.append(round(COVERAGE_SCORE[coverage] * 100.0, 2))
        return dim_scores

    def _synthesize_fallback(
        self,
        criteria: list[dict[str, Any]],
        answer_text: str,
    ) -> list[float]:
        dim_scores: list[float] = []
        for item in criteria:
            windows = self._windows(item["dimension"])
            if not windows:
                dim_scores.append(0.0)
                continue
            hits = sum(1 for window in windows if self._window_hit(answer_text, window))
            dim_scores.append(round(hits / len(windows) * 100.0, 2))
        return dim_scores

    def _apply_length_correction(
        self,
        dim_scores: list[float],
        answer_text: str,
        answer_empty: bool,
    ) -> None:
        if answer_empty:
            for index, _ in enumerate(dim_scores):
                dim_scores[index] = 0.0
        elif len(answer_text) < SHORT_ANSWER_LENGTH_THRESHOLD:
            for index, score in enumerate(dim_scores):
                dim_scores[index] = min(score, SHORT_ANSWER_SCORE_CAP)

    @staticmethod
    def _windows(dimension: str) -> list[str]:
        raw = [dimension[index : index + 2] for index in range(len(dimension) - 1)]
        return list(dict.fromkeys(raw))

    def _window_hit(self, answer_text: str, window: str) -> bool:
        if not window:
            return False

        def is_negated(start: int) -> bool:
            preceding = answer_text[max(0, start - NEGATION_WINDOW_RADIUS) : start]
            return _NEGATION_PATTERN.search(preceding) is not None

        for match in re.finditer(re.escape(window), answer_text):
            if not is_negated(match.start()):
                return True
        return False

    @staticmethod
    def _signal_has_numeric_fields(value: Any) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            return _NUMERIC_KEY_PATTERN.search(value.casefold()) is not None
        if isinstance(value, Mapping):
            for key, item in value.items():
                if isinstance(key, str) and _NUMERIC_KEY_PATTERN.search(key.casefold()):
                    return True
                if TrainingService._signal_has_numeric_fields(item):
                    return True
            return False
        if isinstance(value, list):
            return any(TrainingService._signal_has_numeric_fields(item) for item in value)
        return False

    def _build_score_output(
        self,
        task: dict[str, Any],
        dim_scores: list[float],
        total: float,
        flags: list[str],
        answer_empty: bool,
    ) -> dict[str, Any]:
        criteria = task["evaluation_criteria"]
        dimension_scores = [
            {
                "dimension": item["dimension"],
                "score": score,
                "comment": _comment(item, score, answer_empty),
            }
            for item, score in zip(criteria, dim_scores)
        ]
        return {
            "mode": "score",
            "training_id": task["training_id"],
            "total_score": total,
            "dimension_scores": dimension_scores,
            "overall_comment": _overall_comment(total),
            "improvement_suggestions": _improvement_suggestions(
                dimension_scores, answer_empty
            ),
            "ability_updates": _ability_updates(task["target_abilities"], total),
            "data_quality_flags": flags,
        }


def _comment(item: dict[str, Any], score: float, answer_empty: bool) -> str:
    dim = item["dimension"]
    description = item["description"]
    if answer_empty:
        return f"{dim}：请补充回答该维度内容。"
    if score >= 100.0:
        return f"{dim}：已覆盖该维度要点，{description}"
    if score <= 0.0:
        return f"{dim}：未覆盖该维度要点，{description}"
    return f"{dim}：部分覆盖该维度要点，{description}"


def _overall_comment(total: float) -> str:
    if total >= ABILITY_UPDATE_UPGRADE_THRESHOLD:
        return "整体表现优秀，训练目标达成度高。"
    if total >= ABILITY_UPDATE_DOWNGRADE_THRESHOLD:
        return "整体表现中上，主要能力已达成，仍有细化空间。"
    return "整体覆盖不足，建议对照题目维度要点重新作答。"


def _improvement_suggestions(
    dimension_scores: list[dict[str, Any]], answer_empty: bool
) -> list[str]:
    if answer_empty:
        return ["请针对各评分维度补充作答要点。"]
    suggestions = []
    for item in dimension_scores:
        if item["score"] <= 0.0:
            suggestions.append(f"建议补充「{item['dimension']}」相关内容。")
        elif item["score"] < 100.0:
            suggestions.append(f"「{item['dimension']}」仍有提升空间。")
    return suggestions


def _ability_updates(target_abilities: list[str], total: float) -> list[dict[str, Any]]:
    if total >= ABILITY_UPDATE_UPGRADE_THRESHOLD:
        change = 1
    elif total >= ABILITY_UPDATE_DOWNGRADE_THRESHOLD:
        change = 0
    else:
        change = -1
    return [{"tag": tag, "level_change": change} for tag in target_abilities]


__all__ = [
    "ABILITY_UPDATE_DOWNGRADE_THRESHOLD",
    "ABILITY_UPDATE_UPGRADE_THRESHOLD",
    "COVERAGE_LEVELS",
    "COVERAGE_SCORE",
    "TRAINING_TYPES",
    "TrainingService",
]