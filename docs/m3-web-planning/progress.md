# M3 实现进度

## 已完成
- 后端新增 `backend/app/api/web_business_api.py`（前缀 `/api/web/v1`，9 条路径、
  10 个操作），
  由 `routers.py` 挂载；`main.py` 注入 `career_state_repository`、
  `career_web_tool_service` 与 `WEB_TOOL_TIMEOUT_SECONDS`。
- `StateRepository.list_states_by_owner(owner_id, limit, offset)` 新增，按 owner
  过滤并返回轻量摘要与总数。
- 写请求体 `extra="forbid"`：伪造 `user_id` 返回 422；跨用户读取/枚举返回 404；
  并发竞态由 Repository 条件 upsert 返回 409 `SESSION_OWNERSHIP_CONFLICT`。
- 只读岗位/图谱查询的审计会话改写到 `system:web-read-auditor` 系统 owner 域。
- 前端 `career.ts` 改为 Workflow 中心；删除 `skipAuth`、客户端 `user_id` 与
  `/users/{userId}/histories` 依赖；M3.2 能力在正式模式禁用，Demo 模式保留离线数据。
- `stores/analysis.ts` 增加 `sessionId`；`DataInput`、`AnalysisBoard`、`Profile`、
  `GrowthPlan`、`TrainingPage` 全部改为 sessionId 中心或明确禁用。
- 新增 `deploy/nginx/careerpulse-web.conf`（SPA + `/api` 代理），`deploy/README.md`
  增加第 12 节：前端构建、Nginx 安装、侧端口灰度与回滚。

## 新增/替代/停用的前端接口
| 新增（`/api/web/v1`） | 替代的旧契约 |
|---|---|
| `POST/GET /workflows`、`GET /workflows/{id}` | `/api/users/{userId}/histories`、`/api/histories/{id}/snapshot` |
| `PUT /workflows/{id}/profile` | `/api/student/upload/profile` |
| `PUT /workflows/{id}/target-job` | `matchingAnalyze` 的岗位选择副作用 |
| `POST /workflows/{id}/match` | `/api/matching/analyze` |
| `POST /workflows/{id}/path` | stage3 本地分步路径接口的浏览器直连 |
| `GET /jobs`、`GET /jobs/{id}`、`GET /jobs/{id}/graph` | `/api/jobs`、`/api/jobs/{id}`、`/api/jobs/{id}/graph` |

停用（正式模式抛“尚未开放”，不请求旧接口）：`/api/student/upload/resume`、
`/api/reports/*`、`/api/recommendations`，以及职场训练适配器的正式模式调用。

## 身份与安全
- 身份：`web_owner_id(已验证会话用户.id)`；浏览器只持有 `sessionId`。
- Cookie：HttpOnly + `SameSite=Lax`，生产 `Secure=true`；CSRF Cookie 与
  `X-CSRF-Token` 必须一致，写操作缺失/伪造返回 403。
- owner：所有 Web 查询按 owner 过滤；跨用户返回 404；系统审计会话不可读。

## 测试与验证
- 后端：`python -m pytest -q --ignore=tests/test_micro_database_adaptation.py`
  → **326 passed, 167 subtests passed**（含 8 个 M3 Web 业务测试：匿名 401、
  CSRF 缺失/伪造 403、双用户 404 与不可枚举、伪造 `user_id` 422、Repository
  跨 owner 竞态拒绝、owner 范围分页、完整 happy path、Demo/真实隔离）。
- 前端：`npm run typecheck` 通过；`npm run build` 通过（仅有既有 chunk 体积提示）。
- 修复：新增 Web 工具实例曾改绑 PathAgent 图数据源导致 5 个既有测试失败，
  已通过 `bind_runtime_graph_provider` 开关 + 路径步骤惰性绑定解决。

## 迁移与运行影响
- V008（M1 身份表）、V009（用户—画像归属表）脚本均已生成但**未执行**；本轮未连接
  线上库、未执行任何迁移、未改动 systemd/服务。
- `student_profile` 的 PostgreSQL 归属写入依赖 V009，属于 M3.2 前置条件。
- 本轮全部改动保持未提交状态。

## 环境与回归说明
- 本机 `POSTGRES_*` 指向 localhost:5432（PostgreSQL 16.14，`careerpulse_micro`），
  但后端不加载 `.env`，回归使用 `app.config` 默认端口 5433（无服务）。stage3 路径
  测试因此只在“PathAgent 未被改绑到生产图数据源”时才能通过，这是既有行为。
- 回归统一把 `TEMP`/`TMP` 指向仓库 `.runtime/tests/tmp`，避免本机临时目录权限问题。

## M3.2 待办
- 简历文件解析、报告生成/润色/导出、学习资源推荐、职场训练、Feedback 闭环。
- V009 迁移执行与画像归属写入联调。
