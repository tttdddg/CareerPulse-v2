"""Unified asynchronous LLM client for OpenAI-compatible HTTP providers."""

from __future__ import annotations

import inspect
import json
import logging
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from time import perf_counter
from typing import Any, TypeVar

import httpx
from pydantic import TypeAdapter, ValidationError

from .config import LLMSettings, get_llm_settings


logger = logging.getLogger(__name__)
StructuredT = TypeVar("StructuredT")
Message = Mapping[str, Any]
FallbackFactory = Callable[[Exception], StructuredT | Awaitable[StructuredT]]

_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


class LLMError(RuntimeError):
    """Base exception for unified model calls."""


class LLMConfigurationError(LLMError):
    """Required client configuration or request parameters are invalid."""


class LLMTransportError(LLMError):
    """The provider cannot be reached or returned a non-success status."""


class LLMTimeoutError(LLMTransportError):
    """The provider request exceeded its configured timeout."""


class LLMRateLimitError(LLMTransportError):
    """The provider rejected the request because of rate limiting."""


class LLMResponseError(LLMError):
    """A successful provider response has no usable text content."""


class LLMValidationError(LLMError):
    """Structured output remained invalid after all repair attempts."""


class LLMFallbackError(LLMError):
    """A supplied fallback did not satisfy the requested response schema."""


class LLMClient:
    """Provider-neutral async entry point for all CareerPulse model calls."""

    def __init__(
        self,
        settings: LLMSettings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        mock_responses: Sequence[str] | None = None,
    ) -> None:
        self._settings = settings or get_llm_settings()
        self._transport = transport
        self._mock_responses = list(mock_responses or [])

    async def generate(
        self,
        messages: Sequence[Message] | None = None,
        *,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
        extra_parameters: Mapping[str, Any] | None = None,
    ) -> str:
        """Generate plain text from validated chat messages.

        ``system_prompt``/``user_prompt`` remain supported for compatibility;
        new callers should pass ``messages``.
        """

        normalized_messages = self._normalize_messages(
            messages, system_prompt=system_prompt, user_prompt=user_prompt
        )
        payload = self._build_payload(
            messages=normalized_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_parameters=extra_parameters,
        )
        started = perf_counter()
        try:
            if self._settings.mock_mode:
                content = self._mock_content()
            else:
                response = await self._request(payload, timeout=timeout)
                content = self._extract_content(response)
        except LLMError as exc:
            self._log_call("error", started, len(normalized_messages), type(exc).__name__)
            raise
        self._log_call("success", started, len(normalized_messages), None)
        return content

    async def generate_structured(
        self,
        messages: Sequence[Message],
        response_schema: type[StructuredT] | Any,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
        extra_parameters: Mapping[str, Any] | None = None,
        max_retries: int | None = None,
        fallback: StructuredT | FallbackFactory[StructuredT] | None = None,
    ) -> StructuredT:
        """Generate and validate JSON, repairing invalid output up to two times."""

        adapter = TypeAdapter(response_schema)
        retry_limit = self._settings.max_retries if max_retries is None else max_retries
        if not 0 <= retry_limit <= 2:
            raise LLMConfigurationError("max_retries must be between 0 and 2")

        parameters = dict(extra_parameters or {})
        parameters.setdefault("response_format", {"type": "json_object"})
        working_messages = [dict(message) for message in self._normalize_messages(messages)]
        working_messages.append(
            {
                "role": "system",
                "content": (
                    "Return only JSON matching this JSON Schema: "
                    + json.dumps(adapter.json_schema(), ensure_ascii=False, separators=(",", ":"))
                ),
            }
        )
        last_error: Exception | None = None

        for attempt in range(retry_limit + 1):
            try:
                content = await self.generate(
                    working_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    extra_parameters=parameters,
                )
                return adapter.validate_python(json.loads(self.clean_json_content(content)))
            except LLMError as exc:
                if fallback is not None:
                    return await self._resolve_fallback(fallback, exc, adapter)
                raise
            except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
                last_error = exc
                safe_error = self._safe_validation_error(exc)
                logger.warning(
                    "llm_structured_validation_failed",
                    extra={"attempt": attempt + 1, "max_attempts": retry_limit + 1, "error_type": type(exc).__name__},
                )
                if attempt < retry_limit:
                    working_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "The previous response failed JSON/schema validation. "
                                "Return a complete corrected JSON value only. "
                                f"Validation feedback: {safe_error}"
                            ),
                        }
                    )

        validation_error = LLMValidationError(
            f"LLM structured output failed validation after {retry_limit + 1} attempts"
        )
        if fallback is not None:
            return await self._resolve_fallback(fallback, validation_error, adapter)
        raise validation_error from last_error

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredT] | Any,
        **kwargs: Any,
    ) -> StructuredT:
        """Compatibility alias for existing Agents."""

        return await self.generate_structured(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model,
            **kwargs,
        )

    @staticmethod
    def clean_json_content(content: str) -> str:
        """Remove a JSON Markdown fence without accepting unrelated prose."""

        match = _JSON_FENCE.match(content)
        return (match.group(1) if match else content).strip()

    @staticmethod
    def _normalize_messages(
        messages: Sequence[Message] | None,
        *,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
    ) -> list[dict[str, Any]]:
        if messages is not None and (system_prompt is not None or user_prompt is not None):
            raise LLMConfigurationError("use messages or prompt compatibility arguments, not both")
        if messages is None:
            if not system_prompt or not user_prompt:
                raise LLMConfigurationError("messages must not be empty")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        normalized = [dict(message) for message in messages]
        if not normalized:
            raise LLMConfigurationError("messages must not be empty")
        for message in normalized:
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "user", "assistant"}:
                raise LLMConfigurationError("message role is invalid")
            if not isinstance(content, str) or not content.strip():
                raise LLMConfigurationError("message content must not be empty")
        return normalized

    def _build_payload(
        self,
        *,
        messages: Sequence[Message],
        temperature: float | None,
        max_tokens: int | None,
        extra_parameters: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        effective_temperature = self._settings.temperature if temperature is None else temperature
        if not 0 <= effective_temperature <= 2:
            raise LLMConfigurationError("temperature must be between 0 and 2")
        if max_tokens is not None and max_tokens <= 0:
            raise LLMConfigurationError("max_tokens must be greater than zero")
        payload: dict[str, Any] = {
            "model": self._settings.model,
            "messages": list(messages),
            "temperature": effective_temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        extras = dict(extra_parameters or {})
        conflict = {"model", "messages"}.intersection(extras)
        if conflict:
            raise LLMConfigurationError(
                "extra_parameters cannot override: " + ", ".join(sorted(conflict))
            )
        payload.update(extras)
        return payload

    async def _request(self, payload: Mapping[str, Any], *, timeout: float | None) -> Mapping[str, Any]:
        if not self._settings.api_key:
            raise LLMConfigurationError("A02_LLM_API_KEY is not configured")
        effective_timeout = self._settings.timeout_seconds if timeout is None else timeout
        if effective_timeout <= 0:
            raise LLMConfigurationError("timeout must be greater than zero")
        headers = {"Authorization": f"Bearer {self._settings.api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=effective_timeout) as client:
                response = await client.post(
                    f"{self._settings.base_url}/chat/completions", headers=headers, json=payload
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM provider request timed out") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise LLMRateLimitError("LLM provider rate limit exceeded") from exc
            raise LLMTransportError(f"LLM provider returned HTTP {exc.response.status_code}") from exc
        except (httpx.RequestError, json.JSONDecodeError) as exc:
            raise LLMTransportError("LLM provider request failed") from exc
        if not isinstance(data, Mapping):
            raise LLMResponseError("LLM provider returned a non-object response")
        return data

    @staticmethod
    def _extract_content(response: Mapping[str, Any]) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("LLM response is missing message content") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError("LLM response message content is empty")
        return content

    def _mock_content(self) -> str:
        if self._mock_responses:
            content = self._mock_responses.pop(0)
        else:
            content = self._settings.mock_response
        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError("LLM mock response is empty")
        return content

    @staticmethod
    def _safe_validation_error(exc: Exception) -> str:
        if isinstance(exc, ValidationError):
            errors = exc.errors(include_input=False, include_url=False)
            return json.dumps(errors, ensure_ascii=False, separators=(",", ":"))[:2000]
        if isinstance(exc, json.JSONDecodeError):
            return f"invalid JSON at line {exc.lineno} column {exc.colno}"
        return type(exc).__name__

    @staticmethod
    async def _resolve_fallback(
        fallback: StructuredT | FallbackFactory[StructuredT],
        error: Exception,
        adapter: TypeAdapter[StructuredT],
    ) -> StructuredT:
        try:
            value = fallback(error) if callable(fallback) else fallback
            if inspect.isawaitable(value):
                value = await value
            return adapter.validate_python(value)
        except Exception as exc:
            raise LLMFallbackError("LLM structured fallback failed schema validation") from exc

    def _log_call(self, status: str, started: float, message_count: int, error_type: str | None) -> None:
        logger.info(
            "llm_request",
            extra={
                "status": status,
                "model": self._settings.model,
                "mock_mode": self._settings.mock_mode,
                "message_count": message_count,
                "duration_ms": max(0, round((perf_counter() - started) * 1000)),
                "error_type": error_type,
            },
        )


def create_llm_client(
    settings: LLMSettings | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    mock_responses: Sequence[str] | None = None,
) -> LLMClient:
    """Factory used by application code and tests for dependency injection."""

    return LLMClient(settings=settings, transport=transport, mock_responses=mock_responses)


llm_client = create_llm_client()


__all__ = [
    "LLMClient", "LLMConfigurationError", "LLMError", "LLMFallbackError",
    "LLMRateLimitError", "LLMResponseError", "LLMTimeoutError",
    "LLMTransportError", "LLMValidationError", "create_llm_client", "llm_client",
]
