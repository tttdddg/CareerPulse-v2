"""PostgreSQL provider for validated career-graph nodes and edges."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal, Protocol, runtime_checkable

import psycopg2
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..db import BusinessDatabaseError, business_connection
from ..models import CareerGraphEdge, CareerGraphNode


_NODE_COLUMNS = (
    "type_key",
    "industry",
    "profile_summary",
    "level_range",
    "skill_requirements",
)
_EDGE_COLUMNS = (
    "source_type_key",
    "target_type_key",
    "relation_type",
    "reason",
    "transfer_cost",
    "growth_value",
    "transition_requirements",
    "risk_level",
    "source_industry",
    "target_industry",
)

_SELECT_NODES = """
SELECT type_key, industry, profile_summary, level_range, skill_requirements
FROM public.job_type_profile
ORDER BY type_key
"""
_SELECT_EDGES = """
SELECT edge.source_type_key, edge.target_type_key, edge.relation_type,
       edge.reason, edge.transfer_cost, edge.growth_value,
       edge.transition_requirements, edge.risk_level,
       source_profile.industry AS source_industry,
       target_profile.industry AS target_industry
FROM public.job_type_graph_edge AS edge
JOIN public.job_type_profile AS source_profile
  ON source_profile.type_key = edge.source_type_key
JOIN public.job_type_profile AS target_profile
  ON target_profile.type_key = edge.target_type_key
WHERE (%s IS NULL OR edge.source_type_key = %s)
  AND (%s IS NULL OR edge.relation_type = %s)
ORDER BY edge.source_type_key, edge.target_type_key, edge.relation_type
LIMIT %s
"""


class CareerGraphQuery(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        hide_input_in_errors=True,
    )

    source_type_key: str | None = Field(default=None, min_length=1, max_length=300)
    relation_type: Literal["vertical", "lateral"] | None = None
    limit: int = Field(default=500, ge=1, le=500)


class CareerGraphProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[CareerGraphNode]
    edges: list[CareerGraphEdge]
    data_source: Literal["postgresql", "demo_json"]
    fallback_used: bool
    demo_mode: bool


@runtime_checkable
class CareerGraphProvider(Protocol):
    def load(
        self,
        query: CareerGraphQuery | None = None,
        *,
        fallback_used: bool = False,
    ) -> CareerGraphProviderResult: ...


class CareerGraphProviderError(RuntimeError):
    """Safe provider error without SQL or database parameters."""


class PostgresCareerGraphProviderError(CareerGraphProviderError):
    """PostgreSQL graph data could not be read."""


class CareerGraphProviderDataError(CareerGraphProviderError):
    """A PostgreSQL graph row failed domain validation."""


class PostgresCareerGraphProvider:
    """Load graph data from current PostgreSQL columns using fixed SQL."""

    def load(
        self,
        query: CareerGraphQuery | None = None,
        *,
        fallback_used: bool = False,
    ) -> CareerGraphProviderResult:
        filters = query or CareerGraphQuery()
        node_rows = self._fetch_all(_SELECT_NODES, ())
        edge_rows = self._fetch_all(
            _SELECT_EDGES,
            (
                filters.source_type_key,
                filters.source_type_key,
                filters.relation_type,
                filters.relation_type,
                filters.limit,
            ),
        )
        return CareerGraphProviderResult(
            nodes=[self._node_from_row(row) for row in node_rows],
            edges=[self._edge_from_row(row) for row in edge_rows],
            data_source="postgresql",
            fallback_used=fallback_used,
            demo_mode=False,
        )

    @staticmethod
    def _fetch_all(statement: str, parameters: Sequence[Any]) -> list[Any]:
        try:
            with business_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(statement, parameters)
                    return list(cursor.fetchall())
        except (psycopg2.Error, BusinessDatabaseError):
            raise PostgresCareerGraphProviderError(
                "career graph database is unavailable"
            ) from None

    @staticmethod
    def _payload(row: Any, columns: tuple[str, ...]) -> dict[str, Any]:
        if isinstance(row, Mapping):
            return {column: row[column] for column in columns}
        values = tuple(row)
        if len(values) != len(columns):
            raise ValueError("invalid row length")
        return dict(zip(columns, values))

    @staticmethod
    def _json_list(value: Any) -> list[Any]:
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, list):
            raise ValueError("persisted JSON must be an array")
        return value

    @classmethod
    def _node_from_row(cls, row: Any) -> CareerGraphNode:
        try:
            payload = cls._payload(row, _NODE_COLUMNS)
            return CareerGraphNode(
                node_key=payload["type_key"],
                job_title=payload["type_key"],
                industry=payload["industry"],
                description=payload["profile_summary"],
                level_range=payload["level_range"],
                required_skills=cls._json_list(payload["skill_requirements"]),
                typical_duration=None,
                risk_level=None,
                cities=None,
            )
        except (ValidationError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            raise CareerGraphProviderDataError(
                "career graph node row failed validation"
            ) from None

    @classmethod
    def _edge_from_row(cls, row: Any) -> CareerGraphEdge:
        try:
            payload = cls._payload(row, _EDGE_COLUMNS)
            return CareerGraphEdge(
                source_key=payload["source_type_key"],
                target_key=payload["target_type_key"],
                relation_type=payload["relation_type"],
                reason=payload["reason"],
                transfer_cost=payload["transfer_cost"],
                growth_value=payload["growth_value"],
                source_industry=payload["source_industry"],
                target_industry=payload["target_industry"],
                transition_requirements=cls._json_list(
                    payload["transition_requirements"]
                ),
                risk_level=payload["risk_level"],
            )
        except (ValidationError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            raise CareerGraphProviderDataError(
                "career graph edge row failed validation"
            ) from None


__all__ = [
    "CareerGraphProvider",
    "CareerGraphProviderDataError",
    "CareerGraphProviderError",
    "CareerGraphProviderResult",
    "CareerGraphQuery",
    "PostgresCareerGraphProvider",
    "PostgresCareerGraphProviderError",
]
