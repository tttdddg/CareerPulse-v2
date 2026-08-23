# 百宝箱阶段3最小接入说明

## 1. 接入范围

本版本只发布阶段3的两个业务工具：

- `analyze_job_match`：由 MatchAgent 调用 MatchService 计算匹配度和能力缺口。
- `generate_career_path`：读取同一 CareerPulse session 中已保存的匹配结果，由
  PathAgent 调用 PathService 生成、评分并保存 3 年/5 年路径。

状态与结果可通过两个只读查询 operation 获取。不发布画像、趋势、训练、资源、反馈或
任何阶段4工具；不提供数据库连接、SQL 或表级访问。

百宝箱负责识别意图、收集固定字段、调用工具、解释结构化结果并引导用户查看结果。
CareerPulse 负责所有匹配/缺口/路径计算、评分、状态和运行日志。百宝箱不得生成或上传
分数覆盖 CareerPulse 结果。

## 2. 部署前配置

1. 应用 V001→V004 数据库迁移。生产环境运行
   `python scripts/init_a02_data.py --apply` 前必须配置真实 `A02_DATABASE_URL`；本地 Demo
   可使用 `A02_STATE_DB_PATH` 或默认 SQLite。
2. 生成高强度服务端 token，分别以密钥方式配置到 CareerPulse 和百宝箱。不要写入仓库、
   Prompt、截图或日志。
3. 配置 CareerPulse：

```dotenv
A02_TBOX_API_TOKEN=<deployment-secret>
A02_TBOX_TOOL_TIMEOUT_SECONDS=25
```

超时允许范围是 `(0, 60]` 秒。CareerPulse 在超时后取消 Agent 调用、写入
`timed_out/-6`，并生成不含原始请求的失败 AgentRunLog。平台自身超时应大于 CareerPulse
值并预留网络时间；平台允许的上限需在目标租户控制台实测，当前未验证。

## 3. OpenAPI 与平台配置字段

启动命令（从 `backend/` 目录）：

```powershell
$env:A02_DEMO_MODE = "true"
$env:A02_TBOX_API_TOKEN = "<deployment-secret>"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

OpenAPI 地址：`https://<career-pulse-host>/openapi.json`。

若百宝箱支持 OpenAPI 导入，只选择下列 4 个 operation；不要导入旧 Mock 或阶段4端点：

| operationId | Method | Path | 用途 |
|---|---|---|---|
| `analyze_job_match` | POST | `/api/platform/v1/tools/analyze_job_match` | 匹配/缺口计算 |
| `generate_career_path` | POST | `/api/platform/v1/tools/generate_career_path` | 路径生成/评分 |
| `get_stage3_tool_call_status` | GET | `/api/platform/v1/tools/calls/{tool_call_id}/status` | 状态查询 |
| `get_stage3_tool_call_result` | GET | `/api/platform/v1/tools/calls/{tool_call_id}/result` | 结果重取 |

若需手工配置 HTTP 工具，填写以下逻辑字段。百宝箱控制台的实际字段名称以目标租户为准：

| 逻辑字段 | CareerPulse 固定值 |
|---|---|
| 工具名称 | 对应 operationId |
| Base URL | `https://<career-pulse-host>`（必须可从百宝箱网络访问） |
| Method/Path | 上表固定值 |
| Content-Type | `application/json` |
| Authentication | HTTP Bearer |
| Authorization value | `Bearer <deployment-secret>`（密钥字段） |
| Request schema | OpenAPI 对应 requestBody schema，禁止自由字段 |
| Response schema | OpenAPI 对应 200/错误 response schema |
| Backend timeout | 25 秒（可用环境变量调整，最大 60） |
| Platform timeout | 必须大于 backend timeout；具体上限待控制台实测 |
| Retry | 仅 `retryable=true`；重试必须复用原 `idempotency_key` |
| Streaming | 关闭；工具返回 JSON |

平台的响应大小、并发/频率限制、精确超时上限和 OpenAPI 导入入口无法从当前公开官方资料
确认，必须在目标百宝箱租户完成现场验证后再填写 `10_TBOX_REQUIREMENTS.md`。在验证前不得
声称已配置或已发布。

## 4. 调用规则

- 每个 POST 请求必须包含 `schema_version=stage3-tool-v1` 和调用方生成的
  `idempotency_key`（8–128 字符，仅字母、数字、点、下划线、冒号、连字符）。
- 同一逻辑调用重试必须复用幂等键。相同工具+幂等键+相同 payload 返回原结果；不同
  payload 返回 HTTP 409 / `-8 IDEMPOTENCY_KEY_CONFLICT`。
- `generate_career_path` 只能在同一 `session_id` 的 `analyze_job_match` 成功后调用。
- 路径请求没有 match/path 结果字段。任何额外字段都会被 Pydantic 拒绝为 HTTP 422 / `-2`。
- `request_id` 即 `tool_call_id`，可用于 status/result 查询。查询也必须携带 Bearer token。
- 不要把工具的 `overall_score` 解释成录用概率；路径分只用于已生成候选路径的确定性排序。

## 5. 错误、重试与幂等策略

| code | HTTP | 含义 | 是否重试 |
|---:|---:|---|---|
| 0 | 200 | 成功 | 否 |
| -1 | 500/503 | 内部执行或服务配置错误 | 看 `retryable` |
| -2 | 422 | 固定请求 Schema 不匹配 | 否，先补字段 |
| -3 | 404 | session/tool call 不存在 | 否，先执行前置工具 |
| -4 | — | 保留的 LLM fallback 错误码；本次工具不依赖其生成分数 | — |
| -5 | 503 | 状态或工具日志数据库不可用 | 是，复用幂等键 |
| -6 | 504 | CareerPulse 工具超时 | 是；确认状态后复用幂等键 |
| -7 | 401 | Bearer 鉴权失败 | 否，修正密钥 |
| -8 | 409 | 幂等/payload/并发冲突 | 按错误类型处理 |
| -9 | 409 | session 身份、前置条件或结果状态不满足 | 否，先完成前置步骤 |

错误响应不返回 Python 异常正文、数据库信息、请求正文或 token。

## 6. 日志与隐私

`platform_tool_calls` 只记录请求 SHA-256 指纹、哈希 user_id、状态、耗时、安全错误类型、
CareerState 结果字段指针和 `agent_run_key`。不记录原始 StudentProfile/JobProfile 请求副本、
证据文本、完整工具结果、完整简历、明文 user_id 或 token。`agent_run_key` 对应：

- `session_id:MatchAgent` → AgentRunLog / MatchService ToolCallLog
- `session_id:PathAgent` → AgentRunLog / PathService ToolCallLog

完整结构化结果保存在 CareerState，只通过鉴权后的 result endpoint 读取；数据库不直接
提供给平台。

## 7. Mock 与验收

完整匿名 Mock 请求和实际接口响应见
`docs/a02/examples/tbox_stage3_match_mock.json`。接口测试：

```powershell
python -m unittest tests.test_tbox_stage3_tools -v
```

该测试覆盖成功/失败、固定字段、分数覆盖拒绝、Bearer、超时、幂等、状态/结果查询、
AgentRunLog 关联、隐私、跨应用实例持久化和 OpenAPI operation/security。
