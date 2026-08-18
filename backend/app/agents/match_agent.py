"""Real MatchAgent calling MatchService with optional LLM suggestion text."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .base_agent import BaseAgent
from ..core.llm_client import llm_client
from ..orchestrator.career_state import CareerState
from ..services.match_service import MatchService


class _LLMEnhancement(BaseModel):
    """Simple structured output for LLM suggestion generation."""

    model_config = ConfigDict(extra="forbid")

    suggestions: dict[str, str] = Field(default_factory=dict)
    strengths_summary: str = ""


class MatchAgent(BaseAgent):
    """Call MatchService deterministically, optionally enhance with LLM."""

    name = "MatchAgent"
    required_fields = ("student_profile", "job_profile")
    output_fields = ("match_result",)
    tool_name = "calculate_job_match"

    def __init__(
        self,
        client: Any | None = None,
        service: MatchService | None = None,
    ) -> None:
        self._llm_client = client if client is not None else llm_client
        self._service = service or MatchService()

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        flat_profile = self._flatten_profile(state.student_profile)
        result = self._service.calculate(
            student_profile=flat_profile,
            job_profile=state.job_profile,
        )
        try:
            await self._enhance_with_llm(result)
        except Exception:
            pass
        return {"match_result": result}

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        flat_profile = self._flatten_profile(state.student_profile)
        result = self._service.calculate(
            student_profile=flat_profile,
            job_profile=state.job_profile or {},
        )
        return {"match_result": result}

    async def _enhance_with_llm(self, result: dict[str, Any]) -> None:
        """Fill gap_analysis[].suggestion and strengths via LLM."""
        gaps = [
            {"tag": item.get("dimension", ""), "gap": item.get("gap", 0), "priority": item.get("priority", 0)}
            for item in result.get("skill_gaps", [])
        ]
        strengths = result.get("strengths", [])
        if not gaps and not strengths:
            return

        system_prompt = (
            "你是一个职业发展顾问。请根据以下能力缺口和优势，"
            "为每个缺口写一句提升建议（一句话），并为优势写一句说明。"
            "保持简洁、专业、可操作。"
        )
        user_prompt = json.dumps({"能力缺口": gaps, "优势": strengths}, ensure_ascii=False)

        enhanced = await self._llm_client.generate_structured(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            _LLMEnhancement,
            temperature=0.3,
        )

        for item in result.get("gap_analysis", []):
            tag = item.get("item", "")
            if tag in enhanced.suggestions:
                item["suggestion"] = enhanced.suggestions[tag]

        if enhanced.strengths_summary:
            existing = result.get("strengths", [])
            result["strengths"] = [enhanced.strengths_summary] + [
                s for s in existing if s != enhanced.strengths_summary
            ]

    @staticmethod
    def _flatten_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
        """Flatten unified ability_dimensions to flat abilities list."""
        if not profile:
            return {"abilities": []}

        if "abilities" in profile:
            return {
                "abilities": profile["abilities"],
                "completeness": profile.get("completeness"),
                "missing_fields": profile.get("missing_fields"),
            }

        seen: set[str] = set()
        abilities = []
        for dim in profile.get("ability_dimensions", []):
            dim_level = dim.get("level", 1)
            dim_confidence = dim.get("confidence")
            evidence_list = dim.get("evidence", [])
            evidence_text = "; ".join(evidence_list) if evidence_list else None
            for tag in dim.get("tags", []):
                if tag in seen:
                    continue
                seen.add(tag)
                abilities.append({
                    "tag": tag,
                    "level": dim_level,
                    "confidence": dim_confidence,
                    "evidence": evidence_text,
                })

        result: dict[str, Any] = {"abilities": abilities}
        completeness = profile.get("profile_completeness")
        if completeness is not None:
            result["completeness"] = completeness
        missing_fields = profile.get("missing_fields")
        if missing_fields is not None:
            result["missing_fields"] = missing_fields
        return result


__all__ = ["MatchAgent"]