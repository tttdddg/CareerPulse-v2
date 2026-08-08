"""Common execution, fallback and logging behavior for A02 agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..orchestrator.career_state import AgentLog, CareerState, ToolCallLog


class AgentResult(BaseModel):
    """Unified Agent return format from API_CONTRACTS section 9.2."""

    model_config = ConfigDict(extra="forbid")

    agent_name: str
    status: str = Field(pattern="^(success|partial|failed)$")
    data: dict[str, Any] | None = None
    summary: str
    duration_ms: int = Field(ge=0)
    tool_calls: list[ToolCallLog] = Field(default_factory=list)
    fallback_used: bool = False
    error: str | None = None


class MissingDependencyError(RuntimeError):
    """Raised when an Agent's frozen prerequisite fields are missing."""


class BaseAgent(ABC):
    """Base class that guarantees logging and continuation-safe fallback."""

    name = "BaseAgent"
    required_fields: tuple[str, ...] = ()
    output_fields: tuple[str, ...] = ()
    tool_name = "mock_agent_tool"

    async def run(self, state: CareerState) -> AgentResult:
        started = perf_counter()
        fallback_used = False
        error: str | None = None

        try:
            self._check_dependencies(state)
            data = await self._execute(state)
            self._validate_output(data)
            state.apply_agent_data(data)
            status = "success"
            summary = f"{self.name} Mock 执行完成"
            tool_status = "success"
        except Exception as exc:  # fallback is part of the Agent contract
            fallback_used = True
            error = self._safe_error(exc)
            try:
                data = await self._fallback(state, exc)
                self._validate_output(data)
                if data:
                    state.apply_agent_data(data)
                    status = "partial"
                    summary = f"{self.name} 使用 Mock fallback 继续"
                else:
                    status = "failed"
                    summary = f"{self.name} 跳过，后续 Agent 继续"
            except Exception as fallback_exc:
                data = {}
                status = "failed"
                summary = f"{self.name} fallback 失败，后续 Agent 继续"
                error = f"{error}; fallback: {self._safe_error(fallback_exc)}"
            tool_status = "error"

        duration_ms = max(0, round((perf_counter() - started) * 1000))
        tool_call = ToolCallLog(
            tool_name=self.tool_name,
            input_summary=self._input_summary(state),
            output_summary=self._output_summary(data),
            duration_ms=duration_ms,
            status=tool_status,
        )
        result = AgentResult(
            agent_name=self.name,
            status=status,
            data=data,
            summary=summary,
            duration_ms=duration_ms,
            tool_calls=[tool_call],
            fallback_used=fallback_used,
            error=error,
        )
        state.agent_logs.append(
            AgentLog(
                session_id=state.session_id,
                timestamp=self._timestamp(),
                **result.model_dump(exclude={"data"}),
            )
        )
        return result

    def _check_dependencies(self, state: CareerState) -> None:
        missing = [name for name in self.required_fields if not getattr(state, name)]
        if missing:
            raise MissingDependencyError(
                "missing prerequisite fields: " + ", ".join(missing)
            )

    def _validate_output(self, data: dict[str, Any]) -> None:
        unexpected = set(data) - set(self.output_fields)
        if unexpected:
            raise ValueError(f"unexpected output fields: {sorted(unexpected)}")

    def _input_summary(self, state: CareerState) -> str:
        present = [name for name in self.required_fields if getattr(state, name)]
        return "已提供字段: " + (", ".join(present) if present else "无")

    @staticmethod
    def _output_summary(data: dict[str, Any]) -> str:
        return "已生成字段: " + (", ".join(sorted(data)) if data else "无")

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        # Exceptions are generated internally and never include raw request bodies.
        return f"{type(exc).__name__}: {str(exc)[:200]}"

    @staticmethod
    def _timestamp() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    @abstractmethod
    async def _execute(self, state: CareerState) -> dict[str, Any]:
        """Execute Agent-specific Mock logic."""

    @abstractmethod
    async def _fallback(
        self, state: CareerState, error: Exception
    ) -> dict[str, Any]:
        """Return safe fallback state updates after any failure."""
