"""Drive the FastAPI auth routes against the real PostgreSQL repository.

The unit test suite builds AuthService with MemoryAuthRepository, so cookies,
CSRF and status codes have never been covered against a database. This check
closes that gap through TestClient, then proves the rows reached PostgreSQL and
removes every row it created.

Usage: python deploy/checks/web_http_smoke.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import add_backend_to_path, load_postgres_env  # noqa: E402

load_postgres_env()
add_backend_to_path()

from fastapi.testclient import TestClient  # noqa: E402

from app.db import business_connection  # noqa: E402
from app.main import create_app  # noqa: E402

USERNAME = "http_smoke"
EMAIL = "http-smoke@example.com"
PASSWORD = "HttpSmoke123!"
WRONG = "wrong-password"
SESSION_COOKIE = "careerpulse_session"
CSRF_COOKIE = "careerpulse_csrf"
ORIGIN = "http://localhost:5173"


def counts() -> dict[str, int]:
    tables = ["identity.app_user", "identity.auth_session",
              "identity.auth_login_attempt"]
    out: dict[str, int] = {}
    with business_connection() as connection, connection.cursor() as cursor:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            out[table] = int(cursor.fetchone()[0])
    return out


def cleanup(started_at: datetime) -> dict[str, int]:
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


def pg_row_exists() -> tuple[bool, bool]:
    """(user row in PostgreSQL, session row in PostgreSQL)."""

    with business_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM identity.app_user WHERE username = %s",
            (USERNAME,),
        )
        users = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM identity.auth_session")
        sessions = int(cursor.fetchone()[0])
    return users > 0, sessions > 0


def main() -> int:
    baseline = counts()
    print(f"baseline: {baseline}")

    checks: list[tuple[str, str]] = []
    exit_code = 1
    started_at = datetime.now(timezone.utc)

    try:
        app = create_app()
        # https keeps the Secure session cookie acceptable, matching production.
        with TestClient(app, base_url="https://testserver") as client:
            response = client.get("/api/auth/me")
            checks.append(("anonymous GET /me", str(response.status_code)))

            response = client.post(
                "/api/auth/register",
                json={"username": USERNAME, "email": EMAIL,
                      "password": PASSWORD},
                headers={"Origin": ORIGIN},
            )
            checks.append(("register", str(response.status_code)))
            checks.append(("register CORS header",
                           str(response.headers.get("access-control-allow-origin"))))

            response = client.post(
                "/api/auth/register",
                json={"username": USERNAME, "email": EMAIL,
                      "password": PASSWORD},
            )
            checks.append(("duplicate register", str(response.status_code)))

            response = client.post(
                "/api/auth/login",
                json={"identifier": USERNAME, "password": PASSWORD},
            )
            login_cookies = response.headers.get_list("set-cookie")
            session_flag_line = next(
                (cookie for cookie in login_cookies
                 if cookie.lower().startswith(SESSION_COOKIE)),
                "",
            )
            checks.append(("login", str(response.status_code)))
            checks.append(("session cookie flags",
                           f"Secure={('Secure' in session_flag_line)}, "
                           f"HttpOnly={('HttpOnly' in session_flag_line)}, "
                           f"SameSite=lax="
                           f"{('SameSite=lax' in session_flag_line)}"))
            csrf = client.cookies.get(CSRF_COOKIE, "")

            response = client.get("/api/auth/me")
            body = (response.json().get("user", {})
                    if response.status_code == 200 else {})
            checks.append(("GET /me",
                           f"{response.status_code} user={body.get('username')}"))
            in_pg_user, in_pg_session = pg_row_exists()
            checks.append(("rows in PostgreSQL",
                           f"user={in_pg_user} session={in_pg_session}"))

            response = client.post(
                "/api/auth/login",
                json={"identifier": USERNAME, "password": WRONG},
            )
            checks.append(("wrong password", str(response.status_code)))

            response = client.post("/api/auth/logout")
            checks.append(("logout w/o CSRF", str(response.status_code)))

            response = client.post(
                "/api/auth/logout",
                headers={"X-CSRF-Token": csrf, "Origin": ORIGIN},
            )
            checks.append(("logout (with CSRF)", str(response.status_code)))

            response = client.get("/api/auth/me")
            checks.append(("GET /me after logout", str(response.status_code)))

            for name, detail in checks:
                print(f"  {name:<26} {detail}")

            expected = {
                "anonymous GET /me": "401",
                "register": "201",
                "duplicate register": "409",
                "login": "200",
                "wrong password": "401",
                "logout w/o CSRF": "403",
                "logout (with CSRF)": "204",
                "GET /me after logout": "401",
            }
            bad = []
            for name, want in expected.items():
                got = next((d for n, d in checks if n == name), None)
                if got != want:
                    bad.append(f"{name}: want {want} got {got}")

            me_detail = next((d for n, d in checks if n == "GET /me"), "")
            if not me_detail.startswith("200") or f"user={USERNAME}" not in me_detail:
                bad.append(f"GET /me: unexpected {me_detail!r}")
            if not (in_pg_user and in_pg_session):
                bad.append("auth rows never reached PostgreSQL (memory fallback?)")
            if not login_cookies:
                bad.append("login set no cookies")
            elif not (SESSION_COOKIE in session_flag_line
                      and "Secure" in session_flag_line
                      and "HttpOnly" in session_flag_line):
                bad.append(f"session cookie flags wrong: {session_flag_line!r}")
            if not csrf:
                bad.append("CSRF cookie missing after login")

            if bad:
                print("FAIL: " + "; ".join(bad))
                exit_code = 1
            else:
                print("\nWEB HTTP SMOKE OK: routes, cookies, CSRF and "
                      "PostgreSQL all agree.")
                exit_code = 0
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
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
