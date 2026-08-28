"""Protocol and business integration tests for the remote MCP server."""

from __future__ import annotations

import json
import unittest
import uuid
from pathlib import Path
from typing import Any

import httpx2
from fastapi.testclient import TestClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.agents.feedback_agent import FeedbackAgent
from app.agents.job_agent import JobAgent
from app.agents.match_agent import MatchAgent
from app.agents.path_agent import PathAgent
from app.agents.profile_agent import ProfileAgent
from app.agents.training_agent import TrainingAgent
from app.db_state import StateRepository
from app.main import create_app
from app.mcp.server import create_career_mcp_server
from app.orchestrator import CareerOrchestrator
from app.schemas.career_profile_schema import StudentProfile
from app.schemas.job_schema import JobProfile
from app.schemas.match_schema import MatchResult
from app.schemas.path_schema import PathResult


TOKEN = "test-only-mcp-token"
USER_ID = "anonymous-user-001"
LONG_ANSWER = (
    "我会先同步当前进展和已经确认的事实，再说明风险、下一步与负责人，"
    "并使用异步文档记录决策和反馈期限，确保所有参与者都能追踪。"
)


class OfflineLLMClient:
    """Fail every model call so tests prove the Service/fallback path is local."""

    async def generate_structured(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("simulated offline LLM")


def student_tool_arguments() -> dict[str, Any]:
    return {
        "resume_text": (
            "匿名候选人使用产品规划、需求分析和数据驱动决策完成AI产品项目。"
            "联络信息 candidate@example.com 13800138000 仅用于脱敏日志测试。"
        ),
        "education_level": "硕士",
        "major": "统计学（演示）",
        "graduation_year": 2026,
        "city": "上海",
        "target_job": "AI产品经理",
        "target_industry": "人工智能",
        "years_of_experience": 0.5,
        "skills": [
            "产品规划",
            "需求分析",
            "数据驱动决策",
            "大模型应用",
            "用户研究",
            "项目管理",
            "沟通表达",
        ],
        "projects": ["完成匿名AI产品方案、用户研究、需求拆解和大模型应用原型。"],
        "internships": ["参与匿名项目管理和跨团队沟通表达。"],
    }


def target_job_tool_arguments() -> dict[str, Any]:
    return {
        "job_id": 91001,
        "job_title": "AI产品经理",
        "industry": "人工智能",
        "city": "上海",
        "job_description": "匿名演示岗位，要求产品规划、需求分析和沟通表达。",
    }


def real_orchestrator(repository: StateRepository) -> CareerOrchestrator:
    offline = OfflineLLMClient()
    return CareerOrchestrator(
        agents=[
            ProfileAgent(client=offline),
            JobAgent(client=offline),
            MatchAgent(client=offline),
            PathAgent(client=offline),
            TrainingAgent(client=offline),
            FeedbackAgent(client=offline),
        ],
        repository=repository,
    )


class CareerPulseMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        runtime_dir = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime_dir / f"mcp-{uuid.uuid4().hex}.sqlite3"
        self.repository = StateRepository(sqlite_path=self.db_path)
        self.orchestrator = real_orchestrator(self.repository)
        self.server = create_career_mcp_server(
            self.orchestrator,
            timeout_seconds=2,
        )

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)
        Path(f"{self.db_path}-shm").unlink(missing_ok=True)
        Path(f"{self.db_path}-wal").unlink(missing_ok=True)

    def test_mcp_configuration_requires_token_when_auth_is_enabled(self) -> None:
        with self.assertRaisesRegex(ValueError, "MCP_API_TOKEN"):
            create_app(
                self.orchestrator,
                mcp_enabled=True,
                mcp_auth_enabled=True,
                mcp_api_token="",
            )
        disabled = create_app(
            self.orchestrator,
            mcp_enabled=False,
            mcp_auth_enabled=True,
            mcp_api_token="",
        )
        self.assertFalse(disabled.state.mcp_enabled)

    async def _run_chain(
        self, client: Client, session_id: str
    ) -> tuple[dict[str, Any], ...]:
        common = {"session_id": session_id, "user_id": USER_ID}
        profile = await client.call_tool(
            "build_student_profile",
            {
                **common,
                "trace_id": f"tool-{session_id}-profile",
                **student_tool_arguments(),
            },
        )
        job = await client.call_tool(
            "analyze_target_job",
            {
                **common,
                "trace_id": f"tool-{session_id}-job",
                **target_job_tool_arguments(),
            },
        )
        match = await client.call_tool(
            "analyze_job_match",
            {**common, "trace_id": f"tool-{session_id}-match"},
        )
        path = await client.call_tool(
            "generate_career_path",
            {**common, "trace_id": f"tool-{session_id}-path"},
        )
        for result in (profile, job, match, path):
            self.assertFalse(result.is_error, result)
            self.assertIsNotNone(result.structured_content)
        return tuple(
            result.structured_content for result in (profile, job, match, path)
        )

    async def test_initialize_tools_list_and_input_schemas(self) -> None:
        async with Client(self.server, mode="legacy") as client:
            self.assertIsNotNone(client.session.initialize_result)
            self.assertEqual("CareerPulse-A02", client.server_info.name)
            listed = await client.list_tools()

        expected = {
            "build_student_profile",
            "analyze_target_job",
            "analyze_job_match",
            "generate_career_path",
            "generate_and_score_training",
            "recommend_learning_and_job_resources",
            "save_growth_feedback",
        }
        self.assertEqual(expected, {tool.name for tool in listed.tools})
        schemas = {tool.name: tool.input_schema for tool in listed.tools}
        for name, schema in schemas.items():
            self.assertEqual(False, schema.get("additionalProperties"), name)
            self.assertTrue({"session_id", "user_id"}.issubset(schema["required"]))
            self.assertIn("trace_id", schema["properties"])
            for field_name, field_schema in schema["properties"].items():
                self.assertTrue(
                    field_schema.get("description"),
                    f"{name}.{field_name} is missing a parameter description",
                )
        profile_schema = schemas["build_student_profile"]
        job_schema = schemas["analyze_target_job"]
        nested_schema_json = json.dumps(
            [profile_schema, job_schema], ensure_ascii=False, sort_keys=True
        )
        self.assertNotIn('"$ref"', nested_schema_json)
        self.assertNotIn('"$defs"', nested_schema_json)
        self.assertNotIn("student_input", profile_schema["properties"])
        self.assertNotIn("target_job_input", job_schema["properties"])
        self.assertIn("resume_text", profile_schema["properties"])
        self.assertIn("skills", profile_schema["properties"])
        self.assertIn("job_title", job_schema["required"])
        self.assertEqual(
            {"string", "null"},
            {
                item["type"]
                for item in profile_schema["properties"]["resume_text"]["anyOf"]
            },
        )
        skills_options = profile_schema["properties"]["skills"]["anyOf"]
        self.assertEqual(
            {"string", "array", "null"},
            {option["type"] for option in skills_options},
        )
        self.assertIn(
            "JSON array text",
            profile_schema["properties"]["skills"]["description"],
        )
        skills_array = next(
            option for option in skills_options if option["type"] == "array"
        )
        self.assertEqual("string", skills_array["items"]["type"])
        self.assertEqual("string", job_schema["properties"]["job_title"]["type"])
        self.assertNotIn("student_profile", schemas["analyze_job_match"]["properties"])
        self.assertNotIn("match_result", schemas["generate_career_path"]["properties"])
        training_schema = schemas["generate_and_score_training"]
        resource_schema = schemas["recommend_learning_and_job_resources"]
        feedback_schema = schemas["save_growth_feedback"]
        self.assertEqual(
            {"session_id", "user_id"},
            set(training_schema["required"]),
        )
        self.assertEqual(
            {
                "session_id",
                "user_id",
                "training_type",
                "training_id",
                "user_answer",
                "trace_id",
            },
            set(training_schema["properties"]),
        )
        training_type_schema = training_schema["properties"]["training_type"]
        self.assertEqual(
            {"string", "null"},
            {option["type"] for option in training_type_schema["anyOf"]},
        )
        self.assertNotIn("enum", json.dumps(training_type_schema))
        self.assertIn("remote_collaboration", training_type_schema["description"])
        self.assertEqual(
            {"session_id", "user_id", "trace_id"},
            set(resource_schema["properties"]),
        )
        self.assertEqual(
            {"session_id", "user_id", "satisfaction"},
            set(feedback_schema["required"]),
        )
        self.assertEqual(
            {"string", "integer"},
            {
                option["type"]
                for option in feedback_schema["properties"]["satisfaction"]["anyOf"]
            },
        )
        self.assertEqual(
            {"string", "integer", "null"},
            {
                option["type"]
                for option in feedback_schema["properties"]["resource_rating"]["anyOf"]
            },
        )

    async def test_build_student_profile_accepts_flat_tbox_json_arguments(self) -> None:
        session_id = "mcp-flat-profile-001"
        arguments = {
            "session_id": session_id,
            "user_id": USER_ID,
            "trace_id": "tool-flat-profile-001",
            **student_tool_arguments(),
        }
        async with Client(self.server, mode="legacy") as client:
            result = await client.call_tool("build_student_profile", arguments)

        self.assertFalse(result.is_error, result)
        self.assertTrue(result.structured_content["success"])
        state = self.orchestrator.get_session(session_id)
        assert state is not None
        self.assertEqual(arguments["resume_text"], state.student_input["resume_text"])
        self.assertEqual(arguments["skills"], state.student_input["skills"])
        self.assertEqual(
            {
                "education_level": "硕士",
                "major": "统计学（演示）",
                "graduation_year": 2026,
                "city": "上海",
                "target_job": "AI产品经理",
                "target_industry": "人工智能",
                "years_of_experience": 0.5,
            },
            state.student_input["form_fields"],
        )

    async def test_build_student_profile_normalizes_antbox_string_lists(self) -> None:
        cases = (
            ({"skills": "Python, Vue3, FastAPI"}, "skills", ["Python", "Vue3", "FastAPI"]),
            ({"skills": ["Python", "Vue3", "FastAPI"]}, "skills", ["Python", "Vue3", "FastAPI"]),
            ({"skills": '["Python", "Vue3", "FastAPI"]'}, "skills", ["Python", "Vue3", "FastAPI"]),
            ({"skills": "Vue, Python, FastAPI"}, "skills", ["Vue", "Python", "FastAPI"]),
            ({"skills": "Vue，Python，FastAPI"}, "skills", ["Vue", "Python", "FastAPI"]),
            ({"skills": "Vue、Python、FastAPI"}, "skills", ["Vue", "Python", "FastAPI"]),
            ({"skills": "Vue\nPython\nFastAPI"}, "skills", ["Vue", "Python", "FastAPI"]),
            ({"skills": "Vue"}, "skills", ["Vue"]),
            ({"skills": ""}, "skills", []),
            ({"skills": None}, "skills", None),
            (
                {"projects": "AI 聊天助手，招聘匹配系统"},
                "projects",
                ["AI 聊天助手", "招聘匹配系统"],
            ),
            ({"projects": "AI 应用项目"}, "projects", ["AI 应用项目"]),
            ({"projects": None}, "projects", None),
            (
                {"competitions": '["挑战杯", "创新创业大赛"]'},
                "competitions",
                ["挑战杯", "创新创业大赛"],
            ),
        )
        async with Client(self.server, mode="legacy") as client:
            for index, (field_value, field_name, expected) in enumerate(cases):
                session_id = f"mcp-profile-normalize-{index:02d}"
                result = await client.call_tool(
                    "build_student_profile",
                    {
                        "session_id": session_id,
                        "user_id": USER_ID,
                        "resume_text": "匿名计算机专业学生画像证据。",
                        **field_value,
                    },
                )
                self.assertFalse(result.is_error, result)
                self.assertTrue(result.structured_content["success"])
                state = self.orchestrator.get_session(session_id)
                assert state is not None
                self.assertEqual(expected, state.student_input.get(field_name))

    async def test_profile_and_job_numeric_text_is_normalized_before_strict_models(
        self,
    ) -> None:
        session_id = "mcp-numeric-text-001"
        common = {"session_id": session_id, "user_id": USER_ID}
        async with Client(self.server, mode="legacy") as client:
            profile = await client.call_tool(
                "build_student_profile",
                {
                    **common,
                    "major": "计算机科学",
                    "graduation_year": "2026",
                    "years_of_experience": "0.5",
                    "skills": "Vue, Python, FastAPI",
                },
            )
            job = await client.call_tool(
                "analyze_target_job",
                {
                    **common,
                    "job_title": "AI 应用开发工程师",
                    "job_id": "91001",
                },
            )

        self.assertFalse(profile.is_error, profile)
        self.assertFalse(job.is_error, job)
        state = self.orchestrator.get_session(session_id)
        assert state is not None
        self.assertEqual(2026, state.student_input["form_fields"]["graduation_year"])
        self.assertEqual(0.5, state.student_input["form_fields"]["years_of_experience"])
        self.assertEqual(91001, state.target_job_input["job_id"])

    async def test_analyze_target_job_accepts_flat_tbox_json_arguments(self) -> None:
        session_id = "mcp-flat-job-001"
        arguments = {
            "session_id": session_id,
            "user_id": USER_ID,
            "trace_id": "tool-flat-job-001",
            **target_job_tool_arguments(),
        }
        async with Client(self.server, mode="legacy") as client:
            result = await client.call_tool("analyze_target_job", arguments)

        self.assertFalse(result.is_error, result)
        self.assertTrue(result.structured_content["success"])
        state = self.orchestrator.get_session(session_id)
        assert state is not None
        self.assertEqual(target_job_tool_arguments(), state.target_job_input)

    async def test_four_real_tools_chain_state_fallback_and_private_logs(self) -> None:
        session_id = "mcp-chain-001"
        async with Client(self.server, mode="legacy") as client:
            profile, job, match, path = await self._run_chain(client, session_id)

        self.assertEqual("PROFILE_COMPLETED", profile["status"])
        self.assertTrue(profile["data"]["fallback_used"])
        StudentProfile.model_validate(profile["data"]["student_profile"])
        self.assertEqual("JOB_COMPLETED", job["status"])
        self.assertTrue(job["data"]["fallback_used"])
        JobProfile.model_validate(job["data"]["job_profile"])
        self.assertEqual("MATCH_COMPLETED", match["status"])
        MatchResult.model_validate(match["data"]["match_result"])
        self.assertEqual("PATH_COMPLETED", path["status"])
        PathResult.model_validate(path["data"]["career_roadmap"])

        state = self.orchestrator.get_session(session_id)
        assert state is not None
        self.assertEqual("PATH_COMPLETED", state.status)
        self.assertEqual(
            ["ProfileAgent", "JobAgent", "MatchAgent", "PathAgent"],
            [log.agent_name for log in state.agent_logs],
        )
        for suffix, agent_name in (
            ("profile", "ProfileAgent"),
            ("job", "JobAgent"),
            ("match", "MatchAgent"),
            ("path", "PathAgent"),
        ):
            trace_id = f"tool-{session_id}-{suffix}"
            record = self.repository.get_tool_call(trace_id)
            assert record is not None
            self.assertEqual(trace_id, record["tool_call_id"])
            self.assertEqual(session_id, record["session_id"])
            self.assertEqual("succeeded", record["status"])
            self.assertEqual(f"{session_id}:{agent_name}", record["agent_run_key"])
        serialized_logs = json.dumps(
            self.repository.list_agent_logs(session_id), ensure_ascii=False
        )
        self.assertIn(session_id, serialized_logs)
        self.assertNotIn("candidate@example.com", serialized_logs)
        self.assertNotIn("13800138000", serialized_logs)
        self.assertNotIn(TOKEN, serialized_logs)

    async def test_stage4_tools_continuous_session_generate_score_resources_feedback(
        self,
    ) -> None:
        session_id = "mcp-stage4-chain-001"
        common = {"session_id": session_id, "user_id": USER_ID}
        async with Client(self.server, mode="legacy") as client:
            listed = await client.list_tools()
            self.assertEqual(7, len(listed.tools))
            await self._run_chain(client, session_id)
            generated = await client.call_tool(
                "generate_and_score_training",
                {
                    **common,
                    "trace_id": "tool-stage4-generate-001",
                    "training_type": "remote_collaboration",
                },
            )
            self.assertFalse(generated.is_error, generated)
            generated_body = generated.structured_content
            self.assertTrue(generated_body["success"])
            self.assertEqual("generate", generated_body["data"]["mode"])
            training_id = generated_body["data"]["training_task"]["training_id"]

            scored = await client.call_tool(
                "generate_and_score_training",
                {
                    **common,
                    "trace_id": "tool-stage4-score-001",
                    "training_id": training_id,
                    "user_answer": LONG_ANSWER,
                },
            )
            resources = await client.call_tool(
                "recommend_learning_and_job_resources",
                {**common, "trace_id": "tool-stage4-resources-001"},
            )
            feedback = await client.call_tool(
                "save_growth_feedback",
                {
                    **common,
                    "trace_id": "tool-stage4-feedback-001",
                    "satisfaction": "4",
                    "path_rating": 5,
                    "training_rating": 4,
                    "resource_rating": 4,
                    "comments": "希望继续提供结构化训练建议。",
                },
            )

        for result in (scored, resources, feedback):
            self.assertFalse(result.is_error, result)
            self.assertTrue(result.structured_content["success"])
        scored_body = scored.structured_content
        self.assertEqual("score", scored_body["data"]["mode"])
        self.assertEqual(
            training_id, scored_body["data"]["training_score"]["training_id"]
        )
        self.assertEqual(
            "ResourceService", resources.structured_content["data"]["service_name"]
        )
        self.assertTrue(
            feedback.structured_content["data"]["feedback_result"]["feedback_saved"]
        )
        state = self.orchestrator.get_session(session_id)
        assert state is not None
        self.assertEqual("FEEDBACK_COMPLETED", state.status)
        self.assertIsNotNone(state.training_plan)
        self.assertIsNotNone(state.resource_result)
        self.assertIsNotNone(state.feedback_result)
        self.assertNotIn(LONG_ANSWER, json.dumps(state.model_dump(), ensure_ascii=False))

    async def test_feedback_ratings_accept_numeric_text_and_native_integers(
        self,
    ) -> None:
        cases = (
            ("3", "4"),
            (3, 4),
        )
        async with Client(self.server, mode="legacy") as client:
            for index, (satisfaction, resource_rating) in enumerate(cases):
                session_id = f"mcp-feedback-normalize-{index:02d}"
                common = {"session_id": session_id, "user_id": USER_ID}
                profile = await client.call_tool(
                    "build_student_profile",
                    {
                        **common,
                        "resume_text": "匿名学生具备 Python 与 Vue3 项目经验。",
                        "skills": "Python, Vue3, FastAPI",
                    },
                )
                self.assertFalse(profile.is_error, profile)
                feedback = await client.call_tool(
                    "save_growth_feedback",
                    {
                        **common,
                        "satisfaction": satisfaction,
                        "resource_rating": resource_rating,
                    },
                )
                self.assertFalse(feedback.is_error, feedback)
                self.assertTrue(feedback.structured_content["success"])

    async def test_training_type_accepts_internal_values_and_explicit_chinese_aliases(
        self,
    ) -> None:
        session_id = "mcp-training-aliases-001"
        common = {"session_id": session_id, "user_id": USER_ID}
        cases = (
            ("remote_collaboration", "remote_collaboration"),
            ("远程协作", "remote_collaboration"),
            ("AI 办公任务", "ai_office_task"),
            ("跨岗沟通", "cross_role_communication"),
        )
        async with Client(self.server, mode="legacy") as client:
            await self._run_chain(client, session_id)
            for index, (raw_type, expected_type) in enumerate(cases):
                result = await client.call_tool(
                    "generate_and_score_training",
                    {
                        **common,
                        "trace_id": f"tool-training-alias-{index:02d}",
                        "training_type": raw_type,
                    },
                )
                self.assertFalse(result.is_error, result)
                self.assertTrue(result.structured_content["success"])
                self.assertEqual(
                    expected_type,
                    result.structured_content["data"]["training_task"]["type"],
                )

    async def test_training_type_rejects_unsupported_interview_request_clearly(
        self,
    ) -> None:
        async with Client(self.server, mode="legacy") as client:
            result = await client.call_tool(
                "generate_and_score_training",
                {
                    "session_id": "mcp-unsupported-training",
                    "user_id": USER_ID,
                    "training_type": "AI 应用开发工程师面试自我介绍",
                },
            )

        self.assertTrue(result.is_error, result)
        error_text = " ".join(
            getattr(item, "text", "") for item in result.content
        )
        self.assertIn("training_type is unsupported", error_text)
        self.assertIn("当前不支持面试自我介绍类训练", error_text)

    async def test_stage4_schema_rejects_invalid_and_missing_arguments(self) -> None:
        common = {"session_id": "mcp-stage4-invalid", "user_id": USER_ID}
        async with Client(self.server, mode="legacy") as client:
            invalid_training_type = await client.call_tool(
                "generate_and_score_training",
                {**common, "training_type": "unsupported_training"},
            )
            missing_training_mode = await client.call_tool(
                "generate_and_score_training",
                common,
            )
            extra_resource_context = await client.call_tool(
                "recommend_learning_and_job_resources",
                {**common, "ability_gaps": ["caller override forbidden"]},
            )
            missing_resource_user = await client.call_tool(
                "recommend_learning_and_job_resources",
                {"session_id": "mcp-stage4-invalid"},
            )
            invalid_feedback_rating = await client.call_tool(
                "save_growth_feedback",
                {**common, "satisfaction": 6},
            )
            invalid_feedback_text = await client.call_tool(
                "save_growth_feedback",
                {**common, "satisfaction": "four"},
            )
            missing_feedback_rating = await client.call_tool(
                "save_growth_feedback",
                common,
            )

        for result in (
            invalid_training_type,
            missing_training_mode,
            extra_resource_context,
            missing_resource_user,
            invalid_feedback_rating,
            invalid_feedback_text,
            missing_feedback_rating,
        ):
            self.assertTrue(result.is_error, result)
        numeric_error_text = " ".join(
            getattr(item, "text", "") for item in invalid_feedback_text.content
        )
        self.assertIn("satisfaction must be an integer", numeric_error_text)

    async def test_stage4_handler_failures_return_safe_mcp_envelopes(self) -> None:
        session_id = "mcp-stage4-prerequisite-failure"
        common = {"session_id": session_id, "user_id": USER_ID}
        async with Client(self.server, mode="legacy") as client:
            missing_session = await client.call_tool(
                "generate_and_score_training",
                {
                    "session_id": "mcp-stage4-missing-session",
                    "user_id": USER_ID,
                    "training_type": "remote_collaboration",
                },
            )
            await client.call_tool(
                "build_student_profile", {**common, **student_tool_arguments()}
            )
            await client.call_tool(
                "analyze_target_job", {**common, **target_job_tool_arguments()}
            )
            training = await client.call_tool(
                "generate_and_score_training",
                {**common, "training_type": "remote_collaboration"},
            )
            resources = await client.call_tool(
                "recommend_learning_and_job_resources", common
            )
            feedback = await client.call_tool(
                "save_growth_feedback",
                {
                    **common,
                    "satisfaction": 4,
                    "comments": "请联系 private@example.com",
                },
            )

        self.assertFalse(missing_session.is_error, missing_session)
        self.assertFalse(missing_session.structured_content["success"])
        self.assertEqual(
            "SESSION_NOT_FOUND", missing_session.structured_content["error_code"]
        )
        self.assertFalse(training.is_error, training)
        self.assertFalse(training.structured_content["success"])
        self.assertEqual(
            "TRAINING_PREREQUISITES_NOT_READY",
            training.structured_content["error_code"],
        )
        self.assertFalse(resources.is_error, resources)
        self.assertFalse(resources.structured_content["success"])
        self.assertEqual(
            "MATCH_RESULT_NOT_FOUND", resources.structured_content["error_code"]
        )
        self.assertFalse(feedback.is_error, feedback)
        self.assertFalse(feedback.structured_content["success"])
        self.assertEqual("FEEDBACK_FAILED", feedback.structured_content["error_code"])
        self.assertNotIn("private@example.com", feedback.structured_content["message"])

    async def test_mcp_match_and_path_equal_existing_http_tools(self) -> None:
        mcp_session = "mcp-consistency-001"
        async with Client(self.server, mode="legacy") as client:
            profile, job, mcp_match, mcp_path = await self._run_chain(
                client, mcp_session
            )

        http_db = self.db_path.with_name(f"http-{uuid.uuid4().hex}.sqlite3")
        http_repository = StateRepository(sqlite_path=http_db)
        http_orchestrator = real_orchestrator(http_repository)
        http_app = create_app(
            http_orchestrator,
            tbox_api_token=TOKEN,
            tbox_tool_timeout_seconds=2,
        )
        http_session = "http-consistency-001"
        headers = {"Authorization": f"Bearer {TOKEN}"}
        with TestClient(http_app) as http_client:
            match_response = http_client.post(
                "/api/platform/v1/tools/analyze_job_match",
                headers=headers,
                json={
                    "schema_version": "stage3-tool-v1",
                    "idempotency_key": "http-match-consistency-001",
                    "session_id": http_session,
                    "user_id": USER_ID,
                    "student_profile": profile["data"]["student_profile"],
                    "job_profile": job["data"]["job_profile"],
                },
            )
            self.assertEqual(200, match_response.status_code, match_response.text)
            path_response = http_client.post(
                "/api/platform/v1/tools/generate_career_path",
                headers=headers,
                json={
                    "schema_version": "stage3-tool-v1",
                    "idempotency_key": "http-path-consistency-001",
                    "session_id": http_session,
                    "user_id": USER_ID,
                },
            )
            self.assertEqual(200, path_response.status_code, path_response.text)

        self.assertEqual(
            mcp_match["data"]["match_result"],
            match_response.json()["data"]["match_result"],
        )
        self.assertEqual(
            mcp_path["data"]["career_roadmap"],
            path_response.json()["data"]["career_roadmap"],
        )
        http_db.unlink(missing_ok=True)
        Path(f"{http_db}-shm").unlink(missing_ok=True)
        Path(f"{http_db}-wal").unlink(missing_ok=True)

    async def test_prerequisites_and_schema_rejection_are_explicit(self) -> None:
        async with Client(self.server, mode="legacy") as client:
            missing = await client.call_tool(
                "analyze_job_match",
                {"session_id": "mcp-missing", "user_id": USER_ID},
            )
            missing_body = missing.structured_content
            self.assertFalse(missing_body["success"])
            self.assertEqual("SESSION_NOT_FOUND", missing_body["error_code"])
            self.assertEqual(
                ["student_profile", "job_profile"], missing_body["missing_fields"]
            )

            job_only = {"session_id": "mcp-job-only", "user_id": USER_ID}
            await client.call_tool(
                "analyze_target_job",
                {**job_only, **target_job_tool_arguments()},
            )
            missing_profile = await client.call_tool(
                "analyze_job_match", job_only
            )
            missing_profile_body = missing_profile.structured_content
            self.assertFalse(missing_profile_body["success"])
            self.assertEqual(
                "MATCH_PREREQUISITES_NOT_READY",
                missing_profile_body["error_code"],
            )
            self.assertEqual(
                ["student_profile"], missing_profile_body["missing_fields"]
            )

            common = {"session_id": "mcp-path-early", "user_id": USER_ID}
            await client.call_tool(
                "build_student_profile",
                {**common, **student_tool_arguments()},
            )
            await client.call_tool(
                "analyze_target_job",
                {**common, **target_job_tool_arguments()},
            )
            early_path = await client.call_tool("generate_career_path", common)
            early_body = early_path.structured_content
            self.assertFalse(early_body["success"])
            self.assertEqual("MATCH_NOT_COMPLETED", early_body["error_code"])
            self.assertEqual(["match_result"], early_body["missing_fields"])

            invalid = await client.call_tool(
                "analyze_job_match", {"session_id": "missing-user-id"}
            )
            self.assertTrue(invalid.is_error)
            extra = await client.call_tool(
                "analyze_job_match",
                {
                    "session_id": "unexpected-field",
                    "user_id": USER_ID,
                    "invented_score": 100,
                },
            )
            self.assertTrue(extra.is_error)

    async def test_streamable_http_authorization_and_remote_call(self) -> None:
        app = create_app(
            self.orchestrator,
            mcp_enabled=True,
            mcp_auth_enabled=True,
            mcp_api_token=TOKEN,
            mcp_host="127.0.0.1",
            mcp_path="/mcp",
            mcp_allowed_hosts=["testserver"],
            mcp_allowed_origins=["http://testserver"],
        )
        transport = httpx2.ASGITransport(app=app)
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as unauthorized:
                response = await unauthorized.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1"},
                        },
                    },
                    headers={"Accept": "application/json, text/event-stream"},
                )
                self.assertEqual(401, response.status_code)
                self.assertNotIn(TOKEN, response.text)

            async with httpx2.AsyncClient(
                transport=transport,
                base_url="http://testserver",
                headers={"Authorization": f"Bearer {TOKEN}"},
                follow_redirects=True,
            ) as authorized_http:
                remote_transport = streamable_http_client(
                    "http://testserver/mcp",
                    http_client=authorized_http,
                )
                async with Client(remote_transport, mode="legacy") as client:
                    self.assertIsNotNone(client.session.initialize_result)
                    listed = await client.list_tools()
                    self.assertEqual(7, len(listed.tools))
                    result = await client.call_tool(
                        "analyze_job_match",
                        {"session_id": "remote-missing", "user_id": USER_ID},
                    )
                    self.assertFalse(result.structured_content["success"])
                    self.assertEqual(
                        "SESSION_NOT_FOUND",
                        result.structured_content["error_code"],
                    )


if __name__ == "__main__":
    unittest.main()
