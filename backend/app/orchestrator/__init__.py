"""A02 orchestration package with a cycle-safe public API."""

from .career_state import AgentLog, CareerState, Status, ToolCallLog

__all__ = [
    "AgentLog",
    "CareerOrchestrator",
    "CareerState",
    "StatePersistenceError",
    "Status",
    "ToolCallLog",
]


def __getattr__(name: str):
    if name in {"CareerOrchestrator", "StatePersistenceError"}:
        from .career_orchestrator import CareerOrchestrator, StatePersistenceError

        return {
            "CareerOrchestrator": CareerOrchestrator,
            "StatePersistenceError": StatePersistenceError,
        }[name]
    raise AttributeError(name)
