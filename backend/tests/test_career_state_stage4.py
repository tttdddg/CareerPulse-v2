"""CareerState compatibility and Stage 4 session-context tests."""

from __future__ import annotations

import unittest
import uuid
from pathlib import Path

from app.db_state import StateRepository
from app.orchestrator.career_orchestrator import CareerOrchestrator
from app.orchestrator.career_state import CareerState


def training_task(training_id: str, target: str) -> dict[str, object]:
    return {
        "training_id": training_id,
        "type": "remote_collaboration",
        "title": f"训练 {training_id}",
        "scenario": "场景",
        "task_description": "任务",
        "evaluation_criteria": [],
        "target_abilities": [target],
    }


class CareerStateStage4Tests(unittest.TestCase):
    def test_old_state_initializes_with_fail_safe_stage4_defaults(self) -> None:
        state = CareerState.model_validate(
            {
                "session_id": "old-session",
                "student_profile": {"profile": "legacy"},
                "match_result": {"overall_score": 71.5},
            }
        )

        self.assertIsNone(state.training_plan)
        self.assertIsNone(state.resource_result)
        self.assertIsNone(state.feedback_result)
        self.assertIsNone(state.get_training_task())
        self.assertIsNone(state.get_latest_training_score())
        self.assertEqual([], state.get_latest_ability_updates())
        self.assertIsNone(state.get_growth_snapshot())
        self.assertIsNone(state.get_skill_gaps())
        self.assertEqual(71.5, state.get_match_overall_score())

    def test_profile_match_and_path_fields_keep_existing_write_style(self) -> None:
        state = CareerState(session_id="existing-flow")
        state.apply_agent_data({"student_profile": {"name": "匿名用户"}})
        state.apply_agent_data({"job_profile": {"title": "数据分析师"}})
        state.apply_agent_data(
            {
                "match_result": {
                    "overall_score": 80.0,
                    "skill_gaps": [{"dimension": "Python", "priority": 1}],
                }
            }
        )
        state.apply_agent_data(
            {
                "path_plan": {"target_job": "数据分析师"},
                "learning_plan": {"phases": []},
                "career_roadmap": {"status": "success"},
            }
        )

        self.assertEqual("匿名用户", state.student_profile["name"])
        self.assertEqual("数据分析师", state.job_profile["title"])
        self.assertEqual(80.0, state.get_match_overall_score())
        self.assertEqual("Python", state.get_skill_gaps()[0]["dimension"])
        self.assertEqual("success", state.career_roadmap["status"])

    def test_training_task_score_and_ability_updates_share_one_container(self) -> None:
        task = training_task("training-1", "沟通协作")
        state = CareerState(session_id="training-state")
        state.apply_agent_data(
            {
                "training_plan": {
                    "trainings": [task],
                    "generated_at": "2026-08-24T00:00:00+00:00",
                }
            }
        )
        self.assertEqual(task, state.get_training_task("training-1"))
        self.assertEqual(["沟通协作"], state.get_latest_training_target_abilities())

        score = {
            "training_id": "training-1",
            "total_score": 84.0,
            "dimension_scores": [],
            "overall_comment": "完成良好",
            "improvement_suggestions": [],
            "ability_updates": [{"tag": "沟通协作", "level_change": 1}],
        }
        state.apply_agent_data(
            {
                "training_plan": {
                    **state.training_plan,
                    "latest_score": score,
                }
            }
        )

        self.assertEqual(score, state.get_latest_training_score())
        self.assertEqual(score["ability_updates"], state.get_latest_ability_updates())
        self.assertNotIn("latest_training_score", state.model_dump())
        self.assertNotIn("latest_ability_updates", state.model_dump())

    def test_resource_feedback_and_growth_snapshot_are_written_and_read(self) -> None:
        resources = {
            "learning_resources": [{"title": "Python 基础"}],
            "job_resources": [],
            "certificate_suggestions": [],
            "data_quality_flags": [],
        }
        growth = {
            "competitiveness_score": 76.0,
            "completed_trainings": 0,
            "completed_phases": 0,
            "growth_trend": "stable",
        }
        feedback = {
            "feedback_saved": True,
            "growth_archive_updated": True,
            "updated_priorities": [],
            "growth_snapshot": growth,
            "data_quality_flags": [],
        }
        state = CareerState(session_id="result-state")
        state.apply_agent_data({"resource_result": resources})
        state.apply_agent_data({"feedback_result": feedback})

        self.assertEqual(resources, state.resource_result)
        self.assertEqual(feedback, state.feedback_result)
        self.assertEqual(growth, state.get_growth_snapshot())
        self.assertNotIn("growth_snapshot", state.model_dump())

    def test_latest_scored_task_wins_in_multi_training_plan(self) -> None:
        first = training_task("training-1", "Python")
        second = training_task("training-2", "沟通协作")
        state = CareerState(
            session_id="multi-training",
            training_plan={
                "trainings": [first, second],
                "generated_at": "2026-08-24T00:00:00+00:00",
                "latest_score": {
                    "training_id": "training-1",
                    "ability_updates": [],
                },
            },
        )

        self.assertEqual("training-1", state.get_training_task()["training_id"])
        self.assertEqual(["Python"], state.get_latest_training_target_abilities())
        self.assertEqual("training-2", state.get_training_task("training-2")["training_id"])

    def test_latest_unscored_task_is_last_generated_task(self) -> None:
        state = CareerState(
            session_id="multi-unscored",
            training_plan={
                "trainings": [
                    training_task("training-1", "Python"),
                    training_task("training-2", "沟通协作"),
                ],
                "generated_at": "2026-08-24T00:00:00+00:00",
            },
        )

        self.assertEqual("training-2", state.get_training_task()["training_id"])
        self.assertEqual(["沟通协作"], state.get_latest_training_target_abilities())

    def test_stale_latest_score_falls_back_to_last_available_task(self) -> None:
        state = CareerState(
            session_id="stale-score",
            training_plan={
                "trainings": [training_task("training-2", "沟通协作")],
                "generated_at": "2026-08-24T00:00:00+00:00",
                "latest_score": {
                    "training_id": "removed-training",
                    "ability_updates": [],
                },
            },
        )

        self.assertEqual("training-2", state.get_training_task()["training_id"])
        self.assertIsNone(state.get_training_task("removed-training"))

    def test_stage4_writes_and_reads_do_not_share_mutable_data(self) -> None:
        shared = {
            "resource_result": {
                "learning_resources": [{"title": "共享资源"}],
                "job_resources": [],
                "certificate_suggestions": [],
                "data_quality_flags": [],
            }
        }
        first = CareerState(session_id="session-a")
        second = CareerState(session_id="session-b")
        first.apply_agent_data(shared)
        second.apply_agent_data(shared)

        first.resource_result["learning_resources"][0]["title"] = "会话 A 修改"

        self.assertEqual("共享资源", second.resource_result["learning_resources"][0]["title"])
        self.assertEqual("共享资源", shared["resource_result"]["learning_resources"][0]["title"])

        read_view = second.get_skill_gaps()
        self.assertIsNone(read_view)

    def test_constructor_copies_stage4_nested_values_between_sessions(self) -> None:
        shared_plan = {
            "trainings": [training_task("training-1", "Python")],
            "generated_at": "2026-08-24T00:00:00+00:00",
        }
        first = CareerState(session_id="constructor-a", training_plan=shared_plan)
        second = CareerState(session_id="constructor-b", training_plan=shared_plan)

        first.training_plan["trainings"][0]["title"] = "会话 A 修改"

        self.assertEqual("训练 training-1", second.training_plan["trainings"][0]["title"])
        self.assertEqual("训练 training-1", shared_plan["trainings"][0]["title"])

    def test_stage4_context_survives_repository_round_trip(self) -> None:
        state = CareerState(
            session_id="persisted-stage4",
            match_result={
                "overall_score": 78.0,
                "skill_gaps": [{"dimension": "Python", "priority": 1}],
            },
            training_plan={
                "trainings": [training_task("training-1", "Python")],
                "generated_at": "2026-08-24T00:00:00+00:00",
                "latest_score": {
                    "training_id": "training-1",
                    "ability_updates": [{"tag": "Python", "level_change": 1}],
                },
            },
            resource_result={"learning_resources": [], "data_quality_flags": []},
            feedback_result={
                "growth_snapshot": {
                    "competitiveness_score": 78.0,
                    "completed_trainings": 0,
                    "completed_phases": 0,
                    "growth_trend": "stable",
                }
            },
        )

        runtime_dir = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        database = runtime_dir / f"stage4-{uuid.uuid4().hex}.sqlite3"
        try:
            CareerOrchestrator(repository=StateRepository(sqlite_path=database)).persist(state)
            restored = CareerOrchestrator(
                repository=StateRepository(sqlite_path=database)
            ).get_session("persisted-stage4")
        finally:
            database.unlink(missing_ok=True)
            Path(f"{database}-shm").unlink(missing_ok=True)
            Path(f"{database}-wal").unlink(missing_ok=True)

        self.assertIsNotNone(restored)
        self.assertEqual("training-1", restored.get_training_task()["training_id"])
        self.assertEqual(
            [{"tag": "Python", "level_change": 1}],
            restored.get_latest_ability_updates(),
        )
        self.assertEqual(78.0, restored.get_match_overall_score())
        self.assertEqual("stable", restored.get_growth_snapshot()["growth_trend"])


if __name__ == "__main__":
    unittest.main()
