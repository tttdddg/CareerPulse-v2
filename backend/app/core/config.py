"""Environment-backed configuration for shared A02 infrastructure."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMSettings:
    """Configuration for an OpenAI-compatible chat-completions provider."""

    api_key: str | None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 30.0
    temperature: float = 0.2
    max_retries: int = 2
    mock_mode: bool = False
    mock_response: str = "Mock response"

    def __post_init__(self) -> None:
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("A02_LLM_BASE_URL must be an HTTP(S) URL")
        if not self.model.strip():
            raise ValueError("A02_LLM_MODEL must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("A02_LLM_TIMEOUT_SECONDS must be greater than zero")
        if not 0 <= self.temperature <= 2:
            raise ValueError("A02_LLM_TEMPERATURE must be between 0 and 2")
        if not 0 <= self.max_retries <= 2:
            raise ValueError("A02_LLM_MAX_RETRIES must be between 0 and 2")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def get_llm_settings() -> LLMSettings:
    """Read LLM settings from the current process environment."""

    return LLMSettings(
        api_key=os.getenv("A02_LLM_API_KEY") or None,
        base_url=os.getenv("A02_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        model=os.getenv("A02_LLM_MODEL", "gpt-4o-mini"),
        timeout_seconds=float(os.getenv("A02_LLM_TIMEOUT_SECONDS", "30")),
        temperature=float(os.getenv("A02_LLM_TEMPERATURE", "0.2")),
        max_retries=int(os.getenv("A02_LLM_MAX_RETRIES", "2")),
        mock_mode=_env_bool("A02_LLM_MOCK_MODE", _env_bool("A02_DEMO_MODE", False)),
        mock_response=os.getenv("A02_LLM_MOCK_RESPONSE", "Mock response"),
    )
