# CareerPulse 服务器部署交接清单

- **交接对象**：服务器运维 / 部署执行人
- **依据文档**：`deploy/README.md` §1–§13、`deploy/checks/README.md`、`deploy/checks/browser_e2e.md`
- **适用范围**：阿里云 ECS Ubuntu 22.04，后端 + Vue SPA 首次上线（M1 认证 + M3 Web 业务 API）
- **填写约定**：本文档只允许出现占位符。**凭据不写进本文档、不进 Git、不进 shell history、不进截图。**

执行方式：每阶段完成后打勾，出现「STOP」条件立即停止并回报交接方，不要自行绕过。

---

## 0. 交接物核对

| # | 交接内容 | 提供方 | 接收确认 |
|---|---|---|---|
| 0.1 | 代码仓库地址 + **干净工作区的提交号**（必须包含：`front/vite.config.ts` 代理修复、`deploy/README.md` §13、`deploy/checks/`、本清单 `deploy/HANDOVER.md`） | 交接方 | ☐ |
| 0.2 | `deploy/README.md`（部署主文档，§1–§13） | 随代码 | ☐ |
| 0.3 | `deploy/checks/`（8 个文件：`migration_rehearsal`/`auth_repository_smoke`/`web_http_smoke`/`ownership_check`/`serve_backend` 5 个脚本 + 公共模块 `_common.py` + `README.md` + `browser_e2e.md`） | 随代码 | ☐ |
| 0.4 | 目标数据库信息：主机/端口/库名 `careerpulse_micro`/专用账号（建议非 `postgres` 超级用户） | 接收方 | ☐ |
| 0.5 | 公网域名 A 记录已指向 ECS 公网 IP | 接收方 | ☐ |
| 0.6 | **凭据（走密码管理器或线下，禁止出现在任何文本里）**：`POSTGRES_PASSWORD`、`MCP_API_TOKEN`、`A02_TBOX_API_TOKEN`、LLM key、TLS 私钥 | 双方 | ☐ |
| 0.7 | 数据库备份与恢复责任人在岗 | 接收方 | ☐ |

> **STOP**：0.6 若只能通过聊天工具传递明文，先停下来与交接方确认替代通道。

---

## 1. 前置条件（Go / No-Go）

| # | 检查项 | 期望 | 确认 |
|---|---|---|---|
| 1.1 | 操作系统 | Ubuntu 22.04 x86_64 | ☐ |
| 1.2 | 安全组入站规则 | 仅 22（受控源 IP）、80、443 | ☐ |
| 1.3 | **8000 与 5432 未对公网开放** | `curl` 从外网访问 8000 必须超时/拒绝 | ☐ |
| 1.4 | DNS | A 记录已生效（`dig +short <域名>`） | ☐ |
| 1.5 | PostgreSQL 可达且为**非生产演练库或已备份的正式库** | 可连接 | ☐ |
| 1.6 | 目标库已有四张业务表 | `student_profile`、`job_clean`、`job_type_profile`、`job_type_graph_edge` | ☐ |
| 1.7 | Node.js 20+（仅用于构建前端，可用别的机器） | `node --version` | ☐ |
| 1.8 | 待部署提交已确认 | 提交号写入 §9 | ☐ |

---

## 2. 阶段 A — 代码与运行时（对应 README §3–§5）

```bash
# 系统包
sudo apt update
sudo apt install -y software-properties-common build-essential libpq-dev \
  nginx curl rsync certbot tesseract-ocr tesseract-ocr-chi-sim
sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 账号与代码
sudo useradd --system --create-home --home-dir /opt/careerpulse --shell /usr/sbin/nologin careerpulse
sudo install -d -o careerpulse -g careerpulse -m 0750 \
  /opt/careerpulse/app /opt/careerpulse/venv /var/lib/careerpulse
sudo rsync -a --exclude='.git' ./ /opt/careerpulse/app/
sudo chown -R careerpulse:careerpulse /opt/careerpulse/app

# 运行环境
sudo -u careerpulse python3.11 -m venv /opt/careerpulse/venv
sudo -u careerpulse /opt/careerpulse/venv/bin/python -m pip install --upgrade pip
sudo -u careerpulse /opt/careerpulse/venv/bin/python -m pip install \
  -r /opt/careerpulse/app/backend/requirements-prod.txt
sudo -u careerpulse /opt/careerpulse/venv/bin/python -m pip check
```

**验收（全部通过才继续）**

```bash
sudo -u careerpulse /opt/careerpulse/venv/bin/python -m pip check   # 无输出
sudo -u careerpulse /opt/careerpulse/venv/bin/python -c \
  "import argon2, psycopg2, httpx, fastapi, uvicorn; print('deps ok')"
# 期望：deps ok
```

- ☐ `argon2-cffi==25.1.0`（登录密码哈希）与 `httpx`（检查脚本 TestClient）**已包含在 `requirements-prod.txt`**，无需单独安装，但必须做上面这条导入验证。
- ☐ **不要**执行 `backend/scripts/init_a02_data.py --apply`（README §3 里写的是相对 `backend/` 的路径：四表以 `sql/` 为准）。
- ☐ 本次只执行 `V008`（必需）与 `V009`（可选）；**不要执行 V001–V007**，它们属于另一套状态存储路径。

---

## 3. 阶段 B — 数据库迁移（本次交接的重点）

> 应用**启动时永不自动建表或迁移**（README §6 结尾已声明）。V008 未执行则注册/登录一律 503
> `{"code": "AUTH_DATABASE_UNAVAILABLE"}`（见 `app/auth/dependencies.py:37`）。

### B1. 先备份（强制）

```bash
sudo -u postgres pg_dump -Fc -d careerpulse_micro \
  -f /var/backups/careerpulse_micro_$(date +%F_%H%M).dump
sudo -u postgres pg_restore --list /var/backups/careerpulse_micro_*.dump | head -5
```

- ☐ 备份文件存在且可列出（`/var/backups/` 需事先创建并限制权限）

### B2. 探测：确认打的是哪个库

```bash
sudo -u careerpulse /opt/careerpulse/venv/bin/python \
  /opt/careerpulse/app/deploy/checks/migration_rehearsal.py probe
```

期望：`database` 是目标库、`existing tables` = 4、**`identity schema already exists : False`**、`public.student_profile exists : True`。

> **STOP**：若 `database` 不是预期库名，或 `identity schema already exists : True`（可能已被人执行过），立即停止回报。

### B3. 执行迁移（二选一，不要重复执行）

**方式一（推荐，带断言）**

```bash
sudo -u careerpulse /opt/careerpulse/venv/bin/python \
  /opt/careerpulse/app/deploy/checks/migration_rehearsal.py apply    # V008
sudo -u careerpulse /opt/careerpulse/venv/bin/python \
  /opt/careerpulse/app/deploy/checks/migration_rehearsal.py link     # V009（可选）
sudo -u careerpulse /opt/careerpulse/venv/bin/python \
  /opt/careerpulse/app/deploy/checks/migration_rehearsal.py rerun    # 必须 no-op
```

期望输出：`[before] 4 tables` → `[after ] 7 tables`，`added` 恰为 3 张 `identity.*`，
`removed : []`，`rowcount changed on existing tables: none`；V009 后 8 张表；`rerun` 两次均 `re-run is a no-op`。

**方式二（运维习惯用 psql）**

```bash
sudo -u postgres psql -v ON_ERROR_STOP=1 -d careerpulse_micro -f \
  /opt/careerpulse/app/backend/migrations/V008__create_identity_auth.sql
```

> ⚠️ 方式二执行过之后，**只能再跑 `probe` / `rerun`**，不要再跑 `apply`（断言会因为「没有新增表」而失败，那是预期行为，不是故障）。

### B4. 权限核对（容易漏）

迁移文件里**没有任何 `GRANT` 语句**，表归执行迁移的 PostgreSQL 角色所有。

```bash
sudo -u careerpulse /opt/careerpulse/venv/bin/python \
  /opt/careerpulse/app/deploy/checks/migration_rehearsal.py probe   # 看 user: 一行
```

- ☐ `user:` 必须等于 `/etc/careerpulse/careerpulse.env` 里的 `POSTGRES_USER`
- ☐ 若两者不同，必须显式授权（把 `<POSTGRES_USER>` 换成实际账号）：

```sql
GRANT USAGE ON SCHEMA identity TO "<POSTGRES_USER>";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA identity TO "<POSTGRES_USER>";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA identity TO "<POSTGRES_USER>";
```

### B5. 迁移失败时的回滚

```sql
-- V009（先确认没有业务依赖）
DROP TABLE identity.user_student_profile;
-- V008：仅在确认 identity 表里没有需要保留的数据后
DROP SCHEMA identity CASCADE;
```

或整体恢复：`pg_restore -d careerpulse_micro <B1 的备份文件>`。

---

## 4. 阶段 C — 环境文件（对应 README §6）

```bash
sudo install -d -o root -g careerpulse -m 0750 /etc/careerpulse
sudo install -o root -g careerpulse -m 0640 \
  /opt/careerpulse/app/deploy/env/careerpulse.env.example \
  /etc/careerpulse/careerpulse.env
sudo editor /etc/careerpulse/careerpulse.env
```

| # | 项 | 要求 | 确认 |
|---|---|---|---|
| 4.1 | `POSTGRES_HOST/PORT/DATABASE/USER` | ⚠️ **示例里 `POSTGRES_PORT=5433`，必须改成服务器实际端口**（PostgreSQL 默认 5432）；库名只用 `POSTGRES_DATABASE` | ☐ |
| 4.2 | `POSTGRES_PASSWORD` | 必填；示例为空会导致连接失败 | ☐ |
| 4.3 | `WEB_ALLOWED_ORIGINS` | 必须设为真实浏览器域名。**留空会回退到 `localhost:5173/3000`，生产必被 CORS 拦死** | ☐ |
| 4.4 | `AUTH_COOKIE_SECURE` | HTTPS 下保持 `true` | ☐ |
| 4.5 | `A02_STATE_DB_PATH` | 保持 `/var/lib/careerpulse/career_state.sqlite3`；`A02_DATABASE_URL` 留空（二选一） | ☐ |
| 4.6 | 状态目录属主 | `chown -R careerpulse:careerpulse /var/lib/careerpulse`（只读文件系统会导致写入失败） | ☐ |
| 4.7 | `MCP_API_TOKEN` / `A02_TBOX_API_TOKEN` | 各自独立随机生成；**生成命令不要留 shell history，不要截图** | ☐ |
| 4.8 | `TBOX_*` / `A02_LLM_API_KEY` | 无租户凭据则留空（`/api/tbox/chat` 会返回受控 503，属预期） | ☐ |
| 4.9 | `A02_DEMO_MODE` / `A02_LLM_MOCK_MODE` | 首次上线保持 `true`，待 Prompt 资产与真实凭据到位再关 | ☐ |
| 4.10 | 域名替换 | `api.example.com` 在 MCP 白名单、Nginx 配置中全部替换 | ☐ |
| 4.11 | 文件权限 | `ls -l /etc/careerpulse/careerpulse.env` → `-rw-r----- root careerpulse` | ☐ |
| 4.12 | `AUTH_CSRF_COOKIE_NAME` | 若改了它，前端必须以同值的 `VITE_CSRF_COOKIE_NAME` 重新构建，否则登录后 CSRF 校验必失败（README §6 第 9 条） | ☐ |

---

## 5. 阶段 D — 服务与反向代理（README §7、§8、§12）

### D1. 后端服务

```bash
sudo install -o root -g root -m 0644 \
  /opt/careerpulse/app/deploy/systemd/careerpulse.service /etc/systemd/system/careerpulse.service
sudo systemctl daemon-reload && sudo systemctl enable --now careerpulse
sudo systemctl status careerpulse --no-pager
curl --fail http://127.0.0.1:8000/healthz          # 期望 200
```

### D2. TLS 证书 + API 站（README §8，**必须先签发证书再装配置**）

```bash
sudo systemctl stop nginx                            # 80 端口被占用时需要先停
sudo certbot certonly --standalone -d <你的 API 域名>
```

再把 `deploy/nginx/careerpulse.conf` 里的 `api.example.com` 全部替换为真实域名、核对证书路径，然后：

```bash
sudo install -o root -g root -m 0644 \
  /opt/careerpulse/app/deploy/nginx/careerpulse.conf \
  /etc/nginx/sites-available/careerpulse
sudo ln -sf /etc/nginx/sites-available/careerpulse /etc/nginx/sites-enabled/careerpulse
sudo rm -f /etc/nginx/sites-enabled/default          # 该 ECS 上另有站点时跳过
sudo nginx -t && sudo systemctl enable --now nginx && sudo systemctl reload nginx
```

### D3. 前端构建 + SPA 站（README §12）

```bash
cd /opt/careerpulse/app/front && npm ci && npm run build    # 产出 front/dist

sudo install -o root -g root -m 0644 \
  /opt/careerpulse/app/deploy/nginx/careerpulse-web.conf /etc/nginx/sites-available/careerpulse-web
sudo ln -sf /etc/nginx/sites-available/careerpulse-web /etc/nginx/sites-enabled/careerpulse-web
sudo nginx -t && sudo systemctl reload nginx
```

- ☐ `sudo journalctl -u careerpulse -n 100 --no-pager` 无 Traceback、无反复重连报错
- ☐ API 站与 SPA 站**分属两个站点文件**（`careerpulse.conf` / `careerpulse-web.conf`），两者 `nginx -t` 均通过
- ☐ 前端必须走 `npm run build` 产物由 Nginx 直接伺服，**不要**指望 `npm run dev` 在服务器上常驻

---

## 6. 阶段 E — 验收（README §13 + §9 + §12）

### E1. 自动检查（5 条，逐条记录退出码）

```bash
cd /opt/careerpulse/app
sudo -u careerpulse /opt/careerpulse/venv/bin/python deploy/checks/migration_rehearsal.py probe
sudo -u careerpulse /opt/careerpulse/venv/bin/python deploy/checks/migration_rehearsal.py rerun
sudo -u careerpulse /opt/careerpulse/venv/bin/python deploy/checks/auth_repository_smoke.py
sudo -u careerpulse /opt/careerpulse/venv/bin/python deploy/checks/web_http_smoke.py
sudo -u careerpulse /opt/careerpulse/venv/bin/python deploy/checks/ownership_check.py
```

| 检查 | 期望 | 实测 |
|---|---|---|
| `probe` | `identity schema already exists : True`，`existing tables : 8`（含 V009；若跳过 V009 则为 7） | ☐ |
| `rerun` | 两次 `re-run is a no-op` | ☐ |
| `auth_repository_smoke` | `AUTH REPOSITORY OK`，`after cleanup` 全 0，退出码 0 | ☐ |
| `web_http_smoke` | `WEB HTTP SMOKE OK`（12 项），`after cleanup` 全 0，退出码 0 | ☐ |
| `ownership_check` | `OWNERSHIP OK`，`unknown prefixed owners = 0` | ☐ |

> 两个 smoke 会自己创建并删除测试账号，跑完库里不留行。若退出码为 2 表示有数据残留，必须当场清理再重跑。
> 脚本会自动读取 `/etc/careerpulse/careerpulse.env`，**不会打印任何凭据**。

### E2. 既有 HTTP 冒烟（README §9）

```bash
sudo chmod 0750 /opt/careerpulse/app/deploy/scripts/smoke-test.sh
sudo -u careerpulse bash -c '
  set -a
  source /etc/careerpulse/careerpulse.env
  set +a
  /opt/careerpulse/app/deploy/scripts/smoke-test.sh https://<你的 API 域名>
'
```

> 该脚本校验 `/healthz` 精确响应、`/api/tbox/chat` 路由、MCP 无 token 时 401、带 token 的 `initialize` 响应。
> token 必须来自被 source 的环境文件，**不允许**写成命令行参数。

### E3. 侧端口演练（README §12，**首次上线必须做**）

1. ☐ 现网保持 `127.0.0.1:8000`，候选实例起在 `127.0.0.1:8001`（同一份 env、同一个 `A02_STATE_DB_PATH`）
2. ☐ 直连候选端口（**不走公网域名**）：
   - `GET /api/web/v1/workflows` 无 Cookie → **401**
   - 带会话 Cookie → **200**
   - `POST /api/web/v1/workflows` 缺 `X-CSRF-Token` → **403**
3. ☐ Nginx 上游切到 8001 → `nginx -t` → `systemctl reload nginx`
4. ☐ 浏览器全流程通过后，再把 8001 转正或把上游切回 8000

### E4. 浏览器端到端（`deploy/checks/browser_e2e.md`）

6 步：匿名跳登录(401) → 注册(201/409) → 登录(200 + HttpOnly Cookie) → 业务闭环(201/200 链) → 退出(204) → **跨账号访问他人 workflow 得 404**。

---

## 7. 回滚预案

| 场景 | 动作 |
|---|---|
| 代码问题 | 恢复上一版 `/opt/careerpulse/app` 与对应 venv → `systemctl restart careerpulse`；**永不删除 `/var/lib/careerpulse`** |
| 流量问题 | Nginx 上游 `careerpulse_backend` 切回原端口 → `nginx -t` → `reload`（§12 逆向） |
| 迁移问题 | `DROP TABLE identity.user_student_profile;`（V009）→ `DROP SCHEMA identity CASCADE;`（V008，**先确认无待保留数据**），或 `pg_restore` 恢复 B1 备份 |
| 环境文件问题 | 从 `0640` 备份副本恢复 `/etc/careerpulse/careerpulse.env` → 重启服务 |

---

## 8. 风险与已知限制（交接方声明）

**已在本地 PostgreSQL 16.14 验证过的事实**

- ✅ V008/V009 可执行、只增不改（4→7→8 表，现有表零行数变化），重复执行 no-op
- ✅ PostgreSQL 支持的注册/登录/会话/限流全链路（仓储冒烟 6 项）+ FastAPI 路由/Cookie/CSRF/CORS（HTTP 冒烟 12 项）全绿，均自清理
- ✅ 真实浏览器闭环（Vite dev 代理修复后）与跨账号 404 隔离
- ✅ `326 passed / 167 subtests`、`vue-tsc` 通过、`npm run build` 通过

**尚未验证、需在服务器上确认的**

- ⚠️ 迁移**首次**在目标生产库执行（本地只是演练库）
- ⚠️ 公网 HTTPS 域名下的 Cookie/CORS 行为（本地是自签/本地域名）
- ⚠️ 真实公网浏览器全流程

**已知遗留（不阻塞本次上线，建议排期）**

- 本地历史库有 8 条 pre-M2 raw owner + 37 条 `agent_logs`（2026-08/09 调试遗留）；**新库该计数必须为 0**
- `app/services/{history,matching,report}_service.py` 及对应路由因缺少 `ensure_business_tables` 无法导入、未注册；前端也无调用（接上前会立刻报错）
- 前端产物约 3.5 MB 单 chunk，建议后续代码分割
- **Git 历史中曾包含 TBox 凭据（`TBOX_CHAT_AUTHORIZATION`、`TBOX_USER_ID_SECRET`）**：若这些凭据仍有效，须在租户侧轮换

---

## 9. 签字确认

| 阶段 | 提交/版本 | 执行人 | 时间 | 结果 | 备注 |
|---|---|---|---|---|---|
| 交接物核对（§0） | | | | ☐ | |
| 前置条件（§1） | | | | ☐ | |
| 阶段 A 运行时（§2） | | | | ☐ | |
| 阶段 B 数据库迁移（§3） | | | | ☐ | |
| 阶段 C 环境文件（§4） | | | | ☐ | |
| 阶段 D 服务与代理（§5） | | | | ☐ | |
| 阶段 E 验收（§6） | | | | ☐ | |
| 回滚预案已确认（§7） | | | | ☐ | |

- 交接方签字：____________　日期：________
- 接收方签字：____________　日期：________
