"""Unit tests for the unified LLM client; no real provider is contacted."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import httpx
from pydantic import BaseModel, Field

from app.core.config import LLMSettings, get_llm_settings
from app.core.llm_client import (
    LLMClient,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
    LLMValidationError,
)


class ExampleResult(BaseModel):
    name: str
    score: int = Field(ge=1, le=5)


def settings(**overrides):
    values = {
        "api_key": "test-key-must-not-be-logged",
        "base_url": "https://llm.example/v1",
        "model": "test-model",
        "timeout_seconds": 1.0,
        "temperature": 0.2,
        "max_retries": 2,
        "mock_mode": False,
        "mock_response": "mock text",
    }
    values.update(overrides)
    return LLMSettings(**values)


def provider_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


class ResponseQueue:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected provider request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class LLMClientTests(unittest.IsolatedAsyncioTestCase):
    def test_settings_read_retry_and_mock_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "A02_LLM_API_KEY": "configured-key",
                "A02_LLM_MODEL": "configured-model",
                "A02_LLM_MAX_RETRIES": "1",
                "A02_LLM_MOCK_MODE": "true",
                "A02_LLM_MOCK_RESPONSE": "configured mock",
            },
            clear=True,
        ):
            configured = get_llm_settings()

        self.assertEqual("configured-model", configured.model)
        self.assertEqual(1, configured.max_retries)
        self.assertTrue(configured.mock_mode)
        self.assertEqual("configured mock", configured.mock_response)

    async def test_generate_success(self) -> None:
        queue = ResponseQueue(provider_response("plain response"))
        client = LLMClient(settings(), transport=httpx.MockTransport(queue))

        result = await client.generate([{"role": "user", "content": "hello"}])

        self.assertEqual("plain response", result)
        payload = json.loads(queue.requests[0].content)
        self.assertEqual("test-model", payload["model"])

    async def test_json_code_fence_is_cleaned_and_validated(self) -> None:
        queue = ResponseQueue(provider_response('```json\n{"name":"demo","score":3}\n```'))
        client = LLMClient(settings(), transport=httpx.MockTransport(queue))

        result = await client.generate_structured(
            [{"role": "user", "content": "return data"}], ExampleResult
        )

        self.assertEqual(ExampleResult(name="demo", score=3), result)

    async def test_invalid_json_retries_twice_then_fails(self) -> None:
        queue = ResponseQueue(*(provider_response("not json") for _ in range(3)))
        client = LLMClient(settings(), transport=httpx.MockTransport(queue))

        with self.assertRaisesRegex(LLMValidationError, "after 3 attempts"):
            await client.generate_structured(
                [{"role": "user", "content": "return data"}], ExampleResult
            )

        self.assertEqual(3, len(queue.requests))

    async def test_schema_invalid_is_rejected(self) -> None:
        queue = ResponseQueue(provider_response('{"name":"demo","score":9}'))
        client = LLMClient(settings(), transport=httpx.MockTransport(queue))

        with self.assertRaises(LLMValidationError):
            await client.generate_structured(
                [{"role": "user", "content": "return data"}],
                ExampleResult,
                max_retries=0,
            )

    async def test_retry_feedback_enables_success(self) -> None:
        queue = ResponseQueue(
            provider_response('{"name":"demo","score":9}'),
            provider_response('{"name":"demo","score":4}'),
        )
        client = LLMClient(settings(), transport=httpx.MockTransport(queue))

        result = await client.generate_structured(
            [{"role": "user", "content": "return data"}], ExampleResult
        )

        self.assertEqual(4, result.score)
        retry_payload = json.loads(queue.requests[1].content)
        feedback = retry_payload["messages"][-1]["content"]
        self.assertIn("Validation feedback", feedback)
        self.assertIn("less_than_equal", feedback)

    async def test_timeout_has_specific_exception(self) -> None:
        def timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        client = LLMClient(settings(), transport=httpx.MockTransport(timeout))
        with self.assertRaises(LLMTimeoutError):
            await client.generate([{"role": "user", "content": "hello"}])

    async def test_rate_limit_and_empty_result_are_handled(self) -> None:
        limited = LLMClient(
            settings(),
            transport=httpx.MockTransport(lambda request: httpx.Response(429, request=request)),
        )
        with self.assertRaises(LLMRateLimitError):
            await limited.generate([{"role": "user", "content": "hello"}])

        empty = LLMClient(
            settings(),
            transport=httpx.MockTransport(lambda request: provider_response("")),
        )
        with self.assertRaises(LLMResponseError):
            await empty.generate([{"role": "user", "content": "hello"}])

    async def test_mock_mode_never_uses_network(self) -> None:
        client = LLMClient(
            settings(mock_mode=True, api_key=None, mock_response='{"name":"mock","score":2}')
        )

        text = await client.generate([{"role": "user", "content": "private resume"}])
        structured = await client.generate_structured(
            [{"role": "user", "content": "private resume"}], ExampleResult
        )

        self.assertEqual('{"name":"mock","score":2}', text)
        self.assertEqual("mock", structured.name)

    async def test_validated_default_fallback(self) -> None:
        queue = ResponseQueue(provider_response("bad"))
        client = LLMClient(settings(), transport=httpx.MockTransport(queue))

        result = await client.generate_structured(
            [{"role": "user", "content": "return data"}],
            ExampleResult,
            max_retries=0,
            fallback=lambda error: {"name": "fallback", "score": 1},
        )

        self.assertEqual("fallback", result.name)

    async def test_transport_error_can_use_validated_fallback(self) -> None:
        def timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        client = LLMClient(settings(), transport=httpx.MockTransport(timeout))
        result = await client.generate_structured(
            [{"role": "user", "content": "return data"}],
            ExampleResult,
            fallback={"name": "offline", "score": 1},
        )

        self.assertEqual(ExampleResult(name="offline", score=1), result)

    async def test_logs_do_not_include_key_or_message_content(self) -> None:
        queue = ResponseQueue(provider_response("ok"))
        client = LLMClient(settings(), transport=httpx.MockTransport(queue))

        with self.assertLogs("app.core.llm_client", level="INFO") as captured:
            await client.generate(
                [{"role": "user", "content": "PRIVATE_RESUME_SENTINEL"}]
            )

        serialized = " ".join(captured.output)
        self.assertNotIn("test-key-must-not-be-logged", serialized)
        self.assertNotIn("PRIVATE_RESUME_SENTINEL", serialized)


if __name__ == "__main__":
    unittest.main()
