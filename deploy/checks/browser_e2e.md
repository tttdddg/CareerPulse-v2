# 浏览器端到端验收（手动清单）

自动化脚本覆盖不到浏览器这一层（Cookie、SameSite、CORS、路由守卫、前端状态），
因此每次发布前按本清单在真实浏览器里走一遍。**全部通过约需 5 分钟。**

## 前置条件

- PostgreSQL 已执行 `V008__create_identity_auth.sql`（用 `migration_rehearsal.py` 先演练）
- `backend/.env` 存在且含 `POSTGRES_*`
- 后端与前端开发服务器已启动：

```bash
# 终端 1
python deploy/checks/serve_backend.py          # http://127.0.0.1:8000
# 终端 2
cd front && npm run dev                        # http://localhost:5173
```

Vite 代理会把 `/api` **原样**透传给后端（与 nginx 的 `location /api/` 一致）。
若接口全部 404，说明代理配置被改坏了，先修复再继续。

## 1. 匿名访问

打开 `http://localhost:5173`，应自动跳转到 `#/login?redirect=/`。
Network 面板里 `GET /api/auth/me` 应为 **401**（控制台出现 401 报错属预期）。

## 2. 注册

在注册表单填写用户名、邮箱、密码（≥10 位）并提交：

- `POST /api/auth/register` → **201**
- 页面提示注册成功，登录表单自动带入用户名并清空密码
- 再提交一次相同用户名 → **409**「用户名或邮箱已经被注册」

## 3. 登录

提交登录表单：

- `POST /api/auth/login` → **200**，跳转离开登录页
- Application 面板应有两个 Cookie：
  - `careerpulse_session`：`HttpOnly` + `Secure` + `SameSite=Lax`
  - `careerpulse_csrf`：非 HttpOnly（前端需要读它放进 `X-CSRF-Token`）
- 控制台执行 `document.cookie` 应**看不到** session cookie

## 4. 业务闭环

进入「数据输入」，填写专业技能/证书/实习经历/自我评价，选择目标岗位后点「开始分析」。
Network 面板依次应为：

| 请求 | 状态码 |
| --- | --- |
| `GET /api/web/v1/jobs?keyword=…` | 200 |
| `POST /api/web/v1/workflows` | 201 |
| `PUT /api/web/v1/workflows/{id}/profile` | 200 |
| `PUT /api/web/v1/workflows/{id}/target-job` | 200 |
| `POST /api/web/v1/workflows/{id}/match` | 200 |
| `GET /api/web/v1/jobs/{job_id}/graph` | 200 |

页面应跳到「岗位匹配」并渲染推荐岗位 TOP N 与逐项能力差距建议。

## 5. 身份隔离

1. 点「退出登录」：`POST /api/auth/logout` → **204**，Cookie 全部清除，回到登录页
2. 用**另一个账号**登录，然后在地址栏直接访问第 4 步得到的 workflow 地址：

   ```
   http://localhost:5173/api/web/v1/workflows/<上一个账号的 session_id>
   ```

   预期 **404** 且 `detail.code = WORKFLOW_NOT_FOUND`。
3. 访问 `http://localhost:5173/api/web/v1/workflows?page=1&page_size=10`，
   预期 200 且 `items` 里**没有**别人的会话。

## 6. 收尾

用 `ownership_check.py` 复核数据归属，然后删除测试账号与测试会话：

```bash
python deploy/checks/ownership_check.py
```

> 不要把测试账号留在共享环境里。测试账号名建议统一带 `smoke`/`e2e` 字样，
> 便于事后检索与清理。
