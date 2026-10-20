# M3 审计发现

## 前端契约
- 正式 Vue 前端仍调用未挂载的旧路由：`/api/jobs`、`/api/matching/analyze`、
  `/api/student/upload/*`、`/api/users/{userId}/histories`、
  `/api/histories/{id}/snapshot`、`/api/reports/*`、`/api/recommendations`。
- matching/report 请求显式发送客户端 `user_id`（`payload.userId ?? 'default'`），
  培训模块的 payload 也带 `userId`（适配器未使用）。
- 请求层存在 `skipAuth` 开关，业务调用可以跳过认证，属于不合理的授权旁路。
- 前端状态同时依赖 `studentId` / `jobId` / `reportId`，与“浏览器只持有 sessionId”的
  目标冲突。

## 后端能力
- `ToolService` 已具备 `build_student_profile`、`analyze_target_job`、
  `analyze_job_match`、`generate_career_path`、`search_database_jobs`、
  `read_job_context`、`read_career_graph_edges`，可直接复用，不需要新算法。
- `CareerState` 是唯一归属边界（`session_id` 主键、`user_id` owner、条件 upsert）。
- 只读数据库工具同样会为每次调用持久化一条 CareerState 审计记录（MCP 契约）。
- `PathService` 的默认 Provider 是 `JsonCareerGraphProvider(demo_mode=True)`；
  只有 `CareerMCPToolService` 构造时会把生产数据源策略改绑到共享的 PathAgent 上。

## 关键陷阱
- `CareerMCPToolService.__init__` 会遍历 `orchestrator.agents` 并调用
  `PathAgent.configure_graph_provider(...)`，收紧为“PostgreSQL、禁止 Demo 回退”。
  在 `create_app` 里新增一个服务实例就会改变既有运行链路，曾导致 5 个
  stage3/TBox/MCP 测试失败（`PostgresCareerGraphProviderError`）。
- `PathRequest.student_profile.abilities` 至少需要 3 项，否则路径步骤直接
  `ValidationError`；画像表单必须收集足够的能力标签。
- 职业图谱节点 `job_title` 与岗位画像 `normalized_title` 必须对应（例如
  `后端开发工程师` → `backend-engineer`），否则 `no_reachable_path`。
- 后端不加载 `.env`（无 `load_dotenv`），测试使用 `app.config` 默认值
  （`POSTGRES_PORT=5433`），本地 5432/5434 均不可用于回归判断。
- `backend/app/db.py` 仍保留 `business_connection`，但 `ensure_business_tables`
  已删除，导致 `tests/test_micro_database_adaptation.py` 收集失败（用户既有未跟踪
  文件，回归时用 `--ignore` 跳过，未修改）。

## 隔离要求
- Web owner 固定 `web:<app_user.id>`，只能由已验证会话生成。
- 跨用户读取与枚举统一 404，不泄露会话是否存在。
- Demo 数据只存在于浏览器；服务端 Demo 会话不得进入正式用户历史。
- MCP Bearer Token 不得出现在前端代码、构建产物或截图中。
