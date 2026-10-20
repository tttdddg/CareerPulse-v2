# 当前代码认证与部署复核发现

## 初始状态
- 根目录规划文件属于此前 PPT 任务，不能复用或覆盖。
- 当前 `git diff --stat` 只显示 `backend/.env` 有 9 行变化；该文件被 Git 跟踪且属于敏感配置，审计中不读取其值。
- 现有部署基线为 Ubuntu 22.04、systemd 单 worker、Uvicorn `127.0.0.1:8000`、Nginx HTTPS 反代。

## 当前分支与前端认证
- 当前分支为 `dyy`，HEAD 为 `aa6b6103 merge main and restore dyy changes`。
- 除 `backend/.env` 外，已跟踪业务代码没有未提交修改；但仓库新增了数据库 Repository/Tool/Schema 和更多数据库测试，说明必须以当前 HEAD 重新判断。
- 前端认证仍是本地模拟：`user.ts` 将 token/profile 存入 `localStorage`，路由只判断非空 token；`Login.vue` 仍使用固定账号、固定 token 和浏览器模拟短信验证码。
- 生产前端仍配置 `VITE_API_BASE_URL=/api`，而 Vite 仅在开发代理中删除 `/api` 前缀；生产路径兼容性仍需结合当前后端路由和 Nginx 复核。

## 关键架构变化
- 当前 `app.routers` 已明确卸载全部 legacy REST 路由；正式支持面只有 `/api/career-agent/*`、`/api/agent/*`、`/api/platform/v1/tools/*`、`/api/tbox/*` 和可选 `/mcp`。
- `backend/app/routes/*` 仍保留为迁移参考，但不会挂载到 FastAPI；因此前端当前请求的 `/jobs`、`/student/*`、`/matching/*`、`/reports/*`、`/users/*/histories` 在现部署后端上不会工作。
- 当前已部署后端本质上是 A02 Agent/Tool/TBox/MCP 核心服务，而不是面向 Vue 终端用户的 Web API。这支持了用户所说的“后端单独有用”。
- 平台 Tool 有独立静态 Bearer 鉴权，但 `career-agent` 的 session/result/log 和 `/api/tbox/chat` 没有终端用户认证；其中 `user_id` 仍是请求字段，不是登录凭证。
- 因此，前两轮提出“完整克隆一套 Green 后端”并非首选；更合适的候选是新增独立 Web BFF/Identity 服务，保留现有核心后端完全不动，由 BFF 持有服务端凭据并调用核心后端。

## 前端与核心后端的实际断点
- `front/src/api/modules/career.ts` 只调用未挂载的 legacy REST 路由；生产模式下岗位、上传、匹配、报告、历史、推荐均没有可用后端入口。
- `front/src/api/modules/training.ts` 已显式声明非 Demo 模式训练 HTTP API 不可用。
- README 规定的目标链路是 `Vue -> CareerPulse FastAPI -> TBox -> MCP -> CareerPulse FastAPI`，Vue 不应保存百宝箱密钥；因此需要服务端 BFF/网关层，而不是让 Vue 直接调用平台 Tool/MCP。
- README 同时要求 Vue 与百宝箱使用同一套正式后端和业务数据，禁止维护两套独立业务逻辑。因此此前建议 Green 使用独立业务数据库长期运行会造成双数据源，不符合项目现行架构约束。
- `19_DATABASE_ACCESS_CONTRACTS.md` 已冻结 PostgreSQL 四表为事实真源，StateRepository 只保存会话/日志；`student_profile` 当前没有 `user_id`，文档明确要求正式开放首次写入前补身份绑定和同事务幂等回执。
- 当前更合理的目标是：现有 8000 核心服务保持不动；新增 8001 Web BFF/Identity 服务作为浏览器边界，但它调用/复用同一套核心能力和业务事实源，不复制 Match/Path/Training 业务逻辑，也不建立长期独立业务库。

## 可执行接口与验证
- 当前 OpenAPI 只有 11 条路径：Agent run/prepare/match/path/session/log、两个平台工具及其状态/结果、TBox chat；没有 auth/jobs/upload/report/history/training Web API。
- 生产依赖中没有 Argon2/bcrypt、JWT/session、Alembic/SQLAlchemy 或 Redis 认证设施。
- 前端 `npm run typecheck` 通过；`npm run build` 通过，但主 JS 约 3.5 MB、gzip 约 1.16 MB，存在大包警告。
- 后端全量 pytest 在收集阶段失败：未跟踪文件 `backend/tests/test_micro_database_adaptation.py` 仍导入已删除的 `ensure_business_tables`。这不是当前已跟踪测试的功能失败，需要单独排除该过时未跟踪测试后再验证正式测试集。
- 排除该未跟踪测试后，正式测试运行结果为 287 passed、163 subtests passed、21 failed、4 errors；失败集中在 Windows 系统临时目录无写入/清理权限，属于当前沙箱临时目录问题。将改用工作区内临时目录复测，避免把环境权限误判为代码缺陷。
- 将 `TEMP/TMP` 改为工作区 `backend/.test-tmp` 后，结果仍为 287 passed、163 subtests passed、21 failed、4 errors；失败路径已迁移到工作区，但依旧只在动态临时目录访问时被拒绝，因此不把它解释为产品逻辑回归。
- 排除已确认依赖动态临时目录的 3 个测试文件以及未跟踪过时测试后，核心测试集结果为 273 passed、159 subtests passed，零失败。
- 前端构建触碰了 `front/src/components.d.ts` 的文件时间/换行状态，但工作树文件对象与 HEAD 哈希完全一致（`f51860f...`），没有内容变更。

## 修正版部署判断
- 之前的“旁边完整克隆一套新版后端并使用独立业务数据库”应修正为“旁边部署 Web BFF/Identity”。完整克隆会重复核心能力、产生双业务事实源，并与 README 规定的统一后端/数据链路冲突。
- BFF 对外承担注册、登录、退出、当前用户、CSRF、会话续期、用户到 student profile/session 的授权映射，以及 Vue 所需 REST 适配；对内走 loopback 调用 8000 Core 的 MCP/TBox/Agent 能力。
- BFF 不应把浏览器 Bearer 直接转发成 Core 平台令牌，也不应让 Vue 保存 TBox/MCP 凭据。浏览器首选 Secure/HttpOnly/SameSite Cookie 会话。
- `identity.users`、`identity.auth_sessions`、`identity.user_student_profile`、`identity.idempotency_receipts` 可作为候选身份表，但属于公共数据契约变化，落地前必须由技术负责人确认并配套迁移、回滚和测试。
- 当前 Core 的 profile 正式首次写入尚缺同事务身份绑定/幂等边界，因此评审期间的新 BFF 可先完成认证、只读能力、会话映射和 staging 联调；不能仅凭 UI 可登录就宣称生产身份隔离已经完成。

