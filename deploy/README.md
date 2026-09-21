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
- Do not expose TCP 8000 or the PostgreSQL 16 business port 5433 to the internet.

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

PostgreSQL 16 is required for production business-data reads. It may be omitted
only for an explicitly labelled Demo deployment that does not claim production
database capability. Install or connect to the owner-approved prepared database:

```bash
sudo apt install -y postgresql postgresql-contrib
```

Do not run `scripts/init_a02_data.py --apply` against an empty PostgreSQL
database: migration V001 references the pre-existing `student_profile` table.

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
4. Use `A02_DEMO_MODE=true` only for a labelled Demo deployment. Production
   must set it to `false`; a database failure then fails closed without JSON.
5. A single-instance deployment may keep `A02_STATE_DB_PATH` and leave
   `A02_DATABASE_URL` empty. Configure exactly one of them.
6. Leave outbound TBox values empty unless a real tenant issued the credentials;
   `/api/tbox/chat` will then return a controlled 503 instead of making a call.
7. For production, configure the PostgreSQL 16 business source with
   `POSTGRES_PORT=5433`, `POSTGRES_DATABASE=careerpulse_micro`, the approved
   host/user, and a protected password. The application reads
   `POSTGRES_DATABASE`; do not use `POSTGRES_DB`.

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

- Production database tools and the database-backed Agent path require
  PostgreSQL 16 `careerpulse_micro` with the owner-approved `student_profile`,
  `job_clean`, `job_type_profile`, and `job_type_graph_edge` schemas/data.
- The repository does not contain ProfileAgent and JobAgent Prompt files; real
  LLM execution for those stages falls back until the genuine assets are restored.
- Outbound TBox chat cannot succeed without tenant credentials and live network
  validation.
- This stage has no dedicated business-database readiness endpoint, application
  rate limiter, or multi-worker guarantee. Run the documented preflight and
  read-only Provider checks before enabling traffic.
- Most legacy and Agent REST routes do not yet have application-level auth.
  Restrict access with ECS security rules, Nginx policy, or an API gateway until
  that work is explicitly authorized.
- No Vue frontend is installed or served by this deployment.
