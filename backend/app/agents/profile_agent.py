"""ProfileAgent backed by the shared LLM client with validated fallback."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .base_agent import AgentResult, BaseAgent
from ..core.llm_client import LLMValidationError, llm_client
from ..orchestrator.career_state import CareerState
from ..schemas.profile_schema import StudentProfile, active_ability_tags


_PROMPT_DIR = Path(__file__).resolve().parents[3] / "prompts" / "profile_agent"
_EDUCATION_LEVELS = {"专科", "本科", "硕士", "博士"}
_FALLBACK_ALIASES = {
    "JavaScript": "JavaScript/TypeScript",
    "TypeScript": "JavaScript/TypeScript",
    "SQL": "SQL/数据库",
    "数据库": "SQL/数据库",
    "Kubernetes": "Docker/K8s",
    "K8s": "Docker/K8s",
    "Git": "Git/版本控制",
    "SaaS": "企业服务/SaaS",
}


class ProfileAgent(BaseAgent):
    """Extract an evidence-backed student profile from user-provided facts."""

    name = "ProfileAgent"
    required_fields = ("student_input",)
    output_fields = ("student_profile",)
    tool_name = "analyze_student_profile"

    def __init__(self, client: Any | None = None) -> None:
        self._llm_client = client if client is not None else llm_client

    async def run(self, state: CareerState) -> AgentResult:
        """Keep the BaseAgent envelope while replacing legacy Mock summaries."""

        result = await super().run(state)
        if result.status == "success":
            summary = "ProfileAgent LLM 结构化画像生成完成"
        elif result.status == "partial":
            summary = "ProfileAgent 使用规则或 Demo fallback 继续"
        else:
            summary = "ProfileAgent fallback 失败，后续 Agent 继续"
        result.summary = summary
        if state.agent_logs and state.agent_logs[-1].agent_name == self.name:
            state.agent_logs[-1].summary = summary
        return result

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        system_prompt, user_prompt = self._build_prompts(state)
        raw_profile = await self._llm_client.generate_structured(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            StudentProfile,
            temperature=0.1,
        )
        profile = self._ensure_profile(raw_profile)
        return {"student_profile": profile.model_dump()}

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        try:
            profile = self._fallback_profile(state)
        except Exception as exc:
            # Pydantic errors may echo inputs; never expose them to BaseAgent logs.
            raise RuntimeError("ProfileAgent fallback validation failed") from exc
        return {"student_profile": profile.model_dump()}

    def _build_prompts(self, state: CareerState) -> tuple[str, str]:
        source = state.student_input or {}
        form = self._form_data(state)
        resume_text = self._escape_prompt_block(
            self._as_prompt_text(source.get("resume_text"))
        )
        supplementary_info = self._escape_prompt_block(
            self._supplementary_text(source)
        )
        serialized_form = self._escape_prompt_block(
            json.dumps(form, ensure_ascii=False, separators=(",", ":"))
        )
        system_prompt, user_template = self._prompt_templates()
        user_prompt = (
            user_template.replace("{{resume_text}}", resume_text)
            .replace("{{form_data}}", serialized_form)
            .replace("{{supplementary_info}}", supplementary_info)
        )
        return system_prompt, user_prompt

    def _form_data(self, state: CareerState) -> dict[str, Any]:
        source = state.student_input or {}
        raw_form = source.get("form_fields") or source.get("form_data") or {}
        form = dict(raw_form) if isinstance(raw_form, dict) else {}
        target = state.target_job_input or {}

        source_target = source.get("target_job")
        if not form.get("target_job"):
            form["target_job"] = target.get("job_title") or source_target
        if not form.get("target_industry"):
            form["target_industry"] = target.get("industry")
        return form

    @staticmethod
    def _supplementary_text(source: dict[str, Any]) -> str:
        for field_name in (
            "supplementary_info",
            "supplementary_experience",
            "additional_experience",
        ):
            value = source.get(field_name)
            if value not in (None, "", [], {}):
                return ProfileAgent._as_prompt_text(value)
        return ""

    @staticmethod
    def _as_prompt_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("ProfileAgent input contains non-JSON data") from exc

    @staticmethod
    def _escape_prompt_block(value: str) -> str:
        # The prompt uses XML-like delimiters, so only angle brackets need to be
        # neutralized. Escaping ampersands would change user facts such as "A & B".
        return value.replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    @lru_cache(maxsize=1)
    def _prompt_templates() -> tuple[str, str]:
        try:
            system_prompt = (_PROMPT_DIR / "system.txt").read_text(encoding="utf-8")
            user_template = (_PROMPT_DIR / "user_template.txt").read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            raise RuntimeError("ProfileAgent Prompt V1 could not be loaded") from exc
        required = {"{{resume_text}}", "{{form_data}}", "{{supplementary_info}}"}
        missing = [
            placeholder for placeholder in required if placeholder not in user_template
        ]
        if missing:
            raise RuntimeError("ProfileAgent user template is missing placeholders")
        return system_prompt, user_template

    @staticmethod
    def _ensure_profile(value: Any) -> StudentProfile:
        if isinstance(value, StudentProfile):
            profile = value
        else:
            try:
                profile = StudentProfile.model_validate(value)
            except (ValidationError, TypeError, ValueError) as exc:
                raise LLMValidationError(
                    "ProfileAgent output failed JSON/schema validation"
                ) from exc
        # Frozen field, deterministic source pending: never trust an LLM-produced score.
        return profile.model_copy(update={"competitiveness_score": 0.0})

    def _fallback_profile(self, state: CareerState) -> StudentProfile:
        source = state.student_input or {}
        form = self._form_data(state)
        evidence_text = "\n".join(
            part
            for part in (
                self._as_prompt_text(source.get("resume_text")),
                self._supplementary_text(source),
            )
            if part
        )
        matched_tags = self._rule_tags(evidence_text)
        abilities = self._rule_abilities(matched_tags)
        used_demo_abilities = len(abilities) < 3
        if used_demo_abilities:
            abilities = self._demo_abilities()

        education = form.get("education_level")
        if education not in _EDUCATION_LEVELS:
            education = "本科"
        graduation_year = self._bounded_int(form.get("graduation_year"), 1900, 2200)
        years = self._bounded_float(form.get("years_of_experience"), 0.0, 80.0)
        student_id = self._bounded_int(form.get("student_id"), 1, 2**63 - 1)
        missing_fields = self._missing_fields(form, source, used_demo_abilities)
        completeness = self._fallback_completeness(
            form=form,
            source=source,
            has_rule_abilities=not used_demo_abilities,
        )

        return StudentProfile.model_validate(
            {
                "student_id": student_id,
                "name": "匿名用户",
                "basic_info": {
                    "education_level": education,
                    "major": self._safe_text(form.get("major"), "待补充"),
                    "graduation_year": graduation_year,
                    "target_job": self._safe_text(
                        form.get("target_job"), "待确认岗位"
                    ),
                    "target_industry": self._optional_text(
                        form.get("target_industry")
                    ),
                    "years_of_experience": years,
                },
                "abilities": abilities,
                "competitiveness_score": 0.0,
                "completeness": completeness,
                "missing_fields": missing_fields,
            }
        )

    @staticmethod
    def _rule_tags(text: str) -> list[str]:
        if not text:
            return []
        matches = {
            tag
            for tag in active_ability_tags()
            if ProfileAgent._tag_mentioned(tag, text)
        }
        matches.update(
            standard_tag
            for alias, standard_tag in _FALLBACK_ALIASES.items()
            if alias in text
        )
        return sorted(matches)

    @staticmethod
    def _tag_mentioned(tag: str, text: str) -> bool:
        if tag == "Java" and "JavaScript" in text:
            text = text.replace("JavaScript", "")
        if tag.isascii() and tag.replace("/", "").isalnum():
            return re.search(
                rf"(?<![A-Za-z0-9]){re.escape(tag)}(?![A-Za-z0-9])", text
            ) is not None
        return tag in text

    @staticmethod
    def _rule_abilities(tags: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "tag": tag,
                "level": 2,
                "confidence": 0.5,
                "evidence": f"输入中明确提及{tag}",
            }
            for tag in tags[:30]
        ]

    @staticmethod
    def _demo_abilities() -> list[dict[str, Any]]:
        return [
            {
                "tag": "Python",
                "level": 2,
                "confidence": 0.5,
                "evidence": "阶段1 Demo fallback 标签",
            },
            {
                "tag": "数据分析",
                "level": 2,
                "confidence": 0.5,
                "evidence": "阶段1 Demo fallback 标签",
            },
            {
                "tag": "沟通表达",
                "level": 2,
                "confidence": 0.5,
                "evidence": "阶段1 Demo fallback 标签",
            },
        ]

    @staticmethod
    def _missing_fields(
        form: dict[str, Any], source: dict[str, Any], used_demo_abilities: bool
    ) -> list[str]:
        fields: list[str] = []
        if form.get("education_level") not in _EDUCATION_LEVELS:
            fields.append("学历")
        if not form.get("major"):
            fields.append("专业")
        if not form.get("graduation_year"):
            fields.append("毕业年份")
        if not form.get("target_job"):
            fields.append("目标岗位")
        if not form.get("target_industry"):
            fields.append("目标行业")
        if not source.get("resume_text"):
            fields.append("简历文本")
        if used_demo_abilities:
            fields.append("至少三项可验证的能力经历")
        return fields

    @staticmethod
    def _fallback_completeness(
        *, form: dict[str, Any], source: dict[str, Any], has_rule_abilities: bool
    ) -> float:
        score = 0.0
        education_fields = ("education_level", "major", "graduation_year")
        if all(form.get(name) for name in education_fields):
            score += 0.2
        if form.get("target_job") and form.get("target_industry"):
            score += 0.2
        if form.get("years_of_experience") is not None:
            score += 0.2
        if source.get("resume_text") or ProfileAgent._supplementary_text(source):
            score += 0.2
        if has_rule_abilities:
            score += 0.2
        return round(score, 2)

    @staticmethod
    def _bounded_int(value: Any, minimum: int, maximum: int) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if minimum <= parsed <= maximum else None

    @staticmethod
    def _bounded_float(value: Any, minimum: float, maximum: float) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if minimum <= parsed <= maximum else None

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text[:200] or None

    @staticmethod
    def _safe_text(value: Any, fallback: str) -> str:
        text = str(value).strip() if value is not None else ""
        return (text or fallback)[:200]

    def _input_summary(self, state: CareerState) -> str:
        source = state.student_input or {}
        form = source.get("form_fields") or source.get("form_data") or {}
        form_count = len(form) if isinstance(form, dict) else 0
        has_supplement = any(
            source.get(field_name) not in (None, "", [], {})
            for field_name in (
                "supplementary_info",
                "supplementary_experience",
                "additional_experience",
            )
        )
        return (
            f"简历={'已提供' if source.get('resume_text') else '未提供'}; "
            f"表单字段数={form_count}; "
            f"补充经历={'已提供' if has_supplement else '未提供'}"
        )
