"""Build deterministic, traceable local job-knowledge import files.

Only sourced local records are transformed.  This script does not call an LLM,
scrape the web, or infer market trends from the anonymous demo job profiles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "app" / "data"
OUTPUT_DIR = DATA_DIR / "job_trends"
JOBS_FILE = DATA_DIR / "jobs_demo.json"
ABILITY_TAGS_FILE = DATA_DIR / "ability_tags.json"
JSONL_FILE = OUTPUT_DIR / "job_knowledge.jsonl"
MARKDOWN_FILE = OUTPUT_DIR / "job_knowledge.md"
REPORT_FILE = OUTPUT_DIR / "build_report.json"
UNCONFIRMED_FILE = OUTPUT_DIR / "unconfirmed_data.json"
SOURCE_LABEL = "backend/app/data/jobs_demo.json"
SAMPLE_SEED = 20260810

_WHITESPACE = re.compile(r"\s+")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_IMPORT_FIELDS = (
    "record_id",
    "source",
    "source_date",
    "job_name",
    "job_category",
    "industry",
    "skills",
    "content_type",
    "content",
    "evidence_status",
)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source_file:
        return json.load(source_file)


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    without_controls = _CONTROL_CHARS.sub("", value)
    return _WHITESPACE.sub(" ", without_controls).strip()


def _record_id(record: dict[str, Any]) -> str:
    identity = "\x1f".join(
        [
            record["source"],
            record["job_name"],
            record["job_category"],
            record["industry"],
            record["content_type"],
            *record["skills"],
            record["content"],
        ]
    )
    return "jobkb-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def _build_candidates() -> tuple[list[dict[str, Any]], list[str]]:
    jobs = _load_json(JOBS_FILE)
    ability_records = _load_json(ABILITY_TAGS_FILE)
    active_tags = {
        record["tag"] for record in ability_records if not record.get("deprecated", False)
    }
    candidates: list[dict[str, Any]] = []
    issues: list[str] = []

    for job in jobs:
        job_name = _clean_text(job.get("title"))
        job_category = _clean_text(job.get("normalized_title"))
        industry = _clean_text(job.get("industry"))
        if not all((job_name, job_category, industry)):
            issues.append("跳过缺少岗位名称、岗位类别或行业的演示岗位记录")
            continue

        for requirement in job.get("required_abilities", []):
            tag = _clean_text(requirement.get("tag"))
            if tag not in active_tags:
                issues.append(f"跳过未命中标准能力体系的标签：{tag or '<empty>'}")
                continue
            required_level = requirement.get("required_level")
            weight = requirement.get("weight")
            importance = _clean_text(requirement.get("importance"))
            if (
                isinstance(required_level, bool)
                or not isinstance(required_level, int)
                or not 1 <= required_level <= 5
                or isinstance(weight, bool)
                or not isinstance(weight, (int, float))
                or not 0 < float(weight) <= 1
                or not importance
            ):
                issues.append(f"跳过 {job_name}/{tag} 的无效能力要求")
                continue

            content = (
                f"内部匿名演示岗位画像中，{job_name}列出标准能力标签“{tag}”，"
                f"要求等级为{required_level}，岗位权重为{float(weight):.4f}，"
                f"重要性为{importance}。本记录仅用于数据结构与知识库检索测试，"
                "不代表真实招聘市场事实或技能趋势。"
            )
            record: dict[str, Any] = {
                "source": SOURCE_LABEL,
                "source_date": None,
                "job_name": job_name,
                "job_category": job_category,
                "industry": industry,
                "skills": [tag],
                "content_type": "demo_job_skill_requirement",
                "content": content,
                "evidence_status": "demo_only_not_market_fact",
            }
            record["record_id"] = _record_id(record)
            candidates.append(record)

    return candidates, issues


def _deduplicate(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    unique: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for record in records:
        record_id = record["record_id"]
        if record_id in unique:
            duplicates += 1
            continue
        unique[record_id] = record
    ordered = sorted(
        unique.values(),
        key=lambda item: (
            item["job_category"],
            item["industry"],
            item["skills"],
            item["record_id"],
        ),
    )
    return ordered, duplicates


def _jsonl(records: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps({field: record[field] for field in _IMPORT_FIELDS}, ensure_ascii=False)
        + "\n"
        for record in records
    )


def _markdown(records: list[dict[str, Any]]) -> str:
    sections = [
        "# CareerPulse 岗位知识库本地导入文件\n",
        "> 本文件由 `backend/scripts/build_job_knowledge.py` 确定性生成。",
        "> 当前仅含匿名演示岗位画像基线，不代表真实招聘市场或岗位趋势。\n",
    ]
    for record in records:
        sections.extend(
            [
                f"## {record['job_name']} · {record['skills'][0]}",
                f"- record_id: `{record['record_id']}`",
                f"- source: `{record['source']}`",
                "- source_date: `unknown`",
                f"- job_category: `{record['job_category']}`",
                f"- industry: `{record['industry']}`",
                f"- skills: `{', '.join(record['skills'])}`",
                f"- content_type: `{record['content_type']}`",
                f"- evidence_status: `{record['evidence_status']}`\n",
                record["content"] + "\n",
            ]
        )
    return "\n".join(sections).rstrip() + "\n"


def _unconfirmed() -> dict[str, Any]:
    return {
        "status": "source_material_missing",
        "items": [
            {
                "topic": "岗位和技能真实趋势",
                "reason": "仓库中未发现带可验证来源和日期的招聘报告、行业白皮书或趋势数据集",
                "handling": "未生成hot/rising/declining趋势事实",
            },
            {
                "topic": "资料发布日期",
                "reason": "jobs_demo.json未提供来源发布日期",
                "handling": "source_date保留为null，不使用文件修改时间代替发布日期",
            },
            {
                "topic": "演示岗位权重的市场代表性",
                "reason": "岗位样例明确是匿名演示数据",
                "handling": "标记为demo_only_not_market_fact",
            },
        ],
    }


def build_outputs() -> dict[Path, str]:
    candidates, issues = _build_candidates()
    records, duplicate_count = _deduplicate(candidates)
    sample_size = min(10, len(records))
    sample_ids = sorted(
        random.Random(SAMPLE_SEED).sample(
            [record["record_id"] for record in records], sample_size
        )
    )
    report = {
        "schema_version": "job-knowledge-v1",
        "input_records": len(candidates),
        "output_records": len(records),
        "duplicates_removed": duplicate_count,
        "invalid_records_removed": len(issues),
        "cleaning_issues": sorted(set(issues)),
        "source_inventory": [
            {
                "source": SOURCE_LABEL,
                "source_date": None,
                "source_type": "internal_anonymous_demo",
                "market_trend_evidence": False,
            },
            {
                "source": "backend/app/data/ability_tags.json",
                "source_date": None,
                "source_type": "controlled_ability_taxonomy",
                "market_trend_evidence": False,
            },
        ],
        "random_check_seed": SAMPLE_SEED,
        "random_check_record_ids": sample_ids,
    }
    return {
        JSONL_FILE: _jsonl(records),
        MARKDOWN_FILE: _markdown(records),
        REPORT_FILE: json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        UNCONFIRMED_FILE: json.dumps(_unconfirmed(), ensure_ascii=False, indent=2) + "\n",
    }


def _check(outputs: dict[Path, str]) -> int:
    mismatches = [
        str(path.relative_to(BACKEND_DIR))
        for path, expected in outputs.items()
        if not path.exists() or path.read_text(encoding="utf-8") != expected
    ]
    if mismatches:
        print("Generated files are missing or stale:", file=sys.stderr)
        for mismatch in mismatches:
            print(f"- {mismatch}", file=sys.stderr)
        return 1
    print(f"check passed: {len(_jsonl_records(outputs[JSONL_FILE]))} records")
    return 0


def _jsonl_records(content: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in content.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="verify committed outputs without writing"
    )
    args = parser.parse_args()
    outputs = build_outputs()
    if args.check:
        return _check(outputs)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8", newline="\n")
    print(f"built {len(_jsonl_records(outputs[JSONL_FILE]))} records in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
