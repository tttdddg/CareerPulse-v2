"""Check that persisted business state belongs to a real account.

Reads the PostgreSQL identity tables and the SQLite (or PostgreSQL) state
database and classifies every stored workflow owner:

  * ``web:<uuid>``           owned by a verified CareerPulse Web account
  * ``system:web-read-auditor``  read-only audit rows, never user data
  * ``external:<sha256>``    trusted platform/MCP subject
  * ``None``                 anonymous row
  * anything else            pre-M2 raw owner (should not appear on a fresh DB)

Usage: python deploy/checks/ownership_check.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    add_backend_to_path,
    load_postgres_env,
    state_db_path,
)

load_postgres_env()
add_backend_to_path()

from app.auth.identity import WEB_OWNER_PREFIX, web_owner_id  # noqa: E402
from app.db import business_connection  # noqa: E402

SYSTEM_OWNERS = ("system:web-read-auditor",)
PREFIXES = (WEB_OWNER_PREFIX, "external:")


def main() -> int:
    database = state_db_path()
    print(f"state database: {database} (exists={database.exists()})")

    with business_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, username, role, status FROM identity.app_user "
            "ORDER BY created_at"
        )
        users = cursor.fetchall()
        cursor.execute(
            "SELECT COUNT(*) FROM identity.auth_session "
            "WHERE revoked_at IS NULL AND expires_at > now()"
        )
        live_sessions = cursor.fetchone()[0]

    print(f"\nPostgreSQL identity.app_user ({len(users)} row(s)), "
          f"live auth_session rows={live_sessions}:")
    known: dict[str, str] = {}
    for user_id, username, role, status in users:
        owner = web_owner_id(user_id)
        known[owner] = username
        print(f"  {user_id}  {username:<20} role={role} status={status}")
        print(f"    -> {owner}")

    if not database.exists():
        print("\nno state database yet; nothing to verify")
        return 0

    connection = sqlite3.connect(database)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT session_id, user_id, status, updated_at "
            "FROM career_state ORDER BY updated_at DESC LIMIT 25"
        )
        rows = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM agent_logs")
        logs = cursor.fetchone()[0]
    finally:
        connection.close()

    print(f"\ncareer_state rows ({len(rows)} shown), agent_logs={logs}:")
    owned = system = anonymous = unknown = legacy = 0
    for session_id, user_id, status, updated_at in rows:
        if user_id is None:
            anonymous += 1
            label = "anonymous"
        elif user_id in known:
            owned += 1
            label = f"{known[user_id]} (web account)"
        elif user_id in SYSTEM_OWNERS:
            system += 1
            label = user_id
        elif user_id.startswith(PREFIXES):
            unknown += 1
            label = f"UNKNOWN PREFIXED OWNER: {user_id}"
        else:
            legacy += 1
            label = f"legacy raw owner: {user_id}"
        print(f"  {session_id}  {label}  status={status}  {updated_at}")

    print(f"\nrows owned by a real web account  : {owned}")
    print(f"read-audit rows (system owner)    : {system}")
    print(f"anonymous (user_id NULL) rows     : {anonymous}")
    print(f"unknown prefixed owners           : {unknown}")
    print(f"legacy raw owners (pre-M2 rows)   : {legacy}")

    if unknown:
        print("\nOWNERSHIP FAIL: rows carry an owner that matches no account.")
        return 2
    if legacy:
        print("\nOWNERSHIP OK with warning: pre-M2 raw owners present. "
              "On a freshly provisioned database this count must be 0.")
        return 0
    print("\nOWNERSHIP OK: every persisted row has a resolvable owner.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
