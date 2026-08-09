"""Validate A02 seed data and optionally initialize PostgreSQL.

Examples:
    python backend/scripts/init_a02_data.py --check
    A02_DATABASE_URL=postgresql://... python backend/scripts/init_a02_data.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "app" / "data"
MIGRATION_FILE = BACKEND_DIR / "migrations" / "V001__create_a02_tables.sql"
sys.path.insert(0, str(BACKEND_DIR))

from app.models import (  # noqa: E402
    AbilityTag,
    CareerGraph,
    JobDemo,
    LearningResource,
    StudentDemo,
    TrainingTask,
)


def load_json(name: str) -> Any:
    with (DATA_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_seed_data() -> dict[str, Any]:
    ability_tags = TypeAdapter(list[AbilityTag]).validate_python(load_json("ability_tags.json"))
    students = TypeAdapter(list[StudentDemo]).validate_python(load_json("students_demo.json"))
    jobs = TypeAdapter(list[JobDemo]).validate_python(load_json("jobs_demo.json"))
    graph = CareerGraph.model_validate(load_json("career_graph.json"))
    trainings = TypeAdapter(list[TrainingTask]).validate_python(load_json("training_tasks.json"))
    resources = TypeAdapter(list[LearningResource]).validate_python(load_json("resources.json"))

    if len(ability_tags) < 40:
        raise ValueError("ability_tags.json must contain at least 40 tags")
    if len(students) < 3 or len(jobs) < 3:
        raise ValueError("at least 3 anonymous students and 3 jobs are required")
    if len(trainings) < 10 or len(resources) < 10:
        raise ValueError("at least 10 trainings and 10 resources are required")

    tag_names = [item.tag for item in ability_tags]
    if len(tag_names) != len(set(tag_names)):
        raise ValueError("ability tag names must be unique")
    known_tags = set(tag_names)
    referenced_tags = {
        ability.tag for student in students for ability in student.abilities
    }
    referenced_tags.update(
        ability.tag for job in jobs for ability in job.required_abilities
    )
    referenced_tags.update(
        tag for training in trainings for tag in training.target_abilities
    )
    referenced_tags.update(resource.target_ability for resource in resources)
    unknown_tags = sorted(referenced_tags - known_tags)
    if unknown_tags:
        raise ValueError(f"unknown ability tag references: {unknown_tags}")

    node_keys = [node.node_key for node in graph.nodes]
    if len(node_keys) != len(set(node_keys)):
        raise ValueError("career graph node keys must be unique")
    node_key_set = set(node_keys)
    for edge in graph.edges:
        if edge.source_key not in node_key_set or edge.target_key not in node_key_set:
            raise ValueError(f"career graph edge references missing node: {edge}")
        if edge.source_key == edge.target_key:
            raise ValueError("career graph self edges are not allowed")

    training_types = {item.type for item in trainings}
    required_types = {
        "remote_collaboration",
        "ai_office_task",
        "cross_role_communication",
    }
    if training_types != required_types:
        raise ValueError("training data must cover all three frozen types")

    student_raw = json.dumps(load_json("students_demo.json"), ensure_ascii=False)
    privacy_patterns = {
        "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "phone": r"(?<!\d)1[3-9]\d{9}(?!\d)",
        "identity_number": r"(?<!\d)\d{17}[\dXx](?!\d)",
    }
    for label, pattern in privacy_patterns.items():
        if re.search(pattern, student_raw):
            raise ValueError(f"students_demo.json contains possible {label}")

    migration = MIGRATION_FILE.read_text(encoding="utf-8")
    expected_tables = {
        "ability_tags",
        "student_ability_records",
        "career_graph_nodes",
        "career_graph_edges",
        "training_records",
        "learning_plans",
        "growth_archives",
        "agent_logs",
        "user_feedback",
    }
    missing_tables = [
        table
        for table in sorted(expected_tables)
        if f"CREATE TABLE IF NOT EXISTS {table}" not in migration
    ]
    if missing_tables or "-- ROLLBACK" not in migration:
        raise ValueError(f"migration contract incomplete: {missing_tables}")

    from app.tools.mock_tools import call_mock_tool  # noqa: E402

    tool_checks = {
        "analyze_student_profile": {"session_id": "check"},
        "analyze_job_and_trend": {"session_id": "check", "job_id": 91001},
        "calculate_job_match": {
            "session_id": "check",
            "student_id": 90003,
            "job_id": 91002,
        },
        "recommend_career_path": {
            "session_id": "check",
            "student_id": 90003,
            "job_id": 91002,
        },
        "generate_and_score_training": {
            "session_id": "check",
            "student_id": 90003,
            "job_id": 91002,
            "training_type": "ai_office_task",
        },
        "recommend_learning_and_job_resources": {"session_id": "check"},
        "save_growth_feedback": {
            "session_id": "check",
            "user_id": "demo-user",
            "satisfaction": 4,
        },
    }
    for tool_name, valid_payload in tool_checks.items():
        success = call_mock_tool(tool_name, valid_payload)
        failure = call_mock_tool(tool_name, {})
        if success["code"] != 0 or failure["code"] != -2:
            raise ValueError(
                f"Mock tool success/failure envelope check failed: {tool_name}"
            )

    return {
        "ability_tags": len(ability_tags),
        "students": len(students),
        "jobs": len(jobs),
        "career_nodes": len(graph.nodes),
        "career_edges": len(graph.edges),
        "training_tasks": len(trainings),
        "training_types": sorted(training_types),
        "resources": len(resources),
        "migration_tables": len(expected_tables),
        "privacy_check": "passed",
        "mock_tool_success_failure_check": f"passed ({len(tool_checks)} tools)",
    }


def apply_database() -> None:
    database_url = os.getenv("A02_DATABASE_URL")
    if not database_url:
        raise RuntimeError("A02_DATABASE_URL is required for --apply")
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError("psycopg2 is required for --apply") from exc

    tags = load_json("ability_tags.json")
    graph = load_json("career_graph.json")
    migration = MIGRATION_FILE.read_text(encoding="utf-8")
    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(migration)
            for item in tags:
                cursor.execute(
                    """
                    INSERT INTO ability_tags (tag, category, difficulty, description, deprecated)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (tag) DO UPDATE SET
                      category = EXCLUDED.category,
                      difficulty = EXCLUDED.difficulty,
                      description = EXCLUDED.description,
                      deprecated = EXCLUDED.deprecated
                    """,
                    (item["tag"], item["category"], item["difficulty"], item["description"], item["deprecated"]),
                )
            for node in graph["nodes"]:
                cursor.execute(
                    """
                    INSERT INTO career_graph_nodes (node_key, job_title, level_range, industry, description)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (node_key) DO UPDATE SET
                      job_title = EXCLUDED.job_title,
                      level_range = EXCLUDED.level_range,
                      industry = EXCLUDED.industry,
                      description = EXCLUDED.description
                    """,
                    (node["node_key"], node["job_title"], node["level_range"], node["industry"], node["description"]),
                )
            for edge in graph["edges"]:
                cursor.execute(
                    """
                    INSERT INTO career_graph_edges
                      (source_key, target_key, relation_type, reason, transfer_cost, growth_value, source_industry, target_industry)
                    SELECT %s, %s, %s, %s, %s, %s, %s, %s
                    WHERE NOT EXISTS (
                      SELECT 1 FROM career_graph_edges
                      WHERE source_key = %s AND target_key = %s AND relation_type = %s
                    )
                    """,
                    (
                        edge["source_key"], edge["target_key"], edge["relation_type"], edge["reason"],
                        edge["transfer_cost"], edge["growth_value"], edge.get("source_industry"), edge.get("target_industry"),
                        edge["source_key"], edge["target_key"], edge["relation_type"],
                    ),
                )
        connection.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or initialize A02 data")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="validate files without database access")
    mode.add_argument("--apply", action="store_true", help="apply migration and static seeds")
    args = parser.parse_args()

    summary = validate_seed_data()
    if args.apply:
        apply_database()
        summary["database_apply"] = "completed"
    else:
        summary["database_apply"] = "skipped (check mode)"
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
