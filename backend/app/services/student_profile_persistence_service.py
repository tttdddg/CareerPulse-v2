"""Deterministic mapping and persistence for PostgreSQL student profiles."""

from __future__ import annotations

from collections.abc import Iterable
from math import isclose

from pydantic import ValidationError

from ..repositories.student_profile_repository import StudentProfileRepository
from ..schemas.ability_dimension import ABILITY_DIMENSIONS, AbilityDimension
from ..schemas.career_profile_schema import (
    AbilityDimensionProfile,
    EvidenceSource,
    StudentBasicInfo,
    StudentProfile,
)
from ..schemas.student_persistence_schema import (
    StoredStudentAbility,
    StoredStudentBasicInfo,
    StudentProfilePersistenceResult,
    StudentProfileRecord,
    StudentProfileWrite,
)
from .profile_service import ProfileService, _TAG_DIMENSIONS


class StudentProfilePersistenceError(RuntimeError):
    """Safe domain error that does not contain names or ability evidence."""


class StudentProfileNotFoundError(StudentProfilePersistenceError):
    """No student profile exists for the requested database identifier."""


class StudentProfileMappingError(StudentProfilePersistenceError):
    """A flat or unified profile cannot be mapped without inventing data."""


class StudentProfileScoreMismatchError(StudentProfilePersistenceError):
    """The supplied score is not the deterministic ProfileService result."""


class StudentProfilePersistenceService:
    """Map profiles in both directions and delegate fixed SQL to Repository."""

    def __init__(
        self,
        repository: StudentProfileRepository | None = None,
    ) -> None:
        self.repository = repository or StudentProfileRepository()

    def create_profile(
        self,
        profile: StudentProfile,
        *,
        name: str,
    ) -> StudentProfilePersistenceResult:
        write = self._to_write(profile, name=name)
        record = self.repository.create(write)
        return self._to_result(record, user_id=profile.user_id)

    def save_profile(
        self,
        profile: StudentProfile,
        *,
        student_id: int | None = None,
        name: str | None = None,
    ) -> StudentProfilePersistenceResult:
        """Create or update one validated profile without exposing identity to Agents."""

        display_name = (name or "").strip() or "匿名学生"
        if student_id is None:
            return self.create_profile(profile, name=display_name)
        return self.update_profile(student_id, profile, name=display_name)

    @staticmethod
    def can_persist(profile: StudentProfile) -> bool:
        """Return whether the unified profile satisfies the frozen PG16 minimum.

        ProfileAgent intentionally accepts partial evidence so a conversation can
        ask follow-up questions.  The business table is stricter: education,
        major, target job and at least three evidence-backed abilities are
        required.  Partial profiles therefore remain valid session snapshots
        instead of turning a successful Agent step into a database failure.
        """

        basic = profile.basic_info
        return bool(
            basic.education_level
            and basic.major
            and basic.target_job
            and len(profile.ability_tags) >= 3
        )

    def get_profile(
        self,
        student_id: int,
        *,
        user_id: str,
    ) -> StudentProfilePersistenceResult:
        record = self.repository.get_by_id(student_id)
        if record is None:
            raise StudentProfileNotFoundError("student profile not found")
        return self._to_result(record, user_id=user_id)

    def update_profile(
        self,
        student_id: int,
        profile: StudentProfile,
        *,
        name: str,
    ) -> StudentProfilePersistenceResult:
        write = self._to_write(profile, name=name)
        record = self.repository.update_by_id(student_id, write)
        if record is None:
            raise StudentProfileNotFoundError("student profile not found")
        return self._to_result(record, user_id=profile.user_id)

    @classmethod
    def _to_write(cls, profile: StudentProfile, *, name: str) -> StudentProfileWrite:
        cls._validate_deterministic_score(profile)
        try:
            basic_info = StoredStudentBasicInfo(
                education_level=profile.basic_info.education_level,
                major=profile.basic_info.major,
                graduation_year=profile.basic_info.graduation_year,
                target_job=profile.basic_info.target_job,
                target_industry=profile.basic_info.target_industry,
                years_of_experience=profile.basic_info.years_of_experience,
            )
            abilities = cls._flatten_abilities(profile)
            return StudentProfileWrite(
                name=name,
                basic_info=basic_info,
                abilities=abilities,
                competitiveness_score=profile.career_competitiveness_score,
                completeness=profile.profile_completeness,
                missing_fields=profile.missing_fields,
            )
        except (ValidationError, TypeError, ValueError):
            raise StudentProfileMappingError(
                "student profile cannot be persisted"
            ) from None

    @staticmethod
    def _validate_deterministic_score(profile: StudentProfile) -> None:
        expected = ProfileService.calculate_competitiveness(
            profile.ability_dimensions,
            profile.profile_completeness,
        )
        if not isclose(
            profile.career_competitiveness_score,
            expected,
            rel_tol=0.0,
            abs_tol=1e-6,
        ):
            raise StudentProfileScoreMismatchError(
                "student profile score is not the deterministic service result"
            )

    @classmethod
    def _flatten_abilities(
        cls,
        profile: StudentProfile,
    ) -> list[StoredStudentAbility]:
        if len(profile.ability_tags) != len(set(profile.ability_tags)):
            raise StudentProfileMappingError(
                "student profile ability tags are inconsistent"
            )
        occurrences: dict[str, list[AbilityDimensionProfile]] = {}
        for dimension in profile.ability_dimensions:
            for tag in dimension.tags:
                occurrences.setdefault(tag, []).append(dimension)

        if set(profile.ability_tags) != set(occurrences):
            raise StudentProfileMappingError(
                "student profile ability tags are inconsistent"
            )

        result: list[StoredStudentAbility] = []
        for tag in sorted(occurrences):
            canonical = _TAG_DIMENSIONS.get(tag)
            if canonical is None:
                raise StudentProfileMappingError(
                    "student profile contains an unmapped ability"
                )
            source = next(
                (
                    item
                    for item in occurrences[tag]
                    if item.dimension == canonical
                ),
                None,
            )
            if source is None or not source.evidence:
                raise StudentProfileMappingError(
                    "student profile ability lacks canonical evidence"
                )
            try:
                result.append(
                    StoredStudentAbility(
                        tag=tag,
                        level=source.level,
                        confidence=source.confidence,
                        evidence=source.evidence[0],
                    )
                )
            except ValidationError:
                raise StudentProfileMappingError(
                    "student profile ability cannot be persisted"
                ) from None
        return result

    @classmethod
    def _to_result(
        cls,
        record: StudentProfileRecord,
        *,
        user_id: str,
    ) -> StudentProfilePersistenceResult:
        try:
            dimensions = cls._group_abilities(record.abilities)
            ability_tags = sorted(item.tag for item in record.abilities)
            unified = StudentProfile(
                user_id=user_id,
                basic_info=StudentBasicInfo(
                    name=None,
                    education_level=record.basic_info.education_level,
                    major=record.basic_info.major,
                    graduation_year=record.basic_info.graduation_year,
                    city=None,
                    target_job=record.basic_info.target_job,
                    target_industry=record.basic_info.target_industry,
                    years_of_experience=record.basic_info.years_of_experience,
                ),
                ability_dimensions=dimensions,
                ability_tags=ability_tags,
                profile_completeness=record.completeness,
                career_competitiveness_score=record.competitiveness_score,
                missing_fields=record.missing_fields,
                follow_up_questions=ProfileService._follow_up_questions(
                    record.missing_fields
                ),
                summary=(
                    f"历史画像包含{len(dimensions)}个能力维度、"
                    f"{len(ability_tags)}个能力标签，"
                    f"仍有{len(record.missing_fields)}项信息待补充。"
                ),
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
            return StudentProfilePersistenceResult(
                student_id=record.student_id,
                name=record.name,
                profile=unified,
            )
        except (ValidationError, TypeError, ValueError):
            raise StudentProfileMappingError(
                "stored student profile cannot be mapped"
            ) from None

    @staticmethod
    def _group_abilities(
        abilities: Iterable[StoredStudentAbility],
    ) -> list[AbilityDimensionProfile]:
        grouped: dict[AbilityDimension, list[StoredStudentAbility]] = {}
        for ability in abilities:
            dimension = _TAG_DIMENSIONS.get(ability.tag)
            if dimension is None:
                raise StudentProfileMappingError(
                    "stored student profile contains an unmapped ability"
                )
            grouped.setdefault(dimension, []).append(ability)

        result: list[AbilityDimensionProfile] = []
        for dimension in ABILITY_DIMENSIONS:
            items = grouped.get(dimension)
            if not items:
                continue
            strongest = max(
                items,
                key=lambda item: (item.level, item.confidence, item.tag),
            )
            evidence = list(dict.fromkeys(item.evidence for item in items))
            result.append(
                AbilityDimensionProfile(
                    dimension=dimension,
                    tags=sorted(item.tag for item in items),
                    level=strongest.level,
                    confidence=strongest.confidence,
                    evidence=evidence,
                    evidence_source=EvidenceSource.HISTORY,
                )
            )
        return result


__all__ = [
    "StudentProfileMappingError",
    "StudentProfileNotFoundError",
    "StudentProfilePersistenceError",
    "StudentProfilePersistenceService",
    "StudentProfileScoreMismatchError",
]
