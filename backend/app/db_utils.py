"""Helpers for safe Supabase query result handling."""

from typing import Any


def first_row(result: Any) -> dict | None:
    """Safely return the first row from a Supabase query result."""
    if result is None or not getattr(result, "data", None):
        return None
    data = result.data
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        return data
    return None


def public_user(profile: dict) -> dict:
    """Remove internal fields before returning user data to API clients."""
    return {k: v for k, v in profile.items() if k != "auth_email"}
