"""Deterministic feedback save, symmetric priority adjustment, and growth archive."""

from __future__ import annotations

import copy
import re
from typing import Any

_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_IDENTITY_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")

ERR_MISSING_SESSION_ID = "missing_session_id"
ERR_MISSING_USER_ID = "missing_user_id"
ERR_INVALID_SATISFACTION = "invalid_satisfaction"
ERR_INVALID_RATING = "invalid_rating"
ERR_PRIVACY_VIOLATION = "privacy_violation"

FLAG_LOW_SATISFACTION_RECORDED = "low_satisfaction_recorded"
FLAG_FIRST_GROWTH_SNAPSHOT = "first_growth_snapshot"
FLAG_COMPETITIVENESS_UNAVAILABLE = "competitiveness_unavailable"

TREND_IMPROVING = "improving"
TREND_STABLE = "stable"
TREND_DECLINING = "declining"
TRENDS = (TREND_IMPROVING, TREND_STABLE, TREND_DECLINING)

PRIORITY_STEP = 1
PRIORITY_FLOOR = 1
LOW_RATING_THRESHOLD = 2
NEUTRAL_RATING = 3
HIGH_RATING_THRESHOLD = 4
LOW_SATISFACTION_THRESHOLD = 2

REASON_RAISE_PRIORITY = "训练反馈低，需优先补齐"
REASON_LOWER_PRIORITY = "训练反馈良好，紧迫度下调"


def _has_private_info(text: str) -> bool:
    return bool(
        _EMAIL_PATTERN.search(text)
        or _PHONE_PATTERN.search(text)
        or _IDENTITY_PATTERN.search(text)
    )


def _error(code: str, detail: str) -> dict[str, Any]:
    return {"error": f"{code}:{detail}"}


class FeedbackService:
    """Save feedback and deterministically adjust priorities and growth archive."""

    def __init__(self) -> None:
        self._feedbacks: dict[str, dict[str, Any]] = {}
        self._growth: dict[str, dict[str, Any]] = {}

    def save_feedback(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        satisfaction: int | None = None,
        path_rating: int | None = None,
        training_rating: int | None = None,
        resource_rating: int | None = None,
        comments: str | None = None,
        skill_gaps: list[dict[str, Any]] | None = None,
        abilities: list[dict[str, Any]] | None = None,
        completed_trainings: int = 0,
        completed_phases: int = 0,
        training_target_abilities: list[str] | None = None,
        overall_score: float | None = None,
    ) -> dict[str, Any]:
        validation = self._validate(
            session_id, user_id, satisfaction, path_rating, training_rating,
            resource_rating, comments,
        )
        if validation is not None:
            return validation

        self._feedbacks[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "satisfaction": satisfaction,
            "path_rating": path_rating,
            "training_rating": training_rating,
            "resource_rating": resource_rating,
            "comments": comments,
            "completed_trainings": completed_trainings,
            "completed_phases": completed_phases,
            "overall_score": overall_score,
            "skill_gaps": copy.deepcopy(skill_gaps) if skill_gaps else None,
            "abilities": copy.deepcopy(abilities) if abilities else None,
            "training_target_abilities": (
                list(training_target_abilities) if training_target_abilities else None
            ),
        }

        snapshot, growth_flags = self._update_growth(
            user_id, overall_score, completed_trainings, completed_phases
        )
        updated_priorities = self._adjust_priorities(
            skill_gaps, training_target_abilities, training_rating, satisfaction
        )

        flags = list(growth_flags)
        if satisfaction <= LOW_SATISFACTION_THRESHOLD:
            flags.append(FLAG_LOW_SATISFACTION_RECORDED)

        return {
            "feedback_saved": True,
            "growth_archive_updated": True,
            "updated_priorities": updated_priorities,
            "growth_snapshot": snapshot,
            "data_quality_flags": flags,
        }

    def get_feedback(self, session_id: str) -> dict[str, Any] | None:
        record = self._feedbacks.get(session_id)
        return copy.deepcopy(record) if record else None

    def get_growth(self, user_id: str) -> dict[str, Any] | None:
        snapshot = self._growth.get(user_id)
        return dict(snapshot) if snapshot else None

    @staticmethod
    def _validate(
        session_id: Any,
        user_id: Any,
        satisfaction: Any,
        path_rating: Any,
        training_rating: Any,
        resource_rating: Any,
        comments: Any,
    ) -> dict[str, Any] | None:
        if not isinstance(session_id, str) or not session_id.strip():
            return _error(ERR_MISSING_SESSION_ID, "session_id must be a non-empty string")
        if not isinstance(user_id, str) or not user_id.strip():
            return _error(ERR_MISSING_USER_ID, "user_id must be a non-empty string")
        if isinstance(satisfaction, bool) or not isinstance(satisfaction, int) or not 1 <= satisfaction <= 5:
            return _error(ERR_INVALID_SATISFACTION, f"got {satisfaction!r}")
        for name, value in (
            ("path_rating", path_rating),
            ("training_rating", training_rating),
            ("resource_rating", resource_rating),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= 5
            ):
                return _error(ERR_INVALID_RATING, f"{name}={value!r}")
        if comments is not None and _has_private_info(str(comments)):
            return _error(ERR_PRIVACY_VIOLATION, "comments contains sensitive information")
        return None

    def _update_growth(
        self,
        user_id: str,
        overall_score: float | None,
        completed_trainings: int,
        completed_phases: int,
    ) -> tuple[dict[str, Any], list[str]]:
        flags: list[str] = []
        score = 0.0 if overall_score is None else round(float(overall_score), 2)
        if overall_score is None:
            flags.append(FLAG_COMPETITIVENESS_UNAVAILABLE)

        previous = self._growth.get(user_id)
        completed = completed_trainings + completed_phases
        if previous is None:
            trend = TREND_STABLE
            flags.append(FLAG_FIRST_GROWTH_SNAPSHOT)
        else:
            prev_completed = previous["completed_trainings"] + previous["completed_phases"]
            improved = score > previous["competitiveness_score"] or completed > prev_completed
            declined = score < previous["competitiveness_score"] or completed < prev_completed
            if improved and not declined:
                trend = TREND_IMPROVING
            elif declined and not improved:
                trend = TREND_DECLINING
            else:
                trend = TREND_STABLE

        snapshot = {
            "competitiveness_score": score,
            "completed_trainings": completed_trainings,
            "completed_phases": completed_phases,
            "growth_trend": trend,
        }
        self._growth[user_id] = snapshot
        return snapshot, flags

    @staticmethod
    def _adjust_priorities(
        skill_gaps: list[dict[str, Any]] | None,
        training_target_abilities: list[str] | None,
        training_rating: int | None,
        satisfaction: int,
    ) -> list[dict[str, Any]]:
        if not skill_gaps or not training_target_abilities:
            return []
        if satisfaction <= LOW_SATISFACTION_THRESHOLD:
            return []
        if training_rating is None or training_rating == NEUTRAL_RATING:
            return []

        targets = set(training_target_abilities)
        gap_count = len(skill_gaps)
        updates: list[dict[str, Any]] = []
        for item in skill_gaps:
            if not isinstance(item, dict):
                continue
            tag = item.get("dimension")
            priority = item.get("priority")
            if not isinstance(tag, str) or not tag or tag not in targets:
                continue
            if isinstance(priority, bool) or not isinstance(priority, int):
                continue
            if training_rating <= LOW_RATING_THRESHOLD:
                new_priority = max(PRIORITY_FLOOR, priority - PRIORITY_STEP)
                updates.append({
                    "tag": tag,
                    "old_priority": priority,
                    "new_priority": new_priority,
                    "reason": REASON_RAISE_PRIORITY,
                })
            else:
                new_priority = min(gap_count, priority + PRIORITY_STEP)
                updates.append({
                    "tag": tag,
                    "old_priority": priority,
                    "new_priority": new_priority,
                    "reason": REASON_LOWER_PRIORITY,
                })
        return updates


__all__ = [
    "FLAG_COMPETITIVENESS_UNAVAILABLE",
    "FLAG_FIRST_GROWTH_SNAPSHOT",
    "FLAG_LOW_SATISFACTION_RECORDED",
    "FeedbackService",
    "TREND_DECLINING",
    "TREND_IMPROVING",
    "TREND_STABLE",
    "TRENDS",
]