# 发布前检查（pre-release checks）

这些脚本在**非生产数据库**上验证发布前必须成立的事实。全部只读或自清理，
**不会打印任何凭据**（凭据来自 `backend/.env` 或进程环境变量）。

## 执行顺序

```bash
# 0) 只读探测：确认连的是哪个库、现有多少表
python deploy/checks/migration_rehearsal.py probe

# 1) 迁移演练：只在目标库上执行一次，之后 rerun 必须是 no-op
python deploy/checks/migration_rehearsal.py apply     # V008: identity schema
python deploy/checks/migration_rehearsal.py link      # V009: 用户-画像一一对应
python deploy/checks/migration_rehearsal.py rerun     # 重复执行必须无副作用

# 2) 认证仓储：真实 PostgreSQL 上的注册/登录/会话/限流写入
python deploy/checks/auth_repository_smoke.py

# 3) HTTP 层：FastAPI 路由 + Cookie + CSRF 打到真实 PostgreSQL
python deploy/checks/web_http_smoke.py

# 4) 数据归属：持久化的业务数据必须能追溯到某个账号
python deploy/checks/ownership_check.py

# 5) 浏览器端到端：手动清单见 browser_e2e.md
```

## 每个脚本做什么

| 脚本 | 验证内容 | 副作用 |
| --- | --- | --- |
| `migration_rehearsal.py` | V008/V009 可执行、只新增对象、不改动现有表行数、可重复执行 | 在目标库创建 `identity` schema |
| `auth_repository_smoke.py` | 注册、重复注册被拒、登录、会话校验、错误密码记录、登出吊销 | 创建后**自行删除**测试账号 |
| `web_http_smoke.py` | 路由状态码、Secure/HttpOnly/SameSite Cookie、CSRF 强制、CORS 头、数据确实落库 | 创建后**自行删除**测试账号 |
| `ownership_check.py` | `career_state` 每行都有可解析的 owner，无跨账号串数据 | 只读 |
| `serve_backend.py` | 为浏览器验收启动本地后端 | 启动进程 |

## 约定

- **只在非生产库上运行。** `migration_rehearsal.py apply/link` 会真正执行 DDL。
- 退出码：`0` 通过；`1` 断言失败；`2` 数据泄漏（清理未干净或归属异常）；`3` 连接/运行异常。
- 脚本通过 `app.db` 的正式连接路径访问数据库，与应用运行时完全一致，
  因此能暴露「配置读取时机」「事务提交语义」这类只在真实环境出现的问题。
- 需要 Python 环境里有 `psycopg2`、`fastapi`、`uvicorn`（与 `backend` 运行时一致）。
