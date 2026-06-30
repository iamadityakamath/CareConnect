#!/usr/bin/env python3
"""
Apply SQL migration files from sql/migrations/ to Supabase Postgres.

Requires DATABASE_URL in .env.

Usage:
    pip install -r requirements-setup.txt
    python scripts/apply_migrations.py
    python scripts/apply_migrations.py sql/migrations/002_add_login_code.sql
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "sql" / "migrations"
load_dotenv(ROOT / ".env")


def _connect(database_url: str):
    try:
        import psycopg

        return psycopg.connect(database_url, autocommit=True)
    except ImportError:
        pass

    try:
        import psycopg2

        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        return conn
    except ImportError as exc:
        raise ImportError(
            "Install database driver: pip install -r requirements-setup.txt"
        ) from exc


def migration_files(explicit: list[str] | None) -> list[Path]:
    if explicit:
        paths = []
        for item in explicit:
            path = Path(item)
            if not path.is_absolute():
                path = ROOT / path
            if not path.is_file():
                raise FileNotFoundError(f"Migration not found: {path}")
            paths.append(path)
        return paths

    if not MIGRATIONS_DIR.is_dir():
        return []
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def apply_migration(conn, path: Path) -> None:
    sql = path.read_text()
    print(f"Applying {path.relative_to(ROOT)} ...")
    with conn.cursor() as cur:
        cur.execute(sql)
    print(f"  OK  {path.name}")


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL missing from .env")
        print("Supabase Dashboard -> Project Settings -> Database -> Connection string")
        sys.exit(1)

    try:
        paths = migration_files(sys.argv[1:] or None)
    except FileNotFoundError as exc:
        print(exc)
        sys.exit(1)

    if not paths:
        print(f"No migration files found in {MIGRATIONS_DIR}")
        sys.exit(0)

    try:
        conn = _connect(database_url)
    except ImportError as exc:
        print(exc)
        sys.exit(1)

    try:
        for path in paths:
            try:
                apply_migration(conn, path)
            except Exception as exc:
                message = str(exc)
                if "already exists" in message.lower():
                    print(f"  SKIP {path.name} (already applied)")
                else:
                    print(f"  FAIL {path.name}: {message}")
                    sys.exit(1)
        print("Migrations finished.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
