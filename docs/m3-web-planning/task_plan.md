# CareerPulse M3 Web 业务 API 与前端闭环实现计划

## 目标
在不改写匹配/路径算法、不复活失效旧 CRUD、不操作现网的前提下，把真实注册用户的浏览器
业务闭环收敛到一组受会话保护的 Workflow API：注册→登录→填写画像→查询/选择岗位→
人岗匹配→职业路径→查看自己的历史→退出。

## 阶段
- [x] 阶段 1：审计现有前端契约、ToolService/CareerOrchestrator 签名、StateRepository 与 M1/M2 身份边界
- [x] 阶段 2：设计 `/api/web/v1` 契约与前端映射，冻结新增/替代/禁用清单
- [x] 阶段 3：实现后端 Workflow/Job API 与 owner 范围查询
- [x] 阶段 4：补后端隔离、CSRF、伪造 `user_id`、Repository 竞态测试
- [x] 阶段 5：前端改为 sessionId 中心，移除客户端身份与死契约依赖
- [x] 阶段 6：隐藏/禁用 M3.2 未开放能力，保持 Demo 可用
- [x] 阶段 7：补 happy path、Demo/真实隔离测试并做全量回归
- [x] 阶段 8：前端类型检查、生产构建、Git 差异审计与文档更新

## 范围约束
- 不执行迁移，不连接或修改线上 PostgreSQL，不重启或替换当前比赛评审服务。
- 不重新挂载 `/api/jobs`、`/api/matching/*`、`/api/student/upload/*`、
  `/api/reports/*`、`/api/users/{userId}/histories`、`/api/histories/{id}/snapshot`、
  `/api/recommendations`，不恢复已删除的 `app.db` CRUD 助手。
- 浏览器不提交也不决定 `user_id`；Web 身份只来自已验证 HttpOnly Session。
- MCP Bearer Token 不下发前端。
- Match 分数、差距分析、路径分值必须由 Service 计算，不由 LLM 生成。
- 不覆盖用户已有未提交改动，不自动提交 Git。

## 实施决策
- 新增 `backend/app/api/web_business_api.py`，前缀 `/api/web/v1`，共 9 条路径、
  10 个操作：
  `POST/GET /workflows`、`GET /workflows/{id}`、`PUT /workflows/{id}/profile`、
  `PUT /workflows/{id}/target-job`、`POST /workflows/{id}/match`、
  `POST /workflows/{id}/path`、`GET /jobs`、`GET /jobs/{id}`、`GET /jobs/{id}/graph`。
- 写接口请求体使用 `extra="forbid"`：伪造 `user_id` 在校验层返回 422，不可能改变归属。
- 校验顺序固定：CSRF（403）→ 归属（404）→ 前置条件（409）→ 业务执行。
- 归属以 `StateRepository.list_states_by_owner` + 条件 upsert 为最终防线，API 检查只是早失败。
- 工具调用统一走 `_run_tool`，受 `WEB_TOOL_TIMEOUT_SECONDS`（默认 25s，上限 60s）约束，
  超时返回 504、底层不可用返回 503；`match`/`path` 满足状态时幂等重放。
- 只读岗位/图谱查询的 Tool 审计记录落在 `system:web-read-auditor` 系统 owner 域，
  可审计、用户不可读、也不污染用户历史列表。
- 前端 `career.ts` 改为 Workflow 中心：`analyzeWorkflowMatch(sessionId)` 取代
  `matchingAnalyze`，`fetchWorkflowHistories/fetchWorkflowSnapshot` 取代
  `fetchUserHistories/fetchHistorySnapshot`，删除 `skipAuth` 与所有客户端 `user_id`。
- M3.2 能力（简历解析、报告生成/润色/导出、学习资源推荐、职场训练）在正式模式直接
  禁用并提示“功能暂未开放”，不返回模拟成功；Demo 模式继续使用纯浏览器离线数据。
- `CareerMCPToolService` 增加 `bind_runtime_graph_provider` 开关：只有拥有平台/MCP
  策略的服务实例在构造时改绑 PathAgent 图数据源；Web 服务在真正执行路径步骤时才
  调用 `configure_runtime_graph_provider()`，避免第二个实例收紧其他调用方的数据源。

## 遗留与后续（M3.2）
- 简历文件解析、报告生成/润色/导出、学习资源推荐、职场训练、Feedback。
- `student_profile` 的 PostgreSQL 归属写入仍依赖 V009 迁移（未执行）。
