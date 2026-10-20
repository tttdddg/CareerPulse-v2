"""A02 orchestration package with a cycle-safe public API."""

from .career_state import AgentLog, CareerState, Status, ToolCallLog

__all__ = [
    "AgentLog",
    "CareerOrchestrator",
    "CareerState",
    "StateOwnershipError",
    "StatePersistenceError",
    "Status",
    "ToolCallLog",
]


def __getattr__(name: str):
    if name in {"CareerOrchestrator", "StateOwnershipError", "StatePersistenceError"}:
        from .career_orchestrator import (
            CareerOrchestrator,
            StateOwnershipError,
            StatePersistenceError,
        )

        return {
            "CareerOrchestrator": CareerOrchestrator,
            "StateOwnershipError": StateOwnershipError,
            "StatePersistenceError": StatePersistenceError,
        }[name]
    raise AttributeError(name)
