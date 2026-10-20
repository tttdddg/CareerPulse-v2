# CareerPulse M2 用户数据隔离实现计划

## 目标
在不操作现网、不执行数据库迁移的前提下，按 M2A、M2B 两阶段完成真实用户的数据归属、接口授权以及 Agent/MCP 可信身份链路。

## 阶段
- [x] 阶段 1：重新审计当前 M1 基线、业务表、API、Agent/MCP 身份链路
- [x] 阶段 2（M2A）：设计并实现用户—业务数据归属迁移与普通 API 授权
- [x] 阶段 3（M2A）：补双用户越权与兼容性测试
- [x] 阶段 4（M2B）：实现 Agent/MCP 可信用户注入与数据隔离
- [x] 阶段 5（M2B）：补端到端回归、文档和部署说明
- [x] 阶段 6：运行后端测试、前端类型检查与构建并审计差异

## 范围约束
- 不执行迁移，不连接或修改线上 PostgreSQL。
- 不重启或替换当前比赛评审服务。
- 迁移必须是加法式并提供明确回滚说明。
- 后端不得信任前端传入的 `user_id` 作为正式身份。
- 保留 Demo 模式，但与正式用户数据隔离。
- 不覆盖用户已有未提交改动。

## 实施决策
- Web owner 固定为 `web:<app_user.id>`，只可由已验证 HttpOnly Session 生成。
- 平台/MCP 调用方提供的逻辑 ID 统一转换为不可碰撞的 `external:<sha256>` owner，不能构造 `web:` 主体。
- CareerState Repository 使用条件 upsert 作为最终所有权防线，API 层检查不是唯一防线。
- `WEB_AUTH_ENABLED` 默认开启；仅测试或受控兼容场景可显式关闭。
- V009 只新增用户—画像归属表，不修改或回填线上数据，不在运行时执行迁移。
- 不重新挂载已失效旧 CRUD；另行记录前端 API 现代化缺口。

## 错误记录
| 错误 | 处理 |
|---|---|
| planning-with-files 的 `session-catchup.py` 仍不存在 | 已记录；改为人工检查 Git 状态与既有规划文件 |
| 读取 TBox router 时工作目录误设为仓库根却使用 `app/...` 路径 | 未重复原命令；后续从 `backend` 工作目录读取 |
| 首次同时修改 orchestrator 与其惰性导出时错误假设 `__init__.py` 是直接导入结构 | 读取实际 cycle-safe `__getattr__` 后拆分并正确导出 `StateOwnershipError` |
| 首轮 M2A 回归有 1 个 TBox 断言仍期望原始 `user_id` | 更新为断言规范化 `external:<sha256>` owner；其余 20 项已通过 |
| 新 M2 测试使用 pytest `tmp_path` 时命中本机历史临时目录权限错误 | 改用仓库现有 `.runtime/tests` 随机 SQLite 文件并在 fixture 结束时清理 |
| 一次 `rg` 查询因 PowerShell 参数中的冒号被解释为非法路径 | 已获得所需周边结果；后续拆分查询，不复用该命令形式 |
| 首轮 M2B 回归中直接调用 ToolService 的旧测试出现 16 个身份不匹配 | 网络边界已在 MCP server wrapper 强制哈希；撤销 ToolService 二次规范化，保留内部服务调用的显式主体语义，避免破坏既有组合测试 |
| 同轮 3 个 `TemporaryDirectory` 清理命中本机临时目录权限错误 | 后续验证显式把 TEMP/TMP 指向仓库 `.runtime/tests/tmp`，不修改业务代码规避环境问题 |
