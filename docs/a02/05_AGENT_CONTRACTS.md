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

`ProfileAgent` 只能读取匿名化画像证据和历史画像投影。`name`、明文 `user_id`、
`student_id` 不进入 Prompt；数据库读写不属于 Agent 职责。

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
- `ability_tags.json` 是有效标签唯一来源；当前 81 个有效标签必须全部存在于画像七维映射中，
  不允许校验通过后因缺少 `_TAG_DIMENSIONS` 条目而静默丢弃

### 1.6 Fallback

- 规则：从简历文本中正则提取技能关键词 → 映射到能力标签 → 默认 level=2, confidence=0.5
- Demo：返回 `04_API_CONTRACTS.md §12.3` 中的 `student_profile_demo`

### 1.7 数据库持久化边界（D7-07）

- ProfileAgent 不执行 SQL，只输出经 Pydantic 校验的统一 `StudentProfile`。
- `profile_completeness` 与 `career_competitiveness_score` 仅取
  `ProfileService` 确定性结果；LLM 候选不得覆盖。
- Orchestrator/MCP 适配层在 Agent 成功后调用
  `StudentProfilePersistenceService`；`student_id` 单独保存为
  `CareerState.student_profile_id`，不写入 Agent 输出模型。
- PostgreSQL 历史记录恢复为统一画像时，能力维度的 `evidence_source` 固定为
  `history`，再作为 ProfileService 的历史输入或直接作为幂等重放结果。
- 数据库展示名缺省为 `匿名学生`，只存在于持久化边界，不进入 Agent 状态、Prompt
  或日志。日志仅允许记录散列后的业务引用、来源、记录数和安全错误类型。
- Demo Mode 不写业务 PostgreSQL，响应明确返回 `data_source=demo_json`、
  `demo_mode=true`、`student_id=null`。

---

## 2. JobAgent

### 2.1 职责

解析岗位 JD → 生成岗位能力画像 + 职业趋势分析。

### 2.2 输入

| 来源 | CareerState 字段 | 类型 | 说明 |
|------|-----------------|------|------|
| state | `target_job_input` | object | `{job_id, job_title, industry}` |
| 知识库 | 百宝箱检索结果 | — | 注入 Prompt 上下文 |

数据库模式允许 `target_job_input` 只提供 `job_id` 或 `type_key`。Orchestrator 在运行
JobAgent 前完成固定查询，并将业务引用分别保存到 `CareerState.job_record_id` 和
`CareerState.job_type_key`；JobAgent 不选择查询条件、不接触 SQL。

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
- JobAgent 规则链路的软技能集合按 `category=soft_skill` 动态读取，显式别名从
  `ability_tag_aliases.json` 读取，不维护独立硬编码副本
- `trend_summary` 可引用知识库内容

### 2.6 Fallback

- 规则：从 JobService 查询 `job_type_profile` → 映射为 `required_abilities`
- 无岗位画像时：使用 `job_title` 关键字匹配默认能力向量
- Demo：返回 `04_API_CONTRACTS.md §12.3` 中的 `job_profile_demo`

### 2.7 数据库岗位上下文边界（D7-08）

- `job_id`：固定读取 `job_clean`，再用 `normalized_job_title` 精确连接
  `job_type_profile.type_key`。
- `type_key`：固定读取类型画像及其代表岗位；禁止按相似标题猜测。
- PostgreSQL 的 `skill_requirements` 直接成为 `required_abilities`，等级、权重和重要度
  不经过 LLM；JobAgent 只生成缺省的保守趋势结果。
- 只有原始 JD 时保持原 JobAgent 分析链路，不发起数据库查询。
- 生产数据库无记录或失败时明确失败，不读取 JSON。只有显式 Demo Mode 使用
  `jobs_demo.json`，并标记 `fallback_used=true/data_source=demo_json`。
- `company_name`、完整 JD 和数据库参数不得进入 Agent/Tool 日志；数据库调用日志只保存
  引用类型、散列业务引用、来源、记录数和安全错误分类。

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
  "match_level": "high / good / fair / weak / low / insufficient_data — Service计算",
  "dimension_matches": "array — 等级、Gap、证据、置信度及known/unknown状态，由Service计算",
  "matched_skills": ["string — Service计算"],
  "missing_skills": ["string — 画像未提供，不等于能力为0"],
  "skill_gaps": "array — 仅包含有明确学生等级的不足项",
  "hard_constraint_results": "array — critical能力的passed/failed/unknown结论",
  "confidence": "float 0.0-1.0 — 结果可靠度，由Service计算",
  "evidence": "array — 按统一能力维度对齐的证据",
  "calculation_version": "deterministic-match-v2",
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

- MatchService 失败：由 MatchAgent 记录失败并进入后续明确实现的规则 fallback；
  当前 `match_service.py` 不调用 LLM，也不吞掉非法输入
- LLM 失败：`gap_analysis[].suggestion` 使用固定模板 "建议补充{tag}的实践项目"

### 3.8 数据库数据水合边界（D7-09）

- MatchAgent 运行前由 MCP/Orchestrator 固定工作流检查 `student_profile_id`、
  `job_record_id` 和 `job_type_key`。当会话只有业务引用时，分别经
  `StudentProfilePersistenceService` 与 `JobContextService` 读取 PostgreSQL，映射为统一
  Schema，并通过 Pydantic 校验后写入会话快照。
- `student_profile_snapshot_id`、`job_profile_snapshot_id` 和
  `job_profile_snapshot_type_key` 只用于证明快照与业务引用的归属关系。已有有效快照且
  归属一致时直接复用；引用与快照冲突时返回 `MATCH_CONTEXT_ID_CONFLICT`，禁止覆盖或
  混用。
- 缺少学生画像、岗位画像、学生能力维度或岗位必要能力时，在 MatchAgent 运行前返回
  明确 `missing_fields`。数据库记录不存在、映射无效或连接失败也失败关闭，生产模式不
  读取 Demo JSON 补字段。
- 水合读取以独立的 `MatchContextHydration` 日志记录，MatchAgent 仍以
  `calculate_job_match` 单独记录。日志只包含引用类型、散列引用、来源和记录数，不包含
  姓名、能力证据或完整 JD。
- MatchAgent 和 MatchService 不包含 SQL、连接管理或数据源选择。PostgreSQL 水合结果与
  等价 JSON Demo 快照会形成相同 MatchService 请求；分数、技能缺口、优先级和证据继续
  仅由 MatchService 确定性计算。

---

## 4. PathAgent

> 阶段3当前只完成 CareerGraphRepository、Path Schema 与 PathService。现有 Mock
> PathAgent 尚未接入这些模块，本节描述后续集成边界，不代表百宝箱链路已经可用。

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
1. PathService.calculate(student_profile, job_profile, match_result, preferences, horizon)
   → candidate_paths + path_scores + three_year_roadmap + five_year_roadmap（代码计算）
2. LLM 生成 phase 的 milestone 描述和 alternative_paths 的 reason
```

### 4.6 LLM 调用

- 用于生成 phase 描述文字和路径建议
- 不参与路径评分计算

### 4.7 Fallback

- PathService 对无通路/未知岗位/数据不足返回明确 status、空路线或图内 fallback 节点；
  PathAgent 不得伪造图谱外岗位
- LLM 失败：milestone 用固定模板

### 4.8 数据库职业图谱边界（D7-10）

- PathService 通过注入的 CareerGraph Provider 获取一次完整图谱快照，再构造只读
  `CareerGraphRepository` 执行搜索和评分；PathService 不打开 JSON，也不建立数据库连接。
- MCP 生产装配固定绑定 PostgreSQL Provider。数据库不可用或整图校验失败时失败关闭，不读取
  JSON；只有服务端显式 Demo Mode 才绑定 JSON Provider，显式配置的 Demo fallback 也会在
  日志中标记 `fallback_used`。
- PostgreSQL `job_type_graph_edge` 的 `transfer_cost`、`growth_value`、`risk_level` 和
  `transition_requirements` 原样进入候选路径。PathAgent 和 LLM 不重算、不覆盖这些字段；路径
  得分、风险惩罚、横向/纵向筛选和环路规避继续由 PathService 的既有确定性算法完成。
- PostgreSQL 与 Demo Provider 返回同一图快照时，节点、边、候选路径、得分、风险与转岗要求
  必须完全一致。空图或不完整图按整图校验错误失败；合法但无起点/无通路的图继续使用既有
  `no_reachable_path` 空路径语义。
- PathAgent 日志分别记录 `load_career_graph` Provider 调用和
  `recommend_career_path` PathService 调用。Provider 日志仅包含目标类型键、节点数、边数和
  数据来源，不包含学生证据、完整 JD 或数据库参数。

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

标准 MCP 工具 `generate_and_score_training` 的瞬时参数为：生成模式
`session_id/user_id/training_type`，评分模式 `session_id/user_id/training_id/user_answer`；
`trace_id` 可选。ability gaps、岗位和 evaluation criteria 由 State/Service 提供，调用方不能覆盖。

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

用户完成训练后再次调用同一个 `generate_and_score_training` 工具，并同时提供
`training_id + user_answer`。该工具是 generate/score 合并工具，不拆成两个 MCP 工具：

```json
// 返回 TrainingScore（见 04_API_CONTRACTS.md §6.2）
{
  "training_id": "string",
  "total_score": "float",
  "dimension_scores": [{"dimension": "string", "score": "float", "comment": "string"}],
  "overall_comment": "string — Service 结果，可由已验证文字解释补充",
  "improvement_suggestions": ["string — Service 结果"],
  "ability_updates": [{"tag": "string", "level_change": "int -1 / 0 / +1"}]
}
```

### 5.5 前置条件

- `student_profile` 不为 null
- `job_profile` 不为 null

### 5.6 LLM 调用

- 训练任务由 TrainingService 的冻结任务库确定性生成。
- 评分时 LLM 只可返回无数值的 coverage/reason 语义信号；TrainingService 独占全部数值计算。
- 可选 LLM 文字反馈失败不影响已完成的确定性评分。

### 5.7 Fallback

- LLM coverage 不可用时由 TrainingService 使用其确定性 fallback 评分路径。
- TrainingService/Schema 失败返回安全错误，不虚构训练题、默认分数或 ability update。

---

## 6. FeedbackAgent

### 6.1 职责

保存用户反馈 → 更新学习优先级 → 更新成长档案。

### 6.2 输入

| 来源 | CareerState 字段 | 类型 | 说明 |
|------|-----------------|------|------|
| state | `session_id` | string | |
| 工具参数 | `feedback` | object | `satisfaction` 必填；三个分项 rating 和 comments 可选 |

### 6.3 输出 → `state.feedback_result`

参照 `04_API_CONTRACTS.md §7.1 FeedbackResult`。

### 6.4 前置条件

- 至少一项评分不为 null

### 6.5 执行流程

```
1. FeedbackAgent 从 State 投影 skill gaps、abilities、training targets 和 overall score
2. FeedbackService.save_feedback(...) 保存评分、更新 priorities 和 growth snapshot
3. 结果经 FeedbackAgentResult Schema 校验后写入 feedback_result
4. `growth_snapshot.competitiveness_score` 只描述成长快照；不得写回或覆盖 `state.student_profile` 中的画像竞争力分
```

### 6.6 LLM 调用

- FeedbackService 的保存、priority 和 growth snapshot 为纯确定性计算。
- Agent 可请求一句自然语言解释；解释失败使用固定安全文案，不改变 Service 字段。

### 6.7 Fallback

- FeedbackService/Schema 失败返回安全错误，不声称已保存，也不虚构中性评分或成长快照。

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

### 7.1 双数据源链路不变量（D7-11）

PostgreSQL 与 JSON Demo 的差异在 Agent 之前由 Provider/Service 边界吸收。相同 Pydantic
业务输入必须产生相同 Profile、Job、Match、Path、Training 和 Feedback 业务结果，尤其是
MatchService 分数、PathService 候选路径及 TrainingService 分数。Agent 只允许在日志/响应中
体现来源、Demo 与 fallback 元数据，不得按来源改写确定性业务值。Training/Resource 继续以
版本化 JSON 为真源。

---

## 8. Agent 日志字段（写入 agent_logs）

```json
{
  "session_id": "string",
  "agent_name": "string",
  "service_name": "string | null — Agent实际调用的确定性Service",
  "status": "success | partial | failed",
  "summary": "string",
  "duration_ms": "int",
  "tool_calls": [
    {
      "tool_name": "string",
      "service_name": "string | null",
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
| 2026-09-20 | v1.1 | 冻结六 Agent 双源等价与 Feedback 不覆盖画像竞争力规则 | Codex |
| 2026-08-04 | v1.0 | 初始冻结：6 Agent 输入输出契约、前置条件、fallback | 技术负责人 |
