"""Deterministic career-graph search, scoring, and roadmap generation."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from ..models import CareerGraphEdge, CareerGraphNode
from ..repositories.career_graph_repository import (
    CareerGraphProvider,
    CareerGraphProviderDataError,
    CareerGraphProviderResult,
)
from ..schemas.job_schema import JobProfile
from ..schemas.match_schema import MatchResult
from ..schemas.path_schema import (
    CandidatePath,
    CareerRoadmap,
    PathRequest,
    PathResult,
    UserPreferences,
)
from ..schemas.profile_schema import StudentProfile
from .career_graph_repository import (
    CareerGraphRepository,
    JsonCareerGraphProvider,
)
from .match_service import MatchService
from .path_config import (
    CALCULATION_VERSION,
    DATA_CONFIDENCE_PENALTIES,
    ENTRY_EXPERIENCE_THRESHOLD,
    LEVEL_ORDER,
    MAX_CANDIDATE_PATHS,
    MAX_CONSECUTIVE_LATERAL,
    MAX_PATH_NODES,
    MIN_PATH_DATA_CONFIDENCE,
    PATH_ALGORITHM_VERSION,
    RISK_VALUES,
    SCORE_WEIGHTS,
)


@dataclass(frozen=True)
class GraphLoadMetadata:
    """Privacy-safe provider facts for the PathAgent tool log."""

    data_source: str
    node_count: int
    edge_count: int
    fallback_used: bool
    demo_mode: bool
    duration_ms: int


class PathService:
    """Create stable graph-backed candidate paths and annual roadmaps."""

    def __init__(
        self,
        repository: CareerGraphRepository | None = None,
        match_service: MatchService | None = None,
        *,
        provider: CareerGraphProvider | None = None,
    ) -> None:
        if repository is not None and provider is not None:
            raise ValueError("inject either career graph provider or repository")
        # Repository injection remains for focused algorithm tests. Runtime
        # composition injects a source-policy Provider instead.
        self._repository_override = repository
        self.provider = provider or JsonCareerGraphProvider(demo_mode=True)
        self.match_service = match_service or MatchService()

    @property
    def repository(self) -> CareerGraphRepository:
        """Compatibility view for tests that exercise private search helpers."""

        if self._repository_override is not None:
            return self._repository_override
        result = self.provider.load()
        return CareerGraphRepository.from_provider_result(result)

    def set_provider(self, provider: CareerGraphProvider) -> None:
        """Configure one runtime source policy before requests are served."""

        self.provider = provider
        self._repository_override = None

    def calculate(
        self,
        student_profile: StudentProfile | Mapping[str, Any],
        target_job_profile: JobProfile | Mapping[str, Any],
        match_result: MatchResult | Mapping[str, Any],
        user_preferences: UserPreferences | Mapping[str, Any] | None = None,
        horizon_years: int = 3,
    ) -> dict[str, Any]:
        result, _ = self.calculate_with_metadata(
            student_profile,
            target_job_profile,
            match_result,
            user_preferences,
            horizon_years,
        )
        return result

    def calculate_with_metadata(
        self,
        student_profile: StudentProfile | Mapping[str, Any],
        target_job_profile: JobProfile | Mapping[str, Any],
        match_result: MatchResult | Mapping[str, Any],
        user_preferences: UserPreferences | Mapping[str, Any] | None = None,
        horizon_years: int = 3,
    ) -> tuple[dict[str, Any], GraphLoadMetadata]:
        request = PathRequest.model_validate(
            {
                "student_profile": self._dump(student_profile),
                "target_job_profile": self._dump(target_job_profile),
                "match_result": self._dump(match_result),
                "user_preferences": self._dump(user_preferences or {}),
                "horizon_years": horizon_years,
            }
        )
        load_started = perf_counter()
        provider_result = self._load_graph()
        try:
            repository = (
                self._repository_override
                or CareerGraphRepository.from_provider_result(provider_result)
            )
        except ValueError:
            raise CareerGraphProviderDataError(
                "career graph snapshot failed whole-graph validation"
            ) from None
        metadata = GraphLoadMetadata(
            data_source=provider_result.data_source,
            node_count=len(provider_result.nodes),
            edge_count=len(provider_result.edges),
            fallback_used=provider_result.fallback_used,
            demo_mode=provider_result.demo_mode,
            duration_ms=max(0, round((perf_counter() - load_started) * 1000)),
        )
        return self._calculate(request, repository).model_dump(), metadata

    def _load_graph(self) -> CareerGraphProviderResult:
        if self._repository_override is not None:
            return CareerGraphProviderResult(
                nodes=list(self._repository_override.nodes),
                edges=list(self._repository_override.edges),
                data_source="demo_json",
                fallback_used=False,
                demo_mode=True,
            )
        return self.provider.load()

    def _calculate(
        self,
        request: PathRequest,
        repository: CareerGraphRepository,
    ) -> PathResult:
        assumptions = [
            "候选岗位仅来自已初始化职业图谱，不创建推断节点",
            "路径数值由deterministic PathService计算，不使用LLM",
            "城市数据缺失时地域因素不参与评分",
            "阶段任务仅表示行动方向，不生成课程、训练或资源执行计划",
        ]
        global_flags: list[str] = []
        global_risks: list[str] = []
        if not self._match_result_matches_target(
            request.match_result, request.target_job_profile
        ):
            return self._empty_result(
                request,
                "insufficient_data",
                assumptions,
                ["输入的MatchResult与目标岗位能力向量不一致"],
                ["match_result_target_mismatch"],
            )
        preferences = self._effective_preferences(request)
        if preferences.desired_city is None:
            global_flags.append("desired_city_not_provided")

        years_experience = request.student_profile.basic_info.years_of_experience or 0.0
        starts = repository.entry_roles(
            include_junior=years_experience >= ENTRY_EXPERIENCE_THRESHOLD
        )
        if not starts:
            return self._empty_result(
                request,
                "no_reachable_path",
                assumptions,
                ["职业图谱中没有可用的entry/junior起点"],
                global_flags + ["no_entry_role_in_graph"],
            )

        try:
            start, start_match, start_flags = self._select_start(
                request.student_profile, starts, repository
            )
        except ValueError as error:
            return self._empty_result(
                request,
                "insufficient_data",
                assumptions,
                ["职业图谱起点缺少可验证的能力向量"],
                global_flags + [f"unresolved_start_data:{type(error).__name__}"],
            )
        global_flags.extend(start_flags)
        goal = repository.node_by_title(request.target_job_profile.normalized_title)
        fallback_target = False
        if goal is None:
            global_flags.append(
                f"target_not_in_graph:{request.target_job_profile.normalized_title}"
            )
            global_risks.append("目标岗位不在职业图谱中，推荐结果只能到达图内替代岗位")

        paths = self._search_paths(
            start.node_key, goal.node_key, repository=repository
        ) if goal else []
        if not paths:
            goal = self._fallback_goal(
                start,
                request.target_job_profile.industry,
                exclude_key=goal.node_key if goal else None,
                repository=repository,
            )
            fallback_target = goal is not None
            if goal is not None:
                global_flags.append(f"fallback_target_used:{goal.node_key}")
                paths = self._search_paths(
                    start.node_key, goal.node_key, repository=repository
                )
        if not paths:
            return self._empty_result(
                request,
                "no_reachable_path",
                assumptions,
                global_risks + ["从可进入岗位到目标或替代岗位均无可达路径"],
                global_flags + ["no_reachable_path"],
            )

        scored = []
        for path in paths:
            try:
                scored.append(
                    self._build_candidate(
                        path,
                        request,
                        preferences,
                        start_match,
                        goal,
                        fallback_target,
                        repository,
                    )
                )
            except ValueError:
                global_flags.append(f"candidate_unresolved_node_data:{'->'.join(path)}")
        if not scored:
            return self._empty_result(
                request,
                "insufficient_data",
                assumptions,
                global_risks + ["候选路径节点缺少可验证的能力向量"],
                global_flags + ["no_scorable_candidate_path"],
            )
        candidates = self._select_candidate_types(scored, preferences)
        candidates.sort(
            key=lambda item: (
                -item.score.total_score,
                item.time_estimate_months,
                item.path_id,
            )
        )
        candidates = candidates[:MAX_CANDIDATE_PATHS]
        present_types = {item.path_type for item in candidates}
        for path_type in ("direct", "robust", "extension"):
            if path_type not in present_types:
                global_flags.append(f"candidate_type_unavailable:{path_type}")
        recommended = candidates[0] if candidates else None
        if recommended is None:
            return self._empty_result(
                request,
                "no_reachable_path",
                assumptions,
                global_risks + ["候选路径均被可行性规则过滤"],
                global_flags + ["all_paths_filtered"],
            )

        three_year = self._roadmap(request, recommended, 3, repository)
        five_year = self._roadmap(request, recommended, 5, repository)
        confidence = round(
            (recommended.score.data_confidence + request.match_result.confidence) / 2.0,
            4,
        )
        if confidence < MIN_PATH_DATA_CONFIDENCE:
            global_flags.append("low_path_result_confidence")
        risks = self._dedupe(
            global_risks
            + self._path_risks(recommended)
            + [
                "路线时间是基于图谱典型时长和转移成本的规则估计，不代表招聘承诺"
            ]
        )
        result = PathResult(
            status="success",
            requested_horizon_years=request.horizon_years,
            candidate_paths=candidates,
            recommended_path=recommended,
            alternative_paths=candidates[1:],
            path_scores={item.path_id: item.score for item in candidates},
            three_year_roadmap=three_year,
            five_year_roadmap=five_year,
            assumptions=assumptions,
            risks=risks,
            confidence=confidence,
            data_quality_flags=self._dedupe(
                global_flags
                + [flag for item in candidates for flag in item.data_quality_flags]
            ),
            calculation_version=CALCULATION_VERSION,
        )
        return result

    def _select_start(
        self,
        student: StudentProfile,
        starts: list[CareerGraphNode],
        repository: CareerGraphRepository,
    ) -> tuple[CareerGraphNode, MatchResult, list[str]]:
        ranked: list[
            tuple[float, float, float, float, str, CareerGraphNode, MatchResult, list[str]]
        ] = []
        skipped_flags: list[str] = []
        for raw_node in starts:
            try:
                node, flags = repository.resolved_node(raw_node.node_key)
                match = self._match_node(student, node)
            except ValueError:
                skipped_flags.append(f"entry_node_unresolved:{raw_node.node_key}")
                continue
            gap_cost = sum(item.gap * item.difficulty for item in match.skill_gaps)
            positive_weight = sum(
                item.weight for item in match.dimension_matches if item.weight > 0.0
            )
            observed_weight = sum(
                item.weight
                for item in match.dimension_matches
                if item.weight > 0.0 and item.student_level is not None
            )
            coverage = observed_weight / positive_weight if positive_weight else 0.0
            ranked.append(
                (
                    -coverage,
                    gap_cost,
                    -match.confidence,
                    -match.overall_score,
                    node.node_key,
                    node,
                    match,
                    flags,
                )
            )
        if not ranked:
            raise ValueError("no entry role has a resolvable ability vector")
        _, _, _, _, _, node, match, flags = min(ranked, key=lambda item: item[:5])
        return node, match, skipped_flags + flags

    def _search_paths(
        self,
        start_key: str,
        goal_key: str,
        *,
        repository: CareerGraphRepository | None = None,
    ) -> list[list[str]]:
        graph = repository or self.repository
        max_nodes = min(MAX_PATH_NODES, len(graph.nodes))
        found: list[list[str]] = []

        def dfs(
            current: str,
            path: list[str],
            visited: set[str],
            lateral_run: int,
        ) -> None:
            if current == goal_key:
                found.append(path.copy())
                return
            if len(path) >= max_nodes:
                return
            for edge in graph.outgoing_edges(current):
                if edge.target_key in visited:
                    continue
                next_lateral = lateral_run + 1 if edge.relation_type == "lateral" else 0
                if next_lateral > MAX_CONSECUTIVE_LATERAL:
                    continue
                dfs(
                    edge.target_key,
                    path + [edge.target_key],
                    visited | {edge.target_key},
                    next_lateral,
                )

        dfs(start_key, [start_key], {start_key}, 0)
        return sorted(found, key=lambda item: (len(item), tuple(item)))

    def _fallback_goal(
        self,
        start: CareerGraphNode,
        target_industry: str,
        *,
        exclude_key: str | None,
        repository: CareerGraphRepository,
    ) -> CareerGraphNode | None:
        reachable = repository.reachable_nodes(start.node_key, MAX_PATH_NODES)
        options = [
            node
            for node in reachable
            if node.node_key not in {exclude_key, start.node_key}
            and node.industry == target_industry
        ]
        if not options:
            options = [
                node
                for node in reachable
                if node.node_key not in {exclude_key, start.node_key}
                and node.industry == start.industry
            ]
        return max(
            options,
            key=lambda item: (LEVEL_ORDER[item.level_range], item.node_key),
            default=None,
        )

    def _build_candidate(
        self,
        node_keys: list[str],
        request: PathRequest,
        preferences: UserPreferences,
        start_match: MatchResult,
        goal: CareerGraphNode,
        fallback_target: bool,
        repository: CareerGraphRepository,
    ) -> CandidatePath:
        nodes: list[CareerGraphNode] = []
        flags: list[str] = []
        node_matches: list[MatchResult] = []
        for key in node_keys:
            node, node_flags = repository.resolved_node(key)
            nodes.append(node)
            flags.extend(node_flags)
            node_match = (
                request.match_result
                if node.job_title == request.target_job_profile.normalized_title
                else self._match_node(request.student_profile, node)
            )
            node_matches.append(node_match)
            if node_match.missing_skills:
                flags.append(f"node_match_has_unknown_skills:{node.node_key}")
        edges = [
            next(
                edge
                for edge in repository.outgoing_edges(nodes[index].node_key)
                if edge.target_key == nodes[index + 1].node_key
            )
            for index in range(len(nodes) - 1)
        ]
        raw_path_type = "extension" if any(edge.relation_type == "lateral" for edge in edges) else "direct"
        growth = round(sum(edge.growth_value for edge in edges), 4)
        transfer = round(sum(edge.transfer_cost for edge in edges), 4)
        gap_cost = round(
            sum(
                gap.gap * gap.difficulty
                for node_match in node_matches
                for gap in node_match.skill_gaps
            ),
            4,
        )
        base = round(growth - transfer - gap_cost, 4)
        preference = self._preference_adjustment(nodes, raw_path_type, preferences)
        continuity = self._industry_continuity(edges)
        region_fit = self._region_fit(nodes, preferences.desired_city)
        if region_fit is None:
            flags.append("city_data_unavailable")
        risk_units = sum(RISK_VALUES[node.risk_level or "medium"] for node in nodes)
        risk_units += sum(RISK_VALUES[edge.risk_level] for edge in edges)
        risk_penalty = round(risk_units * SCORE_WEIGHTS["risk"], 4)
        target_consistency = self._target_consistency(
            nodes[-1], request.target_job_profile, fallback_target
        )
        data_confidence = self._data_confidence(flags, fallback_target)
        adjusted = (
            base
            + preference
            + continuity * SCORE_WEIGHTS["industry_continuity"]
            + (region_fit or 0.0) * SCORE_WEIGHTS["region_fit"]
            - risk_penalty
        )
        total = round(adjusted * target_consistency, 4)
        path_id = self._path_id(node_keys)
        if data_confidence < MIN_PATH_DATA_CONFIDENCE:
            flags.append("low_path_data_confidence")
        time_months = max(
            1,
            round(
                sum(repository.node_duration(node) for node in nodes)
                + transfer * SCORE_WEIGHTS["transfer_months"]
            ),
        )
        return CandidatePath(
            path_id=path_id,
            path_type=raw_path_type,
            nodes=nodes,
            edges=edges,
            target_node_key=nodes[-1].node_key,
            fallback_target=fallback_target,
            time_estimate_months=time_months,
            score={
                "current_match_score": start_match.overall_score,
                "growth_value": growth,
                "transfer_cost": transfer,
                "ability_gap_cost": gap_cost,
                "base_score": base,
                "preference_adjustment": preference,
                "industry_continuity": continuity,
                "region_fit": region_fit,
                "risk_penalty": risk_penalty,
                "target_consistency": target_consistency,
                "data_confidence": data_confidence,
                "total_score": total,
            },
            data_quality_flags=self._dedupe(flags),
        )

    def _select_candidate_types(
        self, candidates: list[CandidatePath], preferences: UserPreferences
    ) -> list[CandidatePath]:
        if not candidates:
            return []
        selected: list[CandidatePath] = []
        used: set[str] = set()

        def add(candidate: CandidatePath, path_type: str) -> None:
            if candidate.path_id not in used:
                selected.append(self._with_path_type(candidate, path_type, preferences))
                used.add(candidate.path_id)

        shortest = min(len(item.nodes) for item in candidates)
        direct_options = [item for item in candidates if len(item.nodes) == shortest]
        add(self._best(direct_options), "direct")
        robust_options = sorted(
            [
                item
                for item in candidates
                if all(edge.risk_level == "low" for edge in item.edges)
                and all((node.risk_level or "medium") == "low" for node in item.nodes)
            ],
            key=lambda item: (
                item.score.risk_penalty,
                item.score.transfer_cost,
                -item.score.total_score,
                item.path_id,
            ),
        )
        for item in robust_options:
            if item.path_id not in used:
                add(item, "robust")
                break
        extension_options = [
            item
            for item in candidates
            if any(edge.relation_type == "lateral" for edge in item.edges)
            and item.path_id not in used
        ]
        if extension_options:
            add(self._best(extension_options), "extension")
        for item in sorted(
            candidates,
            key=lambda item: (-item.score.total_score, item.time_estimate_months, item.path_id),
        ):
            if len(selected) >= MAX_CANDIDATE_PATHS:
                break
            if item.path_id not in used:
                add(item, item.path_type)
        return selected

    def _with_path_type(
        self,
        candidate: CandidatePath,
        path_type: str,
        preferences: UserPreferences,
    ) -> CandidatePath:
        preference = self._preference_adjustment(candidate.nodes, path_type, preferences)
        score = candidate.score.model_copy(
            update={
                "preference_adjustment": preference,
                "total_score": round(
                    (
                        candidate.score.base_score
                        + preference
                        + candidate.score.industry_continuity
                        * SCORE_WEIGHTS["industry_continuity"]
                        + (candidate.score.region_fit or 0.0)
                        * SCORE_WEIGHTS["region_fit"]
                        - candidate.score.risk_penalty
                    )
                    * candidate.score.target_consistency,
                    4,
                ),
            }
        )
        return candidate.model_copy(update={"path_type": path_type, "score": score})

    def _roadmap(
        self,
        request: PathRequest,
        path: CandidatePath,
        years: int,
        repository: CareerGraphRepository,
    ) -> CareerRoadmap:
        stages = []
        cumulative = 0
        schedule: list[tuple[int, CareerGraphNode]] = []
        for node in path.nodes:
            cumulative += repository.node_duration(node)
            schedule.append((cumulative, node))
        for year in range(1, years + 1):
            boundary = year * 12
            node = next((item for month, item in schedule if boundary <= month), path.nodes[-1])
            match = (
                request.match_result
                if node.job_title == request.target_job_profile.normalized_title
                else self._match_node(request.student_profile, node)
            )
            key_skills = [
                item.tag
                for item in sorted(
                    node.required_skills or [],
                    key=lambda item: (-item.weight, item.tag),
                )[:4]
            ]
            gaps = match.skill_gaps[:3]
            focus = [item.dimension for item in gaps] or key_skills[:2]
            maturity = self._year_maturity(year, years, node == path.nodes[-1])
            risks = []
            if node.risk_level in {"medium", "high"}:
                risks.append(f"{node.job_title}节点风险等级为{node.risk_level}")
            if any(flag.startswith("required_ability_not_provided") for flag in match.data_quality_flags):
                risks.append("部分岗位能力在学生画像中未提供，阶段差距仍需补充证据确认")
            stages.append(
                {
                    "stage_index": year,
                    "year_label": f"第{year}年",
                    "duration_months": 12,
                    "target_role": node.job_title,
                    "target_node_key": node.node_key,
                    "objectives": [
                        f"{maturity}{node.job_title}的核心职责边界",
                        f"使{('、'.join(focus)) if focus else '核心能力'}达到可验证的岗位应用水平",
                    ],
                    "key_abilities": key_skills,
                    "current_gaps": gaps,
                    "suggested_actions": [
                        f"围绕{tag}承担可验证的项目或工作职责" for tag in (focus or key_skills[:2])
                    ] or [f"持续积累{node.job_title}相关的可验证成果"],
                    "completion_criteria": (
                        f"能够说明并展示{node.job_title}核心职责的可验证成果"
                    ),
                    "risks": risks,
                    "next_stage_condition": self._next_stage_condition(
                        year, years, node, path.nodes[-1]
                    ),
                }
            )
        return CareerRoadmap(
            target_job=request.target_job_profile.title,
            horizon_years=years,
            stages=stages,
            selected_path_id=path.path_id,
            total_score=path.score.total_score,
            path_algorithm_version=PATH_ALGORITHM_VERSION,
        )

    def _match_node(self, student: StudentProfile, node: CareerGraphNode) -> MatchResult:
        if node.required_skills is None:
            raise ValueError(f"career node {node.node_key} has unresolved required_skills")
        job = {
            "job_id": None,
            "title": node.job_title,
            "normalized_title": node.job_title,
            "industry": node.industry or "未知行业",
            "required_abilities": [item.model_dump() for item in node.required_skills],
            "soft_skills": [],
            "salary_range": None,
            "job_description": node.description,
        }
        return MatchResult.model_validate(self.match_service.calculate(student, job))

    @staticmethod
    def _match_result_matches_target(match: MatchResult, target: JobProfile) -> bool:
        expected = {
            item.tag: (item.required_level, round(item.weight, 8))
            for item in target.required_abilities
        }
        actual = {
            item.dimension: (item.required_level, round(item.weight, 8))
            for item in match.dimension_matches
        }
        return actual == expected

    @staticmethod
    def _effective_preferences(request: PathRequest) -> UserPreferences:
        basic = request.student_profile.basic_info
        return UserPreferences(
            target_industry=request.user_preferences.target_industry or basic.target_industry,
            target_job=request.user_preferences.target_job or basic.target_job,
            desired_city=request.user_preferences.desired_city,
            preferred_path_type=request.user_preferences.preferred_path_type,
        )

    @staticmethod
    def _preference_adjustment(
        nodes: list[CareerGraphNode], path_type: str, preferences: UserPreferences
    ) -> float:
        score = 0.0
        if preferences.target_industry and nodes[-1].industry == preferences.target_industry:
            score += SCORE_WEIGHTS["industry_preference"]
        if preferences.target_job and any(
            node.job_title == preferences.target_job for node in nodes
        ):
            score += SCORE_WEIGHTS["job_preference"]
        if preferences.preferred_path_type == path_type:
            score += SCORE_WEIGHTS["preferred_path_type"]
        return round(score, 4)

    @staticmethod
    def _industry_continuity(edges: list[CareerGraphEdge]) -> float:
        if not edges:
            return 1.0
        continuous = sum(
            1
            for edge in edges
            if edge.source_industry is not None
            and edge.source_industry == edge.target_industry
        )
        return round(continuous / len(edges), 4)

    @staticmethod
    def _region_fit(nodes: list[CareerGraphNode], desired_city: str | None) -> float | None:
        if desired_city is None or not any(node.cities for node in nodes):
            return None
        known_nodes = [node for node in nodes if node.cities]
        if not known_nodes:
            return None
        return round(
            sum(desired_city in (node.cities or []) for node in known_nodes) / len(known_nodes),
            4,
        )

    @staticmethod
    def _target_consistency(
        final: CareerGraphNode, target: JobProfile, fallback_target: bool
    ) -> float:
        if not fallback_target and final.job_title == target.normalized_title:
            return 1.0
        if final.industry == target.industry:
            return 0.5
        return 0.0

    @staticmethod
    def _data_confidence(flags: list[str], fallback_target: bool) -> float:
        confidence = 1.0
        confidence -= DATA_CONFIDENCE_PENALTIES["skill_fallback"] * sum(
            flag.startswith("node_skill_vector_fallback") for flag in flags
        )
        confidence -= DATA_CONFIDENCE_PENALTIES["risk_fallback"] * sum(
            flag.startswith("node_risk_default") for flag in flags
        )
        confidence -= DATA_CONFIDENCE_PENALTIES["unknown_node_skills"] * sum(
            flag.startswith("node_match_has_unknown_skills") for flag in flags
        )
        if fallback_target:
            confidence -= DATA_CONFIDENCE_PENALTIES["fallback_target"]
        return round(max(0.0, min(confidence, 1.0)), 4)

    @staticmethod
    def _path_id(node_keys: list[str]) -> str:
        digest = hashlib.sha256("->".join(node_keys).encode("utf-8")).hexdigest()[:12]
        return f"path-{digest}"

    @staticmethod
    def _best(candidates: list[CandidatePath]) -> CandidatePath:
        return min(
            candidates,
            key=lambda item: (-item.score.total_score, item.time_estimate_months, item.path_id),
        )

    @staticmethod
    def _path_risks(path: CandidatePath) -> list[str]:
        risks = []
        if any(edge.risk_level == "high" for edge in path.edges):
            risks.append("推荐路径包含高风险岗位转换边")
        if any(node.risk_level == "high" for node in path.nodes):
            risks.append("推荐路径包含高风险岗位节点")
        if path.fallback_target:
            risks.append("推荐路径使用图内替代目标，未直接到达原目标岗位")
        return risks

    @staticmethod
    def _year_maturity(year: int, horizon: int, at_target: bool) -> str:
        if year == 1:
            return "建立并验证"
        if year == horizon:
            return "巩固并扩展" if at_target else "推进并复核"
        return "深化并应用"

    @staticmethod
    def _next_stage_condition(
        year: int,
        horizon: int,
        current: CareerGraphNode,
        final: CareerGraphNode,
    ) -> str:
        if year == horizon:
            if current.node_key == final.node_key:
                return f"完成{current.job_title}年度目标后评估更高层级或横向机会"
            return f"当前规划期尚未到达{final.job_title}，后续年度继续推进图谱路径"
        return f"核心能力和职责成果通过复核后进入第{year + 1}年"

    def _empty_result(
        self,
        request: PathRequest,
        status: str,
        assumptions: list[str],
        risks: list[str],
        flags: list[str],
    ) -> PathResult:
        return PathResult(
            status=status,
            requested_horizon_years=request.horizon_years,
            candidate_paths=[],
            recommended_path=None,
            alternative_paths=[],
            path_scores={},
            three_year_roadmap=self._empty_roadmap(request.target_job_profile.title, 3),
            five_year_roadmap=self._empty_roadmap(request.target_job_profile.title, 5),
            assumptions=assumptions,
            risks=self._dedupe(risks),
            confidence=0.0,
            data_quality_flags=self._dedupe(flags),
            calculation_version=CALCULATION_VERSION,
        )

    @staticmethod
    def _empty_roadmap(target_job: str, years: int) -> CareerRoadmap:
        return CareerRoadmap(
            target_job=target_job,
            horizon_years=years,
            stages=[],
            selected_path_id=None,
            total_score=None,
            path_algorithm_version=PATH_ALGORITHM_VERSION,
        )

    @staticmethod
    def _dump(value: Any) -> Any:
        model_dump = getattr(value, "model_dump", None)
        return model_dump() if callable(model_dump) else value

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))


__all__ = ["GraphLoadMetadata", "PathService"]
