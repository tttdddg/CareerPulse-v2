# CareerPulse A02 标准远程 MCP 接入说明

## 1. 实现范围

- SDK：官方 Model Context Protocol Python SDK `mcp==2.0.0`（固定稳定版，Python >=3.10）。
- 传输：Streamable HTTP。
- 默认端点：`/mcp`。
- Server 能力版本：`stage4-mcp-v1` 加 D7-06 只读扩展；平台默认 `tools/list` 返回
  7 个高层工具，`MCP_EXPOSE_DATABASE_TOOLS=true` 时返回 11 个。
- 运行方式：挂载到现有 `app.main:app` FastAPI 应用，共用 CareerOrchestrator、
  CareerState、StateRepository、Agent、Service 和平台调用账本。
- 鉴权：MCP 独立静态 Bearer Token；不复用或改变 HTTP Tool API 的
  `A02_TBOX_API_TOKEN`。
- SSE：未实现。当前没有目标百宝箱租户只支持旧 SSE 的已验证证据，避免维护重复传输。

MCP 适配层只处理协议参数到严格 Request Schema、session、状态、鉴权和日志。匹配、能力
缺口、路径、训练评分、资源和成长快照仍由现有确定性 Service/Agent handler 负责。

## 2. 本地安装与启动

从 `backend/` 目录执行：

```powershell
python -m pip install -r requirements.txt

$env:A02_DEMO_MODE = "true"
$env:MCP_ENABLED = "true"
$env:MCP_EXPOSE_DATABASE_TOOLS = "false"
$env:MCP_AUTH_ENABLED = "true"
$env:MCP_API_TOKEN = "example-local-token-change-me"
$env:MCP_HOST = "127.0.0.1"
$env:MCP_PORT = "8000"
$env:MCP_PATH = "/mcp"
$env:MCP_TOOL_TIMEOUT_SECONDS = "25"
$env:MCP_ALLOWED_HOSTS = "127.0.0.1:*,localhost:*"
$env:MCP_ALLOWED_ORIGINS = "http://127.0.0.1:*,http://localhost:*"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

客户端地址：`http://127.0.0.1:8000/mcp`。

`MCP_HOST` / `MCP_PORT` 是部署配置记录和 SDK 传输安全配置；Uvicorn 的 `--host/--port`
必须与之保持一致。`MCP_ENABLED=false` 时不挂载 MCP，原 FastAPI 和 HTTP Tool API 保持原样。

## 3. 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MCP_ENABLED` | `false` | MCP 总开关 |
| `MCP_EXPOSE_DATABASE_TOOLS` | `false` | 是否额外公开 4 个底层数据库工具；百宝箱业务 Agent 保持关闭 |
| `MCP_AUTH_ENABLED` | `true` | 是否要求静态 Bearer；只能在受控本地测试显式关闭 |
| `MCP_API_TOKEN` | 空 | MCP Bearer secret；鉴权启用时必填 |
| `MCP_HOST` | `127.0.0.1` | 运行 host 记录/SDK 安全配置 |
| `MCP_PORT` | `8000` | 运行端口，范围 1–65535 |
| `MCP_PATH` | `/mcp` | Streamable HTTP 路径，必须以 `/` 开头且无尾斜杠 |
| `MCP_ALLOWED_HOSTS` | localhost allowlist | 逗号分隔的 Host allowlist，防 DNS rebinding |
| `MCP_ALLOWED_ORIGINS` | localhost allowlist | 逗号分隔的 Origin allowlist |
| `MCP_TOOL_TIMEOUT_SECONDS` | `25` | MCP Agent 调用超时，范围 `(0,60]` |

不要把真实 Token 写进 `.env.example`、文档、Prompt、截图或日志。

## 4. 鉴权格式

所有远程 MCP 请求携带：

```http
Authorization: Bearer example-local-token-change-me
```

Token 缺失或不匹配返回 HTTP 401，响应不会回显 Token。MCP 鉴权只包装 `/mcp` 传输，
不会影响 `/api/platform/v1/tools/*` 的现有鉴权。

## 5. 工具列表与映射

| MCP 工具 | 现有 Agent/内部工具 | HTTP Tool API | session 行为 |
|---|---|---|---|
| `build_student_profile` | ProfileAgent / `analyze_student_profile` | 无独立正式平台 operation | 写 `student_profile` |
| `analyze_target_job` | JobAgent / `analyze_job_and_trend` | 无独立正式平台 operation | 写 `job_profile/trend_result` |
| `analyze_job_match` | MatchAgent + MatchService / `calculate_job_match` | `analyze_job_match` | 只读已有画像/岗位，写 `match_result` |
| `generate_career_path` | PathAgent + PathService / `recommend_career_path` | `generate_career_path` | 只读已有匹配，写路径结果 |
| `generate_and_score_training` | TrainingAgent + TrainingService / 同名 handler | 无独立 HTTP operation | generate/score 合并，写 training_plan |
| `recommend_learning_and_job_resources` | ResourceService / 同名 handler | 无独立 HTTP operation | 从 State 读 gaps/target job，写 resource_result |
| `save_growth_feedback` | FeedbackAgent + FeedbackService / 同名 handler | 无独立 HTTP operation | 读 State 上下文，写 feedback_result |
| `read_student_profile` | StudentProfilePersistenceService | 无 | 授权后按 ID 读取；身份绑定未配置时失败关闭 |
| `search_jobs` | JobContextService | 无 | 白名单筛选和最多 50 条分页 |
| `read_job_context` | JobContextService | 无 | 按具体岗位 ID 或标准岗位名读取 |
| `read_career_graph_edges` | CareerGraph Provider | 无 | 白名单边查询；生产失败不回退 JSON |

HTTP API 保持 `stage3-tool-v1` 契约不变。HTTP 匹配工具仍接收完整已验证 Profile；MCP 的
七工具共享 session 流程，匹配/路径/资源只接收 `session_id/user_id`。两种传输得到的
MatchResult/PathResult 已做逐字段一致性测试。

## 6. 调用顺序与样例

同一轮百宝箱对话必须记住并复用相同 `session_id` 和 `user_id`，这样后续工具才能恢复
本轮已经建立的学生画像、目标岗位和分析状态。原前四步形成画像→岗位→匹配→路径主链，
后三个工具按需调用。`trace_id` 可省略由服务端生成；若由平台提供，
每个逻辑调用使用唯一值。

### 6.1 build_student_profile

```json
{
  "session_id": "sess-example-001",
  "user_id": "user-example-001",
  "trace_id": "tool-example-profile-001",
  "resume_text": "匿名候选人完成课程后端项目，使用 Python、SQL 和 Git。",
  "education_level": "本科",
  "major": "计算机科学",
  "graduation_year": 2027,
  "target_job": "后端开发工程师",
  "target_industry": "企业服务/SaaS",
  "skills": ["Python", "SQL/数据库", "Git/版本控制"],
  "projects": ["完成匿名课程后端项目"]
}
```

不要填写 `student_input` JSON 对象；上述字段必须直接放在工具参数顶层。除
`session_id/user_id` 外，至少提供一个非空画像证据字段。

成功状态：`PROFILE_COMPLETED`（即对外 PROFILE_READY 语义）。

### 6.2 analyze_target_job

```json
{
  "session_id": "sess-example-001",
  "user_id": "user-example-001",
  "trace_id": "tool-example-job-001",
  "job_id": 91003,
  "job_title": "后端开发工程师",
  "industry": "企业服务/SaaS",
  "job_description": "匿名岗位描述"
}
```

不要填写 `target_job_input` JSON 对象；`job_title` 及其他岗位字段直接放在工具参数顶层。
`job_id` 可省略；生产模式会用 `job_title` 及可选 `city/industry` 在后端内部尝试解析唯一
PostgreSQL 岗位类型，无法唯一确定时保留原始岗位文本分析，不会任意选择岗位。

成功状态：`JOB_COMPLETED`（即对外 JOB_READY 语义）。

### 6.3 analyze_job_match

```json
{
  "session_id": "sess-example-001",
  "user_id": "user-example-001",
  "trace_id": "tool-example-match-001"
}
```

不得传 `student_profile`、`job_profile`、score 或 gaps。成功状态：`MATCH_COMPLETED`。

### 6.4 generate_career_path

```json
{
  "session_id": "sess-example-001",
  "user_id": "user-example-001",
  "trace_id": "tool-example-path-001"
}
```

不得传 match/path JSON、节点或分数。成功状态：`PATH_COMPLETED`。

### 6.5 generate_and_score_training（合并工具）

生成模式：

```json
{
  "session_id": "sess-example-001",
  "user_id": "user-example-001",
  "trace_id": "tool-example-training-generate-001",
  "training_type": "remote_collaboration"
}
```

评分模式再次调用同名工具：

```json
{
  "session_id": "sess-example-001",
  "user_id": "user-example-001",
  "trace_id": "tool-example-training-score-001",
  "training_id": "training-...",
  "user_answer": "匿名回答文本"
}
```

不要传 score、coverage、criteria 或 ability updates。成功时 `data.mode` 分别为
`generate/score`，且只返回 `training_task` 或 `training_score` 其中之一。

### 6.6 recommend_learning_and_job_resources

```json
{
  "session_id": "sess-example-001",
  "user_id": "user-example-001",
  "trace_id": "tool-example-resources-001"
}
```

不要传 `ability_gaps` 或 `target_job`；服务从已保存匹配和岗位读取上下文。

### 6.7 save_growth_feedback

```json
{
  "session_id": "sess-example-001",
  "user_id": "user-example-001",
  "trace_id": "tool-example-feedback-001",
  "satisfaction": 4,
  "path_rating": 5,
  "training_rating": 4,
  "resource_rating": 4,
  "comments": "希望继续提供结构化训练建议。"
}
```

四个 rating 均必须为整数 1–5；只有 `satisfaction` 必填。成功状态：`FEEDBACK_COMPLETED`。

## 7. 统一结果与前置错误

所有工具返回：`success/error_code/message/missing_fields/retryable/trace_id/session_id/status/data`。
典型前置错误：

| error_code | missing_fields | 处理 |
|---|---|---|
| `SESSION_NOT_FOUND` | `student_profile, job_profile` | 先执行画像/岗位工具 |
| `MATCH_PREREQUISITES_NOT_READY` | 实际缺少的画像或岗位 | 补齐对应工具 |
| `STUDENT_PROFILE_INCOMPLETE` | `student_profile.ability_dimensions` | 补充有证据的能力信息 |
| `MATCH_NOT_COMPLETED` | `match_result` | 先成功调用匹配工具 |
| `SESSION_USER_MISMATCH` | 空 | 使用 session 所属 user_id |
| `MCP_TOOL_TIMEOUT` | 空 | 可按 `retryable=true` 重试新调用 |
| `TRAINING_PREREQUISITES_NOT_READY` | 实际缺少的画像/岗位/匹配 | 先完成主链上下文 |
| `TRAINING_NOT_FOUND` | `training_plan` | 使用同一 session 中已生成的 training_id |
| `MATCH_RESULT_NOT_FOUND` | `match_result` | 先执行匹配再请求资源 |
| `RESOURCE_SERVICE_ERROR` | 空 | 可按 `retryable=true` 使用新 trace 重试 |
| `FEEDBACK_FAILED` | 空 | 检查评分/隐私输入；不假定反馈已保存 |

异常堆栈、数据库地址、API Key 和完整简历不会进入 MCP 结果。Profile/Job 的 LLM 失败可使用
现有验证过的规则 fallback；只有显式 Demo Mode 才可使用 Demo 业务数据，并在结果中标记
`fallback_used=true`。Match/Path 的 Service 结果不被 LLM 覆盖。

业务数据源需要与会话存储分别配置：`POSTGRES_HOST`、`POSTGRES_PORT=5433`、
`POSTGRES_DATABASE=careerpulse_micro`、`POSTGRES_USER`、`POSTGRES_PASSWORD` 供四张业务表
使用；`A02_STATE_DB_PATH` 或 `A02_DATABASE_URL` 只供 StateRepository 三类记录使用。生产环境
不得因 PostgreSQL 不可用而切到 JSON。`A02_DEMO_MODE=true` 只表示允许显式 Demo 数据策略，
每次回退仍需返回并记录来源与回退标记。

## 8. 官方客户端测试

项目测试：

```powershell
python -m unittest tests.test_mcp_server -v
python -m unittest tests.test_tbox_stage3_tools -v
```

第一条测试使用官方 MCP Client，覆盖 `initialize`、`tools/list`、`tools/call`、默认7工具与显式开启后的11工具发现，以及高层工具同 session
串联、Training 两模式、Schema 拒绝、安全业务失败、Bearer、Streamable HTTP、HTTP 结果一致性、
fallback 和日志隐私。

远程人工验证示例：

```python
import asyncio
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

async def main():
    async with httpx2.AsyncClient(
        headers={"Authorization": "Bearer example-local-token-change-me"}
    ) as http:
        transport = streamable_http_client(
            "http://127.0.0.1:8000/mcp", http_client=http
        )
        async with Client(transport, mode="legacy") as client:
            print(client.session.initialize_result)
            print(await client.list_tools())

asyncio.run(main())
```

也可以用 MCP Inspector 连接同一 URL，但不得把真实 Token 保存在截图或共享配置中。

## 9. 公网部署要求

- 使用受信任证书的 HTTPS；百宝箱必须能从其网络访问该 URL。
- 反向代理必须放行 POST/GET/DELETE、Authorization、Content-Type 和 `Mcp-*` Header。
- 代理和平台超时必须大于 `MCP_TOOL_TIMEOUT_SECONDS` 并预留网络时间。
- `MCP_ALLOWED_HOSTS` 设置为真实公共域名（必要时带端口模式），不要使用无边界通配符。
- 若客户端会发送 Origin，`MCP_ALLOWED_ORIGINS` 必须只加入实际可信 Origin。
- 多实例部署继续使用共享 PostgreSQL；当前本地 SQLite 只适合单实例 Demo。
- 上线前必须在 PostgreSQL 16 `careerpulse_micro` 上完成四表 schema/行数、只读 Provider 和生产失败关闭检查；仅通过 Mock/JSON 测试不能视为实库验收。
- 在目标环境重新执行官方远程客户端测试，并检查平台调用账本/AgentRunLog。

## 10. 百宝箱中应填写的逻辑字段

控制台字段名称必须以目标租户实际页面为准。若选择“创建 MCP 服务”，逻辑上填写：

| 逻辑字段 | 值 |
|---|---|
| 服务名称 | `CareerPulse A02` |
| 服务 URL | `https://<public-career-pulse-host>/mcp` |
| 传输 | Streamable HTTP |
| Authentication | Bearer / Authorization Header |
| Header | `Authorization: Bearer <deployment-secret>`（密钥字段） |
| 工具发现 | 默认读取 7 个高层工具；管理/测试环境显式开启后为 11 个 |
| 超时 | 大于 CareerPulse 后端超时；平台上限待现场验证 |

目前尚未验证目标百宝箱租户是否支持远程 Streamable HTTP MCP、其精确字段名、超时、返回
大小、并发和 allowlist 要求。因此 CareerPulse 侧已经具备可填写的服务地址契约，但在公网
HTTPS 部署并完成百宝箱现场验证前，不能声称“已接入/已发布”。
