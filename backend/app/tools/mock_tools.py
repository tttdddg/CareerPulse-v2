"""Deterministic A02 Mock platform tools backed by anonymous seed data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEMO_NOTICE = "当前为演示模式，数据为示例数据，不代表真实评估结果"


def _load(name: str) -> Any:
    with (DATA_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


ABILITY_TAGS = _load("ability_tags.json")
STUDENTS = _load("students_demo.json")
JOBS = _load("jobs_demo.json")
CAREER_GRAPH = _load("career_graph.json")
TRAINING_TASKS = _load("training_tasks.json")
RESOURCES = _load("resources.json")
MOCK_TOOL_LOGS: list[dict[str, Any]] = []


def _demo(data: dict[str, Any]) -> dict[str, Any]:
    return {**data, "demo_mode": True, "demo_notice": DEMO_NOTICE}


def _student(student_id: int) -> dict[str, Any]:
    for item in STUDENTS:
        if item["student_id"] == student_id:
            return item
    raise LookupError("演示学生不存在")


def _job(job_id: int | None = None, title: str | None = None) -> dict[str, Any]:
    for item in JOBS:
        if job_id is not None and item["job_id"] == job_id:
            return item
        if title and title in {item["title"], item["normalized_title"]}:
            return item
    raise LookupError("演示岗位不存在")


def _analyze_student_profile(payload: dict[str, Any]) -> dict[str, Any]:
    session_id = str(payload.get("session_id") or "")
    if not session_id:
        raise ValueError("session_id is required")
    index = sum(ord(char) for char in session_id) % len(STUDENTS)
    return _demo(dict(STUDENTS[index]))


def _analyze_job_and_trend(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("session_id"):
        raise ValueError("session_id is required")
    job = _job(payload.get("job_id"), payload.get("job_title"))
    profile = dict(job)
    trend = {
        "job_title": job["title"],
        "industry": job["industry"],
        "trend_summary": "A02固定演示趋势，不代表真实市场判断。",
        "hot_skills": [item["tag"] for item in job["required_abilities"][:3]],
        "rising_skills": ["大模型应用"],
        "declining_skills": [],
        "ai_risk_assessment": "medium",
        "ai_risk_detail": "演示评估：重复性任务可被辅助，关键判断仍需人工完成。",
        "development_opportunities": ["AI辅助工作流"],
        "development_risks": ["演示数据不应替代市场调研"],
        "data_source": "A02 Demo固定数据",
    }
    return _demo({"job_profile": profile, "trend_result": trend})


def _calculate_job_match(payload: dict[str, Any]) -> dict[str, Any]:
    for field in ("session_id", "student_id", "job_id"):
        if payload.get(field) is None:
            raise ValueError(f"{field} is required")
    student = _student(int(payload["student_id"]))
    job = _job(int(payload["job_id"]))
    current_levels = {item["tag"]: item["level"] for item in student["abilities"]}
    difficulty = {item["tag"]: item["difficulty"] for item in ABILITY_TAGS}

    score = 0.0
    gaps: list[dict[str, Any]] = []
    strengths: list[str] = []
    dimensions: list[dict[str, Any]] = []
    priorities: list[tuple[float, dict[str, Any]]] = []
    for requirement in job["required_abilities"]:
        tag = requirement["tag"]
        current = int(current_levels.get(tag, 0))
        required = int(requirement["required_level"])
        weight = float(requirement["weight"])
        ratio = min(current / required, 1.0)
        contribution = ratio * weight * 100.0
        score += contribution
        gap = max(required - current, 0)
        dimensions.append(
            {
                "name": tag,
                "student_score": round(ratio * 100.0, 2),
                "job_required": 100.0,
                "gap": round(ratio * 100.0 - 100.0, 2),
                "weight": weight,
            }
        )
        if gap:
            item = {
                "tag": tag,
                "current_level": current,
                "required_level": required,
                "gap": gap,
                "priority": 0,
            }
            priority_score = gap * weight * (1.0 / difficulty[tag])
            priorities.append((priority_score, item))
        else:
            strengths.append(tag)

    priorities.sort(key=lambda pair: (-pair[0], pair[1]["tag"]))
    for rank, (_, item) in enumerate(priorities, start=1):
        item["priority"] = rank
        gaps.append(item)
    gap_analysis = [
        {
            "item": item["tag"],
            "status": "missing" if item["current_level"] == 0 else "insufficient",
            "suggestion": f"建议完成{item['tag']}演示练习并保留可验证成果。",
        }
        for item in gaps
    ]
    return _demo(
        {
            "overall_score": round(score, 2),
            "dimensions": dimensions,
            "ability_gaps": gaps,
            "gap_analysis": gap_analysis,
            "strengths": strengths,
            "matching_algorithm_version": "deterministic-v1",
        }
    )


def _recommend_career_path(payload: dict[str, Any]) -> dict[str, Any]:
    for field in ("session_id", "student_id", "job_id"):
        if payload.get(field) is None:
            raise ValueError(f"{field} is required")
    _student(int(payload["student_id"]))
    job = _job(int(payload["job_id"]))
    title_to_key = {node["job_title"]: node["node_key"] for node in CAREER_GRAPH["nodes"]}
    target_key = title_to_key.get(job["title"])
    outgoing = [
        edge for edge in CAREER_GRAPH["edges"] if edge["source_key"] == target_key
    ]
    total_score = round(
        max(0.0, sum(edge["growth_value"] - edge["transfer_cost"] for edge in outgoing) * 20),
        2,
    )
    tags = [item["tag"] for item in job["required_abilities"][:3]]
    phases = [
        {"phase":1,"duration_months":6,"target_role":"基础能力补齐","required_abilities":tags,"tasks":["完成演示学习任务"],"milestone":"完成基础作品"},
        {"phase":2,"duration_months":12,"target_role":job["title"],"required_abilities":tags,"tasks":["完成演示岗位项目"],"milestone":"能够独立完成核心任务"},
        {"phase":3,"duration_months":18,"target_role":job["title"],"required_abilities":tags,"tasks":["复盘并完善作品集"],"milestone":"达到演示目标岗位要求"},
    ]
    node_titles = {node["node_key"]: node["job_title"] for node in CAREER_GRAPH["nodes"]}
    alternatives = [
        {
            "type": edge["relation_type"],
            "target_role": node_titles[edge["target_key"]],
            "score": round(max(0.0, edge["growth_value"] - edge["transfer_cost"]) * 20, 2),
            "reason": edge["reason"],
        }
        for edge in outgoing
    ]
    learning = {
        "phases": [
            {"phase":index,"title":phase["target_role"],"tasks":[{"task_id":f"learn-{index}","description":phase["tasks"][0],"target_ability":tags[0],"estimated_hours":20,"resources":[]}]}
            for index, phase in enumerate(phases, start=1)
        ],
        "certificate_suggestions": [],
        "project_suggestions": ["完成一个匿名演示岗位项目"],
    }
    return _demo(
        {
            "path_plan": {"target_job":job["title"],"plan_3year":{"phases":phases,"total_score":total_score},"plan_5year":{"phases":phases,"total_score":total_score},"alternative_paths":alternatives,"path_algorithm_version":"graph-search-v1"},
            "learning_plan": learning,
        }
    )


def _generate_and_score_training(payload: dict[str, Any]) -> dict[str, Any]:
    for field in ("session_id", "student_id", "job_id", "training_type"):
        if payload.get(field) is None:
            raise ValueError(f"{field} is required")
    training_type = payload["training_type"]
    candidates = [item for item in TRAINING_TASKS if item["type"] == training_type]
    if not candidates:
        raise ValueError("unsupported training_type")
    if payload.get("user_answer") is None:
        return _demo({"mode": "generate", **candidates[0]})

    training_id = payload.get("training_id")
    task = next((item for item in TRAINING_TASKS if item["training_id"] == training_id), None)
    if task is None:
        raise LookupError("演示训练题不存在")
    answer_length = len(str(payload["user_answer"]).strip())
    total_score = float(max(40, min(90, 40 + answer_length // 4)))
    dimension_scores = [
        {
            "dimension": item["dimension"],
            "score": round(total_score * item["weight"], 2),
            "comment": "按演示规则计算，未调用外部模型。",
        }
        for item in task["evaluation_criteria"]
    ]
    return _demo(
        {
            "mode": "score",
            "training_id": training_id,
            "total_score": total_score,
            "dimension_scores": dimension_scores,
            "overall_comment": "演示评分仅验证流程，不代表真实能力评价。",
            "improvement_suggestions": ["补充事实依据和明确行动项。"],
            "ability_updates": [
                {"tag": tag, "level_change": 0} for tag in task["target_abilities"]
            ],
        }
    )


def _recommend_resources(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("session_id"):
        raise ValueError("session_id is required")
    gaps = set(payload.get("ability_gaps") or [])
    selected = [item for item in RESOURCES if not gaps or item["target_ability"] in gaps]
    return _demo(
        {
            "learning_resources": selected[:10],
            "job_resources": [],
            "certificate_suggestions": [
                item["target_ability"] for item in selected if item["type"] == "certificate"
            ],
        }
    )


def _save_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    for field in ("session_id", "user_id", "satisfaction"):
        if payload.get(field) is None:
            raise ValueError(f"{field} is required")
    satisfaction = int(payload["satisfaction"])
    if not 1 <= satisfaction <= 5:
        raise ValueError("satisfaction must be between 1 and 5")
    return _demo(
        {
            "feedback_saved": False,
            "growth_archive_updated": False,
            "updated_priorities": [],
            "growth_snapshot": {"competitiveness_score":0.0,"completed_trainings":0,"completed_phases":0,"growth_trend":"stable"},
        }
    )


MOCK_TOOL_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "analyze_student_profile": _analyze_student_profile,
    "analyze_job_and_trend": _analyze_job_and_trend,
    "calculate_job_match": _calculate_job_match,
    "recommend_career_path": _recommend_career_path,
    "generate_and_score_training": _generate_and_score_training,
    "recommend_learning_and_job_resources": _recommend_resources,
    "save_growth_feedback": _save_feedback,
}


def call_mock_tool(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Call a frozen-name Mock tool and return the standard TBox envelope."""
    started = perf_counter()
    request_id = str(uuid4())
    handler = MOCK_TOOL_REGISTRY.get(tool_name)
    try:
        if handler is None:
            raise LookupError("Mock工具不存在")
        data = handler(payload)
        response = {"code":0,"message":"success","request_id":request_id,"data":data,"error":None}
        status = "success"
    except LookupError as exc:
        response = {"code":-3,"message":"resource not found","request_id":request_id,"data":None,"error":{"type":type(exc).__name__,"detail":str(exc)}}
        status = "error"
    except (TypeError, ValueError) as exc:
        response = {"code":-2,"message":"validation failed","request_id":request_id,"data":None,"error":{"type":type(exc).__name__,"detail":str(exc)}}
        status = "error"
    except Exception as exc:
        response = {"code":-1,"message":"Mock tool failed","request_id":request_id,"data":None,"error":{"type":type(exc).__name__,"detail":"request content omitted"}}
        status = "error"

    duration_ms = max(0, round((perf_counter() - started) * 1000))
    MOCK_TOOL_LOGS.append(
        {
            "tool_name": tool_name,
            "input_summary": "已提供字段: " + ", ".join(sorted(payload)),
            "output_summary": f"code={response['code']}",
            "duration_ms": duration_ms,
            "status": status,
            "demo": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    return response
