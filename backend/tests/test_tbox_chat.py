"""Backend integration tests for the formal Ant TBox chat gateway."""

from __future__ import annotations

import asyncio
import json
import unittest
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.auth.identity import external_owner_id
from app.db_state import StateRepository
from app.main import create_app as create_application
from app.orchestrator import CareerOrchestrator, CareerState
from app.platform.tbox import (
    TBoxChatService,
    TBoxClient,
    TBoxClientConfig,
    TBoxSessionMapper,
)


AUTHORIZATION = "Tbox-test-only-authorization"
APP_ID = "career-pulse-test-agent"
USER_ID_SECRET = "test-only-user-id-hmac-secret"


def create_app(*args: Any, **kwargs: Any):
    """Keep gateway protocol tests independent from browser authentication."""

    kwargs.setdefault("web_auth_enabled", False)
    return create_application(*args, **kwargs)


class TBoxChatGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_dir = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime_dir / f"tbox-chat-{uuid.uuid4().hex}.sqlite3"
        self.repository = StateRepository(sqlite_path=self.db_path)
        self.orchestrator = CareerOrchestrator(repository=self.repository)
        self.clients: list[TestClient] = []

    def tearDown(self) -> None:
        for client in self.clients:
            client.close()
        self.db_path.unlink(missing_ok=True)
        Path(f"{self.db_path}-shm").unlink(missing_ok=True)
        Path(f"{self.db_path}-wal").unlink(missing_ok=True)

    def _client(
        self,
        handler: Any,
        *,
        authorization: str = AUTHORIZATION,
        app_id: str = APP_ID,
        user_id_secret: str = USER_ID_SECRET,
        timeout_seconds: float = 1.0,
    ) -> TestClient:
        tbox_client = TBoxClient(
            TBoxClientConfig(
                authorization=authorization,
                app_id=app_id,
                user_id_secret=user_id_secret,
                timeout_seconds=timeout_seconds,
            ),
            transport=httpx.MockTransport(handler),
        )
        service = TBoxChatService(
            tbox_client,
            TBoxSessionMapper(self.orchestrator),
            self.orchestrator,
        )
        client = TestClient(
            create_app(
                self.orchestrator,
                tbox_chat_service=service,
            ),
            raise_server_exceptions=False,
        )
        self.clients.append(client)
        return client

    @staticmethod
    def _payload(
        session_id: str,
        *,
        user_id: str = "anonymous-user-001",
        message: str = "请分析我的职业方向",
        stream: bool = False,
    ) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "user_id": user_id,
            "message": message,
            "stream": stream,
        }

    def test_non_stream_maps_conversation_and_keeps_logs_private(self) -> None:
        upstream_requests: list[dict[str, Any]] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(AUTHORIZATION, request.headers["Authorization"])
            body = json.loads(request.content)
            upstream_requests.append(body)
            response = {
                "requestId": f"upstream-request-{len(upstream_requests)}",
                "conversationId": "conversation-001",
                "messageId": f"message-{len(upstream_requests)}",
                "result": [
                    {
                        "lane": 0,
                        "extraParams": {},
                        "mediaType": "text",
                        "chunk": "这是百宝箱智能体的真实回复。",
                    }
                ],
            }
            if len(upstream_requests) == 1:
                return httpx.Response(
                    200,
                    json={
                        "errorCode": "0",
                        "errorMsg": "success",
                        "data": [response],
                        "traceId": "trace-001",
                    },
                )
            return httpx.Response(200, json=response)

        client = self._client(handler)
        first = client.post(
            "/api/tbox/chat",
            json=self._payload("chat-session-001"),
        )
        self.assertEqual(200, first.status_code, first.text)
        first_body = first.json()
        self.assertEqual(0, first_body["code"])
        self.assertEqual(
            "conversation-001", first_body["data"]["conversation_id"]
        )
        self.assertEqual(
            "这是百宝箱智能体的真实回复。",
            first_body["data"]["content"],
        )
        self.assertNotIn(AUTHORIZATION, first.text)

        second = client.post(
            "/api/tbox/chat",
            json=self._payload(
                "chat-session-001", message="继续给我具体建议"
            ),
        )
        self.assertEqual(200, second.status_code, second.text)
        self.assertNotIn("conversationId", upstream_requests[0])
        self.assertEqual(
            "conversation-001", upstream_requests[1]["conversationId"]
        )
        self.assertEqual(APP_ID, upstream_requests[0]["appId"])
        self.assertTrue(upstream_requests[0]["userId"].startswith("cp_"))
        self.assertNotEqual("anonymous-user-001", upstream_requests[0]["userId"])
        self.assertFalse(upstream_requests[0]["stream"])

        state = self.orchestrator.get_session("chat-session-001")
        assert state is not None
        self.assertEqual("conversation-001", state.platform_session_id)
        self.assertEqual(external_owner_id("anonymous-user-001"), state.user_id)

        for response in (first_body, second.json()):
            record = self.repository.get_tool_call(response["request_id"])
            assert record is not None
            self.assertEqual("tbox_agent_chat", record["tool_name"])
            self.assertEqual("succeeded", record["status"])
            self.assertEqual(
                {"response_mode": "json", "conversation_mapped": True},
                record["result_data"],
            )
            serialized = json.dumps(record, ensure_ascii=False, default=str)
            self.assertNotIn("anonymous-user-001", serialized)
            self.assertNotIn("请分析我的职业方向", serialized)
            self.assertNotIn("真实回复", serialized)
            self.assertNotIn(AUTHORIZATION, serialized)
            self.assertNotIn(USER_ID_SECRET, serialized)

    def test_stream_is_normalized_and_thinking_is_not_exposed(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            self.assertTrue(body["stream"])
            events = [
                (
                    "message",
                    {
                        "type": "header",
                        "payload": json.dumps(
                            {
                                "requestId": "upstream-stream-request",
                                "sessionId": "conversation-stream-001",
                            }
                        ),
                    },
                ),
                (
                    "message",
                    {
                        "type": "thinking",
                        "payload": json.dumps(
                            {"text": "private chain of thought must stay upstream"}
                        ),
                    },
                ),
                (
                    "message",
                    {
                        "type": "chunk",
                        "payload": json.dumps(
                            {
                                "text": "第一段",
                                "conversationId": "conversation-stream-001",
                                "messageId": "stream-message-001",
                            }
                        ),
                    },
                ),
                (
                    "message",
                    {
                        "type": "chunk",
                        "payload": json.dumps(
                            {
                                "text": "第二段",
                                "conversationId": "conversation-stream-001",
                                "messageId": "stream-message-001",
                            }
                        ),
                    },
                ),
                ("end", {"type": "end"}),
            ]
            content = "".join(
                f"event: {name}\ndata: {json.dumps(data)}\n\n"
                for name, data in events
            )
            return httpx.Response(
                200,
                text=content,
                headers={"Content-Type": "text/event-stream"},
            )

        response = self._client(handler).post(
            "/api/tbox/chat",
            json=self._payload("chat-stream-001", stream=True),
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertTrue(
            response.headers["content-type"].startswith("text/event-stream")
        )
        self.assertNotIn("private chain of thought", response.text)
        event_names = [
            line.removeprefix("event: ")
            for line in response.text.splitlines()
            if line.startswith("event: ")
        ]
        self.assertEqual(["session", "delta", "delta", "done"], event_names)
        data = [
            json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        self.assertEqual("conversation-stream-001", data[0]["conversation_id"])
        self.assertEqual(["第一段", "第二段"], [data[1]["content"], data[2]["content"]])
        self.assertEqual(
            "upstream-stream-request", data[3]["upstream_request_id"]
        )

        record = self.repository.get_tool_call(data[0]["request_id"])
        assert record is not None
        self.assertEqual("succeeded", record["status"])
        self.assertEqual(
            {"response_mode": "stream", "conversation_mapped": True},
            record["result_data"],
        )

    def test_timeout_and_upstream_body_are_returned_as_safe_errors(self) -> None:
        async def slow_handler(request: httpx.Request) -> httpx.Response:
            del request
            await asyncio.sleep(0.05)
            return httpx.Response(200, json={})

        timeout_response = self._client(
            slow_handler,
            timeout_seconds=0.01,
        ).post(
            "/api/tbox/chat",
            json=self._payload("chat-timeout-001"),
        )
        self.assertEqual(504, timeout_response.status_code, timeout_response.text)
        timeout_body = timeout_response.json()
        self.assertEqual("TBOX_CHAT_TIMEOUT", timeout_body["error"]["type"])
        timeout_record = self.repository.get_tool_call(timeout_body["request_id"])
        assert timeout_record is not None
        self.assertEqual("timed_out", timeout_record["status"])

        async def failed_handler(request: httpx.Request) -> httpx.Response:
            del request
            return httpx.Response(
                500,
                text="upstream traceback with secret platform details",
            )

        failed_response = self._client(failed_handler).post(
            "/api/tbox/chat",
            json=self._payload("chat-upstream-failure-001"),
        )
        self.assertEqual(502, failed_response.status_code, failed_response.text)
        self.assertEqual(
            "TBOX_UPSTREAM_UNAVAILABLE",
            failed_response.json()["error"]["type"],
        )
        self.assertNotIn("traceback", failed_response.text)
        self.assertNotIn("secret platform details", failed_response.text)
        self.assertNotIn(AUTHORIZATION, failed_response.text)

    def test_stream_protocol_failure_is_a_safe_sse_error_and_is_logged(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            del request
            return httpx.Response(
                200,
                text=(
                    "event: message\n"
                    "data: {\"type\":\"header\",\"payload\":\"not-json\"}\n\n"
                ),
                headers={"Content-Type": "text/event-stream"},
            )

        response = self._client(handler).post(
            "/api/tbox/chat",
            json=self._payload("chat-stream-error-001", stream=True),
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn("event: error", response.text)
        self.assertNotIn("not-json", response.text)
        event_data = next(
            json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines()
            if line.startswith("data: ")
        )
        self.assertEqual("TBOX_RESPONSE_INVALID", event_data["error"]["type"])
        record = self.repository.get_tool_call(event_data["request_id"])
        assert record is not None
        self.assertEqual("failed", record["status"])
        self.assertEqual("TBOX_RESPONSE_INVALID", record["error_type"])

    def test_configuration_validation_and_session_identity_fail_closed(self) -> None:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            del request
            calls += 1
            return httpx.Response(200, json={})

        unconfigured = self._client(
            handler,
            authorization="",
            app_id="",
            user_id_secret="",
        )
        response = unconfigured.post(
            "/api/tbox/chat",
            json=self._payload("chat-unconfigured-001"),
        )
        self.assertEqual(503, response.status_code, response.text)
        self.assertEqual("TBOX_CHAT_NOT_CONFIGURED", response.json()["error"]["type"])
        self.assertEqual(0, calls)
        self.assertIsNone(self.orchestrator.get_session("chat-unconfigured-001"))

        invalid = unconfigured.post(
            "/api/tbox/chat",
            json={**self._payload("chat-invalid-001"), "api_key": "browser-secret"},
        )
        self.assertEqual(422, invalid.status_code, invalid.text)
        self.assertEqual("REQUEST_VALIDATION_FAILED", invalid.json()["error"]["type"])
        self.assertNotIn("browser-secret", invalid.text)

        unconfigured_stream = unconfigured.post(
            "/api/tbox/chat",
            json=self._payload("chat-unconfigured-stream-001", stream=True),
        )
        self.assertEqual(503, unconfigured_stream.status_code)
        self.assertEqual(
            "TBOX_CHAT_NOT_CONFIGURED",
            unconfigured_stream.json()["error"]["type"],
        )

        self.orchestrator.persist(
            CareerState(session_id="chat-owner-001", user_id="owner-a")
        )
        configured = self._client(handler)
        conflict = configured.post(
            "/api/tbox/chat",
            json=self._payload("chat-owner-001", user_id="owner-b"),
        )
        self.assertEqual(409, conflict.status_code, conflict.text)
        self.assertEqual("SESSION_USER_CONFLICT", conflict.json()["error"]["type"])
        self.assertEqual(0, calls)

    def test_openapi_documents_one_unified_chat_entry(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            del request
            return httpx.Response(500)

        openapi = self._client(handler).get("/openapi.json").json()
        operation = openapi["paths"]["/api/tbox/chat"]["post"]
        self.assertEqual("chat_with_tbox_agent", operation["operationId"])
        self.assertIn("TBoxChatRequest", json.dumps(operation))
        self.assertIn(
            "text/event-stream", operation["responses"]["200"]["content"]
        )
        self.assertNotIn(AUTHORIZATION, json.dumps(openapi))
        self.assertNotIn(USER_ID_SECRET, json.dumps(openapi))


if __name__ == "__main__":
    unittest.main()
