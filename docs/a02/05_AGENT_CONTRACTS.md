# 05_AGENT_CONTRACTS — Agent 输入输出契约

> **锁定状态：FROZEN（D2 冻结）**
> 本文件定义 6 个 Agent 的输入、输出、前置依赖、fallback 行为。
> Agent 字段名、类型、枚举值与 `04_API_CONTRACTS.md` 和 `13_MCP_TOOL_CATALOG.md` 捆绑锁定。

---

## 0. 通用约定

- 所有 Agent 继承 `BaseAgent`，输出包裹为统一 Agent 返回格式（见 04_API_CONTRACTS §9.2）
- 每个 Agent 返回 `data` 字段为本节定义的输出结构
- Agent 执行前检查 CareerState 前置字段，缺失时跳过并设置 `status: "failed"`, `fallback_used: true`
- LLM 调用失败重试 2 次，仍失败则使用 `fallback_data`

---

## 1. ProfileAgent

### 1.1 职责

解析用户简历/表单 → 生成结构化学生画像。

### 1.2 输入

| 来源 | CareerState 字段 | 类型 | 说明 |
|------|-----------------|------|------|
| state | `student_input` | object | `{resume_text, form_fields, target_job}` |
| state | `target_job_input` | object\|null | 目标岗位信息 |

### 1.3 输出 → `state.student_profile`

参照 `04_API_CONTRACTS.md §2.1 StudentProfile`。

```json
{
  "student_id": "int | null",
  "name": "string",
  "basic_info": {
    "education_level": "string",
    "major": "string",
    "graduation_year": "int | null",
    "target_job": "string",
    "target_industry": "string | null",
    "years_of_experience": "float | null"
  },
  "abilities": [
    {
      "tag": "string",
      "level": "int 1-5",
      "confidence": "float 0.0-1.0",
      "evidence": "string"
    }
  ],
  "competitiveness_score": "float 0.0-100.0",
  "completeness": "float 0.0-1.0",
  "missing_fields": ["string"]
}
```

### 1.4 前置条件

- `student_input` 不为 null

### 1.5 LLM 调用

- Prompt 模板：`prompts/profile_agent/system.txt`
- 结构化输出 Schema：`schemas/profile_schema.py`
- 要求输出 abilities 最多 30 个标签
- 每个标签从能力标签体系中选取（04_API_CONTRACTS §11）

### 1.6 Fallback

- 规则：从简历文本中正则提取技能关键词 → 映射到能力标签 → 默认 level=2, confidence=0.5
- Demo：返回 `04_API_CONTRACTS.md §12.3` 中的 `student_profile_demo`

---

## 2. JobAgent

### 2.1 职责

解析岗位 JD → 生成岗位能力画像 + 职业趋势分析。

### 2.2 输入

| 来源 | CareerState 字段 | 类型 | 说明 |
|------|-----------------|------|------|
| state | `target_job_input` | object | `{job_id, job_title, industry}` |
| 知识库 | 百宝箱检索结果 | — | 注入 Prompt 上下文 |

### 2.3 输出 → `state.job_profile` + `state.trend_result`

**job_profile** 参照 `04_API_CONTRACTS.md §3.1 JobProfile`：

```json
{
  "job_id": "int | null",
  "title": "string",
  "normalized_title": "string",
  "industry": "string",
  "required_abilities": [
    {
      "tag": "string",
      "required_level": "int 1-5",
      "weight": "float 0.0-1.0",
      "importance": "string critical / important / nice_to_have"
    }
  ],
  "soft_skills": ["string"],
  "salary_range": "string | null",
  "job_description": "string"
}
```

**trend_result** 参照 `04_API_CONTRACTS.md §3.2 TrendResult`：

```json
{
  "job_title": "string",
  "industry": "string",
  "trend_summary": "string",
  "hot_skills": ["string"],
  "rising_skills": ["string"],
  "declining_skills": ["string"],
  "ai_risk_assessment": "string low / medium / high",
  "ai_risk_detail": "string",
  "development_opportunities": ["string"],
  "development_risks": ["string"],
  "data_source": "string"
}
```

### 2.4 前置条件

- `target_job_input` 不为 null

### 2.5 LLM 调用

- Prompt 模板：`prompts/job_agent/system.txt`
- 结构化输出 Schema：`schemas/job_schema.py`
- `required_abilities` 必须从能力标签体系选取
- `trend_summary` 可引用知识库内容

### 2.6 Fallback

- 规则：从 JobService 查询 `job_type_profile` → 映射为 `required_abilities`
- 无岗位画像时：使用 `job_title` 关键字匹配默认能力向量
- Demo：返回 `04_API_CONTRACTS.md §12.3` 中的 `job_profile_demo`

---

## 3. MatchAgent

### 3.1 职责

调用 MatchService 计算匹配分、gap、priority → 用 LLM 生成自然语言解释。

### 3.2 输入

| 来源 | CareerState 字段 | 类型 | 说明 |
|------|-----------------|------|------|
| state | `student_profile` | object | ProfileAgent 输出 |
| state | `job_profile` | object | JobAgent 输出 |

### 3.3 输出 → `state.match_result`

参照 `04_API_CONTRACTS.md §4.1 MatchResult`：

```json
{
  "overall_score": "float 0.0-100.0 — 由 MatchService 代码计算, 非LLM产出",
  "dimensions": [
    {
      "name": "string",
      "student_score": "float",
      "job_required": "float",
      "gap": "float",
      "weight": "float"
    }
  ],
  "ability_gaps": [
    {
      "tag": "string",
      "current_level": "int 1-5",
      "required_level": "int 1-5",
      "gap": "int >=0",
      "priority": "int >=1 — 1=最高优先级, 由 MatchService 计算"
    }
  ],
  "gap_analysis": [
    {
      "item": "string — LLM 生成",
      "status": "string missing / insufficient / adequate — LLM 生成",
      "suggestion": "string — LLM 生成"
    }
  ],
  "strengths": ["string — LLM 生成"],
  "matching_algorithm_version": "deterministic-v1"
}
```

### 3.4 前置条件

- `student_profile` 不为 null 且 `student_profile.abilities` 非空
- `job_profile` 不为 null 且 `job_profile.required_abilities` 非空

### 3.5 执行流程

```
1. MatchService.calculate(student_profile, job_profile)
   → overall_score, dimensions, ability_gaps (代码计算)
2. LLM 生成 gap_analysis[].suggestion 和 strengths (自然语言)
3. 组装完整 match_result
```

### 3.6 LLM 调用

- 仅用于生成 `gap_analysis[].suggestion` 和 `strengths`
- 严禁 LLM 覆盖 MatchService 计算的任何数值

### 3.7 Fallback

- MatchService 失败：使用规则兜底算法（当前 `matching_service.py` 的 `_rule_fallback_analysis`）
- LLM 失败：`gap_analysis[].suggestion` 使用固定模板 "建议补充{tag}的实践项目"

---

## 4. PathAgent

### 4.1 职责

调用 PathService 生成 3年/5年职业路径 → 用 LLM 生成路径说明和建议。

### 4.2 输入

| 来源 | CareerState 字段 | 类型 | 说明 |
|------|-----------------|------|------|
| state | `student_profile` | object | |
| state | `job_profile` | object | |
| state | `match_result` | object | 用于获取 ability_gaps |

### 4.3 输出 → `state.path_plan` + `state.learning_plan`

**path_plan** 参照 `04_API_CONTRACTS.md §5.1 PathPlan`。
**learning_plan** 参照 `04_API_CONTRACTS.md §5.2 LearningPlan`。

### 4.4 前置条件

- `student_profile` 不为 null
- `job_profile` 不为 null
- `match_result` 不为 null

### 4.5 执行流程

```
1. PathService.search(student_profile, job_profile, match_result)
   → plan_3year, plan_5year (代码计算)
2. LLM 生成 phase 的 milestone 描述和 alternative_paths 的 reason
```

### 4.6 LLM 调用

- 用于生成 phase 描述文字和路径建议
- 不参与路径评分计算

### 4.7 Fallback

- PathService 失败：返回固定 3 阶段路径 `[基础→进阶→目标]`
- LLM 失败：milestone 用固定模板

---

## 5. TrainingAgent

### 5.1 职责

生成职场训练任务 → 调用 TrainingService 评分 → 调用 ResourceService 推荐资源。

### 5.2 输入

| 来源 | CareerState 字段 | 类型 | 说明 |
|------|-----------------|------|------|
| state | `student_profile` | object | |
| state | `job_profile` | object | |
| state | `match_result` | object | 用于定位能力短板 |

### 5.3 输出 → `state.training_plan`

```json
{
  "trainings": [
    {
      "training_id": "string",
      "type": "string remote_collaboration / ai_office_task / cross_role_communication",
      "title": "string — LLM 生成",
      "scenario": "string — LLM 生成",
      "task_description": "string — LLM 生成",
      "evaluation_criteria": [
        {
          "dimension": "string",
          "max_score": "float",
          "weight": "float",
          "description": "string"
        }
      ],
      "target_abilities": ["string — 本次训练针对的能力标签"],
      "reference_answer": "string | null"
    }
  ],
  "generated_at": "string ISO-8601"
}
```

### 5.4 训练评分（二次调用）

用户完成训练后，百宝箱再次调用 `generate_and_score_training` 工具（带 `user_answer` 参数）：

```json
// 返回 TrainingScore（见 04_API_CONTRACTS.md §6.2）
{
  "training_id": "string",
  "total_score": "float",
  "dimension_scores": [{"dimension": "string", "score": "float", "comment": "string"}],
  "overall_comment": "string — LLM 生成",
  "improvement_suggestions": ["string — LLM 生成"],
  "ability_updates": [{"tag": "string", "level_change": "int -1 / 0 / +1"}]
}
```

### 5.5 前置条件

- `student_profile` 不为 null
- `job_profile` 不为 null

### 5.6 LLM 调用

- 训练题生成：Prompt 模板 `prompts/training_agent/generate.txt`
- 评价生成：Prompt 模板 `prompts/training_agent/score.txt`

### 5.7 Fallback

- 训练题生成失败：返回内置 3 类各 1 道固定训练题（来自 `data/training_tasks.json`）
- 评分失败：返回默认分数 60 + 通用建议

---

## 6. FeedbackAgent

### 6.1 职责

保存用户反馈 → 更新学习优先级 → 更新成长档案。

### 6.2 输入

| 来源 | CareerState 字段 | 类型 | 说明 |
|------|-----------------|------|------|
| state | `session_id` | string | |
| 工具参数 | `ratings` | object | 用户评分数据 |

### 6.3 输出 → `state.feedback_result`

参照 `04_API_CONTRACTS.md §7.1 FeedbackResult`。

### 6.4 前置条件

- 至少一项评分不为 null

### 6.5 执行流程

```
1. FeedbackService.save(session_id, ratings)
2. FeedbackService.update_priorities(session_id)
3. FeedbackService.update_growth_archive(user_id)
```

### 6.6 LLM 调用

- 不调用 LLM。纯确定性计算。

### 6.7 Fallback

- 反馈数据本地缓存（Redis），数据库恢复后补写

---

## 7. Agent 执行顺序与状态依赖

```
ProfileAgent → JobAgent → MatchAgent → PathAgent → TrainingAgent → FeedbackAgent
    │              │           │            │             │              │
    ▼              ▼           ▼            ▼             ▼              ▼
student_       job_        match_       path_plan    training_     feedback_
profile        profile     result       learning_    plan          result
              trend_                    plan
              result
```

每个 Agent 执行前，Orchestrator 验证前置条件；条件不满足时跳过并记录。

---

## 8. Agent 日志字段（写入 agent_logs）

```json
{
  "session_id": "string",
  "agent_name": "string",
  "status": "success | partial | failed",
  "summary": "string",
  "duration_ms": "int",
  "tool_calls": [
    {
      "tool_name": "string",
      "input_summary": "string — 禁止完整简历",
      "output_summary": "string",
      "duration_ms": "int",
      "status": "success | error"
    }
  ],
  "fallback_used": "bool",
  "error": "string | null",
  "timestamp": "string ISO-8601"
}
```

---

## 9. 版本记录

| 日期 | 版本 | 变更 | 作者 |
|------|------|------|------|
| 2026-08-04 | v1.0 | 初始冻结：6 Agent 输入输出契约、前置条件、fallback | 技术负责人 |
