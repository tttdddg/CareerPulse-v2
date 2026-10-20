"""CareerPulse session to Ant TBox conversation mapping."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from ...orchestrator import CareerOrchestrator, CareerState, StateOwnershipError


class TBoxSessionMappingError(RuntimeError):
    """Base class for safe session mapping failures."""


class TBoxSessionIdentityConflict(TBoxSessionMappingError):
    """The CareerPulse session already belongs to another user."""


class TBoxConversationConflict(TBoxSessionMappingError):
    """A session was unexpectedly bound to a different TBox conversation."""


class TBoxSessionPersistenceError(TBoxSessionMappingError):
    """CareerState could not be read or persisted."""


@dataclass(slots=True)
class _LockEntry:
    lock: asyncio.Lock
    references: int = 0


class TBoxSessionMapper:
    """Persist mappings in CareerState and serialize calls per local session."""

    def __init__(self, orchestrator: CareerOrchestrator) -> None:
        self._orchestrator = orchestrator
        self._pool_guard = asyncio.Lock()
        self._locks: dict[str, _LockEntry] = {}

    @asynccontextmanager
    async def serialized(self, session_id: str) -> AsyncIterator[None]:
        async with self._pool_guard:
            entry = self._locks.get(session_id)
            if entry is None:
                entry = _LockEntry(lock=asyncio.Lock())
                self._locks[session_id] = entry
            entry.references += 1
        acquired = False
        try:
            await entry.lock.acquire()
            acquired = True
            yield
        finally:
            if acquired:
                entry.lock.release()
            async with self._pool_guard:
                entry.references -= 1
                if entry.references == 0 and not entry.lock.locked():
                    self._locks.pop(session_id, None)

    def load_or_create(self, session_id: str, user_id: str) -> CareerState:
        try:
            state = self._orchestrator.get_session(session_id)
        except Exception as exc:
            raise TBoxSessionPersistenceError() from exc

        if state is None:
            state = CareerState(session_id=session_id, user_id=user_id)
            self._persist(state)
            return state
        self._check_identity(state, user_id)
        if state.user_id is None:
            state.user_id = user_id
            self._persist(state)
        return state

    def bind(
        self,
        state: CareerState,
        *,
        user_id: str,
        conversation_id: str,
    ) -> CareerState:
        self._check_identity(state, user_id)
        if state.platform_session_id == conversation_id:
            return state
        if state.platform_session_id is not None:
            raise TBoxConversationConflict()

        data = state.model_dump(mode="python")
        data["platform_session_id"] = conversation_id
        try:
            updated = CareerState.model_validate(data)
        except Exception as exc:
            raise TBoxConversationConflict() from exc
        self._persist(updated)
        return updated

    @staticmethod
    def _check_identity(state: CareerState, user_id: str) -> None:
        if state.user_id is not None and state.user_id != user_id:
            raise TBoxSessionIdentityConflict()

    def _persist(self, state: CareerState) -> None:
        try:
            self._orchestrator.persist(state)
        except StateOwnershipError as exc:
            raise TBoxSessionIdentityConflict() from exc
        except Exception as exc:
            raise TBoxSessionPersistenceError() from exc


__all__ = [
    "TBoxConversationConflict",
    "TBoxSessionIdentityConflict",
    "TBoxSessionMapper",
    "TBoxSessionMappingError",
    "TBoxSessionPersistenceError",
]
