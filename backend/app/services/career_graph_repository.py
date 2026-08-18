"""Validated read-only repository for the CareerPulse career graph."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from ..models import CareerGraph, CareerGraphEdge, CareerGraphNode
from ..schemas.job_schema import JobProfile
from ..schemas.profile_schema import active_ability_tags
from .path_config import DEFAULT_DURATION_MONTHS, LEVEL_ORDER


_CAREER_GRAPH_FILE = Path(__file__).resolve().parents[1] / "data" / "career_graph.json"


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


__all__ = ["CareerGraphRepository"]
