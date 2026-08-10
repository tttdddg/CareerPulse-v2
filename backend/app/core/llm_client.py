"""Shared asynchronous client for OpenAI-compatible LLM providers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, TypeVar

import httpx
from pydantic import TypeAdapter, ValidationError

from .config import LLMSettings, get_llm_settings


StructuredT = TypeVar("StructuredT")


class LLMError(RuntimeError):
    """Base exception that callers can use to trigger retry or fallback."""


class LLMConfigurationError(LLMError):
    """Raised when required provider configuration is unavailable."""


class LLMTransportError(LLMError):
    """Raised when the provider cannot be reached or returns an error status."""


class LLMResponseError(LLMError):
    """Raised when a successful provider response has an invalid shape."""


class LLMValidationError(LLMError):
    """Raised when structured output is not valid JSON or fails its schema."""


class LLMClient:
    """One stable entry point for all CareerPulse model calls.

    Retry and business fallback intentionally remain the responsibility of Agents.
    """

    def __init__(
        self,
        settings: LLMSettings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_llm_settings()
        self._transport = transport

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
        extra_parameters: Mapping[str, Any] | None = None,
    ) -> str:
        """Generate text from system and user prompts."""

        payload = self._build_payload(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_parameters=extra_parameters,
        )
        response = await self._request(payload, timeout=timeout)
        return self._extract_content(response)

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredT] | Any,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
        extra_parameters: Mapping[str, Any] | None = None,
    ) -> StructuredT:
        """Generate JSON and validate it with a Pydantic-compatible type."""

        parameters = dict(extra_parameters or {})
        parameters.setdefault("response_format", {"type": "json_object"})
        content = await self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            extra_parameters=parameters,
        )
        try:
            raw_data = json.loads(content)
            return TypeAdapter(response_model).validate_python(raw_data)
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
            # Do not include model output: it may contain resume or identity data.
            raise LLMValidationError(
                "LLM structured output failed JSON/schema validation"
            ) from exc

    def _build_payload(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None,
        max_tokens: int | None,
        extra_parameters: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if not system_prompt.strip() or not user_prompt.strip():
            raise LLMConfigurationError("system_prompt and user_prompt must not be empty")

        effective_temperature = (
            self._settings.temperature if temperature is None else temperature
        )
        if not 0 <= effective_temperature <= 2:
            raise LLMConfigurationError("temperature must be between 0 and 2")
        if max_tokens is not None and max_tokens <= 0:
            raise LLMConfigurationError("max_tokens must be greater than zero")

        payload: dict[str, Any] = {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": effective_temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        protected = {"model", "messages"}
        extras = dict(extra_parameters or {})
        conflict = protected.intersection(extras)
        if conflict:
            raise LLMConfigurationError(
                "extra_parameters cannot override: " + ", ".join(sorted(conflict))
            )
        payload.update(extras)
        return payload

    async def _request(
        self, payload: Mapping[str, Any], *, timeout: float | None
    ) -> Mapping[str, Any]:
        if not self._settings.api_key:
            raise LLMConfigurationError("A02_LLM_API_KEY is not configured")
        effective_timeout = self._settings.timeout_seconds if timeout is None else timeout
        if effective_timeout <= 0:
            raise LLMConfigurationError("timeout must be greater than zero")

        headers = {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=effective_timeout
            ) as client:
                response = await client.post(
                    f"{self._settings.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMTransportError("LLM provider request timed out") from exc
        except httpx.HTTPStatusError as exc:
            # Status is useful for retry decisions; response bodies may contain secrets.
            raise LLMTransportError(
                f"LLM provider returned HTTP {exc.response.status_code}"
            ) from exc
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


llm_client = LLMClient()
"""Process-wide client for normal Agent use: ``await llm_client.generate(...)``."""


__all__ = [
    "LLMClient",
    "LLMError",
    "LLMConfigurationError",
    "LLMTransportError",
    "LLMResponseError",
    "LLMValidationError",
    "llm_client",
]
