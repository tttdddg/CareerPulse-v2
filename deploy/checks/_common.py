"""Shared helpers for the CareerPulse pre-release checks.

Every check script lives in this directory, imports ``_common`` and therefore
works no matter where the repository sits on disk. Nothing here ever prints a
credential.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def repo_root() -> Path:
    """Walk upwards until the backend application is found."""

    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "backend" / "app" / "main.py").is_file():
            return candidate
    raise RuntimeError("could not locate the repository root from " + str(here))


ROOT = repo_root()
BACKEND = ROOT / "backend"
MIGRATIONS = BACKEND / "migrations"
STATE_DB_DEFAULT = BACKEND / ".runtime" / "career_state.sqlite3"


def add_backend_to_path() -> None:
    """Make ``app.*`` importable exactly like the backend process does."""

    path = str(BACKEND)
    if path not in sys.path:
        sys.path.insert(0, path)


def load_postgres_env() -> None:
    """Read POSTGRES_* out of the local or system env file, never echoing a value.

    Development machines keep them in ``backend/.env``; the ECS host keeps them
    in the protected systemd EnvironmentFile. The application itself never
    calls load_dotenv, so the checks inject exactly what the service would get.
    """

    candidates = (
        BACKEND / ".env",
        Path("/etc/careerpulse/careerpulse.env"),
    )
    env_file = next((path for path in candidates if path.exists()), None)
    if env_file is None:
        print("[warn] no backend/.env and no /etc/careerpulse/careerpulse.env; "
              "relying on process environment")
        return
    loaded = 0
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("POSTGRES_"):
            if key in os.environ:
                continue
            os.environ[key] = value.strip()
            loaded += 1
    print(f"[env] read {loaded} POSTGRES_* value(s) from {env_file} (values hidden)")


def state_db_path() -> Path:
    """Resolve the state database the same way app.db_state does."""

    configured = os.getenv("A02_STATE_DB_PATH")
    return Path(configured).resolve() if configured else STATE_DB_DEFAULT


__all__ = [
    "BACKEND",
    "MIGRATIONS",
    "ROOT",
    "STATE_DB_DEFAULT",
    "add_backend_to_path",
    "load_postgres_env",
    "repo_root",
    "state_db_path",
]
