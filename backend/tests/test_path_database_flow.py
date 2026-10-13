"""PathAgent graph-provider integration for PostgreSQL and explicit Demo mode."""

from __future__ import annotations

import json
import unittest
import uuid
from pathlib import Path
from typing import Any

from app.agents.match_agent import MatchAgent
from app.agents.path_agent import PathAgent
from app.db_state import StateRepository
from app.mcp.tool_service import CareerMCPToolService
from app.models import CareerGraph
from app.orchestrator import CareerOrchestrator, CareerState
from app.repositories.career_graph_repository import (
    CareerGraphProviderDataError,
    CareerGraphProviderResult,
    PostgresCareerGraphProviderError,
)
from app.schemas.mcp_tool_schema import GenerateCareerPathMCPRequest
from app.services.career_graph_repository import (
    CareerGraphProviderSelector,
    JsonCareerGraphProvider,
)
from app.services.match_service import MatchService
from app.services.path_service import PathService
from app.tools.database_tools import DatabaseTools
from tests.stage3_fixtures import (
    job_profile as unified_job_profile,
    student_profile as unified_student_profile,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"


class OfflineClient:
    async def generate_structured(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("offline")


class MemoryGraphProvider:
    def __init__(self, graph: CareerGraph, *, data_source: str = "postgresql") -> None:
        self.graph = graph
        self.data_source = data_source
        self.calls = 0

    def load(self, query=None, *, fallback_used: bool = False):
        self.calls += 1
        return CareerGraphProviderResult(
            nodes=list(self.graph.nodes),
            edges=list(self.graph.edges),
            data_source=self.data_source,
            fallback_used=fallback_used,
            demo_mode=self.data_source == "demo_json",
        )


class FailingGraphProvider:
    def load(self, query=None, *, fallback_used: bool = False):
        raise PostgresCareerGraphProviderError("database details stay private")


def load_json(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    unified = unified_student_profile()
    student = PathAgent._flatten_profile(unified)
    job = unified_job_profile()
    match = MatchService().calculate(MatchAgent._flatten_profile(unified), job)
    return student, job, match


class PathDatabaseFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.graph = CareerGraph.model_validate(load_json("career_graph.json"))
        runtime = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime / f"path-database-{uuid.uuid4().hex}.sqlite3"

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)
        Path(f"{self.db_path}-shm").unlink(missing_ok=True)
        Path(f"{self.db_path}-wal").unlink(missing_ok=True)

    def test_postgresql_and_demo_provider_snapshots_are_identical(self) -> None:
        student, job, match = inputs()
        postgres = MemoryGraphProvider(self.graph)
        demo = JsonCareerGraphProvider(
            DATA_DIR / "career_graph.json",
            demo_mode=True,
        )

        postgres_result, postgres_meta = PathService(
            provider=postgres
        ).calculate_with_metadata(student, job, match)
        demo_result, demo_meta = PathService(
            provider=demo
        ).calculate_with_metadata(student, job, match)

        self.assertEqual(postgres_result, demo_result)
        self.assertEqual("postgresql", postgres_meta.data_source)
        self.assertEqual("demo_json", demo_meta.data_source)
        self.assertEqual(postgres_meta.node_count, demo_meta.node_count)
        self.assertEqual(postgres_meta.edge_count, demo_meta.edge_count)
        self.assertEqual(1, postgres.calls)

    def test_database_edge_facts_survive_search_and_scoring_unchanged(self) -> None:
        student, job, match = inputs()
        result = PathService(
            provider=MemoryGraphProvider(self.graph)
        ).calculate(student, job, match)

        source_edges = {
            (edge.source_key, edge.target_key, edge.relation_type): edge
            for edge in self.graph.edges
        }
        self.assertTrue(result["candidate_paths"])
        self.assertTrue(
            any(
                edge["relation_type"] == "lateral"
                for path in result["candidate_paths"]
                for edge in path["edges"]
            )
        )
        for path in result["candidate_paths"]:
            for edge in path["edges"]:
                source = source_edges[
                    (edge["source_key"], edge["target_key"], edge["relation_type"])
                ]
                self.assertEqual(source.transfer_cost, edge["transfer_cost"])
                self.assertEqual(source.growth_value, edge["growth_value"])
                self.assertEqual(source.risk_level, edge["risk_level"])
                self.assertEqual(
                    source.transition_requirements,
                    edge["transition_requirements"],
                )

    def test_empty_graph_is_an_explicit_whole_graph_error(self) -> None:
        student, job, match = inputs()
        class EmptyGraphProvider:
            def load(self, query=None, *, fallback_used: bool = False):
                return CareerGraphProviderResult(
                    nodes=[],
                    edges=[],
                    data_source="postgresql",
                    fallback_used=False,
                    demo_mode=False,
                )

        with self.assertRaises(CareerGraphProviderDataError):
            PathService(provider=EmptyGraphProvider()).calculate(
                student,
                job,
                match,
            )

    async def test_mcp_path_logs_provider_and_agent_calls_separately(self) -> None:
        student, job, match = inputs()
        provider = MemoryGraphProvider(self.graph)
        orchestrator = CareerOrchestrator(
            agents=[PathAgent(client=OfflineClient())],
            repository=StateRepository(sqlite_path=self.db_path),
        )
        orchestrator.persist(
            CareerState(
                session_id="path-postgresql",
                user_id="path-user",
                status="MATCH_COMPLETED",
                student_profile=unified_student_profile(),
                job_profile=job,
                match_result=match,
            )
        )
        tools = CareerMCPToolService(
            orchestrator,
            database_tools=DatabaseTools(
                graph_selector=CareerGraphProviderSelector(provider),
            ),
        )

        response = await tools.generate_career_path(
            GenerateCareerPathMCPRequest(
                session_id="path-postgresql",
                user_id="path-user",
                trace_id="path-postgresql-01",
            )
        )

        self.assertTrue(response.success)
        state = orchestrator.get_session("path-postgresql")
        log = next(item for item in state.agent_logs if item.agent_name == "PathAgent")
        self.assertEqual(
            ["load_career_graph", "recommend_career_path"],
            [item.tool_name for item in log.tool_calls],
        )
        serialized = json.dumps(log.model_dump(), ensure_ascii=False)
        self.assertIn("data_source=postgresql", serialized)
        self.assertNotIn(job["job_description"], serialized)
        self.assertNotIn(student["abilities"][0]["evidence"], serialized)

    async def test_mcp_regenerates_invalid_completed_path_from_same_session(self) -> None:
        _, job, match = inputs()
        provider = MemoryGraphProvider(self.graph)
        orchestrator = CareerOrchestrator(
            agents=[PathAgent(client=OfflineClient())],
            repository=StateRepository(sqlite_path=self.db_path),
        )
        orchestrator.persist(
            CareerState(
                session_id="path-schema-recovery",
                user_id="path-user",
                status="MATCH_COMPLETED",
                student_profile=unified_student_profile(),
                job_profile=job,
                match_result=match,
            )
        )
        tools = CareerMCPToolService(
            orchestrator,
            database_tools=DatabaseTools(
                graph_selector=CareerGraphProviderSelector(provider),
            ),
        )
        first = await tools.generate_career_path(
            GenerateCareerPathMCPRequest(
                session_id="path-schema-recovery",
                user_id="path-user",
                trace_id="path-schema-recovery-01",
            )
        )
        self.assertTrue(first.success)

        state = orchestrator.get_session("path-schema-recovery")
        state.career_roadmap["three_year_roadmap"]["stages"][0][
            "objectives"
        ] = "invalid-list-value"
        orchestrator.persist(state)

        recovered = await tools.generate_career_path(
            GenerateCareerPathMCPRequest(
                session_id="path-schema-recovery",
                user_id="path-user",
                trace_id="path-schema-recovery-02",
            )
        )

        self.assertTrue(recovered.success)
        self.assertEqual("PATH_COMPLETED", recovered.status)
        self.assertEqual(2, provider.calls)

    async def test_database_failure_is_explicit_and_never_uses_demo(self) -> None:
        student, job, match = inputs()
        orchestrator = CareerOrchestrator(
            agents=[PathAgent(client=OfflineClient())],
            repository=StateRepository(sqlite_path=self.db_path),
        )
        orchestrator.persist(
            CareerState(
                session_id="path-database-failure",
                user_id="path-user",
                status="MATCH_COMPLETED",
                student_profile=unified_student_profile(),
                job_profile=job,
                match_result=match,
            )
        )
        tools = CareerMCPToolService(
            orchestrator,
            database_tools=DatabaseTools(
                graph_selector=CareerGraphProviderSelector(FailingGraphProvider()),
            ),
        )

        response = await tools.generate_career_path(
            GenerateCareerPathMCPRequest(
                session_id="path-database-failure",
                user_id="path-user",
                trace_id="path-database-failure-01",
            )
        )

        self.assertFalse(response.success)
        self.assertEqual("PATH_GRAPH_DATABASE_UNAVAILABLE", response.error_code)
        self.assertTrue(response.retryable)
        self.assertIsNone(orchestrator.get_session("path-database-failure").career_roadmap)


if __name__ == "__main__":
    unittest.main()
