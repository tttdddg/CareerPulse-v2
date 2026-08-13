"""Deterministic profile merging, evidence mapping, and scoring."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..schemas.ability_dimension import ABILITY_DIMENSIONS, AbilityDimension
from ..schemas.career_profile_schema import (
    AbilityDimensionProfile,
    EvidenceSource,
    StudentBasicInfo,
    StudentProfile,
)
from .ability_normalization import AbilityTagNormalizer


_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_TAGS_FILE = _DATA_DIR / "ability_tags.json"
_ALIASES_FILE = _DATA_DIR / "ability_tag_aliases.json"
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_IDENTITY = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_SENTENCE_SPLIT = re.compile(r"[\n\r。！？；;]+")


class ProfileCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfileAbilityCandidate(ProfileCandidateModel):
    dimension: AbilityDimension
    tags: list[str] = Field(default_factory=list, max_length=50)
    level: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, max_length=50)
    evidence_source: EvidenceSource


class ProfileEvidenceExtraction(ProfileCandidateModel):
    """LLM candidate output; ProfileService independently verifies every item."""

    ability_dimensions: list[ProfileAbilityCandidate] = Field(
        default_factory=list, max_length=7
    )
    explicit_facts: list[str] = Field(default_factory=list, max_length=100)
    inferred_items: list[str] = Field(default_factory=list, max_length=100)


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    text: str
    source: EvidenceSource
    context: str


_TAG_DIMENSIONS: dict[str, AbilityDimension] = {
    "数据分析": AbilityDimension.PROFESSIONAL_KNOWLEDGE,
    "机器学习": AbilityDimension.PROFESSIONAL_KNOWLEDGE,
    "深度学习": AbilityDimension.PROFESSIONAL_KNOWLEDGE,
    "大模型应用": AbilityDimension.PROFESSIONAL_KNOWLEDGE,
    "商业分析": AbilityDimension.PROFESSIONAL_KNOWLEDGE,
    "需求分析": AbilityDimension.PROFESSIONAL_KNOWLEDGE,
    "产品规划": AbilityDimension.PROFESSIONAL_KNOWLEDGE,
    "用户研究": AbilityDimension.PROFESSIONAL_KNOWLEDGE,
    "Python": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "Java": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "JavaScript/TypeScript": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "SQL/数据库": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "Linux/运维": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "Docker/K8s": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "云计算": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "数据可视化": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "Python Web开发": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "RAG": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "LLM应用开发": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "Tool Calling": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "MCP": AbilityDimension.TECHNOLOGY_AND_TOOLS,
    "前端开发": AbilityDimension.PROJECT_PRACTICE,
    "后端开发": AbilityDimension.PROJECT_PRACTICE,
    "移动端开发": AbilityDimension.PROJECT_PRACTICE,
    "测试/QA": AbilityDimension.PROJECT_PRACTICE,
    "Git/版本控制": AbilityDimension.PROJECT_PRACTICE,
    "API设计": AbilityDimension.PROJECT_PRACTICE,
    "项目管理": AbilityDimension.PROJECT_PRACTICE,
    "流程设计": AbilityDimension.PROJECT_PRACTICE,
    "沟通表达": AbilityDimension.COMMUNICATION_AND_COLLABORATION,
    "团队协作": AbilityDimension.COMMUNICATION_AND_COLLABORATION,
    "领导力": AbilityDimension.COMMUNICATION_AND_COLLABORATION,
    "远程协作": AbilityDimension.COMMUNICATION_AND_COLLABORATION,
    "解决问题": AbilityDimension.PROBLEM_SOLVING,
    "数据驱动决策": AbilityDimension.PROBLEM_SOLVING,
    "学习能力": AbilityDimension.LEARNING_AND_GROWTH,
    "时间管理": AbilityDimension.LEARNING_AND_GROWTH,
    "抗压能力": AbilityDimension.LEARNING_AND_GROWTH,
    "软考认证": AbilityDimension.LEARNING_AND_GROWTH,
    "PMP": AbilityDimension.LEARNING_AND_GROWTH,
    "计算机等级考试": AbilityDimension.LEARNING_AND_GROWTH,
    "行业认证": AbilityDimension.LEARNING_AND_GROWTH,
    "互联网金融": AbilityDimension.INDUSTRY_AWARENESS,
    "电子商务": AbilityDimension.INDUSTRY_AWARENESS,
    "企业服务/SaaS": AbilityDimension.INDUSTRY_AWARENESS,
    "游戏行业": AbilityDimension.INDUSTRY_AWARENESS,
    "人工智能": AbilityDimension.INDUSTRY_AWARENESS,
    "教育培训": AbilityDimension.INDUSTRY_AWARENESS,
}


class ProfileService:
    """Build a unified profile without delegating final scores to an LLM."""

    def __init__(self, normalizer: AbilityTagNormalizer | None = None) -> None:
        self._normalizer = normalizer or AbilityTagNormalizer()
        self._phrases = self._load_tag_phrases()

    def build_profile(
        self,
        *,
        session_id: str,
        user_id: str | None,
        student_input: Mapping[str, Any] | None,
        historical_profile: Mapping[str, Any] | None = None,
        llm_candidates: ProfileEvidenceExtraction | Mapping[str, Any] | None = None,
        fallback_used: bool = False,
    ) -> StudentProfile:
        source = dict(student_input or {})
        history = dict(historical_profile or {})
        merged = self.merge_profile_data(source, history)
        records = self.collect_evidence(merged, history)
        tag_evidence = self._rule_tag_evidence(records)
        self._merge_historical_tag_evidence(tag_evidence, history)
        if llm_candidates is not None:
            candidates = (
                llm_candidates
                if isinstance(llm_candidates, ProfileEvidenceExtraction)
                else ProfileEvidenceExtraction.model_validate(llm_candidates)
            )
            self._merge_verified_candidates(tag_evidence, candidates, records)
        dimensions = self._build_dimensions(tag_evidence)
        basic_info = StudentBasicInfo.model_validate(merged["basic_info"])
        missing_fields = self._missing_fields(merged, dimensions)
        completeness = self.calculate_completeness(merged, dimensions)
        competitiveness = self.calculate_competitiveness(dimensions, completeness)
        previous_created = self._history_created_at(history)
        now = datetime.now(timezone.utc)
        tags = sorted({tag for item in dimensions for tag in item.tags})
        summary = self._summary(dimensions, tags, fallback_used)
        return StudentProfile(
            user_id=(user_id or history.get("user_id") or f"session:{session_id}"),
            basic_info=basic_info,
            ability_dimensions=dimensions,
            ability_tags=tags,
            profile_completeness=completeness,
            career_competitiveness_score=competitiveness,
            missing_fields=missing_fields,
            follow_up_questions=self._follow_up_questions(missing_fields),
            summary=summary,
            created_at=previous_created or now,
            updated_at=now,
        )

    def merge_profile_data(
        self, source: Mapping[str, Any], history: Mapping[str, Any]
    ) -> dict[str, Any]:
        basic = dict(history.get("basic_info") or {})
        parsed: dict[str, Any] = {}
        for key in ("parsed_data", "resume_result", "parsed_resume", "resume_profile"):
            value = source.get(key)
            if isinstance(value, Mapping):
                parsed.update(value)
        raw_profile = source.get("profile")
        if isinstance(raw_profile, Mapping):
            parsed.update(raw_profile)
        form: dict[str, Any] = {}
        for key in ("basic_info", "user_profile", "form_data", "form_fields"):
            value = source.get(key)
            if isinstance(value, Mapping):
                form.update(value)
        education = parsed.get("education") or source.get("education")
        if isinstance(education, list):
            education = next(
                (item for item in reversed(education) if isinstance(item, Mapping)),
                None,
            )
        if isinstance(education, Mapping):
            for src, dst in (
                ("education_level", "education_level"), ("degree", "education_level"),
                ("major", "major"), ("graduation_year", "graduation_year"),
            ):
                if education.get(src) not in (None, ""):
                    basic[dst] = education[src]
        for key in (
            "education_level", "major", "graduation_year", "city",
            "target_job", "target_industry", "years_of_experience",
        ):
            value = parsed.get(key)
            if value not in (None, ""):
                basic[key] = value
            value = form.get(key)
            if value not in (None, ""):
                basic[key] = value
        target = source.get("target_job")
        if target and not basic.get("target_job"):
            basic["target_job"] = target
        # Identity fields are not needed for career reasoning and must not be
        # copied from parsed resumes into Agent state.
        basic["name"] = None

        merged: dict[str, Any] = {"basic_info": basic}
        merged["resume_text"] = self._text(source.get("resume_text"))
        merged["supplementary_info"] = self._first_value(
            source, "supplementary_info", "supplementary_experience", "additional_experience"
        )
        for field in (
            "skills", "projects", "internships", "work_experience", "competitions", "certificates"
        ):
            values: list[Any] = []
            values.extend(self._as_list(parsed.get(field)))
            values.extend(self._as_list(source.get(field)))
            values.extend(self._as_list(form.get(field)))
            merged[field] = self._deduplicate(values)
        return merged

    def collect_evidence(
        self, merged: Mapping[str, Any], history: Mapping[str, Any]
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        self._append_text_records(records, merged.get("resume_text"), EvidenceSource.RESUME, "resume")
        self._append_text_records(
            records, merged.get("supplementary_info"), EvidenceSource.USER_SUPPLEMENT, "supplement"
        )
        for field, source, context in (
            ("skills", EvidenceSource.FORM, "skill"),
            ("projects", EvidenceSource.PROJECT, "project"),
            ("internships", EvidenceSource.RESUME, "internship"),
            ("work_experience", EvidenceSource.RESUME, "work"),
            ("competitions", EvidenceSource.PROJECT, "competition"),
            ("certificates", EvidenceSource.FORM, "certificate"),
        ):
            for value in merged.get(field) or []:
                self._append_text_records(records, value, source, context)
        self._append_history_records(records, history)
        return self._deduplicate_records(records)

    @staticmethod
    def calculate_completeness(
        merged: Mapping[str, Any], dimensions: list[AbilityDimensionProfile]
    ) -> float:
        basic = merged.get("basic_info") or {}
        education = sum(bool(basic.get(key)) for key in ("education_level", "major", "graduation_year")) / 3
        target = sum(bool(basic.get(key)) for key in ("target_job", "target_industry")) / 2
        experience_values = (merged.get("internships") or []) + (merged.get("work_experience") or [])
        experience = 1.0 if experience_values else (0.5 if basic.get("years_of_experience") is not None else 0.0)
        projects = 1.0 if (merged.get("projects") or merged.get("competitions")) else 0.0
        evidenced_tags = {tag for item in dimensions if item.evidence for tag in item.tags}
        abilities = min(len(evidenced_tags) / 3, 1.0)
        return round(0.2 * (education + target + experience + projects + abilities), 2)

    @staticmethod
    def calculate_competitiveness(
        dimensions: list[AbilityDimensionProfile], completeness: float
    ) -> float:
        evidenced = [item for item in dimensions if item.evidence and item.tags]
        if not evidenced:
            return 0.0
        level_component = (
            sum(item.level * item.confidence for item in evidenced) / (5 * len(ABILITY_DIMENSIONS)) * 70
        )
        breadth_component = len(evidenced) / len(ABILITY_DIMENSIONS) * 20
        completeness_component = completeness * 10
        return round(min(100.0, level_component + breadth_component + completeness_component), 2)

    def _rule_tag_evidence(
        self, records: Iterable[EvidenceRecord]
    ) -> dict[str, list[EvidenceRecord]]:
        result: dict[str, list[EvidenceRecord]] = {}
        for record in records:
            for phrase, tag in self._phrases:
                if self._mentioned(phrase, record.text):
                    result.setdefault(tag, []).append(record)
        return result

    def _merge_verified_candidates(
        self,
        result: dict[str, list[EvidenceRecord]],
        candidates: ProfileEvidenceExtraction,
        records: list[EvidenceRecord],
    ) -> None:
        for candidate in candidates.ability_dimensions:
            for raw_tag in candidate.tags:
                normalized = self._normalizer.normalize(raw_tag)
                tag = normalized.get("standard_tag")
                if not tag:
                    continue
                for evidence in candidate.evidence:
                    record = self._grounded_record(evidence, records)
                    if record and any(
                        mapped == tag and self._mentioned(phrase, record.text)
                        for phrase, mapped in self._phrases
                    ):
                        result.setdefault(tag, []).append(record)

    def _merge_historical_tag_evidence(
        self,
        result: dict[str, list[EvidenceRecord]],
        history: Mapping[str, Any],
    ) -> None:
        for item in history.get("ability_dimensions") or []:
            if not isinstance(item, Mapping):
                continue
            evidence = [
                self._sanitize(self._text(value))[:500]
                for value in item.get("evidence") or []
                if self._text(value)
            ]
            for raw_tag in item.get("tags") or []:
                normalized = self._normalizer.normalize(raw_tag)
                tag = normalized.get("standard_tag")
                if tag:
                    result.setdefault(tag, []).extend(
                        EvidenceRecord(value, EvidenceSource.HISTORY, "history")
                        for value in evidence
                    )
        for item in history.get("abilities") or []:
            if not isinstance(item, Mapping):
                continue
            normalized = self._normalizer.normalize(item.get("tag"))
            tag = normalized.get("standard_tag")
            evidence = self._sanitize(self._text(item.get("evidence")))[:500]
            if tag and evidence:
                result.setdefault(tag, []).append(
                    EvidenceRecord(evidence, EvidenceSource.HISTORY, "history")
                )

    def _build_dimensions(
        self, tag_evidence: Mapping[str, list[EvidenceRecord]]
    ) -> list[AbilityDimensionProfile]:
        grouped: dict[AbilityDimension, dict[str, list[EvidenceRecord]]] = {}
        for tag, records in tag_evidence.items():
            dimension = _TAG_DIMENSIONS.get(tag)
            if dimension is not None and records:
                grouped.setdefault(dimension, {})[tag] = self._deduplicate_records(records)
                practice_records = [
                    record
                    for record in records
                    if record.context in {"project", "competition", "internship", "work"}
                ]
                if practice_records and dimension != AbilityDimension.PROJECT_PRACTICE:
                    grouped.setdefault(AbilityDimension.PROJECT_PRACTICE, {})[
                        tag
                    ] = self._deduplicate_records(practice_records)
        result: list[AbilityDimensionProfile] = []
        for dimension in ABILITY_DIMENSIONS:
            tags = grouped.get(dimension)
            if not tags:
                continue
            all_records = [record for records in tags.values() for record in records]
            strongest = max(all_records, key=self._record_strength)
            evidence = self._deduplicate([record.text for record in all_records])[:10]
            result.append(
                AbilityDimensionProfile(
                    dimension=dimension,
                    tags=sorted(tags),
                    level=max(self._level(record) for record in all_records),
                    confidence=round(min(0.95, max(self._confidence(record) for record in all_records) + min(len(all_records) - 1, 2) * 0.05), 2),
                    evidence=evidence,
                    evidence_source=strongest.source,
                )
            )
        return result

    @staticmethod
    def _level(record: EvidenceRecord) -> int:
        text = record.text
        if re.search(r"主导|负责人|核心负责|带领|技术决策", text) and re.search(r"上线|获奖|成果|优化|解决", text):
            return 4
        if re.search(r"独立|完成|实现|开发|设计|搭建|获奖|解决", text):
            return 3
        if re.search(r"参与|课程|作业|练习|使用|实习", text):
            return 2
        return 1

    @staticmethod
    def _confidence(record: EvidenceRecord) -> float:
        base = {
            "project": 0.78, "competition": 0.78, "internship": 0.78,
            "work": 0.82, "resume": 0.68, "supplement": 0.62,
            "certificate": 0.72, "skill": 0.45, "history": 0.65,
        }.get(record.context, 0.5)
        if re.search(r"独立|负责|完成|实现|开发|设计|搭建|获奖|上线|结果|成果", record.text):
            base += 0.08
        return min(base, 0.95)

    def _record_strength(self, record: EvidenceRecord) -> float:
        return self._confidence(record) + self._level(record) / 10

    @staticmethod
    def _missing_fields(
        merged: Mapping[str, Any], dimensions: list[AbilityDimensionProfile]
    ) -> list[str]:
        basic = merged.get("basic_info") or {}
        missing = [
            key for key in (
                "education_level", "major", "graduation_year", "target_job", "target_industry"
            ) if not basic.get(key)
        ]
        if not (merged.get("internships") or merged.get("work_experience")):
            missing.append("internship_or_work_experience")
        if not (merged.get("projects") or merged.get("competitions")):
            missing.append("project_or_competition_experience")
        if sum(len(item.tags) for item in dimensions if item.evidence) < 3:
            missing.append("at_least_three_evidence_backed_abilities")
        return missing

    @staticmethod
    def _follow_up_questions(missing: list[str]) -> list[str]:
        questions = {
            "education_level": "你的最高学历是什么？",
            "major": "你的专业名称是什么？",
            "graduation_year": "你的预计或实际毕业年份是什么？",
            "target_job": "你目前最希望发展的目标岗位是什么？",
            "target_industry": "你希望进入哪个行业？",
            "internship_or_work_experience": "你是否有实习或工作经历？请说明职责和结果。",
            "project_or_competition_experience": "请补充一个项目或比赛中你负责的任务和结果。",
            "at_least_three_evidence_backed_abilities": "请补充能证明你主要能力的具体任务、行动或成果。",
        }
        return [questions[item] for item in missing if item in questions]

    @staticmethod
    def _summary(
        dimensions: list[AbilityDimensionProfile], tags: list[str], fallback_used: bool
    ) -> str:
        source = "规则兜底" if fallback_used else "明确资料与校验证据"
        return f"基于{source}生成画像，识别{len(tags)}项能力标签，覆盖{len(dimensions)}个能力维度。"

    def _append_history_records(
        self, records: list[EvidenceRecord], history: Mapping[str, Any]
    ) -> None:
        for item in history.get("ability_dimensions") or []:
            if not isinstance(item, Mapping):
                continue
            for evidence in item.get("evidence") or []:
                self._append_text_records(records, evidence, EvidenceSource.HISTORY, "history")
        for item in history.get("abilities") or []:
            if isinstance(item, Mapping):
                self._append_text_records(records, item.get("evidence"), EvidenceSource.HISTORY, "history")

    def _append_text_records(
        self,
        records: list[EvidenceRecord],
        value: Any,
        source: EvidenceSource,
        context: str,
    ) -> None:
        for raw in self._as_list(value):
            text = self._sanitize(self._text(raw))
            for sentence in _SENTENCE_SPLIT.split(text):
                normalized = sentence.strip()[:500]
                if normalized:
                    records.append(EvidenceRecord(normalized, source, context))

    @staticmethod
    def _grounded_record(
        evidence: str, records: Iterable[EvidenceRecord]
    ) -> EvidenceRecord | None:
        normalized = ProfileService._ground_key(evidence)
        if not normalized:
            return None
        for record in records:
            source = ProfileService._ground_key(record.text)
            if normalized in source or source in normalized:
                return record
        return None

    @staticmethod
    def _ground_key(value: str) -> str:
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())

    @staticmethod
    def _mentioned(phrase: str, text: str) -> bool:
        if phrase.isascii() and phrase.replace("/", "").replace(" ", "").isalnum():
            return re.search(rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])", text, re.I) is not None
        return phrase.casefold() in text.casefold()

    @staticmethod
    def _sanitize(value: str) -> str:
        return _IDENTITY.sub("[身份信息已脱敏]", _PHONE.sub("[手机号已脱敏]", _EMAIL.sub("[邮箱已脱敏]", value)))

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, Mapping):
            return "；".join(f"{key}:{ProfileService._text(item)}" for key, item in value.items() if item not in (None, "", [], {}))
        if isinstance(value, (list, tuple, set)):
            return "；".join(ProfileService._text(item) for item in value if item not in (None, "", [], {}))
        return str(value).strip()

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if value in (None, "", [], {}):
            return []
        return list(value) if isinstance(value, (list, tuple, set)) else [value]

    @staticmethod
    def _first_value(source: Mapping[str, Any], *keys: str) -> Any:
        for key in keys:
            if source.get(key) not in (None, "", [], {}):
                return source[key]
        return ""

    @staticmethod
    def _deduplicate(values: Iterable[Any]) -> list[Any]:
        result: list[Any] = []
        seen: set[str] = set()
        for value in values:
            key = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result

    @staticmethod
    def _deduplicate_records(records: Iterable[EvidenceRecord]) -> list[EvidenceRecord]:
        result: list[EvidenceRecord] = []
        seen: set[tuple[str, EvidenceSource, str]] = set()
        for record in records:
            key = (record.text, record.source, record.context)
            if key not in seen:
                seen.add(key)
                result.append(record)
        return result

    @staticmethod
    def _history_created_at(history: Mapping[str, Any]) -> datetime | None:
        value = history.get("created_at")
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_tag_phrases() -> tuple[tuple[str, str], ...]:
        tags = json.loads(_TAGS_FILE.read_text(encoding="utf-8"))
        aliases = json.loads(_ALIASES_FILE.read_text(encoding="utf-8"))
        phrases = [(item["tag"], item["tag"]) for item in tags if not item.get("deprecated", False)]
        phrases.extend((item["alias"], item["standard_tag"]) for item in aliases)
        unique = {(phrase, tag) for phrase, tag in phrases}
        return tuple(sorted(unique, key=lambda item: len(item[0]), reverse=True))


__all__ = [
    "ProfileAbilityCandidate",
    "ProfileEvidenceExtraction",
    "ProfileService",
]
