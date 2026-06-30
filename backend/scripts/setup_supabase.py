#!/usr/bin/env python3
"""
Apply CareConnect schema to Supabase Postgres.

Requires DATABASE_URL in .env.

Find it in Supabase Dashboard:
  1. Open your project
  2. Click the green "Connect" button (top of the page)
  3. Choose "Session pooler" or "Direct connection"
  4. Copy the URI and replace [YOUR-PASSWORD] with your database password

Or skip this script and paste sql/schema.sql into Supabase → SQL Editor instead.

Usage:
    pip install -r requirements-setup.txt
    python scripts/setup_supabase.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _connect(database_url: str):
    """Connect with psycopg v3 (preferred) or psycopg2."""
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


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL missing from .env")
        print("   Supabase Dashboard → Project Settings → Database → Connection string (URI)")
        sys.exit(1)

    try:
        conn = _connect(database_url)
    except ImportError as exc:
        print(f"❌ {exc}")
        sys.exit(1)

    schema_path = ROOT / "sql" / "schema.sql"
    sql = schema_path.read_text()

    print(f"Applying schema from {schema_path} ...")
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        print("✅ Schema applied successfully.")
    except Exception as exc:
        message = str(exc)
        if "already exists" in message:
            print("⚠️  Some schema objects already exist. Drop conflicting objects or use a fresh database.")
            print(f"   Details: {message}")
        else:
            print(f"❌ Schema apply failed: {message}")
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
