# M2 审计发现

## 初步结构
- 当前实际挂载路由只有 auth、Career Agent、Platform Tool、TBox；`app/routes/*` 旧 CRUD 路由已脱离聚合器，不能把它们误当成线上入口。
- M1 已提供 `require_authenticated_request` / `require_current_user`，但 Career Agent、Platform Tool、TBox 和 MCP 尚未使用。
- Career Agent 请求模型允许客户端传 `user_id`，当前只与 session 内既有值比较；首次创建 session 时仍会信任客户端值。
- Platform Tool 同样从 payload 读取 `user_id`，调用账本只保存其哈希；现有 session 三元绑定是比赛模式逻辑，不等同 Web 登录身份。
- CareerState 持久化同时支持 SQLite 与 PostgreSQL，包含 `session_id`、`platform_session_id`、`user_id`，是 M2 最小侵入的主要归属边界。
- 核心业务 PostgreSQL 的 `student_profile` 只有 `student_id`，没有正式用户归属；V001 中 training/growth 等表与当前四表业务库并非同一稳定上线边界。
- MCP 高层工具仍要求调用方提供 `user_id`；必须区分“Web Cookie 用户”和“远程 MCP Bearer 主体”，不能把 MCP 固定 API Token 自动等同某个用户。

## 初步方向
- M2A 优先保护当前真实挂载的 Web/Platform/TBox HTTP 入口，并新增 identity 用户到 `student_profile` 的归属表；不复活已脱离的旧 CRUD 路由。
- M2B 再处理 MCP：远程 MCP 没有终端用户登录 Cookie，需要可信主体映射或显式受控兼容模式，不能伪造 current_user。

## 通道信任边界
- `/api/career-agent/*` 是普通 Web API，目前完全匿名，应改为 Cookie Session 强制认证并由后端覆盖 `CareerState.user_id`。
- `/api/tbox/chat` 是浏览器聊天网关，目前 payload 强制携带 `user_id`；应由 Web Session 注入，前端不再决定身份。
- `/api/platform/v1/tools/*` 是独立的 TBox 服务端集成，已有 `A02_TBOX_API_TOKEN` Bearer 认证。它不是浏览器接口，不能依赖 Cookie；其 `user_id` 应视为受信平台主体，但必须与 Web 主体命名空间隔离。
- `/mcp` 使用单个服务级 Bearer Token。该 Token 只能代表一个集成服务，不能安全冒充任意 Web 用户。推荐让 MCP 数据停留在独立 `mcp:` 主体命名空间，禁止读取 `web:` 会话/画像；真正跨端映射需后续引入每用户授权，而不是复用静态 Token。
- 最小安全模型可将持久化 owner 规范化为 `web:<app_user_uuid>`、`platform:<opaque-id>`、`mcp:<opaque-id>`，从而避免不同认证通道中相同字符串碰撞或跨通道接管。

## 前端与画像持久化
- 正式 Vue 前端仍调用 `/api/jobs`、`/api/student/*`、`/api/matching/*`、`/api/reports/*`、`/api/users/*/histories`、`/api/recommendations`，但这些旧路由当前未挂载；因此 M2A 若目标是“上线可用”，不能只保护 Career Agent，还要核查并恢复这组实际前端契约。
- 前端 matching/report 请求仍显式发送 `user_id`（默认 `default`）；M2A 必须删除或忽略这些字段，并由后端 current_user 注入。
- `StudentProfileRepository` 目前按裸 `student_id` 读写，`StudentProfilePersistenceService.get_profile(..., user_id=...)` 只是把调用方提供的字符串写回响应，未校验数据库归属。
- V008 有 `identity.app_user`，但尚无用户到画像的关联表。M2A 应增加加法式 V009 归属表/约束，并让画像创建、读取、更新在同一事务或所有权校验后执行。

## 旧 CRUD 可恢复性结论
- `app/routes/*` 不是“暂时没 include”这么简单：其 service 仍导入已从 `app.db` 删除的 `get_db_conn`、`ensure_business_tables`，并读写 V006 前的 `student_profile(id, parsed_data)` 结构。
- 当前稳定业务库是四表 PostgreSQL 16；旧 matching/report/history 依赖的 `matching_history`、`career_report` 不属于该稳定模型。直接重新挂载会在导入或首个请求时失败，并破坏当前数据库边界。
- 因此本轮不能把复活旧 CRUD 当成小型 M2 修改。M2 应先完成当前受支持 Agent/TBox/MCP 链路的主体隔离；旧 Vue 契约迁移应作为独立业务 API 现代化阶段，或将前端改接当前 Agent 契约。
- 这也意味着 M2 的“数据隔离”主要落在 CareerState、Agent 日志、Tool 调用和 Agent 写入的 student profile 归属，而不是为已废弃表补权限外壳。

## Agent 画像写入边界
- 默认 `CareerOrchestrator` 的 Web `/run` 只运行各 Agent 并保存 CareerState；普通 Web Agent 链路不会把画像写入 `public.student_profile`。
- PostgreSQL 画像创建/恢复目前集中在 `CareerMCPToolService.build_student_profile`，且授权只依赖 `CareerState(user_id, student_profile_id)` 三元绑定。
- 因此 M2A 可先以 Web CareerState/日志所有权为完整边界；M2B 必须额外封住 MCP profile persistence，确保 MCP 主体不能通过猜测 `student_id` 读取其他通道数据。

## CareerState 并发边界
- `StateRepository._upsert_state` 当前在 session 冲突时无条件覆盖 `user_id` 和 `state_data`。仅在 API 层“先读再比较”存在竞态：两个主体可同时观察不存在并争抢同一 session。
- M2 需要在 SQLite/PostgreSQL upsert 的 `ON CONFLICT DO UPDATE ... WHERE` 中执行 owner 条件，并在零行更新时抛出稳定的 `SessionOwnershipConflict`；API 检查只负责早失败，Repository 才是最终写入防线。
- 旧的 `user_id IS NULL` session 可由首个已认证主体领取，以保留升级兼容；一旦有 owner，不允许另一主体覆盖。
- TBox 浏览器路由最适合在进入 `TBoxChatService` 前把 payload 的 user_id 替换为 `web:<current_user.id>`，这样现有 mapper、HMAC 平台 user id 和日志逻辑可复用。

## 测试兼容策略
- 既有 Stage3/TBox 测试大量直接调用 Web 路由，没有 M1 Cookie。生产默认不能为兼容测试而匿名开放。
- `create_app(web_auth_enabled=False)` 只作为测试/受控兼容开关；默认及部署示例保持 `true`。既有服务级单元测试显式关闭，新 M2 测试使用真实 Cookie + CSRF。
- Platform Tool 的 `user_id` 当前可选，但服务身份隔离需要稳定主体；缺省值可退化为平台 session/idempotency 上下文，推荐继续要求平台传逻辑 subject，并在服务端哈希为 external owner。

## M2B 规范化入口
- MCP server 的 11 个工具都在 `server.py` 构建 Pydantic request，随后统一进入 `CareerMCPToolService._begin_call`；最小防御深度是网络 wrapper 先哈希，ToolService 再确认 canonical external owner。
- Platform Tool 只有两个状态写入口 `analyze_job_match`、`generate_career_path`，可在函数开头复制 payload 并覆盖顶层 `user_id`；match payload 内的 `student_profile.user_id` 也必须同步覆盖，避免身份字段在嵌套业务对象中残留客户端值。
