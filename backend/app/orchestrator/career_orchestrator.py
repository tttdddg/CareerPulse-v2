"""Sequential A02 Mock orchestration with continuation-safe fallback."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from ..agents import (
    BaseAgent,
    FeedbackAgent,
    JobAgent,
    MatchAgent,
    PathAgent,
    ProfileAgent,
    TrainingAgent,
)
from .career_state import CareerState


class CareerOrchestrator:
    """Own CareerState and run the six frozen A02 agents in order."""

    def __init__(self, agents: Iterable[BaseAgent] | None = None) -> None:
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

    async def run(self, state: CareerState) -> CareerState:
        for agent in self.agents:
            await agent.run(state)

        state.final_report = self._build_final_report(state)
        self._sessions[state.session_id] = state.model_copy(deep=True)
        return state

    def get_session(self, session_id: str) -> CareerState | None:
        state = self._sessions.get(session_id)
        return state.model_copy(deep=True) if state else None

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
