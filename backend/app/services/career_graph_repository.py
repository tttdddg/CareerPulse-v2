"""Validated read-only repository for the CareerPulse career graph."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from ..models import CareerGraph, CareerGraphEdge, CareerGraphNode
from ..repositories.career_graph_repository import (
    CareerGraphProvider,
    CareerGraphProviderError,
    CareerGraphProviderResult,
    CareerGraphQuery,
)
from ..schemas.job_schema import JobProfile
from ..schemas.profile_schema import active_ability_tags
from .path_config import DEFAULT_DURATION_MONTHS, LEVEL_ORDER


_CAREER_GRAPH_FILE = Path(__file__).resolve().parents[1] / "data" / "career_graph.json"


class DemoCareerGraphProviderError(CareerGraphProviderError):
    """The explicitly enabled Demo graph could not be loaded."""


class JsonCareerGraphProvider:
    """Read the versioned JSON graph only when Demo Mode is explicit."""

    def __init__(
        self,
        graph_file: Path | str = _CAREER_GRAPH_FILE,
        *,
        demo_mode: bool,
    ) -> None:
        if demo_mode is not True:
            raise ValueError("JSON career graph requires explicit Demo Mode")
        self.graph_file = Path(graph_file)

    def load(
        self,
        query: CareerGraphQuery | None = None,
        *,
        fallback_used: bool = False,
    ) -> CareerGraphProviderResult:
        filters = query or CareerGraphQuery()
        try:
            with self.graph_file.open(encoding="utf-8") as handle:
                graph = CareerGraph.model_validate(json.load(handle))
        except (OSError, TypeError, ValueError, ValidationError, json.JSONDecodeError):
            raise DemoCareerGraphProviderError(
                "Demo career graph data is invalid"
            ) from None

        edges = [
            edge
            for edge in graph.edges
            if (
                filters.source_type_key is None
                or edge.source_key == filters.source_type_key
            )
            and (
                filters.relation_type is None
                or edge.relation_type == filters.relation_type
            )
        ]
        edges.sort(
            key=lambda item: (
                item.source_key,
                item.target_key,
                item.relation_type,
            )
        )
        return CareerGraphProviderResult(
            nodes=sorted(graph.nodes, key=lambda item: item.node_key),
            edges=edges[: filters.limit],
            data_source="demo_json",
            fallback_used=fallback_used,
            demo_mode=True,
        )


class CareerGraphProviderSelector:
    """Apply the production-closed and explicit-Demo source policy."""

    def __init__(
        self,
        postgres_provider: CareerGraphProvider,
        demo_provider: CareerGraphProvider | None = None,
    ) -> None:
        self.postgres_provider = postgres_provider
        self.demo_provider = demo_provider

    def load(
        self,
        query: CareerGraphQuery | None = None,
        *,
        demo_mode: bool = False,
        fallback_to_demo: bool = False,
    ) -> CareerGraphProviderResult:
        if fallback_to_demo and not demo_mode:
            raise ValueError("Demo fallback requires explicit Demo Mode")

        if demo_mode and not fallback_to_demo:
            return self._load_demo(query, fallback_used=False)

        try:
            result = self.postgres_provider.load(query, fallback_used=False)
        except CareerGraphProviderError:
            if not demo_mode or not fallback_to_demo:
                raise
            return self._load_demo(query, fallback_used=True)

        if demo_mode:
            result = result.model_copy(update={"demo_mode": True})
        return self._validated_result(result, full_graph=query is None)

    def _load_demo(
        self,
        query: CareerGraphQuery | None,
        *,
        fallback_used: bool,
    ) -> CareerGraphProviderResult:
        if self.demo_provider is None:
            raise DemoCareerGraphProviderError(
                "Demo career graph provider is not configured"
            )
        result = self.demo_provider.load(query, fallback_used=fallback_used)
        return self._validated_result(result, full_graph=query is None)

    @staticmethod
    def _validated_result(
        result: CareerGraphProviderResult,
        *,
        full_graph: bool,
    ) -> CareerGraphProviderResult:
        if full_graph:
            CareerGraphRepository(
                graph=CareerGraph(nodes=result.nodes, edges=result.edges)
            )
        return result


class ConfiguredCareerGraphProvider:
    """Bind source-policy flags once for injection into PathService."""

    def __init__(
        self,
        selector: CareerGraphProviderSelector,
        *,
        demo_mode: bool = False,
        fallback_to_demo: bool = False,
    ) -> None:
        if fallback_to_demo and not demo_mode:
            raise ValueError("Demo fallback requires explicit Demo Mode")
        self.selector = selector
        self.demo_mode = demo_mode
        self.fallback_to_demo = fallback_to_demo

    def load(
        self,
        query: CareerGraphQuery | None = None,
        *,
        fallback_used: bool = False,
    ) -> CareerGraphProviderResult:
        if fallback_used:
            raise ValueError("configured graph providers own fallback policy")
        try:
            return self.selector.load(
                query,
                demo_mode=self.demo_mode,
                fallback_to_demo=self.fallback_to_demo,
            )
        except ValueError:
            raise CareerGraphProviderDataError(
                "career graph snapshot failed whole-graph validation"
            ) from None


class CareerGraphRepository:
    """Load a career graph and expose deterministic adjacency queries."""

    def __init__(
        self,
        graph_file: Path | str = _CAREER_GRAPH_FILE,
        *,
        graph: CareerGraph | dict | None = None,
        job_profiles: Iterable[JobProfile | dict] = (),
    ) -> None:
        if graph is None:
            with Path(graph_file).open(encoding="utf-8") as handle:
                graph = json.load(handle)
        self.graph = graph if isinstance(graph, CareerGraph) else CareerGraph.model_validate(graph)
        validated_jobs = [
            item if isinstance(item, JobProfile) else JobProfile.model_validate(item)
            for item in job_profiles
        ]
        self._jobs_by_title = {
            item.normalized_title.strip().casefold(): item for item in validated_jobs
        }
        self._nodes = {node.node_key: node for node in self.graph.nodes}
        self._outgoing: dict[str, list[CareerGraphEdge]] = defaultdict(list)
        self._validate()
        for edge in self.graph.edges:
            self._outgoing[edge.source_key].append(edge)
        for edges in self._outgoing.values():
            edges.sort(key=lambda item: (item.target_key, item.relation_type))

    @classmethod
    def from_provider_result(
        cls,
        result: CareerGraphProviderResult,
    ) -> "CareerGraphRepository":
        """Build the existing PathService view without changing score fields."""

        repository = cls(graph=CareerGraph(nodes=result.nodes, edges=result.edges))
        repository.data_source = result.data_source
        repository.fallback_used = result.fallback_used
        repository.demo_mode = result.demo_mode
        return repository

    @property
    def nodes(self) -> tuple[CareerGraphNode, ...]:
        return tuple(sorted(self._nodes.values(), key=lambda item: item.node_key))

    @property
    def edges(self) -> tuple[CareerGraphEdge, ...]:
        return tuple(
            sorted(
                self.graph.edges,
                key=lambda item: (item.source_key, item.target_key, item.relation_type),
            )
        )

    def node(self, node_key: str) -> CareerGraphNode | None:
        return self._nodes.get(node_key)

    def resolved_node(self, node_key: str) -> tuple[CareerGraphNode, list[str]]:
        """Return a complete runtime node and explicit fallback flags."""

        node = self._nodes.get(node_key)
        if node is None:
            raise KeyError(f"unknown career graph node: {node_key}")
        flags: list[str] = []
        updates: dict[str, object] = {}
        if node.required_skills is None:
            job = self._jobs_by_title.get(node.job_title.strip().casefold())
            if job is None:
                raise ValueError(
                    f"career node {node_key} has no required_skills and no same-title job profile"
                )
            updates["required_skills"] = [
                {
                    "tag": item.tag,
                    "required_level": item.required_level,
                    "weight": item.weight,
                    "importance": item.importance,
                }
                for item in job.required_abilities
            ]
            flags.append(f"node_skill_vector_fallback:{node_key}")
        if node.typical_duration is None:
            updates["typical_duration"] = DEFAULT_DURATION_MONTHS[node.level_range]
            flags.append(f"node_duration_default:{node_key}")
        if node.risk_level is None:
            updates["risk_level"] = "medium"
            flags.append(f"node_risk_default:{node_key}")
        return CareerGraphNode.model_validate({**node.model_dump(), **updates}), flags

    def node_by_title(self, title: str) -> CareerGraphNode | None:
        normalized = title.strip().casefold()
        matches = [
            node for node in self._nodes.values() if node.job_title.strip().casefold() == normalized
        ]
        return min(matches, key=lambda item: item.node_key) if matches else None

    def entry_roles(
        self, industry: str | None = None, *, include_junior: bool = False
    ) -> list[CareerGraphNode]:
        levels = {"entry", "junior"} if include_junior else {"entry"}
        return [
            node
            for node in self.nodes
            if node.level_range in levels and (industry is None or node.industry == industry)
        ]

    def outgoing_edges(self, node_key: str) -> tuple[CareerGraphEdge, ...]:
        if node_key not in self._nodes:
            raise KeyError(f"unknown career graph node: {node_key}")
        return tuple(self._outgoing.get(node_key, ()))

    def next_roles(self, node_key: str) -> list[CareerGraphNode]:
        return [
            self._nodes[edge.target_key]
            for edge in self.outgoing_edges(node_key)
            if edge.relation_type == "vertical"
        ]

    def parallel_roles(self, node_key: str) -> list[CareerGraphNode]:
        return [
            self._nodes[edge.target_key]
            for edge in self.outgoing_edges(node_key)
            if edge.relation_type == "lateral"
        ]

    def reachable_nodes(self, start_key: str, max_nodes: int | None = None) -> list[CareerGraphNode]:
        max_path_nodes = max_nodes or len(self._nodes)
        shortest_depth = {start_key: 1}
        queue: list[tuple[str, int]] = [(start_key, 1)]
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_path_nodes:
                continue
            for edge in self.outgoing_edges(current):
                next_depth = depth + 1
                previous = shortest_depth.get(edge.target_key)
                if previous is None or next_depth < previous:
                    shortest_depth[edge.target_key] = next_depth
                    queue.append((edge.target_key, next_depth))
        return [self._nodes[key] for key in sorted(shortest_depth)]

    def detect_cycles(self) -> list[list[str]]:
        """Return normalized directed cycles without rejecting a realistic cyclic graph."""

        cycles: set[tuple[str, ...]] = set()

        def normalize(cycle: list[str]) -> tuple[str, ...]:
            core = cycle[:-1]
            rotations = [tuple(core[index:] + core[:index]) for index in range(len(core))]
            return min(rotations)

        def visit(start: str, current: str, path: list[str], visited: set[str]) -> None:
            for edge in self.outgoing_edges(current):
                target = edge.target_key
                if target == start and len(path) > 1:
                    cycles.add(normalize(path + [start]))
                elif target not in visited and len(path) < len(self._nodes):
                    visit(start, target, path + [target], visited | {target})

        for node_key in sorted(self._nodes):
            visit(node_key, node_key, [node_key], {node_key})
        return [list(cycle) + [cycle[0]] for cycle in sorted(cycles)]

    def node_duration(self, node: CareerGraphNode) -> int:
        return node.typical_duration or DEFAULT_DURATION_MONTHS[node.level_range]

    def _validate(self) -> None:
        if len(self._nodes) != len(self.graph.nodes):
            raise ValueError("career graph node keys must be unique")
        known_tags = active_ability_tags()
        used_nodes: set[str] = set()
        seen_edges: set[tuple[str, str, str]] = set()
        for node in self.graph.nodes:
            if node.required_skills is not None:
                invalid = {item.tag for item in node.required_skills} - known_tags
                if invalid:
                    raise ValueError(f"career node uses unknown ability tags: {sorted(invalid)}")
        for edge in self.graph.edges:
            if edge.source_key not in self._nodes or edge.target_key not in self._nodes:
                raise ValueError("career graph edge references an unknown node")
            if edge.source_key == edge.target_key:
                raise ValueError("career graph self edges are not allowed")
            identity = (edge.source_key, edge.target_key, edge.relation_type)
            if identity in seen_edges:
                raise ValueError("career graph contains a duplicate directed edge")
            seen_edges.add(identity)
            invalid = set(edge.transition_requirements) - known_tags
            if invalid:
                raise ValueError(f"career edge uses unknown ability tags: {sorted(invalid)}")
            source = self._nodes[edge.source_key]
            target = self._nodes[edge.target_key]
            if edge.relation_type == "vertical" and (
                LEVEL_ORDER[target.level_range] <= LEVEL_ORDER[source.level_range]
            ):
                raise ValueError("vertical career graph edges must strictly increase level")
            used_nodes.update((edge.source_key, edge.target_key))
        isolated = sorted(set(self._nodes) - used_nodes)
        if isolated:
            raise ValueError(f"career graph contains isolated nodes: {isolated}")


__all__ = [
    "CareerGraphProviderSelector",
    "ConfiguredCareerGraphProvider",
    "CareerGraphRepository",
    "DemoCareerGraphProviderError",
    "JsonCareerGraphProvider",
]
