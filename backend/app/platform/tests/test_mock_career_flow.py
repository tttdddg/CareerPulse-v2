"""Basic success and fallback tests for the A02 Mock skeleton."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.agents.base_agent import BaseAgent
from app.api.career_agent_api import app as career_agent_app
from app.orchestrator import CareerOrchestrator, CareerState
from app.platform import MockCareerToolRequest, app as tbox_app, run_mock_career_tool


def build_state(session_id: str = "sess-test-001") -> CareerState:
    return CareerState(
        session_id=session_id,
        platform_session_id="tbox-test-001",
        user_id="user-test",
        student_input={
            "resume_text": "private resume text must not enter logs",
            "form_fields": {"major": "数据科学"},
            "ratings": {"satisfaction": 4},
        },
        target_job_input={"job_id": 1, "job_title": "数据分析师", "industry": "互联网"},
    )


class BrokenAgent(BaseAgent):
    name = "BrokenAgent"
    output_fields = ("resource_result",)
    tool_name = "mock_broken_tool"

    async def _execute(self, state: CareerState):
        raise RuntimeError("simulated failure")

    async def _fallback(self, state: CareerState, error: Exception):
        return {"resource_result": {"fallback": True}}


class BrokenFallbackAgent(BaseAgent):
    name = "BrokenFallbackAgent"
    output_fields = ("resource_result",)

    async def _execute(self, state: CareerState):
        raise RuntimeError("simulated execution failure")

    async def _fallback(self, state: CareerState, error: Exception):
        raise RuntimeError("simulated fallback failure")


class MockCareerFlowTests(unittest.IsolatedAsyncioTestCase):
    def test_standalone_apps_expose_expected_routes(self):
        career_paths = {route.path for route in career_agent_app.routes}
        tbox_paths = {route.path for route in tbox_app.routes}

        self.assertIn("/api/career-agent/run", career_paths)
        self.assertIn("/api/career-agent/session/{session_id}", career_paths)
        self.assertIn("/api/agent/logs/{session_id}", career_paths)
        self.assertIn("/api/tbox/mock-career-analysis", tbox_paths)

    async def test_full_chain_generates_report_and_safe_logs(self):
        result = await CareerOrchestrator().run(build_state())

        self.assertEqual(6, len(result.agent_logs))
        self.assertEqual("success", result.final_report["status"])
        self.assertEqual(
            "deterministic-v1", result.match_result["matching_algorithm_version"]
        )
        self.assertIsNotNone(result.path_plan)
        self.assertIsNotNone(result.training_plan)
        serialized_logs = str([log.model_dump() for log in result.agent_logs])
        self.assertNotIn("private resume text", serialized_logs)

    async def test_failure_uses_fallback_and_continues(self):
        orchestrator = CareerOrchestrator(agents=[BrokenAgent()])
        result = await orchestrator.run(build_state("sess-fallback"))

        self.assertTrue(result.resource_result["fallback"])
        self.assertEqual("partial", result.agent_logs[0].status)
        self.assertTrue(result.agent_logs[0].fallback_used)
        self.assertEqual("partial", result.final_report["status"])

    async def test_failed_fallback_is_logged_without_stopping_report(self):
        result = await CareerOrchestrator(agents=[BrokenFallbackAgent()]).run(
            build_state("sess-fallback-error")
        )

        self.assertEqual("failed", result.agent_logs[0].status)
        self.assertTrue(result.agent_logs[0].fallback_used)
        self.assertIn("fallback", result.agent_logs[0].error)
        self.assertIsNotNone(result.final_report)

    async def test_missing_inputs_fallback_through_all_six_agents(self):
        result = await CareerOrchestrator().run(
            CareerState(session_id="sess-missing-inputs")
        )

        self.assertEqual(6, len(result.agent_logs))
        self.assertTrue(any(log.fallback_used for log in result.agent_logs))
        self.assertEqual("partial", result.final_report["status"])
        self.assertIsNotNone(result.match_result)
        self.assertIsNotNone(result.training_plan)

    async def test_tbox_mock_tool_uses_frozen_envelope(self):
        state = build_state("sess-tool")
        response = await run_mock_career_tool(
            MockCareerToolRequest(
                session_id=state.session_id,
                platform_session_id=state.platform_session_id,
                user_id=state.user_id,
                student_input=state.student_input,
                target_job_input=state.target_job_input,
            )
        )

        self.assertEqual(0, response.code)
        self.assertIsNone(response.error)
        self.assertEqual("sess-tool", response.data["session_id"])
        self.assertIn("final_report", response.data)

    async def test_tbox_mock_tool_returns_error_envelope(self):
        payload = MockCareerToolRequest(session_id="sess-tool-error")
        with patch(
            "app.platform.tbox_adapter.orchestrator.run",
            new=AsyncMock(side_effect=RuntimeError("simulated platform failure")),
        ):
            response = await run_mock_career_tool(payload)

        self.assertEqual(-1, response.code)
        self.assertIsNone(response.data)
        self.assertEqual("RuntimeError", response.error.type)


if __name__ == "__main__":
    unittest.main()
