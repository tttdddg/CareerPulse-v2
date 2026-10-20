# M2 实现进度

## 2026-10-19
- 已读取 planning-with-files 与 Typescript Standards。
- 已确认 M1 改动仍在工作区，现网未被操作。
- 下一步：审计业务表、普通 API、Agent/MCP 的 `user_id` 来源与持久化边界。
- 已完成第一轮文件与路由清单审计：确认旧 CRUD 路由未挂载，M2 应围绕当前 Agent/Platform/TBox/MCP 入口设计。
- 已区分 Web Cookie、TBox 平台 Bearer、MCP 服务 Bearer 三类认证边界；后续用命名空间 owner 隔离，避免将静态服务 Token 伪装成终端用户认证。
- 已发现正式前端仍依赖当前未挂载的旧 CRUD 路由，且 matching/report 继续发送客户端 `user_id`；M2A 需要把“恢复前端契约”和“后端所有权校验”一起处理。
- 深入检查后确认旧 CRUD 依赖已删除的数据库 helper 和旧表结构，不能安全直接恢复；本轮将优先完成受支持链路的隔离，并把前端契约现代化明确列为独立后续项。
- 已确认 Web Agent 不写业务画像，PostgreSQL 画像写入集中在 MCP ToolService；M2A 与 M2B 的持久化边界可分别处理。
- 已确定 CareerState 所有权必须下沉到 Repository 条件 upsert，避免 API 先读后写竞态；TBox 则在路由边界注入 Web owner。
- 阶段 1 完成；进入 M2A Web owner、V009 归属表和 Repository 所有权实现。
- 已加入 owner 工具、Web auth/CSRF 开关、CareerState 条件 upsert、V009 用户—画像归属表，并开始改造 Career Agent/TBox 路由。
- M2A 完成：Career Agent/TBox 写接口要求 Web Session + CSRF，读取按 `web:<id>` 隐藏其他用户 session；Repository 阻止并发跨 owner 覆盖。
- 新增双用户、匿名、CSRF、TBox 身份覆盖和 Repository 竞态测试；连同 M1/Stage3/TBox 回归共 25 项通过。
- 进入 M2B：规范化 Platform/MCP external owner，并验证其不能读取 Web session。
- M2B 完成：Platform/MCP 边界统一生成 `external:<sha256>` owner，移除 ToolService 二次规范化；Platform Tool 覆盖顶层与画像内部客户端 `user_id`。
- MCP、Platform、Stage4 回归共 57 项通过；新增 `test_cross_identity_isolation.py` 5 项（Web↔Platform、Web↔MCP 双向不可访问、两个 external 主体不可共享 session）。
- 后端完整回归 **318 项全部通过**（含 167 子测试）；前端 `vue-tsc` 类型检查通过，生产构建成功。
- 客户端 `user_id` 信任审计：所有入口均在边界转换为 `web:`/`external:` owner；旧 CRUD 路由（matching/reports）确认未挂载，无残留。
- 已更新 API 契约（新增 12.7 身份隔离章节，v2.0）、根目录与 deploy 的 env 示例（补充 `WEB_AUTH_ENABLED`/`WEB_ALLOWED_ORIGINS`）。
- 已知遗留：`test_micro_database_adaptation.py` 引用已删除的旧 CRUD `app.db` 函数导致收集失败，非 M2 范围，回归时用 `--ignore` 跳过；V008/V009 迁移脚本仍未执行，线上未操作。
