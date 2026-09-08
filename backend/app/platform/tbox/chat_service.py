"""Application service for the CareerPulse to Ant TBox chat gateway."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from time import perf_counter
from uuid import uuid4

from ...orchestrator import CareerOrchestrator
from .client import (
    TBoxClient,
    TBoxClientError,
    TBoxConfigurationError,
    TBoxProtocolError,
    TBoxTimeoutError,
)
from .schemas import (
    TBoxChatData,
    TBoxChatErrorDetail,
    TBoxChatRequest,
    TBoxChatResponse,
    TBoxChatStreamEvent,
)
from .session_mapper import (
    TBoxConversationConflict,
    TBoxSessionIdentityConflict,
    TBoxSessionMapper,
    TBoxSessionPersistenceError,
)


class TBoxChatException(Exception):
    """Stable browser-facing error independent of upstream exception text."""

    def __init__(
        self,
        *,
        code: int,
        http_status: int,
        error_type: str,
        message: str,
        detail: str,
        retryable: bool,
        request_id: str,
    ) -> None:
        super().__init__(error_type)
        self.code = code
        self.http_status = http_status
        self.error_type = error_type
        self.message = message
        self.detail = detail
        self.retryable = retryable
        self.request_id = request_id

    def detail_model(self) -> TBoxChatErrorDetail:
        return TBoxChatErrorDetail(
            type=self.error_type,
            detail=self.detail,
            retryable=self.retryable,
        )


class TBoxChatService:
    """Coordinate session mapping, platform calls, response mapping and logs."""

    _TOOL_NAME = "tbox_agent_chat"

    def __init__(
        self,
        client: TBoxClient,
        mapper: TBoxSessionMapper,
        orchestrator: CareerOrchestrator,
    ) -> None:
        self._client = client
        self._mapper = mapper
        self._orchestrator = orchestrator

    def ensure_configured(self) -> None:
        """Fail before an SSE response starts when credentials are missing."""

        request_id = self._new_request_id()
        try:
            self._client.ensure_configured()
        except Exception as exc:
            raise self._translate_error(exc, request_id) from exc

    async def chat(self, payload: TBoxChatRequest) -> TBoxChatResponse:
        request_id = self._new_request_id()
        started_at = perf_counter()
        call_logged = False
        try:
            self._client.ensure_configured()
            async with self._mapper.serialized(payload.session_id):
                state = self._mapper.load_or_create(
                    payload.session_id, payload.user_id
                )
                self._begin_call(payload, request_id, state.platform_session_id)
                call_logged = True
                try:
                    async with asyncio.timeout(
                        self._client.config.timeout_seconds
                    ):
                        reply = await self._client.chat(
                            query=payload.message,
                            user_id=self._platform_user_id(payload.user_id),
                            conversation_id=state.platform_session_id,
                        )
                    state = self._mapper.bind(
                        state,
                        user_id=payload.user_id,
                        conversation_id=reply.conversation_id,
                    )
                except Exception as exc:
                    safe_error = self._translate_error(exc, request_id)
                    self._finish_failure(
                        request_id,
                        safe_error,
                        duration_ms=self._duration_ms(started_at),
                    )
                    raise safe_error from exc

                self._finish_success(
                    request_id,
                    stream=False,
                    mapped=state.platform_session_id is not None,
                    duration_ms=self._duration_ms(started_at),
                )
                return TBoxChatResponse(
                    request_id=request_id,
                    data=TBoxChatData(
                        session_id=payload.session_id,
                        conversation_id=reply.conversation_id,
                        message_id=reply.message_id,
                        upstream_request_id=reply.request_id,
                        content=reply.content,
                    ),
                )
        except TBoxChatException:
            raise
        except Exception as exc:
            safe_error = self._translate_error(exc, request_id)
            if call_logged:
                self._finish_failure(
                    request_id,
                    safe_error,
                    duration_ms=self._duration_ms(started_at),
                )
            raise safe_error from exc

    async def stream(
        self, payload: TBoxChatRequest
    ) -> AsyncIterator[TBoxChatStreamEvent]:
        request_id = self._new_request_id()
        started_at = perf_counter()
        call_logged = False
        conversation_id: str | None = None
        message_id: str | None = None
        upstream_request_id: str | None = None
        session_emitted = False
        ended = False
        received_characters = 0
        try:
            self._client.ensure_configured()
            async with self._mapper.serialized(payload.session_id):
                state = self._mapper.load_or_create(
                    payload.session_id, payload.user_id
                )
                conversation_id = state.platform_session_id
                self._begin_call(payload, request_id, conversation_id)
                call_logged = True
                async with asyncio.timeout(self._client.config.timeout_seconds):
                    async for frame in self._client.stream_chat(
                        query=payload.message,
                        user_id=self._platform_user_id(payload.user_id),
                        conversation_id=conversation_id,
                    ):
                        if frame.conversation_id:
                            state = self._mapper.bind(
                                state,
                                user_id=payload.user_id,
                                conversation_id=frame.conversation_id,
                            )
                            conversation_id = frame.conversation_id
                        if frame.request_id:
                            upstream_request_id = frame.request_id
                        if frame.message_id:
                            message_id = frame.message_id

                        if (
                            conversation_id is not None
                            and not session_emitted
                        ):
                            session_emitted = True
                            yield TBoxChatStreamEvent(
                                type="session",
                                request_id=request_id,
                                session_id=payload.session_id,
                                conversation_id=conversation_id,
                            )
                        if frame.kind == "chunk":
                            if conversation_id is None or frame.text is None:
                                raise TBoxProtocolError()
                            received_characters += len(frame.text)
                            if received_characters > 100_000:
                                raise TBoxProtocolError()
                            yield TBoxChatStreamEvent(
                                type="delta",
                                request_id=request_id,
                                session_id=payload.session_id,
                                conversation_id=conversation_id,
                                message_id=message_id,
                                content=frame.text,
                            )
                        elif frame.kind == "end":
                            ended = True
                            break

                if not ended or conversation_id is None:
                    raise TBoxProtocolError()
                self._finish_success(
                    request_id,
                    stream=True,
                    mapped=True,
                    duration_ms=self._duration_ms(started_at),
                )
                yield TBoxChatStreamEvent(
                    type="done",
                    request_id=request_id,
                    session_id=payload.session_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    upstream_request_id=upstream_request_id,
                )
        except asyncio.CancelledError:
            if call_logged:
                cancelled = TBoxChatException(
                    code=-6,
                    http_status=499,
                    error_type="CLIENT_DISCONNECTED",
                    message="chat stream disconnected",
                    detail="The client disconnected before the stream completed",
                    retryable=True,
                    request_id=request_id,
                )
                try:
                    self._finish_failure(
                        request_id,
                        cancelled,
                        duration_ms=self._duration_ms(started_at),
                    )
                except TBoxChatException:
                    # A disconnected response cannot report a secondary log
                    # failure. Preserve cancellation and never expose internals.
                    pass
            raise
        except Exception as exc:
            safe_error = self._translate_error(exc, request_id)
            if call_logged:
                try:
                    self._finish_failure(
                        request_id,
                        safe_error,
                        duration_ms=self._duration_ms(started_at),
                    )
                except TBoxChatException as persistence_error:
                    safe_error = persistence_error
            yield TBoxChatStreamEvent(
                type="error",
                request_id=request_id,
                session_id=payload.session_id,
                conversation_id=conversation_id,
                error=safe_error.detail_model(),
            )

    def _begin_call(
        self,
        payload: TBoxChatRequest,
        request_id: str,
        conversation_id: str | None,
    ) -> None:
        canonical = json.dumps(
            {
                "message_sha256": hashlib.sha256(
                    payload.message.encode("utf-8")
                ).hexdigest(),
                "session_id": payload.session_id,
                "stream": payload.stream,
                "user_id_sha256": self._hash_user_id(payload.user_id),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        try:
            _, created = self._orchestrator.repository.create_tool_call(
                tool_call_id=request_id,
                tool_name=self._TOOL_NAME,
                idempotency_key=request_id,
                request_fingerprint=fingerprint,
                session_id=payload.session_id,
                platform_session_id=conversation_id,
                user_id_hash=self._hash_user_id(payload.user_id),
            )
        except Exception as exc:
            raise self._persistence_error(request_id) from exc
        if not created:
            raise self._persistence_error(request_id)

    def _finish_success(
        self,
        request_id: str,
        *,
        stream: bool,
        mapped: bool,
        duration_ms: int,
    ) -> None:
        try:
            self._orchestrator.repository.finish_tool_call(
                request_id,
                status="succeeded",
                result_data={
                    "response_mode": "stream" if stream else "json",
                    "conversation_mapped": mapped,
                },
                duration_ms=duration_ms,
            )
        except Exception as exc:
            raise self._persistence_error(request_id) from exc

    def _finish_failure(
        self,
        request_id: str,
        error: TBoxChatException,
        *,
        duration_ms: int,
    ) -> None:
        try:
            self._orchestrator.repository.finish_tool_call(
                request_id,
                status=(
                    "timed_out"
                    if error.error_type == "TBOX_CHAT_TIMEOUT"
                    else "failed"
                ),
                error_code=error.code,
                error_type=error.error_type,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            raise self._persistence_error(request_id) from exc

    @staticmethod
    def _translate_error(exc: Exception, request_id: str) -> TBoxChatException:
        if isinstance(exc, TBoxChatException):
            return exc
        if isinstance(exc, (TBoxTimeoutError, TimeoutError)):
            return TBoxChatException(
                code=-4,
                http_status=504,
                error_type="TBOX_CHAT_TIMEOUT",
                message="AI career partner timed out",
                detail="The upstream response did not complete in time",
                retryable=True,
                request_id=request_id,
            )
        if isinstance(exc, TBoxConfigurationError):
            return TBoxChatException(
                code=-1,
                http_status=503,
                error_type="TBOX_CHAT_NOT_CONFIGURED",
                message="AI career partner is not configured",
                detail="The server-side TBox application credentials are unavailable",
                retryable=False,
                request_id=request_id,
            )
        if isinstance(exc, TBoxSessionIdentityConflict):
            return TBoxChatException(
                code=-3,
                http_status=409,
                error_type="SESSION_USER_CONFLICT",
                message="chat session conflict",
                detail="This CareerPulse session belongs to another user",
                retryable=False,
                request_id=request_id,
            )
        if isinstance(exc, TBoxConversationConflict):
            return TBoxChatException(
                code=-3,
                http_status=409,
                error_type="TBOX_CONVERSATION_CONFLICT",
                message="chat session conflict",
                detail="The TBox conversation mapping could not be updated safely",
                retryable=False,
                request_id=request_id,
            )
        if isinstance(exc, TBoxSessionPersistenceError):
            return TBoxChatService._persistence_error(request_id)
        if isinstance(exc, TBoxProtocolError):
            return TBoxChatException(
                code=-6,
                http_status=502,
                error_type=exc.error_type,
                message="AI career partner returned an invalid response",
                detail=(
                    "The upstream response did not match the supported "
                    "TBox protocol"
                ),
                retryable=exc.retryable,
                request_id=request_id,
            )
        if isinstance(exc, TBoxClientError):
            return TBoxChatException(
                code=-6,
                http_status=502,
                error_type=exc.error_type,
                message="AI career partner is temporarily unavailable",
                detail="The TBox platform call could not be completed",
                retryable=exc.retryable,
                request_id=request_id,
            )
        return TBoxChatException(
            code=-1,
            http_status=500,
            error_type="TBOX_CHAT_INTERNAL_ERROR",
            message="AI career partner request failed",
            detail="CareerPulse could not complete the chat request",
            retryable=False,
            request_id=request_id,
        )

    @staticmethod
    def _persistence_error(request_id: str) -> TBoxChatException:
        return TBoxChatException(
            code=-5,
            http_status=503,
            error_type="TBOX_CHAT_LOG_WRITE_FAILED",
            message="chat persistence unavailable",
            detail="CareerPulse could not persist the chat session or call status",
            retryable=True,
            request_id=request_id,
        )

    @staticmethod
    def _new_request_id() -> str:
        return f"chat-{uuid4().hex}"

    @staticmethod
    def _hash_user_id(user_id: str) -> str:
        return hashlib.sha256(user_id.encode("utf-8")).hexdigest()

    def _platform_user_id(self, user_id: str) -> str:
        digest = hmac.new(
            self._client.config.user_id_secret.encode("utf-8"),
            user_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"cp_{digest}"

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return max(0, int((perf_counter() - started_at) * 1000))


__all__ = ["TBoxChatException", "TBoxChatService"]
