# CareerPulse M1 真实认证实现计划

## 目标
在不操作现网、不执行数据库迁移的前提下，实现 PostgreSQL 服务端 Session、Argon2 密码、注册/登录/me/注销、前端真实认证接入及必要测试。

## 阶段
- [x] 阶段 1：确认现有数据库与 API 测试模式，冻结 M1 契约
- [x] 阶段 2：实现认证迁移、Repository、Service、安全工具和 API
- [x] 阶段 3：改造前端认证 API、Store、路由与登录注册页
- [x] 阶段 4：补充测试、契约和部署示例
- [x] 阶段 5：运行后端测试、前端类型检查与构建并修复

## 范围约束
- 不执行迁移，不连接或修改线上 PostgreSQL。
- 不重构 Match、Path、Training、MCP 或 Agent 业务。
- 不处理 M2 的全业务数据隔离，只为后续提供可信 current_user 基础。
- 不提交 Git，不覆盖用户已有改动。

## 关键决策
- 使用 PostgreSQL 持久化的不透明服务端 Session；浏览器仅保存 HttpOnly Cookie。
- 密码使用 Argon2id。
- API 路径为 `/api/auth/register|login|me|logout`。
- 注册字段采用 username/email/password；现有模拟短信从正式流程移除。
- 登录成功设置不透明 Session Cookie 和可由前端读取的双提交 CSRF Cookie；Axios 自动回送 `X-CSRF-Token`。
- AuthService 通过 `app.state` 注入，测试使用内存 Repository，不访问真实 PostgreSQL。
- 认证数据库沿用现有 `business_transaction`，迁移只新增 `identity` schema，不运行时建表。

## 错误记录
| 错误 | 处理 |
|---|---|
| planning-with-files 声明的 session-catchup.py 不存在 | 已读取既有根规划和 git diff，改用独立认证规划目录 |
| 仓库改名后默认工作目录不存在，补丁工具无法启动 | 经用户授权创建空的旧路径占位；实际文件继续写入 `CareerPulse-v2` |
| 首次前端大补丁同时删除并新增同一路径，apply_patch 拒绝多操作同目标 | 拆为“删除旧 Store”和“新增新 Store”两个补丁后完成 |
| 多文件收尾补丁因 `main.py` 带 UTF-8 BOM 无法匹配首行 | 拆分补丁，并显式匹配 BOM 后完成 |
| Argon2 首次安装受限于沙箱网络 | 获得用户批准后联网安装并完成测试 |
| 全量 pytest 被既有未跟踪 `test_micro_database_adaptation.py` 在收集阶段阻塞 | 该测试引用仓库已不存在的 `ensure_business_tables`，未修改用户文件；M1 与相关既有测试均单独通过 |

