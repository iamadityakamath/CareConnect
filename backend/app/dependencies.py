from typing import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.database import get_supabase_client
from app.db_utils import first_row, public_user
from app.exceptions import ForbiddenError, UnauthorizedError
from app.jwt_validation import decode_supabase_jwt
from app.pillbox_compat import enrich_elder_profile, fetch_user_row

security = HTTPBearer(auto_error=False)

VALID_ROLES = frozenset({"caregiver", "elder"})


def get_db() -> Client:
    return get_supabase_client()


def _decode_token(credentials: HTTPAuthorizationCredentials | None) -> dict:
    """Validate Supabase JWT and return the payload."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing authentication token")

    try:
        return decode_supabase_jwt(credentials.credentials)
    except UnauthorizedError:
        raise
    except Exception:
        raise UnauthorizedError("Invalid or expired token")


def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Validate JWT only — used right after Supabase signup before profile exists."""
    payload = _decode_token(credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")
    return {
        "id": user_id,
        "email": payload.get("email"),
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Client = Depends(get_db),
) -> dict:
    """Validate JWT and require a complete app profile with a valid role."""
    payload = _decode_token(credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")

    profile = fetch_user_row(db, user_id)

    if not profile or profile.get("role") not in VALID_ROLES:
        raise UnauthorizedError("Account not set up. Complete registration first.")

    profile = enrich_elder_profile(db, profile)
    safe = public_user(profile)
    return {
        "id": safe["id"],
        "email": safe.get("email") or payload.get("email"),
        "role": safe.get("role"),
        "full_name": safe.get("full_name"),
        "last_name": safe.get("last_name"),
        "phone": safe.get("phone"),
        "timezone": safe.get("timezone"),
        "account_status": safe.get("account_status"),
    }


def require_role(required_role: str) -> Callable:
    """Dependency factory that enforces a specific user role."""

    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") != required_role:
            raise ForbiddenError(f"This action requires a {required_role} account")
        return current_user

    return role_checker


require_caregiver = require_role("caregiver")
require_patient = require_role("elder")
