#!/usr/bin/env python3
"""
Audit Supabase data for CareConnect caregiver + patient provisioning.

Checks users, relationships, auth alignment, and optional PillBox profiles.
Runs a create-verify-cleanup provision test unless --skip-live-test is passed.

Requires in .env:
  SUPABASE_URL
  SUPABASE_SERVICE_KEY
  SUPABASE_ANON_KEY

Usage:
    python scripts/audit_supabase.py
    python scripts/audit_supabase.py --skip-live-test
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app.config import get_settings
from app.database import get_supabase_client
from app.db_utils import first_row
from app.services import auth_service


def _short(value: str | None, length: int = 8) -> str:
    if not value:
        return "?"
    return value if len(value) <= length else f"{value[:length]}…"


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def _ok(message: str) -> None:
    print(f"  OK   {message}")


def _warn(message: str) -> None:
    print(f"  WARN {message}")


def _fail(message: str) -> None:
    print(f"  FAIL {message}")


def probe_tables(db) -> dict[str, bool]:
    from app.schema_compat import CARECONNECT_TABLE_COLUMNS, get_table_columns

    available: dict[str, bool] = {}
    for table in sorted(CARECONNECT_TABLE_COLUMNS):
        try:
            get_table_columns(db, table)
            available[table] = True
            _ok(f"{table} — accessible")
        except Exception as exc:
            available[table] = False
            message = exc
            if hasattr(exc, "args") and exc.args:
                arg = exc.args[0]
                if isinstance(arg, dict):
                    message = arg.get("message", exc)
            _fail(f"{table} — {message}")

    for table, col in [("profiles", "id"), ("patients", "id")]:
        try:
            db.table(table).select(col).limit(1).execute()
            available[table] = True
            _ok(f"{table} — accessible (PillBox optional)")
        except Exception:
            available[table] = False
            _warn(f"{table} — not present (CareConnect-only database)")
    return available


def audit_core_tables(db) -> tuple[list[dict], list[dict], list[dict]]:
    users = db.table("users").select("*").order("created_at", desc=True).execute().data or []
    caregivers = [u for u in users if u.get("role") == "caregiver"]
    elders = [u for u in users if u.get("role") == "elder"]
    rels = db.table("relationships").select("*").order("created_at", desc=True).execute().data or []
    active_rels = [r for r in rels if r.get("status") == "active"]

    print(f"  users total: {len(users)} (caregivers={len(caregivers)}, elders={len(elders)})")
    print(f"  relationships total: {len(rels)} (active={len(active_rels)})")

    if users:
        _ok("users table has data")
    else:
        _warn("No rows in users table")

    if caregivers and elders and active_rels:
        _ok("At least one caregiver, elder, and active relationship exist")
    elif elders and not active_rels:
        _warn("Elders exist but no active relationships")
    elif not elders:
        _warn("No elder profiles in users table yet")

    return users, rels, active_rels


def audit_referential_integrity(users: list[dict], rels: list[dict]) -> int:
    user_ids = {u["id"] for u in users}
    issues = 0

    for rel in rels:
        caregiver_id = rel.get("caregiver_id")
        elder_id = rel.get("elder_id")
        rel_label = _short(rel.get("id"))

        if caregiver_id not in user_ids:
            _fail(f"relationship {rel_label} caregiver missing from users")
            issues += 1
        if elder_id not in user_ids:
            _fail(f"relationship {rel_label} elder missing from users")
            issues += 1

        caregiver = next((u for u in users if u["id"] == caregiver_id), None)
        elder = next((u for u in users if u["id"] == elder_id), None)
        if caregiver and caregiver.get("role") != "caregiver":
            _fail(f"relationship {rel_label} caregiver has role={caregiver.get('role')}")
            issues += 1
        if elder and elder.get("role") != "elder":
            _fail(f"relationship {rel_label} elder has role={elder.get('role')}")
            issues += 1

    if not rels:
        _warn("No relationships to validate")
    elif issues == 0:
        _ok("All relationships point to valid caregiver + elder users")

    return issues


def audit_elder_profiles(elders: list[dict]) -> int:
    issues = 0
    for elder in elders:
        label = _short(elder.get("id"))
        auth_email = elder.get("auth_email") or ""
        if not auth_email.startswith("patient."):
            _fail(f"elder {label}: auth_email should start with patient.")
            issues += 1
        if elder.get("email") is not None:
            _warn(f"elder {label}: email field is set (expected null for managed patients)")
        if not elder.get("last_name"):
            _fail(f"elder {label}: missing last_name")
            issues += 1
        if elder.get("account_status") not in ("managed", "active"):
            _fail(f"elder {label}: unexpected account_status={elder.get('account_status')}")
            issues += 1
        if not elder.get("login_code_set_at"):
            _warn(f"elder {label}: login_code_set_at not set")

    if elders and issues == 0:
        _ok("All elder profiles have expected auth_email, last_name, account_status")

    return issues


def audit_profiles_table(db, users: list[dict], elders: list[dict]) -> int:
    profiles = db.table("profiles").select("id, role").execute().data or []
    profile_ids = {p["id"] for p in profiles}
    print(f"  profiles total: {len(profiles)}")

    issues = 0
    missing = [u for u in users if u["id"] not in profile_ids]
    if missing:
        _warn(f"{len(missing)} users row(s) have no matching profiles row")
        issues += 1
    else:
        _ok("Every users row has a matching profiles row")

    for elder in elders[:5]:
        profile = next((p for p in profiles if p["id"] == elder["id"]), None)
        label = _short(elder.get("id"))
        if not profile:
            _warn(f"elder {label}: no profiles row")
            issues += 1
        elif profile.get("role") != "patient":
            _warn(f"elder {label}: profiles.role={profile.get('role')} (expected patient)")
            issues += 1
        else:
            _ok(f"elder {label}: profiles.role=patient")

    return issues


def audit_auth_alignment(db, users: list[dict], domain: str) -> int:
    issues = 0
    for user in users[:8]:
        user_id = user["id"]
        label = _short(user_id)
        try:
            auth_user = db.auth.admin.get_user_by_id(user_id).user
        except Exception:
            _fail(f"user {label}: auth lookup failed")
            issues += 1
            continue

        if not auth_user:
            _fail(f"user {label}: missing auth.users row")
            issues += 1
            continue

        if user.get("role") == "elder":
            email_ok = domain in (auth_user.email or "")
            if email_ok:
                _ok(f"elder {label}: auth.users exists")
            else:
                _fail(f"elder {label}: unexpected auth email domain")
                issues += 1
        else:
            _ok(f"caregiver {label}: auth.users exists")

    return issues


def print_sample_links(users: list[dict], active_rels: list[dict]) -> None:
    for rel in active_rels[:5]:
        caregiver = next((u for u in users if u["id"] == rel["caregiver_id"]), {})
        elder = next((u for u in users if u["id"] == rel["elder_id"]), {})
        caregiver_label = _short(caregiver.get("id"))
        elder_label = _short(elder.get("id"))
        print(
            f"  • caregiver {caregiver_label} → elder {elder_label} "
            f"(last={elder.get('last_name') or '?'}) | rel={_short(rel.get('id'))} status={rel.get('status')}"
        )


def run_live_provision_test(db, users: list[dict]) -> int:
    caregivers = [u for u in users if u.get("role") == "caregiver"]
    if not caregivers:
        _warn("Skipping live test — no caregiver in users table")
        return 0

    caregiver_id = caregivers[0]["id"]
    login_code = str(100000 + (uuid.uuid4().int % 900000))
    last_name = f"Audit{uuid.uuid4().hex[:4]}"
    full_name = f"Audit Patient {last_name}"
    created_user_id: str | None = None
    issues = 0

    try:
        result = auth_service.provision_patient(
            db,
            caregiver_id=caregiver_id,
            full_name=full_name,
            last_name=last_name,
            login_code=login_code,
            phone=None,
        )
        created_user_id = result["patient"]["id"]
        relationship_id = result["relationship_id"]
        _ok(f"provision_patient returned patient={_short(created_user_id)} rel={_short(relationship_id)}")

        user_row = first_row(
            db.table("users").select("*").eq("id", created_user_id).limit(1).execute()
        )
        if not user_row or user_row.get("role") != "elder":
            _fail("users row missing or wrong role after provision")
            issues += 1
        else:
            _ok("users row created with role=elder")

        rel_row = first_row(
            db.table("relationships").select("*").eq("id", relationship_id).limit(1).execute()
        )
        if (
            not rel_row
            or rel_row.get("status") != "active"
            or rel_row.get("caregiver_id") != caregiver_id
        ):
            _fail("relationships row missing or invalid after provision")
            issues += 1
        else:
            _ok("relationships row created active + linked to caregiver")

        auth_user = db.auth.admin.get_user_by_id(created_user_id).user
        if not auth_user or f"patient.{created_user_id}" not in (auth_user.email or ""):
            _fail("auth.users row missing or wrong email after provision")
            issues += 1
        else:
            _ok("auth.users row exists with patient.* email")

        profile_row = first_row(
            db.table("profiles").select("id, role").eq("id", created_user_id).limit(1).execute()
        )
        if profile_row:
            _ok(f"profiles row created via trigger (role={profile_row.get('role')})")
        else:
            _warn("profiles row missing after provision (trigger may not have fired)")
            issues += 1

        session = auth_service.patient_login(db, last_name, login_code)
        if session.get("access_token"):
            _ok("patient_login works with last_name + login_code")
        else:
            _fail("patient_login did not return access_token")
            issues += 1

    except Exception as exc:
        _fail(f"Live provision test failed: {type(exc).__name__}: {exc}")
        issues += 1
    finally:
        if created_user_id:
            try:
                db.table("relationships").delete().eq("elder_id", created_user_id).execute()
                db.table("users").delete().eq("id", created_user_id).execute()
                db.auth.admin.delete_user(created_user_id)
                _ok("Cleaned up test patient")
            except Exception as cleanup_exc:
                _warn(f"Cleanup issue: {type(cleanup_exc).__name__}")

    return issues


def print_summary() -> None:
    _section("Summary")
    print("  Expected on patient add:")
    print("    1. auth.users     — Supabase login (password = login code)")
    print("    2. users          — app profile (role=elder)")
    print("    3. relationships  — caregiver_id + elder_id, status=active")
    print("    4. profiles       — auto-created by PillBox auth trigger")
    print("  Not filled on add: medications, checkins, contacts, medical_history, patients")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit CareConnect Supabase provisioning data.")
    parser.add_argument(
        "--skip-live-test",
        action="store_true",
        help="Read-only audit; do not create and delete a test patient.",
    )
    args = parser.parse_args()

    settings = get_settings()
    db = get_supabase_client()
    issue_count = 0

    _section("Connection")
    print(f"  Supabase URL: {settings.SUPABASE_URL}")
    _ok("Connected with service role client")

    _section("Table availability")
    available = probe_tables(db)

    _section("CareConnect core tables (users + relationships)")
    users, rels, active_rels = audit_core_tables(db)

    _section("Referential integrity checks")
    issue_count += audit_referential_integrity(users, rels)

    elders = [u for u in users if u.get("role") == "elder"]
    _section("Elder profile field checks")
    issue_count += audit_elder_profiles(elders)

    if available.get("profiles"):
        _section("PillBox profiles table (auth trigger side effect)")
        issue_count += audit_profiles_table(db, users, elders)
    else:
        _warn("profiles table not available — skipping PillBox trigger audit")

    _section("Auth users vs users table alignment")
    issue_count += audit_auth_alignment(db, users, settings.PATIENT_AUTH_EMAIL_DOMAIN)

    _section("Sample active caregiver → patient links")
    if active_rels:
        print_sample_links(users, active_rels)
    else:
        _warn("No active relationships to display")

    if not args.skip_live_test:
        _section("Live end-to-end provision test (create → verify → cleanup)")
        issue_count += run_live_provision_test(db, users)
    else:
        _warn("Skipped live provision test (--skip-live-test)")

    print_summary()

    if issue_count:
        print(f"\nAudit finished with {issue_count} issue(s).")
        return 1

    print("\nAudit finished — all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
