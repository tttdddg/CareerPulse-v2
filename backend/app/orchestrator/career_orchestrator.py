"""Sequential A02 orchestration with state persistence and safe fallback."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable

from ..agents import (
    BaseAgent,
    FeedbackAgent,
    JobAgent,
    MatchAgent,
    PathAgent,
    ProfileAgent,
    TrainingAgent,
)
from ..db_state import StateRepository
from .career_state import CareerState


class CareerOrchestrator:
    """Own CareerState, run the six A02 agents in order, and persist snapshots."""

    def __init__(
        self,
        agents: Iterable[BaseAgent] | None = None,
        repository: StateRepository | None = None,
    ) -> None:
        self.agents = list(
            agents
            or [
                ProfileAgent(),
                JobAgent(),
                MatchAgent(),
                PathAgent(),
                TrainingAgent(),
                FeedbackAgent(),
            ]
        )
        self._sessions: dict[str, CareerState] = {}
        self.repository = repository or StateRepository()

    async def run(self, state: CareerState) -> CareerState:
        state.set_status("INITIALIZED")
        for agent in self.agents:
            await agent.run(state)

        state.final_report = self._build_final_report(state)
        state.set_status(self._final_status(state))
        self.persist(state)
        return state

    async def run_stage(
        self,
        state: CareerState,
        agent_name: str,
        *,
        stage_input: dict[str, Any] | None = None,
    ) -> CareerState:
        """Run one configured Agent and durably persist the resulting snapshot."""

        agent = next(
            (candidate for candidate in self.agents if candidate.name == agent_name),
            None,
        )
        if agent is None:
            raise ValueError(f"Agent is not configured: {agent_name}")

        input_key = {
            "TrainingAgent": "training",
            "FeedbackAgent": "feedback",
        }.get(agent_name)
        if stage_input is not None and input_key is None:
            raise ValueError(
                f"Agent does not accept transient stage input: {agent_name}"
            )

        original_input = state.student_input
        if stage_input is not None:
            staged_input = deepcopy(state.student_input or {})
            staged_input[input_key] = deepcopy(stage_input)
            state.student_input = staged_input
        try:
            await agent.run(state)
        finally:
            if stage_input is not None:
                state.student_input = original_input
        self.persist(state)
        return state

    def persist(self, state: CareerState) -> None:
        """Atomically persist state plus all current Agent logs."""

        try:
            self.repository.save_state_and_logs(
                state.model_dump(mode="json"),
                [log.model_dump(mode="json") for log in state.agent_logs],
            )
        except Exception as exc:
            state.set_status("FAILED", error_type=f"DATABASE_WRITE_FAILED:{type(exc).__name__}")
            raise StatePersistenceError("career state persistence failed") from exc
        self._sessions[state.session_id] = state.model_copy(deep=True)

    def get_session(self, session_id: str) -> CareerState | None:
        state = self._sessions.get(session_id)
        if state is not None:
            return state.model_copy(deep=True)
        data = self.repository.get_state(session_id)
        if data is None:
            return None
        return CareerState.model_validate(data)

    def get_agent_logs(self, session_id: str):
        """Read AgentRunLog rows from their durable table."""

        return self.repository.list_agent_logs(session_id)

    @staticmethod
    def _final_status(state: CareerState) -> str:
        if any(log.status == "failed" for log in state.agent_logs):
            return "PARTIAL"
        if any(log.fallback_used for log in state.agent_logs):
            return "PARTIAL"
        return "COMPLETED"

    @staticmethod
    def _build_final_report(state: CareerState) -> dict[str, object]:
        fallback_agents = [
            log.agent_name for log in state.agent_logs if log.fallback_used
        ]
        return {
            "session_id": state.session_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "partial" if fallback_agents else "success",
            "fallback_agents": fallback_agents,
            "student_profile": state.student_profile,
            "job_profile": state.job_profile,
            "trend_result": state.trend_result,
            "match_result": state.match_result,
            "path_plan": state.path_plan,
            "learning_plan": state.learning_plan,
            "career_roadmap": state.career_roadmap,
            "training_plan": state.training_plan,
            "resource_result": state.resource_result,
            "feedback_result": state.feedback_result,
        }


class StatePersistenceError(RuntimeError):
    """Raised after a database transaction fails and has been rolled back."""


__all__ = ["CareerOrchestrator", "StatePersistenceError"]
