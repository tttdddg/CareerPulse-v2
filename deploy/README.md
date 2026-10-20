# CareerPulse ECS deployment

This directory prepares the backend-only first deployment on Alibaba Cloud ECS:

- Ubuntu 22.04 x86_64
- Python 3.11 virtual environment
- one Uvicorn worker managed by systemd
- Nginx reverse proxy for REST, MCP Streamable HTTP, and TBox chat SSE
- SQLite state at `/var/lib/careerpulse` for the minimal first deployment

It does not deploy the Vue frontend, create legacy business tables, restore
missing Agent Prompt files, or contact a real TBox/LLM tenant.

## 1. Fixed paths and placeholders

The supplied service file assumes:

| Item | Path |
|---|---|
| repository | `/opt/careerpulse/app` |
| virtual environment | `/opt/careerpulse/venv` |
| environment file | `/etc/careerpulse/careerpulse.env` |
| local state | `/var/lib/careerpulse/career_state.sqlite3` |
| service user | `careerpulse` |
| internal listener | `127.0.0.1:8000` |

Replace every `api.example.com` occurrence in the Nginx and environment files
with the fixed public DNS name before enabling the service. HTTPS is required
for public Bearer credentials; do not send MCP tokens over plain HTTP.

## 2. ECS network rules

Allow inbound traffic only as follows:

- TCP 22 from trusted administrator addresses.
- TCP 80 for certificate issuance and HTTPS redirect.
- TCP 443 for REST and MCP.
- Do not expose TCP 8000 or PostgreSQL 5432 to the internet.

Point the DNS A record at the ECS elastic/public IP before requesting a TLS
certificate.

## 3. Install operating-system packages

Ubuntu 22.04 does not use Python 3.11 as this project's assumed system default,
so install an explicit 3.11 interpreter and venv support. The commands below use
the commonly used deadsnakes PPA; an organization-approved Python 3.11 package
source may be substituted.

```bash
sudo apt update
sudo apt install -y software-properties-common build-essential libpq-dev \
  nginx curl rsync certbot tesseract-ocr tesseract-ocr-chi-sim
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
python3.11 --version
```

PostgreSQL is optional for the first MCP-only state deployment. Install it only
when the finalized `careerpulse_micro` database is available for REST routes:

```bash
sudo apt install -y postgresql postgresql-contrib
```

Do not run `scripts/init_a02_data.py --apply` against `careerpulse_micro`:
the finalized four-table SQL in `sql/` is authoritative and runtime requests
must not create or migrate tables in that database.

## 4. Create the service account and copy the repository

From a checkout or uploaded release directory:

```bash
sudo useradd --system --create-home --home-dir /opt/careerpulse \
  --shell /usr/sbin/nologin careerpulse
sudo install -d -o careerpulse -g careerpulse -m 0750 \
  /opt/careerpulse/app /opt/careerpulse/venv /var/lib/careerpulse
sudo rsync -a --exclude='.git' ./ /opt/careerpulse/app/
sudo chown -R careerpulse:careerpulse /opt/careerpulse/app
```

If the user already exists, `useradd` will report that fact; verify its home,
group, and shell rather than recreating it.

## 5. Build the Python 3.11 virtual environment

```bash
sudo -u careerpulse python3.11 -m venv /opt/careerpulse/venv
sudo -u careerpulse /opt/careerpulse/venv/bin/python -m pip install --upgrade pip
sudo -u careerpulse /opt/careerpulse/venv/bin/python -m pip install \
  -r /opt/careerpulse/app/backend/requirements-prod.txt
sudo -u careerpulse /opt/careerpulse/venv/bin/python -m pip check
```

`requirements-prod.txt` is a curated Python 3.11/Linux direct-dependency list,
not a freeze of the Windows development environment. `psycopg2` builds against
`libpq-dev`; OCR also requires the Tesseract packages installed above.

## 6. Create the protected environment file

```bash
sudo install -d -o root -g careerpulse -m 0750 /etc/careerpulse
sudo install -o root -g careerpulse -m 0640 \
  /opt/careerpulse/app/deploy/env/careerpulse.env.example \
  /etc/careerpulse/careerpulse.env
sudo editor /etc/careerpulse/careerpulse.env
```

Before starting the service:

1. Replace `api.example.com` in both MCP allowlists.
2. Generate a strong, unique `MCP_API_TOKEN`; leaving it empty makes startup
   fail closed while MCP authentication is enabled.
3. Generate a different `A02_TBOX_API_TOKEN` if stage-3 REST tools are public.
4. Keep `A02_DEMO_MODE=true` and `A02_LLM_MOCK_MODE=true` until real LLM
   credentials and the missing ProfileAgent/JobAgent Prompt assets are present.
5. Keep `A02_STATE_DB_PATH` for the first deployment and leave
   `A02_DATABASE_URL` empty. Configure exactly one of them.
6. Leave outbound TBox values empty unless a real tenant issued the credentials;
   `/api/tbox/chat` will then return a controlled 503 instead of making a call.
7. Fill `POSTGRES_*` only when the finalized `careerpulse_micro` database is
   available; keep Agent state on `A02_STATE_DB_PATH` unless separately planned.
8. Set `WEB_ALLOWED_ORIGINS` to the deployed Vue origin. Keep
   `AUTH_COOKIE_SECURE=true` under HTTPS; use `false` only for local HTTP
   development.
9. If `AUTH_CSRF_COOKIE_NAME` is changed, build the frontend with the same
   value in `VITE_CSRF_COOKIE_NAME`.

M1 authentication requires `backend/migrations/V008__create_identity_auth.sql`.
Back up PostgreSQL and apply this migration explicitly in staging before making
the authentication endpoints public. Application startup never creates or
migrates these tables automatically.

Generate secrets locally on the ECS without printing them into shell history,
deployment logs, screenshots, or source-controlled files. Keep the populated
environment file at mode 0640 or stricter.

## 7. Install and start systemd

```bash
sudo install -o root -g root -m 0644 \
  /opt/careerpulse/app/deploy/systemd/careerpulse.service \
  /etc/systemd/system/careerpulse.service
sudo systemctl daemon-reload
sudo systemctl enable --now careerpulse
sudo systemctl status careerpulse --no-pager
sudo journalctl -u careerpulse -n 100 --no-pager
curl --fail http://127.0.0.1:8000/healthz
```

The unit runs one Uvicorn worker and binds only to loopback. `MCP_HOST` and
`MCP_PORT` are MCP configuration values; Uvicorn's `ExecStart` remains the
authoritative socket configuration.

## 8. Issue TLS and install Nginx

Obtain the certificate before installing the supplied HTTPS configuration. One
simple first-time method is Certbot standalone mode while port 80 is free:

```bash
sudo systemctl stop nginx
sudo certbot certonly --standalone -d api.example.com
```

Then replace `api.example.com` in `deploy/nginx/careerpulse.conf`, verify the
certificate paths, and install the site:

```bash
sudo install -o root -g root -m 0644 \
  /opt/careerpulse/app/deploy/nginx/careerpulse.conf \
  /etc/nginx/sites-available/careerpulse
sudo ln -s /etc/nginx/sites-available/careerpulse \
  /etc/nginx/sites-enabled/careerpulse
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

The only intentionally destructive command above removes the enabled default
site symlink, not application data. Skip it if the ECS hosts another site.

The Nginx configuration:

- forwards the original Host and Authorization headers;
- disables request/response buffering for `/mcp` and `/api/tbox/chat`;
- gives MCP 75-second and TBox chat 150-second upstream timeouts;
- limits request bodies to 10 MiB;
- keeps Uvicorn and PostgreSQL private.

## 9. Run smoke checks

First make the script executable on Linux. Run it with the same protected
environment used by systemd so the token is never placed on the command line:

```bash
sudo chmod 0750 /opt/careerpulse/app/deploy/scripts/smoke-test.sh
sudo -u careerpulse bash -c '
  set -a
  source /etc/careerpulse/careerpulse.env
  set +a
  /opt/careerpulse/app/deploy/scripts/smoke-test.sh https://api.example.com
'
```

The script verifies:

- exact minimal `/healthz` response;
- routing to `/api/tbox/chat` using a schema-invalid request that cannot trigger
  an external TBox call;
- HTTP 401 for MCP without a token;
- an authenticated MCP `initialize` response.

It never prints the MCP token.

## 10. Updates and rollback

Before an update, preserve `/etc/careerpulse/careerpulse.env` and
`/var/lib/careerpulse`. Replace only `/opt/careerpulse/app`, rebuild the venv if
requirements changed, run tests, and restart:

```bash
sudo systemctl restart careerpulse
sudo systemctl reload nginx
sudo journalctl -u careerpulse -n 100 --no-pager
```

Rollback by restoring the previous application directory and matching virtual
environment, then restart the service. Never delete the state directory as part
of a code rollback.

## 11. Known first-stage limitations

- Legacy REST routes that use PostgreSQL still require an existing database and
  the owner-approved `student_profile`, `job_clean`, `job_type_profile`, and
  `job_type_graph_edge` schemas/data.
- The repository does not contain ProfileAgent and JobAgent Prompt files; real
  LLM execution for those stages falls back until the genuine assets are restored.
- Outbound TBox chat cannot succeed without tenant credentials and live network
  validation.
- This first stage has no database readiness endpoint, PostgreSQL connection
  pool, general-purpose application rate limiter, or multi-worker guarantee.
  M1 login attempts have a database-backed limiter only.
- Most legacy and Agent REST routes do not yet have application-level auth.
  Restrict access with ECS security rules, Nginx policy, or an API gateway until
  that work is explicitly authorized.
- The Vue SPA is served by Nginx as described in section 12; only the M3 Web
  business API (`/api/web/v1`) and the M1 auth API (`/api/auth`) are covered by
  session + CSRF enforcement.

## 12. Frontend SPA and side-port rollout (M3)

The browser build is static. Build it on a machine with Node.js 20+ and copy the
result, or build on the ECS host:

```bash
cd /opt/careerpulse/app/front
npm ci
npm run build
```

Serve `front/dist` with `deploy/nginx/careerpulse-web.conf`. That site:

- serves the SPA with `try_files $uri /index.html`;
- proxies `/api/` to the same backend upstream, preserving `Host`,
  `X-Forwarded-Proto`, cookies and the `X-CSRF-Token` header, so the HttpOnly
  session cookie and the CSRF cookie work unchanged on a single origin;
- caches only the content-hashed `/assets/` bundle.

Install it next to the API site (same steps as section 8, using
`careerpulse-web.conf` and the certificate for the browser domain).

### Side-port rollout

The browser API must never be validated for the first time against the live
service. Start the candidate build on a side port and switch traffic only after
its checks pass:

1. Keep the running service on `127.0.0.1:8000`. Start the candidate on
   `127.0.0.1:8001` with the same protected environment file and the same
   `A02_STATE_DB_PATH`.
2. Exercise it directly, never through the public hostname: register a throwaway
   account, then check `GET /api/web/v1/workflows` returns 401 without a cookie
   and 200 with the session cookie, and `POST /api/web/v1/workflows` returns 403
   without the CSRF header.
3. Point the Nginx upstream `careerpulse_backend` at `127.0.0.1:8001`, run
   `nginx -t`, then `systemctl reload nginx`.
4. After the browser flow is confirmed, make the side instance the real service
   (systemd unit listening on 8001, or restart the main unit on 8000 and move
   the upstream back).

Rollback is the same switch in reverse: point `careerpulse_backend` back to the
previous port, `nginx -t`, `systemctl reload nginx`. Both instances share
`A02_STATE_DB_PATH`, so rolling back code does not roll back or delete user
data; never delete `/var/lib/careerpulse` during a rollback.
