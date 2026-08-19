# D3 接入 CareerState、AgentRunLog、API

阶段3第7步已完成：将 CareerOrchestrator 的 Agent 链路 API 从独立 FastAPI 应用挂载到主路由，补齐 final_report 中缺失的 career_roadmap 字段。AgentRunLog（agent_logs）随 API 挂载自动暴露。旧路由全部保留，零影响。未涉及数据库持久化、平台工具注册、前端修改。

### 1. 修改文件

| 文件                                                | 变更           | 说明                                               |
| ------------------------------------------------- | ------------ | ------------------------------------------------ |
| `backend/app/routers.py`                          | +3 行         | 导入并挂载 `career_agent_router` 和 `agent_log_router` |
| `backend/app/orchestrator/career_orchestrator.py` | +1 行 (65→66) | `_build_final_report()` 返回值增加 `career_roadmap`   |

### 2. 关键设计

#### API 架构变更

```
主 FastAPI 应用（app/main.py → app/routers.py）
  旧业务路由（保守保留）：
    jobs_router       → GET /jobs, /jobs/{id}/profile, /jobs/{id}/graph
    students_router   → POST /student/upload/resume, /student/upload/profile
    matching_router   → POST /matching/analyze
    reports_router    → POST /reports/generate 等
    history_router    → GET /users/{id}/histories 等
    recommendations_router → GET /recommendations

  + 新 Agent 链路 API（新增挂载）：
    career_agent_router → POST /api/career-agent/run
                        → GET  /api/career-agent/session/{session_id}
    agent_log_router    → GET  /api/agent/logs/{session_id}
```

新 API 前缀 `/api/career-agent/` 和 `/api/agent/` 与所有旧路由（`/jobs`、`/matching`、`/reports` 等）无路径冲突，两个路由体系在主应用中共存。

#### final_report 补齐

`final_report` 是 CareerOrchestrator 在 6 个 Agent 全部运行完毕后自动组装的执行摘要。此前因 D5 阶段将 CareerOrchestrator 视为冻结代码，新增的 `career_roadmap` 未纳入。本次在 `_build_final_report()` 返回值中补入 `"career_roadmap": state.career_roadmap`，使 final_report 完整覆盖所有 Agent 产出。

#### AgentRunLog 接入

`AgentLog` 类定义在 `career_state.py` 中，由 `BaseAgent.run()` 在每个 Agent 执行完成后自动创建并 append 到 `CareerState.agent_logs`（每个 Agent 一条，含 status/duration/fallback/error 等字段）。本次通过挂载 `GET /api/agent/logs/{session_id}` 端点将其暴露为可查询的 API 数据，无需额外代码。

### 3. 验证结果

| #   | 验收项                                                                | 结果                          |
| --- | ------------------------------------------------------------------ | --------------------------- |
| 1   | `compileall` 编译通过                                                  | ✅                           |
| 2   | uvicorn 启动正常                                                       | ✅                           |
| 3   | `POST /api/career-agent/run` → 200，完整 CareerState JSON             | ✅（7 个结果字段 + 6 条 agent_logs） |
| 4   | `GET /api/career-agent/session/{id}` → 200，career_roadmap non-null | ✅                           |
| 5   | `GET /api/agent/logs/{id}` → 200，返回 6 条日志数组                        | ✅                           |
| 6   | `final_report` 含 `career_roadmap` 且值非 None                         | ✅                           |
| 7   | 旧路由 `GET /jobs` 仍正常返回 200                                          | ✅                           |
| 8   | 不存在 session 返回 404                                                 | ✅                           |

总计 17 项检查全部通过（含字段非空、Agent 状态、日志条数等细分断言）。

### 4. API 路径概览

| 方法   | 路径                                       | 说明                                                                 |
| ---- | ---------------------------------------- | ------------------------------------------------------------------ |
| POST | `/api/career-agent/run`                  | 运行全部 6 个 Agent（Profile → Job → Match → Path → Training → Feedback） |
| GET  | `/api/career-agent/session/{session_id}` | 获取完整运行结果（CareerState）                                              |
| GET  | `/api/agent/logs/{session_id}`           | 获取 Agent 执行日志数组                                                    |

输入格式（POST /api/career-agent/run）：

```json
{
  "session_id": "...",
  "platform_session_id": null,
  "user_id": null,
  "student_input": { "basic_info": {...}, ... },
  "target_job_input": { "job_id": ..., "title": "...", ... }
}
```

输出：CareerState Pydantic model 的全量 JSON 序列化，含 student_profile / job_profile / match_result / path_plan / learning_plan / career_roadmap / final_report / agent_logs 等字段。

### 5. 兼容性说明

- **旧路由**：全部保留，代码零修改，路径不重叠，功能不受影响。
- **旧 Service**：仍使用旧 matching_service / report_service / history_service，未替换。
- **独立 FastAPI app**：`career_agent_api.py` 中自有的独立 app 保留不变，不干扰主应用。
- **前端**：未修改，仍使用旧路由调用旧接口；新 API 可作为未来切换到 Agent 链路的候选入口。
- **数据库**：本次不涉及持久化（符合 D3 stage1.md "持久化用内存，暂缓迁移" 的约定）。

### 6. 未解决问题

| 问题                 | 说明                                                                  |
| ------------------ | ------------------------------------------------------------------- |
| 服务重启后 session 数据丢失 | CareerState 和 agent_logs 存储在内存中（CareerOrchestrator._sessions），属已知设计 |
| 旧路由仍使用旧 service    | 需后续阶段统一替换为 Agent 链路结果，本次保守保留                                        |
| 平台工具注册             | 属于阶段 5（百宝箱正式集成），本次仅挂载 HTTP API                                      |
| Agent 链路 API 契约文档  | 未写入 `docs/a02/04_API_CONTRACTS.md`，待后续统一更新                          |

# 


