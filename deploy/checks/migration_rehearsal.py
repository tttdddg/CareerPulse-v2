"""Rehearse the PostgreSQL migrations against a real, non-production database.

Usage:
    python deploy/checks/migration_rehearsal.py probe   # read-only snapshot
    python deploy/checks/migration_rehearsal.py apply   # run V008, assert only identity.* appears
    python deploy/checks/migration_rehearsal.py link    # run V009, assert only the link table appears
    python deploy/checks/migration_rehearsal.py rerun   # run both again: must be a no-op

The scripts carry their own BEGIN/COMMIT, so on the server the same files can
be executed with ``psql -f``. This check exists because every migration must be
proved additive before it touches a shared database.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    MIGRATIONS,
    add_backend_to_path,
    load_postgres_env,
)

add_backend_to_path()


def snapshot(connection) -> dict[str, int]:
    """Return {schema.table: rowcount} for every user table."""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT n.nspname || '.' || c.relname
              FROM pg_catalog.pg_class c
              JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
             WHERE c.relkind = 'r'
               AND n.nspname NOT IN ('pg_catalog', 'information_schema')
             ORDER BY 1
            """
        )
        tables = [row[0] for row in cursor.fetchall()]
        counts: dict[str, int] = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 - catalog names
            counts[table] = int(cursor.fetchone()[0])
    return counts


def snapshot_with_pool() -> dict[str, int]:
    from app.db import business_connection

    with business_connection() as connection:
        return snapshot(connection)


def probe() -> None:
    from app.db import business_connection

    with business_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0].split(",")[0]
        cursor.execute("SELECT current_database(), current_user")
        database, user = cursor.fetchone()
        cursor.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname = 'identity'"
        )
        identity_exists = cursor.fetchone() is not None
        cursor.execute(
            "SELECT to_regclass('public.student_profile') IS NOT NULL"
        )
        has_student_profile = cursor.fetchone()[0]
        cursor.execute(
            "SELECT count(*) FROM public.student_profile" if has_student_profile
            else "SELECT 0"
        )
        student_rows = cursor.fetchone()[0]

    print(f"server     : {version}")
    print(f"database   : {database}  (user: {user})")
    print(f"identity schema already exists : {identity_exists}")
    print(f"public.student_profile exists  : {bool(has_student_profile)}"
          f"  rows={student_rows}")
    counts = snapshot_with_pool()
    print(f"existing tables                : {len(counts)}")


def run_migration(filename: str, expected_tables: list[str], label: str) -> None:
    from app.db import business_connection

    migration = MIGRATIONS / filename
    if not migration.exists():
        raise SystemExit(f"migration file not found: {migration}")
    sql = io.open(migration, encoding="utf-8").read()

    before = snapshot_with_pool()
    print(f"[before] {len(before)} tables")

    with business_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        # The file carries its own BEGIN/COMMIT; this extra commit is a safety
        # net in case the driver still believes a transaction is open. It must
        # run inside the block: business_connection() rolls back on exit.
        connection.commit()

    after = snapshot_with_pool()
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = {
        name: (before[name], after[name])
        for name in sorted(set(before) & set(after))
        if before[name] != after[name]
    }

    print(f"[after ] {len(after)} tables")
    print(f"added   : {added}")
    print(f"removed : {removed}")
    print(f"rowcount changed on existing tables: {changed or 'none'}")

    if expected_tables:
        with business_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename, indexname
                  FROM pg_indexes
                 WHERE schemaname = 'identity'
                 ORDER BY tablename, indexname
                """
            )
            indexes = cursor.fetchall()
            cursor.execute(
                """
                SELECT conname, contype
                  FROM pg_constraint
                 WHERE connamespace = 'identity'::regnamespace
                 ORDER BY conname
                """
            )
            constraints = cursor.fetchall()

        print("indexes   :")
        for table, index in indexes:
            print(f"  {table:<24} {index}")
        print("constraints:")
        for name, kind in constraints:
            print(f"  [{kind}] {name}")

    assert not removed, "a table disappeared!"
    assert not changed, "an existing table's rowcount changed!"
    assert added == sorted(expected_tables), (
        f"{label}: expected exactly {expected_tables}, got {added}"
    )
    if expected_tables:
        print(f"\n{label} OK: {', '.join(expected_tables)} created, "
              "no existing table touched.")
    else:
        print(f"\n{label} OK: re-run is a no-op, "
              f"{len(after)} tables unchanged.")


def apply() -> None:
    run_migration(
        "V008__create_identity_auth.sql",
        [
            "identity.app_user",
            "identity.auth_session",
            "identity.auth_login_attempt",
        ],
        "V008",
    )


def link() -> None:
    run_migration(
        "V009__link_users_to_student_profiles.sql",
        ["identity.user_student_profile"],
        "V009",
    )


def rerun() -> None:
    """A second run must be a no-op: deployment scripts sometimes run twice."""
    run_migration("V008__create_identity_auth.sql", [], "V008 re-run")
    run_migration("V009__link_users_to_student_profiles.sql", [], "V009 re-run")


COMMANDS = {
    "probe": probe,
    "apply": apply,
    "link": link,
    "rerun": rerun,
}


def main() -> int:
    load_postgres_env()
    command = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if command not in COMMANDS:
        raise SystemExit(
            f"unknown command: {command} (choose from {sorted(COMMANDS)})"
        )
    COMMANDS[command]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
