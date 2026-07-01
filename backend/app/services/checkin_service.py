from datetime import datetime, timezone

from supabase import Client

from app.exceptions import ValidationError
from app.schema_compat import filter_table_payload, table_select_expr
from app.services.user_service import verify_elder_access


def create_checkin(db: Client, elder_id: str, mood_score: int, note: str | None) -> dict:
    """Submit a wellness check-in for an elder."""
    payload = filter_table_payload(db, "checkins", {"elder_id": elder_id, "mood_score": mood_score, "note": note})
    result = db.table("checkins").insert(payload).execute()
    if not result.data:
        raise ValidationError("Failed to create check-in")
    return result.data[0]


def list_checkins(
    db: Client,
    elder_id: str,
    requester_id: str,
    requester_role: str,
    page: int = 1,
    page_size: int = 20,
) -> list[dict]:
    """Return paginated check-in history for an elder."""
    verify_elder_access(db, requester_id, elder_id, requester_role)
    offset = (page - 1) * page_size
    result = (
        db.table("checkins")
        .select(table_select_expr(db, "checkins"))
        .eq("elder_id", elder_id)
        .order("created_at", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return result.data or []


def get_checkin_status(
    db: Client, elder_id: str, requester_id: str, requester_role: str
) -> dict:
    """Return last check-in time and whether the elder needs attention."""
    verify_elder_access(db, requester_id, elder_id, requester_role)

    result = (
        db.table("checkins")
        .select("created_at")
        .eq("elder_id", elder_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return {
            "last_checkin_at": None,
            "hours_since": None,
            "needs_attention": True,
        }

    last_at_str = result.data[0]["created_at"]
    last_at = datetime.fromisoformat(last_at_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    hours_since = (now - last_at).total_seconds() / 3600

    return {
        "last_checkin_at": last_at_str,
        "hours_since": round(hours_since, 1),
        "needs_attention": hours_since > 24,
    }
