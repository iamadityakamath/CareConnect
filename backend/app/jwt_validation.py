"""Validate Supabase Auth JWTs (ES256 via JWKS, with HS256 legacy fallback)."""

from functools import lru_cache

import httpx
from jose import JWTError, jwk, jwt

from app.config import get_settings
from app.exceptions import UnauthorizedError


@lru_cache(maxsize=1)
def _jwks_url() -> str:
    settings = get_settings()
    return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"


def _fetch_jwks() -> dict:
    response = httpx.get(_jwks_url(), timeout=10.0)
    response.raise_for_status()
    return response.json()


def _signing_key_from_jwks(token: str, jwks: dict):
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return jwk.construct(key_data)
    raise JWTError("Signing key not found in JWKS")


def decode_supabase_jwt(token: str) -> dict:
    """
    Decode and verify a Supabase access token.

    Newer Supabase projects sign JWTs with ES256 (JWKS).
    Older projects use HS256 with SUPABASE_JWT_SECRET.
    """
    settings = get_settings()
    header = jwt.get_unverified_header(token)
    algorithm = header.get("alg", "HS256")

    decode_errors: list[str] = []

    if algorithm == "ES256":
        try:
            jwks = _fetch_jwks()
            key = _signing_key_from_jwks(token, jwks)
            return jwt.decode(
                token,
                key,
                algorithms=["ES256"],
                audience="authenticated",
            )
        except JWTError as exc:
            decode_errors.append(f"ES256: {exc}")
            # JWKS may have rotated — retry once with a fresh fetch
            try:
                jwks = _fetch_jwks()
                key = _signing_key_from_jwks(token, jwks)
                return jwt.decode(
                    token,
                    key,
                    algorithms=["ES256"],
                    audience="authenticated",
                )
            except JWTError as retry_exc:
                decode_errors.append(f"ES256 retry: {retry_exc}")

    if settings.SUPABASE_JWT_SECRET:
        try:
            return jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except JWTError as exc:
            decode_errors.append(f"HS256: {exc}")

    raise UnauthorizedError("Invalid or expired token")


def clear_jwks_cache() -> None:
    """Clear cached JWKS URL lookup (for tests)."""
    _jwks_url.cache_clear()
