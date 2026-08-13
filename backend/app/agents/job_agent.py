"""JobAgent backed by the shared LLM client with validated fallback."""

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
from ..schemas.job_schema import JobAgentOutput, JobProfile, TrendResult
from ..schemas.profile_schema import active_ability_tags


_PROMPT_DIR = Path(__file__).resolve().parents[3] / "prompts" / "job_agent"
_JOBS_DEMO_FILE = Path(__file__).resolve().parents[1] / "data" / "jobs_demo.json"
_SOFT_SKILL_TAGS = {
    "沟通表达",
    "团队协作",
    "领导力",
    "解决问题",
    "学习能力",
    "时间管理",
    "抗压能力",
    "远程协作",
}
_TAG_ALIASES = {
    "JavaScript": "JavaScript/TypeScript",
    "TypeScript": "JavaScript/TypeScript",
    "SQL": "SQL/数据库",
    "数据库": "SQL/数据库",
    "Kubernetes": "Docker/K8s",
    "K8s": "Docker/K8s",
    "Git": "Git/版本控制",
    "SaaS": "企业服务/SaaS",
}
_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?%?")


class _JobGroundingError(RuntimeError):
    """Raised when valid structured output is not grounded in supplied sources."""


class JobAgent(BaseAgent):
    """Extract an evidence-backed job profile and conservative trend result."""

    name = "JobAgent"
    required_fields = ("target_job_input",)
    output_fields = ("job_profile", "trend_result")
    tool_name = "analyze_job_and_trend"

    def __init__(self, client: Any | None = None) -> None:
        self._llm_client = client if client is not None else llm_client

    async def run(self, state: CareerState) -> AgentResult:
        """Keep the frozen BaseAgent envelope with accurate JobAgent summaries."""

        result = await super().run(state)
        if result.status == "success":
            summary = "JobAgent LLM 岗位画像与趋势分析生成完成"
        elif result.status == "partial":
            summary = "JobAgent 使用规则或 Demo fallback 继续"
        else:
            summary = "JobAgent fallback 失败，后续 Agent 继续"
        result.summary = summary
        if state.agent_logs and state.agent_logs[-1].agent_name == self.name:
            state.agent_logs[-1].summary = summary
        return result

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        system_prompt, user_prompt = self._build_prompts(state)
        raw_output = await self._llm_client.generate_structured(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            JobAgentOutput,
            temperature=0.1,
        )
        output = self._ensure_output(raw_output, state)
        return output.model_dump()

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        try:
            return self._fallback_output(state).model_dump()
        except Exception as exc:
            # Validation errors can echo provider/user content; keep logs summary-only.
            raise RuntimeError("JobAgent fallback validation failed") from exc

    def _build_prompts(self, state: CareerState) -> tuple[str, str]:
        target = state.target_job_input or {}
        title = self._first_text(target, "job_title", "job_name", "title")
        if not title:
            raise ValueError("JobAgent target is missing job_title")
        job_context = {
            "job_id": self._positive_int(target.get("job_id")),
            "title": title,
            "industry": self._first_text(target, "industry"),
        }
        job_name = self._escape_prompt_block(
            json.dumps(job_context, ensure_ascii=False, separators=(",", ":"))
        )
        job_description = self._escape_prompt_block(self._job_description(target))
        trend_context = self._escape_prompt_block(self._trend_context(target))
        system_prompt, user_template = self._prompt_templates()
        user_prompt = (
            user_template.replace("{{job_name}}", job_name)
            .replace("{{job_description}}", job_description)
            .replace("{{trend_context}}", trend_context)
        )
        return system_prompt, user_prompt

    @staticmethod
    def _job_description(target: dict[str, Any]) -> str:
        return JobAgent._first_prompt_value(
            target, "job_description", "jd_text", "jd", "description"
        )

    @staticmethod
    def _trend_context(target: dict[str, Any]) -> str:
        return JobAgent._first_prompt_value(
            target,
            "trend_context",
            "trend_data",
            "trend_material",
            "knowledge_context",
        )

    @staticmethod
    def _first_prompt_value(target: dict[str, Any], *field_names: str) -> str:
        for field_name in field_names:
            value = target.get(field_name)
            if value not in (None, "", [], {}):
                return JobAgent._as_prompt_text(value)
        return ""

    @staticmethod
    def _as_prompt_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("JobAgent input contains non-JSON data") from exc

    @staticmethod
    def _escape_prompt_block(value: str) -> str:
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
            raise RuntimeError("JobAgent Prompt V1 could not be loaded") from exc
        required = {"{{job_name}}", "{{job_description}}", "{{trend_context}}"}
        if any(placeholder not in user_template for placeholder in required):
            raise RuntimeError("JobAgent user template is missing placeholders")
        return system_prompt, user_template

    def _ensure_output(self, value: Any, state: CareerState) -> JobAgentOutput:
        try:
            output = (
                value
                if isinstance(value, JobAgentOutput)
                else JobAgentOutput.model_validate(value)
            )
            output = self._apply_target_identity(output, state)
            output = JobAgentOutput.model_validate(output)
        except (ValidationError, TypeError, ValueError) as exc:
            raise LLMValidationError(
                "JobAgent output failed JSON/schema validation"
            ) from exc
        self._validate_grounding(output, state)
        return output

    def _validate_grounding(
        self, output: JobAgentOutput, state: CareerState
    ) -> None:
        target = state.target_job_input or {}
        jd_text = self._job_description(target)
        if jd_text:
            for ability in output.job_profile.required_abilities:
                if not ability.evidence or not self._text_grounded(
                    ability.evidence, jd_text
                ):
                    raise _JobGroundingError(
                        "JobAgent ability evidence is not grounded in the JD"
                    )
            salary = output.job_profile.salary_range
            if salary and not self._text_grounded(salary, jd_text):
                raise _JobGroundingError(
                    "JobAgent salary range is not grounded in the JD"
                )

        trend_context = self._trend_context(target)
        trend = output.trend_result
        trend_skills = trend.hot_skills + trend.rising_skills + trend.declining_skills
        if trend_context:
            if any(
                not self._tag_or_alias_mentioned(tag, trend_context)
                for tag in trend_skills
            ):
                raise _JobGroundingError(
                    "JobAgent trend skill is not grounded in trend context"
                )
            source_numbers = set(_NUMBER_PATTERN.findall(trend_context))
            output_numbers = set(
                _NUMBER_PATTERN.findall(self._trend_explanation_text(trend))
            )
            if output_numbers - source_numbers:
                raise _JobGroundingError(
                    "JobAgent trend contains unsupported numeric claims"
                )
        else:
            if (
                trend_skills
                or trend.development_opportunities
                or trend.development_risks
                or trend.ai_risk_assessment != "medium"
                or "未提供" not in trend.trend_summary
                or "未提供" not in trend.ai_risk_detail
                or trend.data_source != "未提供可验证的岗位趋势资料"
            ):
                raise _JobGroundingError(
                    "JobAgent trend must remain conservative without trend context"
                )

    @staticmethod
    def _text_grounded(candidate: str, source: str) -> bool:
        def normalize(value: str) -> str:
            return re.sub(r"[^\w\u4e00-\u9fff]+", "", value).lower()

        normalized_candidate = normalize(candidate)
        normalized_source = normalize(source)
        return bool(normalized_candidate) and normalized_candidate in normalized_source

    @staticmethod
    def _tag_or_alias_mentioned(tag: str, text: str) -> bool:
        if JobAgent._tag_mentioned(tag, text):
            return True
        return any(
            JobAgent._tag_mentioned(alias, text)
            for alias, standard_tag in _TAG_ALIASES.items()
            if standard_tag == tag
        )

    @staticmethod
    def _trend_explanation_text(trend: TrendResult) -> str:
        return "\n".join(
            [
                trend.trend_summary,
                trend.ai_risk_detail,
                *trend.development_opportunities,
                *trend.development_risks,
                trend.data_source,
            ]
        )

    def _apply_target_identity(
        self, output: JobAgentOutput, state: CareerState
    ) -> JobAgentOutput:
        target = state.target_job_input or {}
        title = self._first_text(target, "job_title", "job_name", "title")
        industry = self._first_text(target, "industry")
        job_id = self._positive_int(target.get("job_id"))
        profile_updates: dict[str, Any] = {"job_id": job_id}
        trend_updates: dict[str, Any] = {}
        if title:
            profile_updates["title"] = title
            trend_updates["job_title"] = title
        if industry:
            profile_updates["industry"] = industry
            trend_updates["industry"] = industry
        return JobAgentOutput(
            job_profile=output.job_profile.model_copy(update=profile_updates),
            trend_result=output.trend_result.model_copy(update=trend_updates),
        )

    def _fallback_output(self, state: CareerState) -> JobAgentOutput:
        target = state.target_job_input or {}
        title = self._first_text(target, "job_title", "job_name", "title") or "数据分析师"
        industry = self._first_text(target, "industry") or "待确认"
        job_id = self._positive_int(target.get("job_id"))
        jd_text = self._job_description(target)
        tags = self._rule_tags(jd_text)

        if tags:
            abilities = self._rule_abilities(tags, jd_text)
            profile = JobProfile.model_validate(
                {
                    "job_id": job_id,
                    "title": title,
                    "normalized_title": title,
                    "industry": industry,
                    "required_abilities": abilities,
                    "soft_skills": [tag for tag in tags if tag in _SOFT_SKILL_TAGS],
                    "salary_range": None,
                    "job_description": self._fallback_summary(jd_text),
                }
            )
        else:
            profile = self._demo_profile(title, industry, job_id)

        trend = self._fallback_trend(
            title=title,
            industry=industry,
            trend_context=self._trend_context(target),
        )
        return JobAgentOutput(job_profile=profile, trend_result=trend)

    @staticmethod
    def _rule_tags(text: str) -> list[str]:
        if not text:
            return []
        matches = {
            tag
            for tag in active_ability_tags()
            if JobAgent._tag_mentioned(tag, text)
        }
        matches.update(
            standard_tag
            for alias, standard_tag in _TAG_ALIASES.items()
            if JobAgent._tag_mentioned(alias, text)
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
    def _rule_abilities(tags: list[str], jd_text: str) -> list[dict[str, Any]]:
        selected = tags[:30]
        raw_weight = round(1.0 / len(selected), 6)
        abilities: list[dict[str, Any]] = []
        assigned = 0.0
        for index, tag in enumerate(selected):
            weight = round(1.0 - assigned, 6) if index == len(selected) - 1 else raw_weight
            assigned = round(assigned + weight, 6)
            abilities.append(
                {
                    "tag": tag,
                    "required_level": 2,
                    "weight": weight,
                    "importance": "important",
                    "evidence": JobAgent._evidence_sentence(jd_text, tag),
                }
            )
        return abilities

    @staticmethod
    def _evidence_sentence(text: str, tag: str) -> str:
        aliases = [tag] + [
            alias for alias, standard_tag in _TAG_ALIASES.items() if standard_tag == tag
        ]
        sentences = [
            sentence.strip()
            for sentence in re.split(r"[\n\r。！？!?]+", text)
            if sentence.strip()
        ]
        evidence = next(
            (
                sentence
                for sentence in sentences
                if any(JobAgent._tag_mentioned(alias, sentence) for alias in aliases)
            ),
            f"JD 中明确提及{tag}",
        )
        evidence = _EMAIL_PATTERN.sub("[邮箱已脱敏]", evidence)
        evidence = _PHONE_PATTERN.sub("[手机号已脱敏]", evidence)
        return evidence[:1000]

    @staticmethod
    def _fallback_summary(jd_text: str) -> str:
        cleaned = _EMAIL_PATTERN.sub("[邮箱已脱敏]", jd_text)
        cleaned = _PHONE_PATTERN.sub("[手机号已脱敏]", cleaned).strip()
        return (cleaned[:5000] or "岗位 JD 信息有限，已生成规则画像。")

    def _demo_profile(
        self, title: str, industry: str, job_id: int | None
    ) -> JobProfile:
        demos = self._demo_profiles()
        demo = next(
            (
                item
                for item in demos
                if item["title"] in title or title in item["title"]
            ),
            demos[0],
        )
        payload = dict(demo)
        payload.update(
            {
                "job_id": job_id,
                "title": title,
                "normalized_title": demo["normalized_title"],
                "industry": industry,
                "job_description": "A02 Demo fallback 岗位画像，不代表当前 JD 明确要求。",
            }
        )
        return JobProfile.model_validate(payload)

    @staticmethod
    @lru_cache(maxsize=1)
    def _demo_profiles() -> tuple[dict[str, Any], ...]:
        try:
            records = json.loads(_JOBS_DEMO_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("JobAgent demo profiles could not be loaded") from exc
        if not isinstance(records, list) or not records:
            raise RuntimeError("JobAgent demo profiles are empty")
        return tuple(records)

    @staticmethod
    def _fallback_trend(
        *, title: str, industry: str, trend_context: str
    ) -> TrendResult:
        if trend_context.strip():
            summary = "已收到岗位趋势资料，但规则 fallback 无法可靠判断技能变化方向。"
            detail = "规则 fallback 不对趋势资料作确定性 AI 风险推断。"
            source = "用户提供的岗位趋势上下文（规则 fallback，未验证）"
        else:
            summary = "未提供可验证趋势资料，无法形成可靠趋势判断。"
            detail = "未提供可验证趋势资料，无法形成可靠 AI 风险结论。"
            source = "未提供可验证的岗位趋势资料"
        return TrendResult(
            job_title=title,
            industry=industry,
            trend_summary=summary,
            hot_skills=[],
            rising_skills=[],
            declining_skills=[],
            ai_risk_assessment="medium",
            ai_risk_detail=detail,
            development_opportunities=[],
            development_risks=[],
            data_source=source,
        )

    @staticmethod
    def _first_text(target: dict[str, Any], *field_names: str) -> str | None:
        for field_name in field_names:
            value = target.get(field_name)
            if value is not None:
                text = str(value).strip()
                if text:
                    return text[:200]
        return None

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _input_summary(self, state: CareerState) -> str:
        target = state.target_job_input or {}
        has_title = bool(self._first_text(target, "job_title", "job_name", "title"))
        has_jd = self._has_input(
            target, "job_description", "jd_text", "jd", "description"
        )
        has_trend = self._has_input(
            target,
            "trend_context",
            "trend_data",
            "trend_material",
            "knowledge_context",
        )
        return (
            f"岗位名称={'已提供' if has_title else '未提供'}; "
            f"JD={'已提供' if has_jd else '未提供'}; "
            f"趋势资料={'已提供' if has_trend else '未提供'}"
        )

    @staticmethod
    def _has_input(target: dict[str, Any], *field_names: str) -> bool:
        return any(
            field_name in target and target[field_name] not in (None, "", [], {})
            for field_name in field_names
        )
