# 04_API_CONTRACTS — 公共数据契约

## 阶段3统一领域 Schema（增量，不替换冻结字段）

阶段3新增请求、领域、响应三层 Pydantic Schema。现有 `CareerState.student_profile`、
`job_profile`、`trend_result` 字段及阶段2 Agent 输出保持兼容；后续 Service 负责从旧结构
映射到统一领域结构，Schema 层不执行评分、趋势推断或 LLM 调用。

- 固定能力维度仅由 `AbilityDimension` 定义：专业知识、技术与工具、项目实践、沟通协作、
  问题解决、学习成长、行业认知。
- `AbilityDimensionProfile` 同时供统一学生画像与岗位画像使用，包含 `dimension`、`tags`、
  `level`（1-5）、`confidence`（0-1）、`evidence[]`、`evidence_source`。
- `evidence_source` 可标记 `resume`、`form`、`project`、`assessment`、
  `job_description`、`knowledge_base`、`user_supplement`、`history` 或 `demo`；
  ProfileAgent 更新画像时用 `history` 保留已有画像中的可验证证据。
- 请求层：`StudentProfileRequest`、`JobProfileRequest`、`CareerTrendRequest`。
- 领域层：`StudentProfile`、`JobProfile`、`CareerTrend`。
- 响应层：泛型 `AgentResponse[T]`，统一承载状态、数据、摘要、fallback 与错误信息。
- `profile_completeness` 范围为 0-1；`career_competitiveness_score` 范围为 0-100，分数必须
  由确定性 Service 提供，不能由 Schema 或 LLM 自行计算。


> **锁定状态：FROZEN（D2 冻结）**
> 本文件定义的字段名、类型、枚举值不得随意修改。
> 修改本文件须同时更新：`05_AGENT_CONTRACTS.md`、`13_MCP_TOOL_CATALOG.md`、后端 Schema 和百宝箱工具配置。
> 修改前须在 `decisions/` 下创建 ADR 记录原因。

---

## 0. 约定

- 所有字段名使用 **snake_case**（后端 / 数据库）
- 前端 API 请求/响应同样使用 snake_case（后端返回即前端消费）
- 数值字段：分数统一 `0.0–100.0`，等级统一 `1–5`，百分比统一 `0.0–1.0`
- 时间字段：ISO-8601 字符串 `"2026-08-04T14:30:00+08:00"`
- JSON Schema 中 `"required"` 字段不得删减

---

## 1. CareerState

CareerState 是跨 Agent 共享的会话级状态对象，由 CareerOrchestrator 持有并逐 Agent 更新。

```json
{
  "session_id": "string, required — 后端会话ID, e.g. sess-20260804-001",
  "platform_session_id": "string | null — 百宝箱会话ID, 首次对话时填充",
  "user_id": "string | null — 登录用户ID",
  "status": "string — 阶段状态，见 §1.1",
  "error_type": "string | null — FAILED 时的可判断错误类型",
  "student_input": "object | null — 用户原始输入 {resume_text, form_fields, target_job}",
  "student_profile_id": "int | null — PostgreSQL student_profile 业务记录引用；不得放入 Agent 画像",
  "student_profile_updated_at": "string | null — 最近一次数据库画像版本时间",
  "target_job_input": "object | null — 目标岗位 {job_id, job_title, industry}",
  "job_record_id": "int | null — PostgreSQL job_clean 记录引用",
  "job_type_key": "string | null — PostgreSQL job_type_profile.type_key",
  "job_data_source": "session | postgresql | demo_json | null",
  "student_profile": "object | null — ProfileAgent 输出, 见 §2.1",
  "job_profile": "object | null — JobAgent 输出, 见 §3.1",
  "trend_result": "object | null — 趋势分析结果, 见 §3.2",
  "match_result": "object | null — MatchAgent 输出, 见 §4.1",
  "path_plan": "object | null — PathAgent 输出, 见 §5.1",
  "learning_plan": "object | null — 学习计划, 见 §5.2",
  "career_roadmap": "object | null — PathService 完整确定性 PathResult, 见 §5.4",
  "training_plan": "object | null — TrainingAgent 输出, 见 §6.1",
  "resource_result": "object | null — 资源推荐结果, 见 §6.2",
  "feedback_result": "object | null — FeedbackAgent 输出, 见 §7.1",
  "final_report": "object | null — 完整报告聚合",
  "agent_logs": "array — AgentLog[], 见 §8"
}
```

### 1.1 状态流转规则

```
student_input + target_job_input
  → ProfileAgent → student_profile
  → JobAgent → job_profile + trend_result
  → MatchAgent → match_result
  → PathAgent → path_plan + learning_plan
  → TrainingAgent → training_plan
  → (用户完成训练) → resource_result
  → FeedbackAgent → feedback_result
  → CareerOrchestrator → final_report
```

每个 Agent 执行前检查前置字段是否为 null；为 null 时跳过并记录 fallback。

阶段3本地分步状态：

```text
INITIALIZED
  → MATCH_STARTED → MATCH_COMPLETED
  → PATH_STARTED  → PATH_COMPLETED
```

执行失败统一写入 `FAILED`，并在 `error_type` 中保存不含原始简历/JD的错误类型。
完整六 Agent 链可继续使用 `COMPLETED` / `PARTIAL`。

### 1.2 阶段3本地分步 API（HTTP，不含平台 Tool/MCP）

| 方法 | 路径 | 输入 | 输出 |
|---|---|---|---|
| POST | `/api/career-agent/stage3/prepare` | `session_id/user_id` + 阶段2 `StudentProfile`、`JobProfile`（至少一个） | `CareerState` |
| POST | `/api/career-agent/stage3/match` | `session_id/user_id` | `CareerState`，成功状态 `MATCH_COMPLETED` |
| POST | `/api/career-agent/stage3/path` | `session_id/user_id` | `CareerState`，成功状态 `PATH_COMPLETED` |
| GET | `/api/career-agent/session/{session_id}` | path parameter | 持久化 `CareerState` |
| GET | `/api/agent/logs/{session_id}` | path parameter | 持久化 `AgentLog[]` |

`prepare` 只接收阶段2真实 Schema，不接收客户端提供的 Match/Path 结果。`match` 和
`path` 从数据库读取前一步结果；相同 session 的相同请求幂等返回已有结果，不追加重复日志；
相同 session 的冲突画像返回 HTTP 409。

### 1.3 百宝箱阶段3最小工具 API（`stage3-tool-v1`）

以下是加法扩展，不改变 §1.2 的本地接口，也不接入阶段4工具。所有端点均要求
`Authorization: Bearer <A02_TBOX_API_TOKEN>`，请求/响应模型均 `extra=forbid`。

| 方法 | 路径 | operationId | 固定请求 | 固定成功响应 |
|---|---|---|---|---|
| POST | `/api/platform/v1/tools/analyze_job_match` | `analyze_job_match` | `AnalyzeJobMatchRequest` | `AnalyzeJobMatchResponse` |
| POST | `/api/platform/v1/tools/generate_career_path` | `generate_career_path` | `GenerateCareerPathRequest` | `GenerateCareerPathResponse` |
| GET | `/api/platform/v1/tools/calls/{tool_call_id}/status` | `get_stage3_tool_call_status` | path parameter | `ToolStatusResponse` |
| GET | `/api/platform/v1/tools/calls/{tool_call_id}/result` | `get_stage3_tool_call_result` | path parameter | `ToolResultResponse` |

`AnalyzeJobMatchRequest` 必填字段：

```json
{
  "schema_version": "stage3-tool-v1",
  "idempotency_key": "string(8-128)",
  "session_id": "string(1-128)",
  "platform_session_id": "string|null",
  "user_id": "string|null",
  "student_profile": "阶段2 StudentProfile",
  "job_profile": "阶段2 JobProfile"
}
```

`GenerateCareerPathRequest` 必填/可选字段：

```json
{
  "schema_version": "stage3-tool-v1",
  "idempotency_key": "string(8-128)",
  "session_id": "string(1-128)",
  "platform_session_id": "string|null",
  "user_id": "string|null"
}
```

路径请求不接受 `match_result`、`overall_score`、`skill_gaps`、候选节点或路径分数；这些值
只能从后端持久化的匹配结果进入 PathService。匹配请求也不接受任何结果分数字段。

成功 envelope 固定为 `code/message/request_id/data/error`。`request_id` 即持久化的
`tool_call_id`；`data.agent_run_id` 固定关联 `session_id:MatchAgent` 或
`session_id:PathAgent`。匹配数据仅返回 `match_result`，路径数据仅返回
`career_roadmap`，不回传完整学生画像。

相同 `tool_name + idempotency_key` 和相同请求指纹返回原 `request_id`/结果，并设置
`idempotent_replay=true`；相同键但不同请求返回 `-8`。原始请求、Bearer token 和明文
`user_id` 不写入平台调用日志。

### 1.4 标准远程 MCP Server（`stage4-mcp-v1`）

这是 §1.3 HTTP Tool API 的加法适配，不删除或改变 HTTP `stage3-tool-v1` 契约。服务使用官方
`mcp==2.0.0`，传输为 Streamable HTTP，默认端点 `/mcp`。启用时要求
`Authorization: Bearer <MCP_API_TOKEN>`；本地测试可以显式设置
`MCP_AUTH_ENABLED=false`。当前没有百宝箱只支持旧 SSE 的已验证依据，因此不提供 `/sse`。

| MCP 工具 | 必填输入 | 真实执行入口 | 成功状态 | 确定性结果 |
|---|---|---|---|---|
| `build_student_profile` | `session_id/user_id` + 至少一个扁平画像证据字段 | `ProfileAgent` / `ProfileService` / `StudentProfilePersistenceService` | `PROFILE_COMPLETED` | `StudentProfile`；满足冻结表最低要求时同时返回 PostgreSQL `student_id` |
| `analyze_target_job` | `session_id/user_id/job_title` + 可选扁平岗位字段 | `JobAgent` | `JOB_COMPLETED` | `JobProfile + TrendResult` |
| `analyze_job_match` | `session_id/user_id` | `MatchAgent` / `MatchService` | `MATCH_COMPLETED` | `MatchResult` |
| `generate_career_path` | `session_id/user_id` | `PathAgent` / `PathService` | `PATH_COMPLETED` | `PathResult` |
| `generate_and_score_training` | generate: `session_id/user_id/training_type`; score: `session_id/user_id/training_id/user_answer` | `TrainingAgent` / `TrainingService` | `TRAINING_COMPLETED` | `TrainingTask` 或 `TrainingScore` |
| `recommend_learning_and_job_resources` | `session_id/user_id` | `ResourceService` | 保持当前 session 状态 | `ResourceRecommendation` |
| `save_growth_feedback` | `session_id/user_id/satisfaction` | `FeedbackAgent` / `FeedbackService` | `FEEDBACK_COMPLETED` | `FeedbackAgentResult` |

`build_student_profile` 的 MCP 公开字段为基础类型：可选 `resume_text`、
`education_level`、`major`、`graduation_year`、`city`、`target_job`、
`target_industry`、`years_of_experience`、`skills`、`projects`、`internships`、
`work_experience`、`competitions`、`certificates`、`supplementary_info`，其中
`skills` 及各经历字段是字符串数组。调用时至少提供一个非空画像证据字段。

比赛模式把调用方提供的 `user_id` 视为可信逻辑身份。画像满足 PG16 冻结表最低要求
（学历、专业、目标岗位以及至少三项有证据能力）时，`build_student_profile` 创建或更新
`student_profile`，并把返回的 `student_id` 绑定到当前 `CareerState`。部分画像仍是合法的
对话输入，但只保存为 session 快照，返回 `student_id=null/data_source=session`，用于继续追问，
不会因数据库写入要求而把既有成功链路变为失败。

`analyze_target_job` 的 MCP 公开字段为必填字符串 `job_title`，以及可选基础类型
`job_id`、`industry`、`city`、`job_description`、`trend_context`。这两个工具不再公开
`student_input` / `target_job_input` 嵌套对象；MCP 适配层会用扁平字段构造内部严格模型。
这一变化只影响 MCP 工具参数，§1.3 的 HTTP Tool API 契约保持不变。

内部严格 `TargetJobInput` 另支持互斥业务引用 `type_key`。存在 `job_id` 时固定读取
`job_clean` 并按 `normalized_job_title` 关联 `job_type_profile`；存在 `type_key` 时固定
读取该类型画像及其代表岗位。数据库引用优先于同请求中的自由文本，分支不得交给 LLM。
仅提供公开 `job_title` 时，服务端先以标题及可选 `city/industry` 在内部确定性解析岗位：
标题直接命中标准类型，或搜索结果可归并为唯一标准类型时读取 PostgreSQL 上下文；无匹配、
存在多个类型或自动查询不可用时不任意选择，继续使用原始岗位证据分析。

数据库岗位成功响应在既有 `agent_run_id/fallback_used/job_profile/trend_result` 基础上
加法返回：

```json
{
  "job_id": "int | null",
  "type_key": "string | null",
  "data_source": "session | postgresql | demo_json",
  "demo_mode": "bool"
}
```

数据库 `skill_requirements` 的 `tag/required_level/weight/importance` 必须原值映射，
JobAgent 和 LLM 不得重算。PostgreSQL 无记录返回 `JOB_CONTEXT_NOT_FOUND`；数据库不可用
返回可重试的 `JOB_DATABASE_UNAVAILABLE`，生产模式禁止回退 `jobs_demo.json`。显式
Demo Mode 跳过 PostgreSQL，返回相同 `JobProfile` 模型并标记
`data_source=demo_json/fallback_used=true`。

`generate_and_score_training` 是一个合并工具，不拆分为生成/评分两个 MCP 名称。生成模式不传
`user_answer`，必须传三值枚举 `training_type`；评分模式必须传 `training_id + user_answer`，
可选 `training_type` 只能用于校验其与已保存任务一致。调用方不得传 evaluation criteria、
coverage、score 或 ability updates；所有数值由 TrainingService 计算。

`recommend_learning_and_job_resources` 不接受 `ability_gaps` 或 `target_job`。它从同一 session
的 `match_result.skill_gaps` 和 `job_profile` 读取有序上下文，返回
`learning_resources/job_resources/certificate_suggestions/data_quality_flags`。

`save_growth_feedback` 要求整数 `satisfaction`（1–5），可选同范围的 `path_rating`、
`training_rating`、`resource_rating` 和最长 10000 字符 `comments`。技能缺口、训练目标和综合分
从 State 投影，调用方不能传入或覆盖。

所有工具可选传 `trace_id`（1–64 字符，标识符字符集同 `tool_call_id`）；缺省时服务端生成
`tool-<uuid>`。`trace_id` 同时是 `platform_tool_calls.tool_call_id`，用于关联安全平台调用日志和
`session_id:<AgentName>` AgentRunLog。每个逻辑调用必须使用唯一 trace；原始输入、Token 和
明文 user_id 不写入平台调用账本。

MCP 统一结构化结果字段：

```json
{
  "success": true,
  "error_code": null,
  "message": "string",
  "missing_fields": [],
  "retryable": false,
  "trace_id": "tool-...",
  "session_id": "string",
  "status": "PROFILE_COMPLETED | JOB_COMPLETED | MATCH_COMPLETED | PATH_COMPLETED | TRAINING_COMPLETED | FEEDBACK_COMPLETED | ...",
  "data": "tool-specific validated object | null"
}
```

业务前置失败返回 `success=false`、稳定 `error_code`、`missing_fields` 和 `retryable`，不返回
Python 堆栈。Pydantic/JSON Schema 不匹配由 MCP `tools/call` 协议错误拒绝。常见阶段4错误包括
`TRAINING_PREREQUISITES_NOT_READY`、`TRAINING_NOT_FOUND`、`TRAINING_TYPE_MISMATCH`、
`MATCH_RESULT_NOT_FOUND`、`RESOURCE_SERVICE_ERROR` 和 `FEEDBACK_FAILED`。匹配要求同一
session 已保存 `student_profile` 和 `job_profile`；路径要求已保存 `match_result` 且状态为
`MATCH_COMPLETED`。匹配、路径、训练和资源工具都不接受可覆盖后端业务结果的输入。

`PROFILE_COMPLETED`/`JOB_COMPLETED` 是仓库现有状态机中对外“PROFILE_READY/JOB_READY”
语义的正式状态名，不新增第二套状态枚举。规则 fallback 产生的结构化 Profile/Job 仍通过
固定 Schema 验证并保留 `fallback_used=true` AgentRunLog。

`build_student_profile.data` 在保持既有 `agent_run_id/fallback_used/student_profile`
字段不变的基础上，加法返回：

```json
{
  "student_id": "int | null — 仅由 PostgreSQL RETURNING 产生",
  "data_source": "session | postgresql | demo_json",
  "demo_mode": "bool"
}
```

启用画像持久化时，调用顺序固定为：ProfileAgent 产出 → `StudentProfile` Pydantic
校验 → `ProfileService` 确定性分数复核 → PostgreSQL 创建/更新 → 调用账本写入
`student_id/updated_at` 安全检查点 → CareerState 快照。State 只保存画像会话投影、
`student_profile_id` 和版本时间；从 PostgreSQL 恢复的能力证据统一标记
`evidence_source=history`。姓名不进入 Prompt、CareerState 画像或日志；调用方未提供
合规展示名时数据库使用 `匿名学生`。

同一 `trace_id` 的成功重放读取账本中的原 `student_id`，不得再次插入。若 PostgreSQL
提交后 CareerState 快照失败，但安全检查点已写入，重试按该 ID 恢复画像和状态。由于
当前业务表仍没有 `user_id` 绑定及同事务幂等回执。比赛组合根已按项目负责人确认的信任
模型默认注入 `StudentProfilePersistenceService`，但这不代表生产安全门禁已经满足。检查点
自身写入失败或进程恰在业务提交与检查点之间崩溃时不能声称 exactly-once，正式多租户部署
仍受 §19 数据库接入门禁约束。

### 1.5 CareerPulse → 百宝箱智能体 Chat API（`tbox-chat-v1`）

这是与 §1.3/§1.4 相反方向的加法接口：Vue 调用 CareerPulse，CareerPulse 再使用服务端凭据
调用百宝箱正式智能体。浏览器请求不得包含百宝箱 API Key/Token。

| 方法 | 路径 | operationId | 请求 | 普通响应 |
|---|---|---|---|---|
| POST | `/api/tbox/chat` | `chat_with_tbox_agent` | `TBoxChatRequest` | `TBoxChatResponse` |

固定请求：

```json
{
  "session_id": "career-session-001",
  "user_id": "anonymous-user-001",
  "message": "请分析我的职业方向",
  "stream": false
}
```

`session_id/user_id` 只允许 1–128 字符的标识符字符集；`message` 为 1–20000 字符；请求模型
`extra=forbid`。`user_id` 用于校验 session 归属，不是登录鉴权凭证；适配层使用仅服务端持有的
HMAC secret 将其转换成稳定匿名值后再填写百宝箱 `userId`，不发送本地明文 user_id。

普通成功响应：

```json
{
  "code": 0,
  "message": "success",
  "request_id": "chat-<uuid>",
  "data": {
    "session_id": "career-session-001",
    "conversation_id": "百宝箱 conversationId",
    "message_id": "百宝箱 messageId 或 null",
    "upstream_request_id": "百宝箱 requestId 或 null",
    "content": "智能体文本回复"
  },
  "error": null
}
```

`stream=true` 时 HTTP Content-Type 为 `text/event-stream`，每个 `data` 仍是严格 JSON。事件顺序：

```text
event: session  # request_id/session_id/conversation_id
event: delta    # 文本增量 content，可重复
event: done     # message_id/upstream_request_id，正常结束
event: error    # 任意阶段失败后的安全 error；出现后不再有 done
```

上游 `thinking`、`meta` 和原始错误正文不进入这些事件。流已经建立后的平台失败使用
`event:error` 表达，因此 HTTP 状态仍可能是 200；调用方必须以 `done` 或 `error` 判断终态。

首次调用不传百宝箱 `conversationId`。适配层从 header/chunk/普通响应取得 conversationId 后
写入同一 `CareerState.platform_session_id`，后续调用自动带回。一个 CareerPulse session 只能
属于一个 user_id 和一个百宝箱 conversationId，冲突返回 HTTP 409。

错误 envelope 仍为 `code/message/request_id/data/error`：

| code | HTTP | 典型错误 | retryable |
|---:|---:|---|---|
| -1 | 500/503 | 网关内部错误或未配置正式智能体 | false |
| -2 | 422 | 请求 Schema 不匹配 | false |
| -3 | 409 | session 用户或 conversation 映射冲突 | false |
| -4 | 504 | 百宝箱响应超时 | true |
| -5 | 503 | CareerState/调用日志持久化失败 | true |
| -6 | 502 | 百宝箱连接、限流、5xx 或响应协议错误 | 看 `error.retryable` |

每次实际出站调用写入 `platform_tool_calls`，`tool_name=tbox_agent_chat`。只保存 SHA-256 请求
指纹、哈希 user_id、session/conversation 标识、状态、耗时和 `json/stream` 模式；不保存
message、reply、上游错误体或任何授权值。聊天不自动重试，也不回退到旧 Mock。

---

## 2. 学生画像（StudentProfile）

### 2.1 结构

```json
{
  "student_id": "int | null",
  "name": "string — 匿名化姓名",
  "basic_info": {
    "education_level": "string — 专科/本科/硕士/博士",
    "major": "string",
    "graduation_year": "int | null",
    "target_job": "string",
    "target_industry": "string | null",
    "years_of_experience": "float | null"
  },
  "abilities": [
    {
      "tag": "string — 能力标签名, 必须来自能力标签体系 §11",
      "level": "int — 1-5, 见 §10",
      "confidence": "float — 0.0-1.0, 证据置信度",
      "evidence": "string — 证据文本摘要, 禁止包含手机号/邮箱/身份证"
    }
  ],
  "competitiveness_score": "float — 0.0-100.0, 综合竞争力评分",
  "completeness": "float — 0.0-1.0, 画像完整度",
  "missing_fields": ["string — 缺失信息字段名"]
}
```

### 2.2 约束

- `abilities` 至少包含 3 个标签，至多 30 个
- `level` 为 1-5 整数
- `confidence` < 0.3 的条目应在百宝箱对话中追问
- `completeness` < 0.5 时百宝箱应引导补充信息

---

## 3. 岗位画像（JobProfile / TrendResult）

### 3.1 JobProfile

```json
{
  "job_id": "int | null",
  "title": "string — 岗位名称",
  "normalized_title": "string — 归一化岗位名",
  "industry": "string",
  "required_abilities": [
    {
      "tag": "string — 能力标签名",
      "required_level": "int — 1-5",
      "weight": "float — 0.0-1.0, 该能力在岗位中的权重, 同一岗位所有权重之和为1.0",
      "importance": "string — critical / important / nice_to_have"
    }
  ],
  "soft_skills": ["string"],
  "salary_range": "string | null",
  "job_description": "string"
}
```

### 3.2 TrendResult（岗位趋势分析）

```json
{
  "job_title": "string",
  "industry": "string",
  "trend_summary": "string — 1-2句趋势总结",
  "hot_skills": ["string — 近期高频技能标签"],
  "rising_skills": ["string — 正在变重要的技能"],
  "declining_skills": ["string — 需求下降的技能"],
  "ai_risk_assessment": "string — low / medium / high",
  "ai_risk_detail": "string — AI替代风险说明",
  "development_opportunities": ["string"],
  "development_risks": ["string"],
  "data_source": "string — 知识库来源说明, 如 '基于2025Q4-2026Q1公开招聘数据' "
}
```

---

## 4. 匹配结果（MatchResult）

### 4.1 结构

```json
{
  "overall_score": "float — 0.0-100.0, 综合匹配度, 由 MatchService 代码计算",
  "match_level": "string — high / good / fair / weak / low / insufficient_data",
  "dimension_matches": [
    {
      "dimension": "string — 统一能力标签",
      "student_level": "int 1-5 | null — null 表示画像未提供，不等于0级",
      "required_level": "int — 1-5",
      "gap": "int >=0 | null — 仅学生等级已知时计算",
      "score": "float 0.0-100.0 | null",
      "weight": "float — 0.0-1.0",
      "student_evidence": "string | null",
      "job_evidence": "string | null",
      "confidence": "float 0.0-1.0 | null",
      "importance": "string — critical / important / nice_to_have",
      "status": "string — matched / gap / unknown / excluded"
    }
  ],
  "matched_skills": ["string — 达到要求的正权重能力"],
  "missing_skills": ["string — 岗位需要但学生画像未提供的正权重能力"],
  "skill_gaps": ["object — 有明确学生等级且低于岗位要求的能力差距、证据和优先级"],
  "hard_constraint_results": ["object — critical能力的passed/failed/unknown结论"],
  "confidence": "float — 0.0-1.0, 结果可靠度而非能力等级",
  "evidence": ["object — 按能力维度对齐的学生和岗位证据"],
  "calculation_version": "string — 固定为 deterministic-match-v2",
  "data_quality_flags": ["string — 画像缺失、低置信度等确定性标志"],
  "dimensions": [
    {
      "name": "string — 维度名称",
      "student_score": "float — 0.0-100.0",
      "job_required": "float — 0.0-100.0",
      "gap": "float — student_score - job_required, 负数表示不足",
      "weight": "float — 0.0-1.0"
    }
  ],
  "ability_gaps": [
    {
      "tag": "string — 能力标签",
      "current_level": "int — 0-5；0仅为旧兼容投影中的未知哨兵",
      "required_level": "int — 1-5",
      "gap": "int — required_level - current_level, ≥0",
      "priority": "int — 提升优先级, 1=最高, 正整数, 由 MatchService 计算"
    }
  ],
  "gap_analysis": [
    {
      "item": "string — 差距项描述",
      "status": "string — missing / insufficient / adequate",
      "suggestion": "string — 提升建议"
    }
  ],
  "strengths": ["string — 匹配优势项"],
  "matching_algorithm_version": "string — 固定为 'deterministic-v1' , 证明不是LLM计算"
}
```

### 4.2 匹配公式（确定性）

```
Score(u,i) = Σ wk × min(Suk / Jik, 1)
  其中:
    wk  = 岗位能力 k 的权重, Σwk = 1.0
    Suk = 学生能力 k 的等级 (1-5)
    Jik = 岗位要求能力 k 的等级 (1-5)

Gap_k    = max(Jik - Suk, 0)

Priority_k = Gap_k × wk × (1 / Difficulty_k)
  其中 Difficulty_k 为能力提升难度系数 (1.0-3.0)

已知维度集合 Kobs = 学生画像提供 level 且岗位 weight > 0 的能力维度
Score(u,i) = Σ(k∈Kobs) wk × min(Suk / Jik, 1) / Σ(k∈Kobs) wk

缺失能力: student_level / gap / score = null，不直接判定为0级；
可观测岗位权重 < 0.5 时 match_level = insufficient_data。
旧 ability_gaps.current_level=0 仅为 deterministic-v1 兼容投影。
```

> 匹配分 **严禁由 LLM 直接产出**。LLM 仅负责 `gap_analysis[].suggestion` 和 `strengths` 的自然语言生成。
> 阶段3加法扩展与缺失语义见 `decisions/ADR-001-stage3-match-result-extension.md`。

---

## 5. 路径规划（PathPlan / LearningPlan）

### 5.1 PathPlan

```json
{
  "target_job": "string",
  "plan_3year": {
    "phases": [
      {
        "phase": "int — 1-based",
        "duration_months": "int",
        "target_role": "string",
        "required_abilities": ["string"],
        "tasks": ["string"],
        "milestone": "string"
      }
    ],
    "total_score": "float — 路径评分, 由 PathService 计算"
  },
  "plan_5year": {
    "phases": [
      {
        "phase": "int",
        "duration_months": "int",
        "target_role": "string",
        "required_abilities": ["string"],
        "tasks": ["string"],
        "milestone": "string"
      }
    ],
    "total_score": "float"
  },
  "alternative_paths": [
    {
      "type": "string — vertical(纵向晋升) / lateral(横向转岗)",
      "target_role": "string",
      "score": "float",
      "reason": "string"
    }
  ],
  "path_algorithm_version": "string — 固定为 'graph-search-v1'"
}
```

### 5.2 LearningPlan

```json
{
  "phases": [
    {
      "phase": "int",
      "title": "string — 阶段标题 e.g. '第1阶段：基础能力补齐'",
      "tasks": [
        {
          "task_id": "string",
          "description": "string",
          "target_ability": "string — 关联能力标签",
          "estimated_hours": "int",
          "resources": ["string — 推荐资源URL或名称"]
        }
      ]
    }
  ],
  "certificate_suggestions": ["string"],
  "project_suggestions": ["string"]
}
```

### 5.3 路径评分公式

```
PathScore = GrowthValue - TransferCost - AbilityGapCost

GrowthValue       = Σ (目标岗位能力等级 × 该能力市场溢价系数)
TransferCost      = Σ (需要学习的新能力数 × 学习难度)
AbilityGapCost    = Σ (Gap_k × Difficulty_k)
```

### 5.4 阶段3确定性 PathResult（加法扩展）

PathService 独立返回以下结构；冻结 `path_plan` 仍保留，后续由 PathAgent 做兼容投影：

```json
{
  "status": "success / no_reachable_path / insufficient_data",
  "requested_horizon_years": "3 / 5",
  "candidate_paths": ["CandidatePath — 图谱节点序列、边、评分与数据标志"],
  "recommended_path": "CandidatePath | null",
  "alternative_paths": ["CandidatePath"],
  "path_scores": {"path_id": "PathScore"},
  "three_year_roadmap": "CareerRoadmap — 3个年度阶段",
  "five_year_roadmap": "CareerRoadmap — 5个年度阶段",
  "assumptions": ["string"],
  "risks": ["string"],
  "confidence": "float 0.0-1.0",
  "data_quality_flags": ["string"],
  "calculation_version": "deterministic-path-v1"
}
```

每个 `PathScore` 至少包含：`current_match_score/growth_value/transfer_cost/ability_gap_cost/`
`base_score/preference_adjustment/industry_continuity/region_fit/risk_penalty/`
`target_consistency/data_confidence/total_score`。

```text
base_score = growth_value - transfer_cost - ability_gap_cost
adjusted = base_score + preference + industry_continuity×5 + region_fit×5 - risk_penalty
total_score = adjusted × target_consistency
```

未知学生能力不按0级计 Gap；未知岗位不创建推断节点。具体决策见
`decisions/ADR-002-stage3-career-graph-and-roadmap.md`。

---

## 6. 训练（TrainingTask / TrainingScore）

### 6.1 TrainingTask

```json
{
  "training_id": "string",
  "type": "string — remote_collaboration / ai_office_task / cross_role_communication",
  "title": "string",
  "scenario": "string — 场景背景描述",
  "task_description": "string — 任务要求",
  "evaluation_criteria": [
    {
      "dimension": "string — 评分维度名",
      "max_score": "float",
      "weight": "float",
      "description": "string — 评分标准"
    }
  ],
  "reference_answer": "string | null — 参考答案要点"
}
```

### 6.2 TrainingScore（用户提交后返回）

```json
{
  "training_id": "string",
  "total_score": "float — 0.0-100.0",
  "dimension_scores": [
    {
      "dimension": "string",
      "score": "float",
      "comment": "string"
    }
  ],
  "overall_comment": "string — 综合评价",
  "improvement_suggestions": ["string"],
  "ability_updates": [
    {
      "tag": "string",
      "level_change": "int — -1 / 0 / +1"
    }
  ]
}
```

---

## 7. 反馈（FeedbackResult / GrowthArchive）

### 7.1 FeedbackResult

```json
{
  "session_id": "string",
  "satisfaction": "int — 1-5, 用户总体满意度",
  "path_rating": "int | null — 1-5",
  "training_rating": "int | null — 1-5",
  "resource_rating": "int | null — 1-5",
  "comments": "string | null",
  "updated_priorities": [
    {
      "tag": "string",
      "old_priority": "int",
      "new_priority": "int",
      "reason": "string"
    }
  ],
  "growth_archive_updated": "bool"
}
```

### 7.2 GrowthArchive（成长档案快照）

```json
{
  "user_id": "string",
  "snapshot_time": "string — ISO-8601",
  "abilities": [
    {
      "tag": "string",
      "level": "int — 1-5",
      "updated_at": "string — ISO-8601"
    }
  ],
  "competitiveness_score": "float",
  "completed_trainings": "int",
  "completed_phases": "int",
  "growth_trend": "string — improving / stable / declining"
}
```

---

## 8. AgentLog

```json
{
  "session_id": "string",
  "agent_name": "string — ProfileAgent / JobAgent / MatchAgent / PathAgent / TrainingAgent / FeedbackAgent",
  "service_name": "string | null — MatchService / PathService 等确定性 Service",
  "status": "string — success / partial / failed",
  "summary": "string — 1句话摘要",
  "duration_ms": "int",
  "tool_calls": [
    {
      "tool_name": "string",
      "service_name": "string | null",
      "input_summary": "string — 禁止包含完整简历文本",
      "output_summary": "string",
      "duration_ms": "int",
      "status": "string — success / error"
    }
  ],
  "fallback_used": "bool",
  "error": "string | null",
  "timestamp": "string — ISO-8601"
}
```

> 隐私约束：`input_summary` 和 `output_summary` 中**不得出现**手机号、邮箱、身份证号、完整简历文本。

---

## 9. 统一错误格式

### 9.1 后端 API 响应

```json
{
  "code": "int — 0=成功, 非0=错误",
  "message": "string — 人类可读消息",
  "request_id": "string — 请求追踪ID",
  "data": "object | null — 成功时携带数据",
  "error": "object | null — 失败时携带详情"
}
```

### 9.2 Agent 统一返回格式

```json
{
  "agent_name": "string",
  "status": "string — success / partial / failed",
  "data": "object | null",
  "summary": "string",
  "duration_ms": "int",
  "tool_calls": "array",
  "fallback_used": "bool",
  "error": "string | null"
}
```

### 9.3 百宝箱 Tool 统一返回格式

```json
{
  "code": "int — 0=成功",
  "message": "string",
  "request_id": "string — UUID, 后端生成",
  "data": "object | null",
  "error": "object | null — {type: string, detail: string}"
}
```

### 9.4 错误码约定

| code | 含义 |
|------|------|
| 0 | 成功 |
| -1 | 通用错误 |
| -2 | 参数校验失败 |
| -3 | 资源不存在（学生/岗位/报告） |
| -4 | LLM 调用失败（返回 fallback） |
| -5 | 数据库错误 |
| -6 | 超时 |
| -7 | Bearer 鉴权失败 |
| -8 | 幂等键、会话 payload 或并发调用冲突 |
| -9 | 会话身份或工具前置条件不满足 / 结果尚不可用 |

---

## 10. 能力等级范围

**统一 5 级评分**，适用范围：学生画像、岗位要求、能力缺口。

| Level | 含义 | 描述 |
|-------|------|------|
| 1 | 入门 | 了解基本概念，无实践经验 |
| 2 | 初级 | 能在指导下完成任务 |
| 3 | 中级 | 能独立完成任务，有一定深度 |
| 4 | 高级 | 能带领小团队完成任务，有深入理解 |
| 5 | 专家 | 行业领先水平，能指导和创新 |

**映射**：
- `current_level` / `required_level` 均为 1-5 整数
- 缺失能力时 `current_level = 0`（仅 Gap 计算中使用，画像中不存在 level=0 标签）
- `competitiveness_score` 是 0.0–100.0 的浮点数，由能力等级加权计算得出

---

## 11. 能力标签体系

### 11.1 分类

能力标签按 5 个一级类别组织。标签名使用中文，**标签名是全局唯一标识**，新增不删旧。

#### A. 技术硬技能（Hard Skills）

| 标签 | 难度系数 | 说明 |
|------|---------|------|
| Python | 1.5 | Python 编程 |
| Java | 1.5 | Java 编程 |
| JavaScript/TypeScript | 1.3 | 前端语言 |
| SQL/数据库 | 1.2 | 数据库查询与设计 |
| Linux/运维 | 1.8 | 系统运维 |
| Docker/K8s | 2.0 | 容器与编排 |
| 云计算 | 2.0 | AWS/Azure/阿里云 |
| 数据分析 | 1.5 | pandas/Excel/BI |
| 机器学习 | 2.5 | ML算法与框架 |
| 深度学习 | 3.0 | DL/NLP/CV |
| 大模型应用 | 2.5 | LLM应用开发/RAG/Agent |
| 前端开发 | 1.5 | Vue/React |
| 后端开发 | 2.0 | Spring/FastAPI/Django |
| 移动端开发 | 2.0 | iOS/Android/Flutter |
| 测试/QA | 1.3 | 自动化测试 |

#### B. 产品与业务能力（Product & Business）

| 标签 | 难度系数 | 说明 |
|------|---------|------|
| 需求分析 | 1.5 | 需求调研与文档 |
| 产品规划 | 2.0 | 产品路线图与策略 |
| 用户研究 | 1.8 | 用户访谈与洞察 |
| 数据驱动决策 | 1.8 | 用数据支持业务判断 |
| 商业分析 | 2.0 | 商业模式与市场分析 |
| 项目管理 | 1.5 | 敏捷/Scrum/进度管理 |

#### C. 通用素养（Soft Skills）

| 标签 | 难度系数 | 说明 |
|------|---------|------|
| 沟通表达 | 1.5 | 口头与书面表达 |
| 团队协作 | 1.2 | 跨团队合作 |
| 领导力 | 2.5 | 团队管理与激励 |
| 解决问题 | 1.5 | 分析与解决问题能力 |
| 学习能力 | 1.0 | 快速掌握新知识 |
| 时间管理 | 1.0 | 优先级与效率 |
| 抗压能力 | 1.5 | 高压环境适应 |

#### D. 行业知识（Domain Knowledge）

| 标签 | 难度系数 | 说明 |
|------|---------|------|
| 互联网金融 | 2.0 | 金融科技领域 |
| 电子商务 | 1.5 | 电商行业 |
| 企业服务/SaaS | 1.5 | B2B软件 |
| 游戏行业 | 1.8 | 游戏开发与运营 |
| 人工智能 | 2.5 | AI行业知识 |
| 教育培训 | 1.2 | 在线教育 |

#### E. 职业资质（Certifications）

| 标签 | 难度系数 | 说明 |
|------|---------|------|
| 软考认证 | 1.5 | 计算机技术与软件专业技术资格 |
| PMP | 2.0 | 项目管理专业认证 |
| 计算机等级考试 | 1.0 | 全国计算机等级考试 |
| 行业认证 | 1.5 | AWS/华为/思科等 |

### 11.2 管理规则

- **新增**：可以新增标签，不可删除已有标签（数据中有引用）
- **废弃**：标记 `deprecated: true` 但保留标签名
- **标签名唯一**：不区分中英文括号和空格，统一为中文括号
- **最低数据**：初始至少包含上述 40 个标签

---

## 12. Demo 数据格式

### 12.1 触发方式

- 环境变量 `A02_DEMO_MODE=true`（后端）
- 环境变量 `VITE_DEMO_MODE=true`（前端）
- 请求头 `X-Demo-Mode: true`

### 12.2 Demo 数据要求

```json
{
  "demo_mode": "bool — true, 必须在响应中显式标示",
  "demo_notice": "string — 固定为 '当前为演示模式，数据为示例数据，不代表真实评估结果'"
}
```

Demo Mode 下：
- Agent 返回固定数据，不调用外部 LLM
- Agent 日志正常生成（标记 `demo: true`）
- 前端页面明确显示"演示数据"水印或标签
- **禁止**将 Demo 数据冒充为真实平台测试结果

### 12.3 Demo 固定数据

```json
{
  "student_profile_demo": {
    "name": "林思然（演示）",
    "basic_info": {
      "education_level": "本科",
      "major": "信息管理与信息系统",
      "graduation_year": 2025,
      "target_job": "AI产品经理",
      "target_industry": "人工智能"
    },
    "abilities": [
      {"tag": "Python", "level": 3, "confidence": 0.85, "evidence": "完成数据挖掘课程项目"},
      {"tag": "数据分析", "level": 3, "confidence": 0.80, "evidence": "用户行为分析实习"},
      {"tag": "产品规划", "level": 2, "confidence": 0.70, "evidence": "参与校园产品设计竞赛"},
      {"tag": "用户研究", "level": 3, "confidence": 0.75, "evidence": "用户调研课程项目"},
      {"tag": "沟通表达", "level": 3, "confidence": 0.80, "evidence": "课程汇报与团队项目"}
    ],
    "competitiveness_score": 42.0,
    "completeness": 0.60,
    "missing_fields": ["实习经历详情", "项目经历详情"]
  },
  "job_profile_demo": {
    "title": "AI产品经理",
    "industry": "人工智能",
    "required_abilities": [
      {"tag": "产品规划", "required_level": 4, "weight": 0.25, "importance": "critical"},
      {"tag": "需求分析", "required_level": 4, "weight": 0.20, "importance": "critical"},
      {"tag": "数据驱动决策", "required_level": 3, "weight": 0.15, "importance": "important"},
      {"tag": "大模型应用", "required_level": 3, "weight": 0.15, "importance": "important"},
      {"tag": "用户研究", "required_level": 3, "weight": 0.10, "importance": "important"},
      {"tag": "沟通表达", "required_level": 4, "weight": 0.10, "importance": "nice_to_have"},
      {"tag": "项目管理", "required_level": 2, "weight": 0.05, "importance": "nice_to_have"}
    ]
  },
  "match_result_demo": {
    "overall_score": 48.5,
    "dimensions": [
      {"name": "专业技能", "student_score": 55.0, "job_required": 75.0, "gap": -20.0, "weight": 0.60},
      {"name": "学习能力", "student_score": 70.0, "job_required": 65.0, "gap": 5.0, "weight": 0.15},
      {"name": "实践能力", "student_score": 45.0, "job_required": 75.0, "gap": -30.0, "weight": 0.15},
      {"name": "通用素养", "student_score": 68.0, "job_required": 70.0, "gap": -2.0, "weight": 0.10}
    ],
    "ability_gaps": [
      {"tag": "产品规划", "current_level": 2, "required_level": 4, "gap": 2, "priority": 1},
      {"tag": "大模型应用", "current_level": 0, "required_level": 3, "gap": 3, "priority": 1},
      {"tag": "需求分析", "current_level": 0, "required_level": 4, "gap": 4, "priority": 2},
      {"tag": "数据驱动决策", "current_level": 0, "required_level": 3, "gap": 3, "priority": 2}
    ]
  }
}
```

---

## 12.4 参数化只读数据库 MCP 工具（D7-06 加法契约）

在既有七个高层工具保持不变的前提下，保留四个可选只读业务工具。它们默认不出现在平台
`tools/list` 中，只有服务端设置 `MCP_EXPOSE_DATABASE_TOOLS=true` 时才注册公开：

| 工具名 | 固定业务参数 | 上限与约束 |
|---|---|---|
| `read_student_profile` | `session_id`、`user_id`、`student_id`、可选 `trace_id` | `student_id >= 1`；必须通过会话到学生引用的授权绑定；禁止姓名搜索 |
| `search_jobs` | `session_id`、`user_id`、可选 `keyword/city/industry/page/page_size/trace_id` | `page_size <= 50`；不接受排序、SQL、表名或列名；列表不返回公司名和完整 JD |
| `read_job_context` | `session_id`、`user_id`、`job_id` 或 `normalized_title`、可选 `trace_id` | 两种岗位引用必须且只能提供一个；不计算匹配分 |
| `read_career_graph_edges` | `session_id`、`user_id`、可选 `source_type_key/relation_type/limit/trace_id` | `relation_type=vertical/lateral`；`limit <= 500` |

四个响应继续使用 MCP 统一 envelope：
`success/error_code/message/missing_fields/retryable/trace_id/session_id/status/data`。
成功 `data` 固定包含 `data_source=postgresql|demo_json` 和 `fallback_used`。生产数据库失败
不得读取 JSON；只有服务端显式 Demo Mode 才可选择 Demo Provider 或执行 Demo 回退。

数据库调用通过现有调用账本、trace 幂等检查、超时和错误转换。账本只保存业务 ID、筛选项
是否存在、分页、返回条数、来源和回退标记，不保存姓名、完整 `basic_info`、能力证据、完整
JD、数据库凭据或 SQL 参数正文。

比赛模式使用已持久化 CareerState 执行严格三元绑定：请求的 `session_id` 必须存在，
`user_id` 必须等于该 session 的逻辑用户，`student_id` 必须等于该 session 保存的
`student_profile_id`。任一项不一致均拒绝读取。该规则不等同于生产 SSO/Token 身份认证；
正式多租户部署仍应由网关提供可信主体，并在业务数据库落地用户到画像的长期归属关系。

## 12.5 双数据源等价与失败语义（D7-11）

- PostgreSQL 与 JSON Demo Provider 必须先映射到相同严格 Pydantic 业务模型；时间戳、`data_source`、`demo_mode` 和 `fallback_used` 不参与业务等价比较。
- 同一学生、岗位和图谱快照产生的 Profile/Job 投影、Match 分数与缺口、Path 候选与路线、Training 分数、Resource 推荐和 Feedback 结果必须相同。
- 生产环境数据库连接失败统一返回可重试 `DATABASE_UNAVAILABLE`（MCP 超时为可重试 `MCP_TOOL_TIMEOUT`），响应不得携带 JSON Demo 数据。
- 显式 Demo Mode 才允许 Demo Provider；数据库失败后的 Demo 回退必须同时返回 `data_source=demo_json` 和 `fallback_used=true`。
- Feedback 的 `growth_snapshot.competitiveness_score` 可记录 Match 的 `overall_score`，但不得回写或覆盖 `student_profile.competitiveness_score` / `career_competitiveness_score`。
- `training_tasks.json` 与 `resources.json` 保持原契约与加载路径，不增加数据库来源字段。

## 13. 版本记录

| 日期 | 版本 | 变更 | 作者 |
|------|------|------|------|
| 2026-09-21 | v1.8 | 比赛模式启用完整画像 PostgreSQL 持久化及 CareerState 三元引用授权；部分画像保持 session 兼容 | Codex |
| 2026-09-20 | v1.7 | 冻结双数据源等价、生产失败关闭、Demo 回退和 Feedback 不回写画像规则 | Codex |
| 2026-09-20 | v1.6 | 接入 analyze_target_job 的确定性 PostgreSQL 岗位上下文与来源元数据 | Codex |
| 2026-09-20 | v1.5 | 加法定义画像数据库引用、来源元数据及 PostgreSQL-first 状态恢复边界 | Codex |
| 2026-09-19 | v1.4 | 加法注册四个参数化只读数据库 MCP 工具；冻结来源元数据、上限和学生授权失败关闭规则 | Codex |
| 2026-08-27 | v1.3 | 加法注册 stage4-mcp-v1 三工具，标准 MCP 工具总数更新为7 | CareerPulse A02 Team |
| 2026-08-21 | v1.2 | 加法新增 stage3-mcp-v1 四工具、状态、trace、错误和安全约束 | CareerPulse A02 Team |
| 2026-08-04 | v1.0 | 初始冻结：CareerState、统一错误格式、能力等级、能力标签体系、Demo格式 | 技术负责人 |

> **后续修改本文件的流程**：
> 1. 在 `decisions/` 创建 ADR 记录变更原因
> 2. 更新本文件和关联文档
> 3. 通知成员2更新 Service 和工具
> 4. 通知百宝箱更新工具 Schema
