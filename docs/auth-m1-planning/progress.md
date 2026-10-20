# M1 实现进度

## 2026-10-15
- 已读取 planning-with-files 与 Typescript Standards。
- 已尝试会话恢复；技能脚本缺失，已人工核对根规划和差异摘要。
- 下一步：读取测试夹具、数据库连接方式和前端初始化流程，冻结实现细节。
- 已完成阶段 1：冻结认证契约、Cookie/CSRF 方案、服务注入和数据库边界。
- 下一步：实现后端认证模块、迁移和 API。
- 已完成后端认证配置、Schema、安全工具、Repository、Service、FastAPI 依赖和四个 API。
- 已新增 V008 迁移文件并更新 Argon2 依赖；迁移未执行。
- 下一步：改造前端真实认证流程。
- 已完成前端 auth API、Cookie/CSRF Axios 配置、User Store、异步路由守卫、启动恢复、退出清理和登录注册页面改造。
- 下一步：补认证测试、API 契约和部署环境示例。
- 已新增内存 Repository API 测试、Web 认证契约、部署环境变量与迁移说明。
- 已移除宽松 OPTIONS 回退，Web CORS 改为 `WEB_ALLOWED_ORIGINS` 显式白名单。
- 已确认 V008 仅包含 M1 用户、会话和登录失败记录，不提前引入 M2 画像绑定。
- 后端认证测试 5/5（含非白名单 CORS 拒绝）、既有部署/TBox 回归 21/21 通过。
- 前端 `vue-tsc --noEmit` 与 Vite 生产构建通过；仅有既存的大 chunk 警告。
- 尝试全量 pytest；被用户已有、未纳入 Git 的 `test_micro_database_adaptation.py` 在收集阶段阻塞（引用已不存在的 `ensure_business_tables`），与本次 M1 无关。
- 未执行数据库迁移、未连接线上数据库、未改动或重启线上服务。
