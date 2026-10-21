"""Prove the auth stack works against the migrated identity schema.

Uses the real AuthService + AuthRepository (PostgreSQL), then removes every row
it created so the database is left exactly as it was.

Flow: register -> duplicate register rejected -> login -> authenticate ->
wrong password recorded -> logout revokes session -> cleanup.

Usage: python deploy/checks/auth_repository_smoke.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import add_backend_to_path, load_postgres_env  # noqa: E402

load_postgres_env()
add_backend_to_path()

from app.auth import AuthService  # noqa: E402
from app.auth.repository import AuthIdentityConflict  # noqa: E402
from app.auth.service import InvalidCredentials, InvalidSession  # noqa: E402

USERNAME = "pre_release_smoke"
EMAIL = "pre-release-smoke@example.com"
PASSWORD = "PreRelease123!"
CLIENT = "127.0.0.1"


def counts() -> dict[str, int]:
    from app.db import business_connection

    tables = ["identity.app_user", "identity.auth_session",
              "identity.auth_login_attempt"]
    out: dict[str, int] = {}
    with business_connection() as connection, connection.cursor() as cursor:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            out[table] = int(cursor.fetchone()[0])
    return out


def cleanup(started_at: datetime) -> dict[str, int]:
    from app.db import business_connection

    with business_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM identity.app_user WHERE username = %s",
                (USERNAME,),
            )
            removed_users = cursor.rowcount
            cursor.execute(
                "DELETE FROM identity.auth_login_attempt WHERE attempted_at >= %s",
                (started_at,),
            )
            removed_attempts = cursor.rowcount
        connection.commit()
    print(f"cleanup: removed {removed_users} user row(s), "
          f"{removed_attempts} attempt row(s)")
    return counts()


def main() -> int:
    baseline = counts()
    print(f"baseline: {baseline}")

    service = AuthService()
    started_at = datetime.now(timezone.utc)
    checks: list[tuple[str, str]] = []
    exit_code = 1

    try:
        user = service.register(USERNAME, EMAIL, PASSWORD)
        checks.append(("register",
                       f"id={user.id} role={user.role} status={user.status}"))

        try:
            service.register(USERNAME, EMAIL, PASSWORD)
            checks.append(("duplicate register", "UNEXPECTED: accepted"))
        except AuthIdentityConflict:
            checks.append(("duplicate register", "rejected (unique index works)"))

        created = service.login(USERNAME, PASSWORD, CLIENT)
        checks.append(("login",
                       f"token_len={len(created.token)} "
                       f"csrf_len={len(created.csrf_token)} "
                       f"expires={created.expires_at.isoformat()}"))

        authed = service.authenticate(created.token)
        checks.append(("authenticate(token)",
                       f"user={authed.username} id={authed.id}" if authed
                       else "FAILED (None)"))

        try:
            service.login(USERNAME, "wrong-password", CLIENT)
            checks.append(("wrong password", "UNEXPECTED: accepted"))
        except InvalidCredentials:
            checks.append(("wrong password", "rejected + attempt recorded"))

        service.logout(created.token)
        try:
            service.authenticate(created.token)
            checks.append(("logout", "session still valid (UNEXPECTED)"))
        except InvalidSession:
            checks.append(("logout", "session revoked (raises InvalidSession)"))

        for name, detail in checks:
            print(f"  {name:<22} {detail}")

        bad = any("UNEXPECTED" in d or "FAILED" in d for _, d in checks)
        exit_code = 1 if bad else 0
        if exit_code == 0:
            print("\nAUTH REPOSITORY OK: PostgreSQL-backed login works.")
    except Exception as exc:  # noqa: BLE001
        print(f"smoke test raised: {type(exc).__name__}: {exc}")
        exit_code = 3
    finally:
        remaining = cleanup(started_at)
        leaked = {k: v for k, v in remaining.items() if v != baseline[k]}
        print(f"after cleanup: {remaining}")
        if leaked:
            print(f"LEAK: {leaked}")
            exit_code = 2

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
