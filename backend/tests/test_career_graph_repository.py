"""PostgreSQL and explicit-Demo career graph provider coverage."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch

from pydantic import ValidationError

from app.db import BusinessDatabaseUnavailable
from app.models import CareerGraphEdge
from app.repositories.career_graph_repository import (
    CareerGraphProviderError,
    CareerGraphProviderResult,
    CareerGraphQuery,
    PostgresCareerGraphProvider,
    PostgresCareerGraphProviderError,
)
from app.services.career_graph_repository import (
    CareerGraphProviderSelector,
    CareerGraphRepository,
    JsonCareerGraphProvider,
)


LEVELS = ("entry", "junior", "mid", "senior", "lead")


def graph_payload() -> dict[str, list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    for index in range(10):
        key = f"role-{index}"
        nodes.append(
            {
                "node_key": key,
                "job_title": key,
                "level_range": LEVELS[index % 5],
                "industry": "行业A" if index < 5 else "行业B",
                "description": f"{key}岗位画像",
                "required_skills": [
                    {
                        "tag": "Python",
                        "required_level": min(index % 5 + 1, 5),
                        "weight": 1.0,
                        "importance": "critical",
                    }
                ],
                "typical_duration": None,
                "risk_level": None,
                "cities": None,
            }
        )

    pairs: list[tuple[int, int, str]] = []
    for base in (0, 5):
        pairs.extend((base + step, base + step + 1, "vertical") for step in range(4))
    pairs.extend(
        [
            (0, 5, "lateral"),
            (1, 6, "lateral"),
            (2, 7, "lateral"),
            (3, 8, "lateral"),
            (4, 9, "lateral"),
            (5, 0, "lateral"),
            (6, 1, "lateral"),
        ]
    )
    edges = [
        {
            "source_key": f"role-{source}",
            "target_key": f"role-{target}",
            "relation_type": relation,
            "reason": f"路径 {source} 到 {target}",
            "transfer_cost": round(0.5 + source / 10, 2),
            "growth_value": round(1.0 + target / 10, 2),
            "source_industry": "行业A" if source < 5 else "行业B",
            "target_industry": "行业A" if target < 5 else "行业B",
            "transition_requirements": ["Python"],
            "risk_level": "medium",
        }
        for source, target, relation in pairs
    ]
    return {"nodes": nodes, "edges": edges}


def node_rows(payload: dict[str, list[dict[str, Any]]]) -> list[tuple[Any, ...]]:
    return [
        (
            node["node_key"],
            node["industry"],
            node["description"],
            node["level_range"],
            node["required_skills"],
        )
        for node in payload["nodes"]
    ]


def edge_rows(payload: dict[str, list[dict[str, Any]]]) -> list[tuple[Any, ...]]:
    return [
        (
            edge["source_key"],
            edge["target_key"],
            edge["relation_type"],
            edge["reason"],
            edge["transfer_cost"],
            edge["growth_value"],
            edge["transition_requirements"],
            edge["risk_level"],
            edge["source_industry"],
            edge["target_industry"],
        )
        for edge in payload["edges"]
    ]


def postgres_result(
    query: CareerGraphQuery | None = None,
) -> CareerGraphProviderResult:
    payload = graph_payload()
    provider = PostgresCareerGraphProvider()
    filters = query or CareerGraphQuery()
    filtered_edges = [
        row
        for row in edge_rows(payload)
        if (filters.source_type_key is None or row[0] == filters.source_type_key)
        and (filters.relation_type is None or row[2] == filters.relation_type)
    ]
    filtered_edges.sort(key=lambda row: (row[0], row[1], row[2]))
    filtered_edges = filtered_edges[: filters.limit]
    with patch.object(
        provider,
        "_fetch_all",
        side_effect=[node_rows(payload), filtered_edges],
    ):
        return provider.load(query)


class StubProvider:
    def __init__(
        self,
        result: CareerGraphProviderResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    def load(
        self,
        query: CareerGraphQuery | None = None,
        *,
        fallback_used: bool = False,
    ) -> CareerGraphProviderResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result.model_copy(update={"fallback_used": fallback_used})


class CareerGraphProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.graph_file = Path(self.temp_directory.name) / "career_graph.json"
        self.graph_file.write_text(
            json.dumps(graph_payload(), ensure_ascii=False),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_postgres_and_json_providers_serialize_same_domain_graph(self) -> None:
        postgres = postgres_result()
        demo = JsonCareerGraphProvider(
            self.graph_file,
            demo_mode=True,
        ).load()

        self.assertEqual(
            [item.model_dump(mode="json") for item in postgres.nodes],
            [item.model_dump(mode="json") for item in demo.nodes],
        )
        self.assertEqual(
            [item.model_dump(mode="json") for item in postgres.edges],
            [item.model_dump(mode="json") for item in demo.edges],
        )
        self.assertEqual("postgresql", postgres.data_source)
        self.assertEqual("demo_json", demo.data_source)
        self.assertFalse(postgres.fallback_used)
        self.assertFalse(demo.fallback_used)

    def test_both_providers_apply_the_same_validated_edge_filters(self) -> None:
        query = CareerGraphQuery(
            source_type_key="role-0",
            relation_type="lateral",
            limit=1,
        )
        postgres = postgres_result(query)
        demo = JsonCareerGraphProvider(
            self.graph_file,
            demo_mode=True,
        ).load(query)

        self.assertEqual(
            [item.model_dump(mode="json") for item in postgres.edges],
            [item.model_dump(mode="json") for item in demo.edges],
        )
        self.assertEqual(1, len(postgres.edges))

    def test_postgres_query_uses_current_fields_and_parameterized_filters(self) -> None:
        payload = graph_payload()
        calls: list[tuple[str, tuple[Any, ...]]] = []

        def fetch(statement: str, parameters: tuple[Any, ...]) -> list[Any]:
            calls.append((statement, parameters))
            return node_rows(payload) if not parameters else edge_rows(payload)[:2]

        provider = PostgresCareerGraphProvider()
        with patch.object(provider, "_fetch_all", side_effect=fetch):
            provider.load(
                CareerGraphQuery(
                    source_type_key="role-0",
                    relation_type="vertical",
                    limit=2,
                )
            )

        edge_sql, parameters = calls[1]
        for column in (
            "source_type_key",
            "target_type_key",
            "relation_type",
            "transfer_cost",
            "growth_value",
            "transition_requirements",
            "risk_level",
            "reason",
        ):
            self.assertIn(column, edge_sql)
        self.assertIn("LIMIT %s", edge_sql)
        self.assertNotIn("role-0", edge_sql)
        self.assertEqual(
            ("role-0", "role-0", "vertical", "vertical", 2),
            parameters,
        )

    def test_filter_parameters_reject_unknown_relation_and_excessive_limit(self) -> None:
        with self.assertRaises(ValidationError):
            CareerGraphQuery(relation_type="promotion")
        with self.assertRaises(ValidationError):
            CareerGraphQuery(limit=501)
        with self.assertRaises(ValidationError):
            CareerGraphQuery.model_validate({"order_by": "growth_value"})

    def test_postgres_database_failure_is_safe_and_distinct(self) -> None:
        @contextmanager
        def unavailable() -> Iterator[None]:
            raise BusinessDatabaseUnavailable("private database details")
            yield

        with patch(
            "app.repositories.career_graph_repository.business_connection",
            return_value=unavailable(),
        ):
            with self.assertRaises(PostgresCareerGraphProviderError) as caught:
                PostgresCareerGraphProvider().load()

        self.assertEqual(
            "career graph database is unavailable",
            str(caught.exception),
        )

    def test_json_provider_requires_explicit_demo_mode(self) -> None:
        with self.assertRaises(ValueError):
            JsonCareerGraphProvider(self.graph_file, demo_mode=False)

    def test_production_failure_never_calls_demo_provider(self) -> None:
        postgres = StubProvider(error=CareerGraphProviderError("database failed"))
        demo = StubProvider(result=postgres_result())
        selector = CareerGraphProviderSelector(postgres, demo)

        with self.assertRaises(CareerGraphProviderError):
            selector.load(demo_mode=False)

        self.assertEqual(1, postgres.calls)
        self.assertEqual(0, demo.calls)

    def test_explicit_demo_can_load_directly_or_fallback_after_database_error(self) -> None:
        base = postgres_result().model_copy(
            update={"data_source": "demo_json", "demo_mode": True}
        )
        direct_demo = StubProvider(result=base)
        direct_postgres = StubProvider(result=postgres_result())
        selector = CareerGraphProviderSelector(direct_postgres, direct_demo)

        direct = selector.load(demo_mode=True)
        self.assertEqual("demo_json", direct.data_source)
        self.assertFalse(direct.fallback_used)
        self.assertEqual(0, direct_postgres.calls)

        failed_postgres = StubProvider(
            error=CareerGraphProviderError("database failed")
        )
        fallback_demo = StubProvider(result=base)
        fallback = CareerGraphProviderSelector(
            failed_postgres,
            fallback_demo,
        ).load(demo_mode=True, fallback_to_demo=True)
        self.assertEqual("demo_json", fallback.data_source)
        self.assertTrue(fallback.fallback_used)
        self.assertTrue(fallback.demo_mode)

    def test_full_graph_validation_rejects_unknown_edge_without_dropping_it(self) -> None:
        result = postgres_result()
        invalid_edge = result.edges[0].model_copy(
            update={"target_key": "unknown-role"}
        )
        invalid = result.model_copy(
            update={"edges": [invalid_edge, *result.edges[1:]]}
        )

        with self.assertRaises(ValueError):
            CareerGraphProviderSelector(StubProvider(result=invalid)).load()

    def test_existing_path_repository_accepts_provider_result_and_keeps_metadata(self) -> None:
        result = postgres_result()
        repository = CareerGraphRepository.from_provider_result(result)

        node, flags = repository.resolved_node("role-0")
        self.assertEqual(12, node.typical_duration)
        self.assertEqual("medium", node.risk_level)
        self.assertIn("node_duration_default:role-0", flags)
        self.assertIn("node_risk_default:role-0", flags)
        self.assertEqual("postgresql", repository.data_source)
        self.assertFalse(repository.fallback_used)


if __name__ == "__main__":
    unittest.main()
