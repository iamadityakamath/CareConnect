from datetime import date

from supabase import Client

from app.db_utils import first_row, public_user
from app.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.pillbox_compat import (
    enrich_elder_profile,
    fetch_user_row,
    filter_users_payload,
    split_profile_updates,
    update_pillbox_patient_details,
    users_select_expr,
)

ALLOWED_PROFILE_UPDATES = frozenset({
    "full_name", "last_name", "phone", "timezone", "date_of_birth", "address", "notes",
})


def _get_user_profile(db: Client, user_id: str) -> dict:
    """Fetch a user profile row by id."""
    profile = fetch_user_row(db, user_id)
    if not profile:
        raise NotFoundError("User not found")
    profile = enrich_elder_profile(db, profile)
    return public_user(profile)


def get_me_profile(db: Client, user_id: str, auth_user: dict) -> dict:
    """Return current user profile merged from Supabase auth and users table."""
    profile = fetch_user_row(db, user_id)
    if profile:
        profile = enrich_elder_profile(db, profile)
        return public_user(profile)
    return public_user(auth_user)


def create_user_profile(
    db: Client,
    user_id: str,
    email: str | None,
    auth_email: str,
    full_name: str,
    last_name: str,
    role: str,
    phone: str | None,
    timezone: str | None = None,
) -> dict:
    """Create a user profile row after Supabase signup."""
    existing = first_row(
        db.table("users").select("id").eq("id", user_id).limit(1).execute()
    )
    if existing:
        raise ValidationError("User profile already exists")

    payload = {
        "id": user_id,
        "email": email,
        "auth_email": auth_email,
        "full_name": full_name,
        "last_name": last_name.strip(),
        "role": role,
        "phone": phone,
        "account_status": "active",
    }
    if timezone:
        payload["timezone"] = timezone

    result = db.table("users").insert(payload).execute()
    if not result.data:
        raise ValidationError("Failed to create user profile")
    return public_user(result.data[0])


def get_user_profile(db: Client, user_id: str, requester_id: str) -> dict:
    """Fetch a user profile if requester is self or linked caregiver/elder."""
    if user_id != requester_id:
        _verify_linked(db, requester_id, user_id)
    return _get_user_profile(db, user_id)


def update_user_profile(
    db: Client, user_id: str, requester_id: str, updates: dict
) -> dict:
    """Update profile fields for self, or for a linked patient when requester is their caregiver."""
    profile = fetch_user_row(db, user_id)
    if not profile:
        raise NotFoundError("User not found")

    if user_id != requester_id:
        if profile.get("role") == "elder":
            verify_caregiver_for_elder(db, requester_id, user_id)
        else:
            raise ForbiddenError("Can only update your own profile")

    filtered = {
        k: v for k, v in updates.items()
        if v is not None and k in ALLOWED_PROFILE_UPDATES
    }
    if not filtered:
        return _get_user_profile(db, user_id)

    if "last_name" in filtered:
        filtered["last_name"] = filtered["last_name"].strip()

    if "date_of_birth" in filtered and filtered["date_of_birth"] is not None:
        dob = filtered["date_of_birth"]
        filtered["date_of_birth"] = dob.isoformat() if isinstance(dob, date) else str(dob)[:10]

    users_updates, patients_updates = split_profile_updates(db, filtered)

    if users_updates:
        result = (
            db.table("users")
            .update(users_updates)
            .eq("id", user_id)
            .execute()
        )
        if not result.data:
            raise NotFoundError("User not found")

    if patients_updates and profile.get("role") == "elder":
        caregiver_id = requester_id
        if user_id == requester_id:
            rel = first_row(
                db.table("relationships")
                .select("caregiver_id")
                .eq("elder_id", user_id)
                .eq("status", "active")
                .limit(1)
                .execute()
            )
            if rel:
                caregiver_id = rel["caregiver_id"]
        update_pillbox_patient_details(db, user_id, caregiver_id, patients_updates)

    return _get_user_profile(db, user_id)


def _verify_linked(db: Client, user_a: str, user_b: str) -> None:
    """Verify two users share an active relationship."""
    result = (
        db.table("relationships")
        .select("id")
        .eq("status", "active")
        .or_(
            f"and(caregiver_id.eq.{user_a},elder_id.eq.{user_b}),"
            f"and(caregiver_id.eq.{user_b},elder_id.eq.{user_a})"
        )
        .limit(1)
        .execute()
    )
    if not result.data:
        raise ForbiddenError("No active relationship between users")


def verify_caregiver_for_elder(db: Client, caregiver_id: str, elder_id: str) -> None:
    """Verify caregiver has an active relationship with the elder."""
    result = (
        db.table("relationships")
        .select("id")
        .eq("caregiver_id", caregiver_id)
        .eq("elder_id", elder_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not result.data:
        raise ForbiddenError("Not authorized for this elder")


def verify_elder_access(db: Client, requester_id: str, elder_id: str, requester_role: str) -> None:
    """Verify requester can access elder data (self or linked caregiver)."""
    if requester_id == elder_id:
        return
    if requester_role == "caregiver":
        verify_caregiver_for_elder(db, requester_id, elder_id)
        return
    raise ForbiddenError("Not authorized to access this elder's data")


def invite_elder(
    db: Client, caregiver_id: str, elder_email: str | None, invite_code: str | None
) -> dict:
    """Create a pending relationship invite to link caregiver and elder."""
    if not elder_email and not invite_code:
        raise ValidationError("Provide elder_email or invite_code")

    elder_id: str | None = None

    if elder_email:
        elder_row = first_row(
            db.table("users")
            .select("id, role")
            .eq("email", elder_email)
            .eq("role", "elder")
            .limit(1)
            .execute()
        )
        if not elder_row:
            raise NotFoundError("Elder not found with that email")
        elder_id = elder_row["id"]
    else:
        rel_row = first_row(
            db.table("relationships")
            .select("*")
            .eq("id", invite_code)
            .eq("status", "pending")
            .limit(1)
            .execute()
        )
        if not rel_row:
            raise NotFoundError("Invalid invite code")
        return rel_row

    existing = first_row(
        db.table("relationships")
        .select("id, status")
        .eq("caregiver_id", caregiver_id)
        .eq("elder_id", elder_id)
        .limit(1)
        .execute()
    )
    if existing:
        if existing["status"] == "active":
            raise ValidationError("Relationship already active")
        return existing

    result = (
        db.table("relationships")
        .insert({
            "caregiver_id": caregiver_id,
            "elder_id": elder_id,
            "status": "pending",
            "created_by": caregiver_id,
        })
        .execute()
    )
    if not result.data:
        raise ValidationError("Failed to create invite")
    return result.data[0]


def accept_relationship(db: Client, relationship_id: str, elder_id: str) -> dict:
    """Accept a pending relationship invite as the elder."""
    rel = first_row(
        db.table("relationships")
        .select("*")
        .eq("id", relationship_id)
        .limit(1)
        .execute()
    )
    if not rel:
        raise NotFoundError("Relationship not found")
    if rel["elder_id"] != elder_id:
        raise ForbiddenError("Only the invited elder can accept")
    if rel["status"] != "pending":
        raise ValidationError("Relationship is not pending")

    result = (
        db.table("relationships")
        .update({"status": "active"})
        .eq("id", relationship_id)
        .execute()
    )
    if not result.data:
        raise NotFoundError("Relationship not found")
    return result.data[0]


def _count_active_medications(db: Client, elder_id: str) -> int:
    """Count active medications for an elder/patient id.

    Supports both CareConnect (``elder_id``) and shared PillBox (``patient_id``) schemas.
    """
    for column in ("elder_id", "patient_id"):
        try:
            meds = (
                db.table("medications")
                .select("id", count="exact")
                .eq(column, elder_id)
                .eq("active", True)
                .execute()
            )
            return meds.count or 0
        except Exception:
            continue
    return 0


def _last_checkin_at(db: Client, elder_id: str) -> str | None:
    """Return the most recent check-in timestamp for an elder, if available."""
    try:
        checkin = (
            db.table("checkins")
            .select("created_at")
            .eq("elder_id", elder_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return checkin.data[0]["created_at"] if checkin.data else None
    except Exception:
        return None


def get_patient_detail(db: Client, caregiver_id: str, patient_id: str) -> dict:
    """Return full patient profile for a linked caregiver, including login code."""
    verify_caregiver_for_elder(db, caregiver_id, patient_id)

    profile = fetch_user_row(db, patient_id)
    if not profile or profile.get("role") != "elder":
        raise NotFoundError("Patient not found")

    profile = enrich_elder_profile(db, profile)
    safe = public_user(profile)
    safe["login_code"] = profile.get("login_code")
    return safe


def get_my_elders(db: Client, caregiver_id: str) -> list[dict]:
    """List linked elders with last check-in and active medication counts."""
    rels = (
        db.table("relationships")
        .select("id, elder_id, status, created_at")
        .eq("caregiver_id", caregiver_id)
        .eq("status", "active")
        .execute()
    )
    summaries = []
    for rel in rels.data or []:
        elder = first_row(
            db.table("users")
            .select(users_select_expr(
                db, "full_name", "last_name", "email", "timezone", "login_code"
            ))
            .eq("id", rel["elder_id"])
            .limit(1)
            .execute()
        ) or {}
        summaries.append({
            "elder_id": rel["elder_id"],
            "full_name": elder.get("full_name"),
            "last_name": elder.get("last_name"),
            "email": elder.get("email"),
            "login_code": elder.get("login_code"),
            "relationship_id": rel["id"],
            "status": rel["status"],
            "last_checkin_at": _last_checkin_at(db, rel["elder_id"]),
            "active_medication_count": _count_active_medications(db, rel["elder_id"]),
        })
    return summaries


def get_my_caregivers(db: Client, elder_id: str) -> list[dict]:
    """List linked caregivers for an elder."""
    rels = (
        db.table("relationships")
        .select("id, caregiver_id, status")
        .eq("elder_id", elder_id)
        .eq("status", "active")
        .execute()
    )
    summaries = []
    for rel in rels.data or []:
        caregiver = first_row(
            db.table("users")
            .select("full_name, last_name, email")
            .eq("id", rel["caregiver_id"])
            .limit(1)
            .execute()
        ) or {}
        summaries.append({
            "caregiver_id": rel["caregiver_id"],
            "full_name": caregiver.get("full_name"),
            "last_name": caregiver.get("last_name"),
            "email": caregiver.get("email"),
            "relationship_id": rel["id"],
            "status": rel["status"],
        })
    return summaries


def delete_relationship(db: Client, relationship_id: str, user_id: str) -> None:
    """Unlink a caregiver-elder relationship."""
    rel = first_row(
        db.table("relationships")
        .select("*")
        .eq("id", relationship_id)
        .limit(1)
        .execute()
    )
    if not rel:
        raise NotFoundError("Relationship not found")
    if user_id not in (rel["caregiver_id"], rel["elder_id"]):
        raise ForbiddenError("Not authorized to delete this relationship")

    db.table("relationships").delete().eq("id", relationship_id).execute()
