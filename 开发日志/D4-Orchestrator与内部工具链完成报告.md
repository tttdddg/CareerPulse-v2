# 《D4-Orchestrator与内部工具链完成报告》

## 1. 完成结论

D4-2.5 已完成。CareerPulse 内部已经具备三个冻结名称、四个真实业务动作：

1. `generate_and_score_training` — 生成模式
2. `generate_and_score_training` — 评分模式
3. `recommend_learning_and_job_resources`
4. `save_growth_feedback`

这些能力位于阶段3既有的 transport-neutral `CareerMCPToolService` 应用层，复用 CareerOrchestrator、CareerState、StateRepository、trace 幂等、安全调用账本、超时与错误 envelope。它们尚未通过 MCP decorator、HTTP router 或百宝箱配置注册。

真实内部路径只调用 TrainingAgent、FeedbackAgent、TrainingService、ResourceService、FeedbackService；不会调用 `mock_tools.py` 的旧训练长度评分或 `feedback_saved=false` 占位逻辑。

## 2. 百宝箱未来只需调用的现成能力

### 2.1 生成训练题

内部方法：

```text
CareerMCPToolService.generate_and_score_training(request)
```

调用方输入：

```json
{
  "session_id": "string",
  "user_id": "string",
  "trace_id": "string | null",
  "training_type": "remote_collaboration | ai_office_task | cross_role_communication"
}
```

系统自动从 State 补齐：

- `match_result.skill_gaps[].dimension` → 有序 ability gaps
- 已有 student profile / job profile 前置
- target job 上下文

真实链路：

```text
内部工具 -> CareerOrchestrator.run_stage(stage_input)
         -> TrainingAgent
         -> TrainingService.generate
         -> state.training_plan
```

返回 `data.mode=generate` 和经过 Schema 验证的 `data.training_task`。缺 match/profile/job 时返回安全失败，不生成假题。

### 2.2 提交答案并评分

内部方法与生成相同，调用方只需提交：

```json
{
  "session_id": "string",
  "user_id": "string",
  "trace_id": "string | null",
  "training_id": "string",
  "user_answer": "string"
}
```

系统自动从 State 补齐：

- training ID 对应的真实 TrainingTask
- TrainingTask.type
- evaluation criteria
- target abilities
- 当前 match gaps 与 target job（供已接入的资源结果使用）

真实链路：

```text
内部工具 -> CareerOrchestrator 临时注入回答
         -> TrainingAgent 五档语义判断
         -> TrainingService.score
         -> state.training_plan.latest_score
```

所有 dimension scores、total score、ability updates 仍只来自 TrainingService。LLM 失败时使用 TrainingService 既有 fallback；自然语言反馈失败不影响评分。返回 `data.mode=score` 和 `data.training_score`。

### 2.3 推荐资源

内部方法：

```text
CareerMCPToolService.recommend_learning_and_job_resources(request)
```

调用方输入：

```json
{
  "session_id": "string",
  "user_id": "string",
  "trace_id": "string | null"
}
```

调用方不能传入或覆盖 ability gaps / target job。系统自动从 State 提取：

- `match_result.skill_gaps[].dimension`，保持原顺序
- `job_profile.title`

真实链路：

```text
内部工具 -> CareerState 投影上下文
         -> ResourceService.recommend_resources
         -> state.resource_result
```

没有新建 ResourceAgent，也不调用 LLM。完整返回 learning resources、job resources、certificate suggestions 和 data quality flags。

### 2.4 保存反馈与成长快照

内部方法：

```text
CareerMCPToolService.save_growth_feedback(request)
```

调用方输入：

```json
{
  "session_id": "string",
  "user_id": "string",
  "trace_id": "string | null",
  "satisfaction": "int 1-5",
  "path_rating": "int 1-5 | null",
  "training_rating": "int 1-5 | null",
  "resource_rating": "int 1-5 | null",
  "comments": "string | null"
}
```

系统自动从 State 补齐：

- 最近真实 skill gaps
- 最近训练 task 的 target abilities
- 当前 abilities
- 最近 match overall score
- completed trainings / phases：当前没有可靠统计，继续使用冻结 Service 允许的 `0 / 0`

真实链路：

```text
内部工具 -> CareerOrchestrator.run_stage(stage_input)
         -> FeedbackAgent
         -> FeedbackService.save_feedback
         -> state.feedback_result / growth_snapshot
```

返回完整 FeedbackService 结果与自然语言确认句；LLM 说明失败不影响真实保存。

## 3. 统一返回结构

四个动作沿用阶段3成熟 envelope：

```json
{
  "success": true,
  "error_code": null,
  "message": "string",
  "missing_fields": [],
  "retryable": false,
  "trace_id": "string",
  "session_id": "string",
  "status": "CareerState status",
  "data": "动作对应的严格 Schema"
}
```

失败时 `success=false`、`data=null`，返回稳定 error code、缺失字段和 retryable，不返回 Python 异常正文、用户回答或 comments。

输入 Schema 使用 `extra=forbid`：非法 training type、非法 rating、缺 training ID、空答案以及调用方试图覆盖 ability gaps 等情况都会在进入 Orchestrator 前被拒绝。

## 4. Orchestrator 临时输入机制

`CareerOrchestrator.run_stage()` 新增可选 `stage_input`，仅允许 TrainingAgent 和 FeedbackAgent 使用：

1. 深拷贝并临时注入 `student_input.training` 或 `student_input.feedback`；
2. Agent 在本次执行内读取；
3. 无论成功、失败或超时，都在 finally 中恢复原 student input；
4. 恢复后才持久化 CareerState 和安全 AgentLog。

因此 user answer 和 comments 不会因为内部工具调用而永久写入 CareerState。调用账本仅保留请求 SHA-256 指纹、结果字段指针和安全错误类型，不保存原文。

## 5. Trace、幂等与 session 隔离

- 每个调用可传 trace ID；未传时服务端生成。
- 同一工具、同一 trace、同一参数会回放已持久化结果，不重复执行 Agent。
- 同一 trace 被用于不同参数时返回 `TRACE_ID_CONFLICT`。
- session ID 与 user ID 必须匹配已有 State；不允许跨用户读取。
- 训练 task 必须存在于当前 session；另一个 session 即使提交相同 training ID 也不能评分。
- 资源调用没有 ResourceAgent，账本的 `agent_run_key` 为 null；这是诚实的 Tool→ResourceService 调用记录。

## 6. 真实链路与 mock 链路区分

### 真实内部链路

- 入口：`CareerMCPToolService` 的三个阶段4方法。
- 数据：持久化 CareerState 中的真实 Profile/Match/Path/Training 上下文。
- 计算：冻结 Service。
- LLM：仅 TrainingAgent 语义五档判断和可选自然语言说明；测试使用离线 mock。
- 结果：真实写入 `training_plan`、`resource_result`、`feedback_result`。

### 显式 mock/demo 链路

- 入口：`call_mock_tool()` / `MOCK_TOOL_REGISTRY`。
- 输出带 `demo_mode=true` 与 demo notice。
- 旧 mock 训练评分和 `feedback_saved=false` 仅保留给明确的历史 demo/test。
- 真实 API、MCP 与本次内部工具服务均不引用 `call_mock_tool()`。

本步骤没有删除或修改 mock_tools，避免破坏阶段3必要 demo；测试已证明同名真实反馈返回 `feedback_saved=true`，与显式 mock 清晰区分。

## 7. 修改文件

- `backend/app/orchestrator/career_orchestrator.py`
  - 为 `run_stage` 增加安全的临时 stage input 注入与恢复。
- `backend/app/mcp/tool_service.py`
  - 新增三个冻结名称对应的未注册阶段4方法。
  - 复用 session、identity、trace、幂等、超时、错误与调用账本逻辑。
  - 资源动作直接消费冻结 ResourceService，不创建 ResourceAgent。
- `backend/app/schemas/internal_tool_schema.py`
  - 新增阶段4内部请求、数据和结果 Schema。
- `backend/tests/test_stage4_internal_tools.py`
  - 新增 14 项完全离线内部工具链测试。
- `task_plan.md`、`findings.md`、`progress.md`
  - 记录核查、架构裁决、实现和测试证据。
- `开发日志/D4-Orchestrator与内部工具链完成报告.md`
  - 本报告。

## 8. 测试结果

### 8.1 新增内部工具测试

- `backend/tests/test_stage4_internal_tools.py`
- 结果：`14 passed`

覆盖：

- generate training
- score training
- recommend resources
- save feedback / growth snapshot
- 缺 match result
- 缺当前 training / 非法 training ID
- 非法 training type / rating /上下文覆盖字段
- user answer 隐私
- comments 隐私
- LLM mock failure
- ResourceService error
- session 隔离
- trace 幂等回放
- 真实链路与旧 mock 区分

### 8.2 阶段3工具无回归

- MCP server + HTTP stage3 tools + stage3 E2E：`21 passed`
- MCP `tools/list` 仍严格只有：
  - `build_student_profile`
  - `analyze_target_job`
  - `analyze_job_match`
  - `generate_career_path`

### 8.3 冻结 Service 回归

- TrainingService + ResourceService + FeedbackService：`61 passed / 14 subtests`

### 8.4 全量回归

- 完整结果：`236 passed / 96 subtests，5 failed`
- 5 项失败仍全部来自既有 ProfileAgent prompt 文件缺失，与 D4-2.1～D4-2.4 基线一致。
- 排除该既有阻塞文件后的适用全量：`231 passed / 96 subtests`。
- `python -m compileall -q app tests`：通过。
- `git diff --check`：通过，仅有现有 LF/CRLF 提示。

## 9. 明确未修改

- TrainingService / ResourceService / FeedbackService
- `backend/app/mcp/server.py`
- 阶段3 CareerAgent API / Platform Tool API
- `backend/app/tools/mock_tools.py`
- 数据库 Schema 与 migration
- 百宝箱配置与系统 Prompt

## 10. 尚未进行的平台操作

本步骤没有进行：

- 百宝箱阶段4工具注册
- MCP `tools/list` 阶段4扩展
- HTTP 平台路由新增
- ngrok
- 公网 VM
- 正式域名
- 线上部署
- 百宝箱配置修改

下一阶段只需在确认正式平台契约后，为上述三个内部方法增加薄 MCP/HTTP adapter；Agent、Service、State、Orchestrator 和内部业务调用链无需重新实现。

## 11. 已知边界

- 旧工具目录中的 student ID / job ID 输入是历史规划版本；本次未注册内部 Schema 已对齐当前 session/user + State 模式。正式平台注册前仍需由技术负责人冻结最终公开 Schema。
- CareerState 当前保存当前计划/最近结果，不是完整训练历史库；较早训练被新计划替换后，相关旧 trace 可能无法从 State 回放完整结果。
- completed training / phase 仍没有可靠统计来源，本步骤没有用计划数量虚构完成次数。
- resource result 的 job resources 当前遵循冻结 ResourceService，返回 unavailable flag。
