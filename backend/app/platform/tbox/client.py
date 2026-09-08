"""Async HTTP client for the Ant TBox Enterprise chat API."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from .schemas import TBoxUpstreamReply, TBoxUpstreamStreamFrame


OFFICIAL_TBOX_CHAT_URL = "https://api.tbox.cn/api/chat"
_MAX_SSE_EVENT_BYTES = 1_000_000


class TBoxClientError(RuntimeError):
    """Safe client error that never includes response bodies or credentials."""

    def __init__(self, error_type: str, *, retryable: bool) -> None:
        super().__init__(error_type)
        self.error_type = error_type
        self.retryable = retryable


class TBoxConfigurationError(TBoxClientError):
    def __init__(self) -> None:
        super().__init__("TBOX_CHAT_NOT_CONFIGURED", retryable=False)


class TBoxTimeoutError(TBoxClientError):
    def __init__(self) -> None:
        super().__init__("TBOX_CHAT_TIMEOUT", retryable=True)


class TBoxProtocolError(TBoxClientError):
    def __init__(self) -> None:
        super().__init__("TBOX_RESPONSE_INVALID", retryable=True)


class TBoxUpstreamError(TBoxClientError):
    pass


@dataclass(frozen=True, slots=True)
class TBoxClientConfig:
    """Server-only TBox credentials and transport limits."""

    api_url: str = OFFICIAL_TBOX_CHAT_URL
    authorization: str = field(default="", repr=False)
    app_id: str = ""
    user_id_secret: str = field(default="", repr=False)
    timeout_seconds: float = 45.0

    def __post_init__(self) -> None:
        parsed = urlsplit(self.api_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("TBOX_CHAT_API_URL must be an absolute HTTPS URL")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 120:
            raise ValueError("TBOX_CHAT_TIMEOUT_SECONDS must be in (0, 120]")

    @classmethod
    def from_env(cls) -> "TBoxClientConfig":
        return cls(
            api_url=os.getenv("TBOX_CHAT_API_URL", OFFICIAL_TBOX_CHAT_URL).strip(),
            authorization=os.getenv("TBOX_CHAT_AUTHORIZATION", "").strip(),
            app_id=os.getenv("TBOX_APP_ID", "").strip(),
            user_id_secret=os.getenv("TBOX_USER_ID_SECRET", "").strip(),
            timeout_seconds=float(os.getenv("TBOX_CHAT_TIMEOUT_SECONDS", "45")),
        )

    def ensure_configured(self) -> None:
        if not self.authorization or not self.app_id or not self.user_id_secret:
            raise TBoxConfigurationError()


class TBoxClient:
    """Call TBox without exposing its authorization value to callers."""

    def __init__(
        self,
        config: TBoxClientConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport

    def ensure_configured(self) -> None:
        self.config.ensure_configured()

    def _payload(
        self,
        *,
        query: str,
        user_id: str,
        conversation_id: str | None,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "appId": self.config.app_id,
            "query": query,
            "userId": user_id,
            "stream": stream,
        }
        if conversation_id:
            payload["conversationId"] = conversation_id
        return payload

    def _headers(self, *, stream: bool) -> dict[str, str]:
        return {
            "Authorization": self.config.authorization,
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        timeout = httpx.Timeout(self.config.timeout_seconds)
        return httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            transport=self._transport,
        )

    async def chat(
        self,
        *,
        query: str,
        user_id: str,
        conversation_id: str | None,
    ) -> TBoxUpstreamReply:
        self.ensure_configured()
        try:
            async with self._client() as client:
                response = await client.post(
                    self.config.api_url,
                    headers=self._headers(stream=False),
                    json=self._payload(
                        query=query,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        stream=False,
                    ),
                )
        except httpx.TimeoutException as exc:
            raise TBoxTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise TBoxUpstreamError(
                "TBOX_CONNECTION_FAILED", retryable=True
            ) from exc

        self._check_status(response.status_code)
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise TBoxProtocolError() from exc
        try:
            return self._parse_non_stream(body)
        except TBoxClientError:
            raise
        except Exception as exc:
            raise TBoxProtocolError() from exc

    async def stream_chat(
        self,
        *,
        query: str,
        user_id: str,
        conversation_id: str | None,
    ) -> AsyncIterator[TBoxUpstreamStreamFrame]:
        self.ensure_configured()
        try:
            async with self._client() as client:
                async with client.stream(
                    "POST",
                    self.config.api_url,
                    headers=self._headers(stream=True),
                    json=self._payload(
                        query=query,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        stream=True,
                    ),
                ) as response:
                    self._check_status(response.status_code)
                    async for event_name, data in self._iter_sse(response):
                        try:
                            frame = self._parse_stream_event(event_name, data)
                        except TBoxClientError:
                            raise
                        except Exception as exc:
                            raise TBoxProtocolError() from exc
                        if frame is not None:
                            yield frame
        except httpx.TimeoutException as exc:
            raise TBoxTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise TBoxUpstreamError(
                "TBOX_CONNECTION_FAILED", retryable=True
            ) from exc

    @staticmethod
    def _check_status(status_code: int) -> None:
        if 200 <= status_code < 300:
            return
        if status_code in {401, 403}:
            raise TBoxUpstreamError(
                "TBOX_AUTHENTICATION_FAILED", retryable=False
            )
        if status_code == 429:
            raise TBoxUpstreamError("TBOX_RATE_LIMITED", retryable=True)
        if status_code >= 500:
            raise TBoxUpstreamError("TBOX_UPSTREAM_UNAVAILABLE", retryable=True)
        raise TBoxUpstreamError("TBOX_REQUEST_REJECTED", retryable=False)

    @classmethod
    def _parse_non_stream(cls, body: Any) -> TBoxUpstreamReply:
        if not isinstance(body, Mapping):
            raise TBoxProtocolError()

        error_code = body.get("errorCode")
        if error_code is not None and str(error_code) != "0":
            raise TBoxUpstreamError("TBOX_UPSTREAM_REJECTED", retryable=False)

        raw_data: Any = body.get("data") if error_code is not None else body
        entries = raw_data if isinstance(raw_data, list) else [raw_data]
        if not entries or not all(isinstance(item, Mapping) for item in entries):
            raise TBoxProtocolError()

        texts: list[str] = []
        conversation_id: str | None = None
        message_id: str | None = None
        request_id: str | None = None
        for entry in entries:
            assert isinstance(entry, Mapping)
            conversation_id = cls._optional_string(
                entry.get("conversationId")
            ) or conversation_id
            message_id = cls._optional_string(entry.get("messageId")) or message_id
            request_id = cls._optional_string(entry.get("requestId")) or request_id
            result = entry.get("result")
            if not isinstance(result, list):
                continue
            for item in result:
                if not isinstance(item, Mapping):
                    continue
                if item.get("mediaType") != "text":
                    continue
                chunk = item.get("chunk")
                if isinstance(chunk, str) and chunk:
                    texts.append(chunk)

        if not conversation_id or not texts:
            raise TBoxProtocolError()
        return TBoxUpstreamReply(
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
            content="".join(texts),
        )

    @staticmethod
    async def _iter_sse(
        response: httpx.Response,
    ) -> AsyncIterator[tuple[str, str]]:
        event_name = "message"
        data_lines: list[str] = []
        event_size = 0
        async for raw_line in response.aiter_lines():
            line = raw_line.rstrip("\r")
            if not line:
                if data_lines:
                    yield event_name, "\n".join(data_lines)
                event_name = "message"
                data_lines = []
                event_size = 0
                continue
            if line.startswith(":"):
                continue
            field_name, separator, value = line.partition(":")
            if separator and value.startswith(" "):
                value = value[1:]
            if field_name == "event":
                event_name = value or "message"
            elif field_name == "data":
                event_size += len(value.encode("utf-8"))
                if event_size > _MAX_SSE_EVENT_BYTES:
                    raise TBoxProtocolError()
                data_lines.append(value)
        if data_lines:
            yield event_name, "\n".join(data_lines)

    @classmethod
    def _parse_stream_event(
        cls,
        event_name: str,
        raw_data: str,
    ) -> TBoxUpstreamStreamFrame | None:
        try:
            body = json.loads(raw_data)
        except json.JSONDecodeError as exc:
            raise TBoxProtocolError() from exc
        if not isinstance(body, Mapping):
            raise TBoxProtocolError()
        if body.get("errorCode") is not None and str(body["errorCode"]) != "0":
            raise TBoxUpstreamError("TBOX_UPSTREAM_REJECTED", retryable=False)

        event_type = body.get("type")
        if event_name == "error" or event_type == "error":
            raise TBoxUpstreamError("TBOX_UPSTREAM_STREAM_FAILED", retryable=True)
        if event_name == "end" or event_type == "end":
            return TBoxUpstreamStreamFrame(kind="end")
        if event_type in {"thinking", "meta"}:
            return None

        payload = body.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise TBoxProtocolError() from exc
        if not isinstance(payload, Mapping):
            raise TBoxProtocolError()

        if event_type == "header":
            conversation_id = cls._optional_string(
                payload.get("sessionId") or payload.get("conversationId")
            )
            return TBoxUpstreamStreamFrame(
                kind="header",
                conversation_id=conversation_id,
                request_id=cls._optional_string(payload.get("requestId")),
            )
        if event_type == "chunk":
            text = payload.get("text")
            if not isinstance(text, str):
                raise TBoxProtocolError()
            return TBoxUpstreamStreamFrame(
                kind="chunk",
                conversation_id=cls._optional_string(
                    payload.get("conversationId")
                ),
                message_id=cls._optional_string(payload.get("messageId")),
                text=text,
            )
        return None

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None


__all__ = [
    "OFFICIAL_TBOX_CHAT_URL",
    "TBoxClient",
    "TBoxClientConfig",
    "TBoxClientError",
    "TBoxConfigurationError",
    "TBoxProtocolError",
    "TBoxTimeoutError",
    "TBoxUpstreamError",
]
