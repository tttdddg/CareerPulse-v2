"""Real PathAgent calling PathService with optional LLM stage enhancement."""

from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .base_agent import AgentResult, BaseAgent
from ..core.llm_client import llm_client
from ..orchestrator.career_state import CareerState, ToolCallLog
from ..repositories.career_graph_repository import (
    CareerGraphProvider,
    CareerGraphProviderError,
)
from ..services.path_service import GraphLoadMetadata, PathService


_GRAPH_LOAD_METADATA: ContextVar[GraphLoadMetadata | None] = ContextVar(
    "path_graph_load_metadata",
    default=None,
)


class _LLMStageEnhancement(BaseModel):
    """Structured output for LLM stage description generation."""

    model_config = ConfigDict(extra="forbid")

    stages: list[dict[str, Any]] = Field(default_factory=list)


class PathAgent(BaseAgent):
    """Call PathService deterministically, optionally enhance with LLM."""

    name = "PathAgent"
    service_name = "PathService"
    required_fields = ("student_profile", "job_profile", "match_result")
    output_fields = ("path_plan", "learning_plan", "career_roadmap")
    tool_name = "recommend_career_path"

    def __init__(
        self,
        client: Any | None = None,
        service: PathService | None = None,
    ) -> None:
        self._llm_client = client if client is not None else llm_client
        self._service = service or PathService()
        self._runtime_provider_configurable = service is None

    def configure_graph_provider(self, provider: CareerGraphProvider) -> None:
        """Bind the runtime graph source before this Agent serves requests."""

        if self._runtime_provider_configurable:
            self._service.set_provider(provider)

    async def run(self, state: CareerState) -> AgentResult:
        token = _GRAPH_LOAD_METADATA.set(None)
        try:
            result = await super().run(state)
            metadata = _GRAPH_LOAD_METADATA.get()
            if metadata is not None and state.agent_logs:
                state.agent_logs[-1].tool_calls.insert(
                    0,
                    ToolCallLog(
                        tool_name="load_career_graph",
                        service_name=type(self._service.provider).__name__[:64],
                        input_summary=(
                            "target_type_key="
                            f"{(state.job_profile or {}).get('normalized_title', 'unknown')}"
                        ),
                        output_summary=(
                            f"data_source={metadata.data_source}; "
                            f"node_count={metadata.node_count}; "
                            f"edge_count={metadata.edge_count}"
                        ),
                        duration_ms=metadata.duration_ms,
                        status="success",
                    ),
                )
            return result
        finally:
            _GRAPH_LOAD_METADATA.reset(token)

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        flat_profile = self._flatten_profile(state.student_profile)
        preferences = self._extract_preferences(state.student_profile)
        result, metadata = self._service.calculate_with_metadata(
            student_profile=flat_profile,
            target_job_profile=state.job_profile,
            match_result=state.match_result,
            user_preferences=preferences,
            horizon_years=3,
        )
        _GRAPH_LOAD_METADATA.set(metadata)
        try:
            await self._enhance_with_llm(result)
        except Exception:
            pass
        return {
            "path_plan": self._build_path_plan(result, state),
            "learning_plan": self._build_learning_plan(result),
            "career_roadmap": result,
        }

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        if isinstance(error, CareerGraphProviderError):
            raise error
        flat_profile = self._flatten_profile(state.student_profile)
        preferences = self._extract_preferences(state.student_profile)
        try:
            result, metadata = self._service.calculate_with_metadata(
                student_profile=flat_profile or {},
                target_job_profile=state.job_profile or {},
                match_result=state.match_result or {},
                user_preferences=preferences,
                horizon_years=3,
            )
            _GRAPH_LOAD_METADATA.set(metadata)
        except Exception:
            result = self._build_fallback_result(state)
        return {
            "path_plan": self._build_path_plan(result, state),
            "learning_plan": self._build_learning_plan(result),
            "career_roadmap": result,
        }

    async def _enhance_with_llm(self, result: dict[str, Any]) -> None:
        """Enhance CareerStage objectives/suggested_actions/completion_criteria via LLM."""
        three_year = result.get("three_year_roadmap", {})
        stages = three_year.get("stages", [])
        if not stages:
            return

        clean_stages = [
            {
                "stage_index": s.get("stage_index"),
                "target_role": s.get("target_role"),
                "key_abilities": s.get("key_abilities", []),
            }
            for s in stages
        ]

        system_prompt = (
            "你是一个职业规划顾问。请根据以下路径阶段数据，"
            "为每个阶段生成具体目标、行动建议和完成标准。"
            "保持简洁、可操作。"
        )
        user_prompt = json.dumps({"路径阶段": clean_stages}, ensure_ascii=False)

        enhanced = await self._llm_client.generate_structured(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            _LLMStageEnhancement,
            temperature=0.3,
        )

        stage_map = {item.get("stage_index"): item for item in enhanced.stages}
        for stage in stages:
            idx = stage.get("stage_index")
            llm_item = stage_map.get(idx)
            if llm_item is None:
                continue
            if llm_item.get("objectives"):
                stage["objectives"] = llm_item["objectives"]
            if llm_item.get("suggested_actions"):
                stage["suggested_actions"] = llm_item["suggested_actions"]
            if llm_item.get("completion_criteria"):
                stage["completion_criteria"] = llm_item["completion_criteria"]

    @staticmethod
    def _build_path_plan(result: dict[str, Any], state: CareerState) -> dict[str, Any]:
        """Project PathResult to the backward-compatible path_plan format."""
        target_job = (state.job_profile or {}).get("title", "")
        three_year = result.get("three_year_roadmap", {})
        five_year = result.get("five_year_roadmap", {})

        def _phase(stage: dict[str, Any]) -> dict[str, Any]:
            return {
                "phase": stage.get("stage_index"),
                "duration_months": stage.get("duration_months", 12),
                "target_role": stage.get("target_role", ""),
                "required_abilities": stage.get("key_abilities", []),
                "tasks": stage.get("suggested_actions", []),
                "milestone": stage.get("completion_criteria", ""),
            }

        recommended = result.get("recommended_path")
        alternatives = result.get("alternative_paths", [])
        alt_paths = []
        if recommended:
            rec_nodes = recommended.get("nodes", [])
            alt_paths.append({
                "type": recommended.get("path_type", "direct"),
                "target_role": rec_nodes[-1].get("job_title", "") if rec_nodes else "",
                "score": recommended.get("score", {}).get("total_score", 0.0),
                "reason": "推荐路径",
            })
        for alt in alternatives:
            alt_nodes = alt.get("nodes", [])
            alt_paths.append({
                "type": alt.get("path_type", "direct"),
                "target_role": alt_nodes[-1].get("job_title", "") if alt_nodes else "",
                "score": alt.get("score", {}).get("total_score", 0.0),
                "reason": "备选路径",
            })

        return {
            "target_job": target_job,
            "plan_3year": {
                "phases": [_phase(s) for s in three_year.get("stages", [])],
                "total_score": three_year.get("total_score", 0.0),
            },
            "plan_5year": {
                "phases": [_phase(s) for s in five_year.get("stages", [])],
                "total_score": five_year.get("total_score", 0.0),
            },
            "alternative_paths": alt_paths,
            "path_algorithm_version": "graph-search-v1",
        }

    @staticmethod
    def _build_learning_plan(result: dict[str, Any]) -> dict[str, Any]:
        """Build learning_plan from CareerStage data."""
        three_year = result.get("three_year_roadmap", {})
        stages = three_year.get("stages", [])

        phases = []
        for stage in stages:
            idx = stage.get("stage_index", 1)
            target_role = stage.get("target_role", "")
            actions = stage.get("suggested_actions", [])
            key_abilities = stage.get("key_abilities", [])
            tasks = []
            for i, action in enumerate(actions):
                ability = key_abilities[min(i, len(key_abilities) - 1)] if key_abilities else ""
                tasks.append({
                    "task_id": f"phase-{idx}-task-{i + 1}",
                    "description": action,
                    "target_ability": ability,
                    "estimated_hours": 40,
                    "resources": [],
                })
            if not tasks:
                tasks.append({
                    "task_id": f"phase-{idx}-task-1",
                    "description": f"围绕{target_role}积累可验证成果",
                    "target_ability": key_abilities[0] if key_abilities else "通用能力",
                    "estimated_hours": 40,
                    "resources": [],
                })
            phases.append({
                "phase": idx,
                "title": f"第{idx}阶段：{target_role}",
                "tasks": tasks,
            })

        return {
            "phases": phases,
            "certificate_suggestions": [],
            "project_suggestions": [
                f"完成{s.get('target_role', '')}相关的可验证项目"
                for s in stages
            ] or ["完成一个可展示的项目"],
        }

    @staticmethod
    def _build_fallback_result(state: CareerState) -> dict[str, Any]:
        """Build a minimal valid PathResult-shaped dict when Service cannot run."""
        target_job = (state.job_profile or {}).get("title", "")
        empty_roadmap = {
            "target_job": target_job,
            "horizon_years": 3,
            "stages": [],
            "selected_path_id": None,
            "total_score": None,
            "path_algorithm_version": "graph-search-v1",
        }
        return {
            "status": "insufficient_data",
            "requested_horizon_years": 3,
            "candidate_paths": [],
            "recommended_path": None,
            "alternative_paths": [],
            "path_scores": {},
            "three_year_roadmap": empty_roadmap,
            "five_year_roadmap": {**empty_roadmap, "horizon_years": 5},
            "assumptions": ["fallback: insufficient input data"],
            "risks": [],
            "confidence": 0.0,
            "data_quality_flags": ["fallback_empty_result"],
            "calculation_version": "deterministic-path-v1",
        }

    @staticmethod
    def _flatten_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
        """Flatten unified ability_dimensions to flat abilities list
        compatible with profile_schema.StudentProfile."""
        if not profile:
            return {"abilities": [], "student_id": None, "name": "匿名用户",
                    "basic_info": {}, "competitiveness_score": 0.0,
                    "completeness": None, "missing_fields": None}

        result: dict[str, Any] = {}

        if "abilities" in profile:
            result["abilities"] = profile["abilities"]
        else:
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
            result["abilities"] = abilities

        result["student_id"] = profile.get("student_id")
        result["name"] = (profile.get("name")
                         or (profile.get("basic_info") or {}).get("name")
                         or "匿名用户")

        basic = dict(profile.get("basic_info", {}))
        basic.pop("city", None)
        basic.pop("name", None)
        result["basic_info"] = basic

        cscore = profile.get("career_competitiveness_score")
        result["competitiveness_score"] = cscore if cscore is not None else 0.0

        completeness = profile.get("profile_completeness")
        if completeness is not None:
            result["completeness"] = completeness
        missing_fields = profile.get("missing_fields")
        if missing_fields is not None:
            result["missing_fields"] = missing_fields

        return result

    @staticmethod
    def _extract_preferences(profile: dict[str, Any] | None) -> dict[str, Any]:
        """Extract user preferences from unified student_profile basic_info."""
        if not profile:
            return {}
        basic = profile.get("basic_info", {})
        return {
            "target_industry": basic.get("target_industry"),
            "target_job": basic.get("target_job"),
            "desired_city": basic.get("city"),
        }


__all__ = ["PathAgent"]
