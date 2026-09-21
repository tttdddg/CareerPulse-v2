"""ProfileAgent orchestration for the Stage 3 unified student profile."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .base_agent import AgentResult, BaseAgent
from ..core.llm_client import llm_client
from ..orchestrator.career_state import CareerState
from ..services.profile_service import ProfileEvidenceExtraction, ProfileService


_PROMPT_DIR = Path(__file__).resolve().parents[3] / "prompts" / "profile_agent"
_DEFAULT_SYSTEM_PROMPT = """你是 CareerPulse ProfileAgent 的证据提取器。
只提取用户明确提供的信息，模型推断必须单独标记且不得作为事实或评分依据。
不得输出姓名、联系方式、证件号、student_id、完整度或竞争力分数。
能力候选必须能由输入证据直接支持；最终合并和评分由 ProfileService 完成。"""
_DEFAULT_USER_TEMPLATE = """请从以下匿名化画像材料提取结构化证据：
<profile_material>{{profile_material}}</profile_material>"""


class ProfileAgent(BaseAgent):
    """Merge facts, extract candidates, and build an evidence-grounded profile."""

    name = "ProfileAgent"
    required_fields: tuple[str, ...] = ()
    output_fields = ("student_profile",)
    tool_name = "analyze_student_profile"

    def __init__(
        self,
        client: Any | None = None,
        service: ProfileService | None = None,
    ) -> None:
        self._llm_client = client if client is not None else llm_client
        self._service = service or ProfileService()

    async def run(self, state: CareerState) -> AgentResult:
        result = await super().run(state)
        if result.status == "success":
            summary = "ProfileAgent 统一画像生成完成"
        elif result.status == "partial":
            summary = "ProfileAgent 使用证据规则 fallback 生成可用画像"
        else:
            summary = "ProfileAgent 画像生成失败，后续 Agent 继续"
        result.summary = summary
        if state.agent_logs and state.agent_logs[-1].agent_name == self.name:
            state.agent_logs[-1].summary = summary
        return result

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        if not self._has_profile_input(state):
            raise ValueError("ProfileAgent input is empty")
        messages = self._build_messages(state)
        candidates = await self._llm_client.generate_structured(
            messages,
            ProfileEvidenceExtraction,
            temperature=0.1,
        )
        profile = self._service.build_profile(
            session_id=state.session_id,
            user_id=state.user_id,
            student_input=state.student_input,
            historical_profile=state.student_profile,
            llm_candidates=candidates,
            fallback_used=False,
        )
        return {"student_profile": profile.model_dump(mode="json")}

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        profile = self._service.build_profile(
            session_id=state.session_id,
            user_id=state.user_id,
            student_input=state.student_input,
            historical_profile=state.student_profile,
            llm_candidates=None,
            fallback_used=True,
        )
        return {"student_profile": profile.model_dump(mode="json")}

    def _build_messages(self, state: CareerState) -> list[dict[str, str]]:
        system_prompt, user_template = self._prompt_templates()
        source = dict(state.student_input or {})
        merged = self._service.merge_profile_data(source, state.student_profile or {})
        prompt_payload = {
            "basic_info": merged["basic_info"],
            "resume_text": merged["resume_text"],
            "skills": merged["skills"],
            "education": source.get("education"),
            "projects": merged["projects"],
            "internships": merged["internships"],
            "work_experience": merged["work_experience"],
            "competitions": merged["competitions"],
            "certificates": merged["certificates"],
            "supplementary_info": merged["supplementary_info"],
            # A historical snapshot can originate outside this Agent.  Keep
            # identity fields out of the prompt even when a caller supplied
            # an older, less strict snapshot.
            "historical_profile": self._history_without_identity(
                state.student_profile
            ),
        }
        serialized = json.dumps(prompt_payload, ensure_ascii=False, separators=(",", ":"))
        user_prompt = user_template.replace(
            "{{profile_material}}", self._escape_prompt_block(serialized)
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _build_prompts(self, state: CareerState) -> tuple[str, str]:
        """Compatibility helper retained for prompt safety tests."""

        messages = self._build_messages(state)
        return messages[0]["content"], messages[1]["content"]

    @staticmethod
    @lru_cache(maxsize=1)
    def _prompt_templates() -> tuple[str, str]:
        try:
            system_prompt = (_PROMPT_DIR / "system.txt").read_text(encoding="utf-8")
            user_template = (_PROMPT_DIR / "user_template.txt").read_text(encoding="utf-8")
        except OSError:
            system_prompt = _DEFAULT_SYSTEM_PROMPT
            user_template = _DEFAULT_USER_TEMPLATE
        if "{{profile_material}}" not in user_template:
            raise RuntimeError("ProfileAgent user template is missing profile_material")
        return system_prompt, user_template

    @staticmethod
    def _escape_prompt_block(value: str) -> str:
        return value.replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _has_profile_input(state: CareerState) -> bool:
        return bool(state.student_input or state.student_profile)

    @staticmethod
    def _history_without_identity(
        profile: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if profile is None:
            return None
        safe = dict(profile)
        safe.pop("user_id", None)
        basic_info = safe.get("basic_info")
        if isinstance(basic_info, dict):
            safe["basic_info"] = {
                key: value for key, value in basic_info.items() if key != "name"
            }
        return safe

    def _input_summary(self, state: CareerState) -> str:
        source = state.student_input or {}
        form = source.get("form_fields") or source.get("form_data") or {}
        experience_fields = (
            "projects", "internships", "work_experience", "competitions", "certificates"
        )
        return (
            f"简历={'已提供' if source.get('resume_text') else '未提供'}; "
            f"表单字段数={len(form) if isinstance(form, dict) else 0}; "
            f"经历来源数={sum(bool(source.get(name)) for name in experience_fields)}; "
            f"历史画像={'已提供' if state.student_profile else '未提供'}"
        )


__all__ = ["ProfileAgent"]
