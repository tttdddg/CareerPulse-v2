"""A02 orchestration package with a cycle-safe public API."""

from .career_state import AgentLog, CareerState, ToolCallLog

__all__ = ["AgentLog", "CareerOrchestrator", "CareerState", "ToolCallLog"]


def __getattr__(name: str):
    if name == "CareerOrchestrator":
        from .career_orchestrator import CareerOrchestrator

        return CareerOrchestrator
    raise AttributeError(name)
