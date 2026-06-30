import uuid
from datetime import datetime, timezone as dt_timezone

import time

import httpx
from supabase import Client, create_client

from app.config import get_settings
from app.db_utils import first_row, public_user
from app.exceptions import ForbiddenError, UnauthorizedError, ValidationError
from app.pillbox_compat import ensure_pillbox_patient


def _patient_auth_email(user_id: str) -> str:
    """Build the internal Supabase auth email for a patient account."""
    settings = get_settings()
    return f"patient.{user_id}@{settings.PATIENT_AUTH_EMAIL_DOMAIN}"


def _patient_auth_metadata_role() -> str:
    """Role stored in Supabase Auth user_metadata on create.

    The shared PillBox DB trigger writes metadata role into ``profiles.role``,
    which only allows caregiver/patient/both — not our app role ``elder``.
    """
    return "patient"


def _anon_client() -> Client:
    """Return a Supabase client using the anon key for password sign-in."""
    settings = get_settings()
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


def _session_response(
    session, profile: dict, *, set_patient_persistent: bool = True
) -> dict:
    """Build a standard auth session payload."""
    now = int(time.time())
    expires_in = session.expires_in or 3600
    payload = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "expires_at": now + expires_in,
        "user": public_user(profile),
    }
    if set_patient_persistent and profile.get("role") == "elder":
        settings = get_settings()
        payload["persistent_until"] = now + settings.PATIENT_SESSION_DAYS * 86400
    return payload


def caregiver_signup(
    db: Client,
    email: str,
    password: str,
    full_name: str,
    last_name: str,
    phone: str | None,
    timezone: str | None = None,
) -> dict:
    """Register a caregiver via Supabase Auth and create their app profile."""
    existing = (
        db.table("users")
        .select("id")
        .eq("email", email)
        .limit(1)
        .execute()
    )
    if existing and existing.data:
        raise ValidationError("An account with this email already exists")

    try:
        auth_response = db.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {
                    "role": "caregiver",
                    "full_name": full_name,
                    "last_name": last_name,
                },
            }
        )
    except Exception as exc:
        raise ValidationError("Failed to create caregiver account") from exc

    user_id = auth_response.user.id
    profile_payload = {
        "id": user_id,
        "email": email,
        "auth_email": email,
        "full_name": full_name,
        "last_name": last_name.strip(),
        "role": "caregiver",
        "phone": phone,
        "account_status": "active",
    }
    if timezone:
        profile_payload["timezone"] = timezone

    profile_result = db.table("users").insert(profile_payload).execute()
    if not profile_result.data:
        db.auth.admin.delete_user(user_id)
        raise ValidationError("Failed to create caregiver profile")

    anon = _anon_client()
    try:
        sign_in = anon.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        raise ValidationError("Account created but sign-in failed") from exc

    if not sign_in.session:
        raise ValidationError("Account created but no session returned")

    return _session_response(sign_in.session, profile_result.data[0])


def caregiver_login(db: Client, email: str, password: str) -> dict:
    """Authenticate a caregiver with email + password via Supabase Auth."""
    anon = _anon_client()
    try:
        auth_response = anon.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception:
        raise UnauthorizedError("Invalid email or password")

    if not auth_response.session or not auth_response.user:
        raise UnauthorizedError("Invalid email or password")

    user_id = auth_response.user.id
    profile_row = first_row(
        db.table("users").select("*").eq("id", user_id).limit(1).execute()
    )

    if not profile_row:
        raise UnauthorizedError("Caregiver profile not found. Complete registration.")

    if profile_row.get("role") != "caregiver":
        raise ForbiddenError("This login is for caregiver accounts only")

    return _session_response(auth_response.session, profile_row)


def provision_patient(
    db: Client,
    caregiver_id: str,
    full_name: str,
    last_name: str,
    login_code: str,
    phone: str | None,
    timezone: str | None = None,
    date_of_birth: str | None = None,
    address: str | None = None,
    notes: str | None = None,
) -> dict:
    """Create a patient auth account, profile, and active caregiver link."""
    temp_email = f"pending.{uuid.uuid4()}@{get_settings().PATIENT_AUTH_EMAIL_DOMAIN}"

    try:
        auth_response = db.auth.admin.create_user(
            {
                "email": temp_email,
                "password": login_code,
                "email_confirm": True,
                "user_metadata": {
                    "role": _patient_auth_metadata_role(),
                    "last_name": last_name,
                    "full_name": full_name,
                },
            }
        )
    except Exception as exc:
        raise ValidationError("Failed to create patient login account") from exc

    user_id = auth_response.user.id
    auth_email = _patient_auth_email(user_id)

    try:
        db.auth.admin.update_user_by_id(user_id, {"email": auth_email})
    except Exception:
        db.auth.admin.delete_user(user_id)
        raise ValidationError("Failed to finalize patient login account")

    now = datetime.now(dt_timezone.utc).isoformat()
    profile_payload = {
        "id": user_id,
        "email": None,
        "auth_email": auth_email,
        "full_name": full_name,
        "last_name": last_name.strip(),
        "role": "elder",
        "phone": phone,
        "account_status": "managed",
        "login_code": login_code,
        "login_code_set_at": now,
    }
    if timezone:
        profile_payload["timezone"] = timezone
    if date_of_birth:
        profile_payload["date_of_birth"] = date_of_birth
    if address:
        profile_payload["address"] = address.strip()
    if notes:
        profile_payload["notes"] = notes.strip()

    profile_result = db.table("users").insert(profile_payload).execute()
    if not profile_result.data:
        db.auth.admin.delete_user(user_id)
        raise ValidationError("Failed to create patient profile")

    rel_result = (
        db.table("relationships")
        .insert(
            {
                "caregiver_id": caregiver_id,
                "elder_id": user_id,
                "status": "active",
                "created_by": caregiver_id,
            }
        )
        .execute()
    )
    if not rel_result.data:
        db.table("users").delete().eq("id", user_id).execute()
        db.auth.admin.delete_user(user_id)
        raise ValidationError("Failed to link patient to caregiver")

    ensure_pillbox_patient(db, caregiver_id, user_id, full_name)

    return {
        "patient": public_user(profile_result.data[0]),
        "relationship_id": rel_result.data[0]["id"],
    }


def patient_login(db: Client, last_name: str, login_code: str) -> dict:
    """Authenticate a patient with last name + numeric code and return session tokens."""
    normalized_name = last_name.strip()
    candidates = (
        db.table("users")
        .select("*")
        .eq("role", "elder")
        .ilike("last_name", normalized_name)
        .execute()
    )

    if not candidates.data:
        raise UnauthorizedError("Invalid last name or login code")

    anon = _anon_client()
    session = None
    matched_profile = None

    for profile in candidates.data:
        try:
            auth_response = anon.auth.sign_in_with_password(
                {"email": profile["auth_email"], "password": login_code}
            )
        except Exception:
            continue
        if auth_response.session:
            session = auth_response.session
            matched_profile = profile
            break

    if not session or not matched_profile:
        raise UnauthorizedError("Invalid last name or login code")

    if matched_profile.get("role") != "elder":
        raise ForbiddenError("This login is for patient accounts only")

    if matched_profile.get("account_status") == "managed":
        db.table("users").update({"account_status": "active"}).eq(
            "id", matched_profile["id"]
        ).execute()
        matched_profile["account_status"] = "active"

    return _session_response(session, matched_profile)


def refresh_session(db: Client, refresh_token: str) -> dict:
    """Exchange a Supabase refresh token for a new access token."""
    settings = get_settings()
    try:
        response = httpx.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token",
            params={"grant_type": "refresh_token"},
            json={"refresh_token": refresh_token},
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise UnauthorizedError("Session expired. Please sign in again.") from exc

    if response.status_code >= 400:
        raise UnauthorizedError("Session expired. Please sign in again.")

    payload = response.json()
    user_id = payload.get("user", {}).get("id")
    if not user_id:
        raise UnauthorizedError("Session expired. Please sign in again.")

    profile_row = first_row(
        db.table("users").select("*").eq("id", user_id).limit(1).execute()
    )
    if not profile_row:
        raise UnauthorizedError("User profile not found")

    class _RefreshedSession:
        access_token = payload["access_token"]
        refresh_token = payload.get("refresh_token") or refresh_token
        expires_in = payload.get("expires_in") or 3600

    return _session_response(_RefreshedSession(), profile_row, set_patient_persistent=False)


def update_patient_login_code(
    db: Client, caregiver_id: str, patient_id: str, login_code: str
) -> dict:
    """Allow a linked caregiver to reset a patient's numeric login code."""
    from app.services.user_service import verify_caregiver_for_elder

    verify_caregiver_for_elder(db, caregiver_id, patient_id)

    patient = first_row(
        db.table("users")
        .select("*")
        .eq("id", patient_id)
        .eq("role", "elder")
        .limit(1)
        .execute()
    )
    if not patient:
        raise ValidationError("Patient not found")

    try:
        db.auth.admin.update_user_by_id(
            patient_id,
            {"password": login_code},
        )
    except Exception as exc:
        raise ValidationError("Failed to update login code") from exc

    result = (
        db.table("users")
        .update({
            "login_code": login_code,
            "login_code_set_at": datetime.now(dt_timezone.utc).isoformat(),
        })
        .eq("id", patient_id)
        .execute()
    )
    if not result.data:
        raise ValidationError("Failed to update patient profile")
    return public_user(result.data[0])
