from supabase import Client

from app.db_utils import first_row
from app.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.services.user_service import verify_caregiver_for_elder, verify_elder_access


def create_entry(db: Client, requester_id: str, requester_role: str, data: dict) -> dict:
    """Add a medical history entry for an elder (caregiver only)."""
    if requester_role != "caregiver":
        raise ForbiddenError("Only caregivers can manage medical history")

    elder_id = data["elder_id"]
    verify_caregiver_for_elder(db, requester_id, elder_id)

    result = db.table("medical_history").insert(data).execute()
    if not result.data:
        raise ValidationError("Failed to create medical history entry")
    return result.data[0]


def list_entries(
    db: Client,
    elder_id: str,
    requester_id: str,
    requester_role: str,
    category: str | None = None,
    active_only: bool | None = None,
) -> list[dict]:
    """List medical history entries, optionally filtered by category."""
    verify_elder_access(db, requester_id, elder_id, requester_role)
    query = db.table("medical_history").select("*").eq("elder_id", elder_id)
    if category:
        query = query.eq("category", category)
    if active_only is True:
        query = query.eq("is_active", True)
    result = query.order("created_at", desc=True).execute()
    return result.data or []


def update_entry(
    db: Client, entry_id: str, requester_id: str, requester_role: str, updates: dict
) -> dict:
    """Update a medical history entry (caregiver only)."""
    if requester_role != "caregiver":
        raise ForbiddenError("Only caregivers can manage medical history")

    entry = _get_entry(db, entry_id)
    verify_caregiver_for_elder(db, requester_id, entry["elder_id"])

    filtered = {k: v for k, v in updates.items() if v is not None}
    if not filtered:
        return entry

    if "date_occurred" in filtered and filtered["date_occurred"] is not None:
        filtered["date_occurred"] = str(filtered["date_occurred"])

    result = (
        db.table("medical_history")
        .update(filtered)
        .eq("id", entry_id)
        .execute()
    )
    if not result.data:
        raise NotFoundError("Entry not found")
    return result.data[0]


def delete_entry(db: Client, entry_id: str, requester_id: str, requester_role: str) -> None:
    """Delete a medical history entry (caregiver only)."""
    if requester_role != "caregiver":
        raise ForbiddenError("Only caregivers can manage medical history")

    entry = _get_entry(db, entry_id)
    verify_caregiver_for_elder(db, requester_id, entry["elder_id"])
    db.table("medical_history").delete().eq("id", entry_id).execute()


def get_emergency_summary(
    db: Client, elder_id: str, requester_id: str, requester_role: str
) -> dict:
    """Return condensed allergies, conditions, and emergency contacts for ER use."""
    verify_elder_access(db, requester_id, elder_id, requester_role)

    allergies = (
        db.table("medical_history")
        .select("*")
        .eq("elder_id", elder_id)
        .eq("category", "allergy")
        .eq("is_active", True)
        .execute()
    )
    conditions = (
        db.table("medical_history")
        .select("*")
        .eq("elder_id", elder_id)
        .eq("category", "condition")
        .eq("is_active", True)
        .execute()
    )
    contacts = (
        db.table("contacts")
        .select("id, name, phone, contact_type, is_primary")
        .eq("elder_id", elder_id)
        .eq("contact_type", "emergency")
        .execute()
    )

    return {
        "allergies": allergies.data or [],
        "active_conditions": conditions.data or [],
        "emergency_contacts": contacts.data or [],
    }


def _get_entry(db: Client, entry_id: str) -> dict:
    entry = first_row(
        db.table("medical_history")
        .select("*")
        .eq("id", entry_id)
        .limit(1)
        .execute()
    )
    if not entry:
        raise NotFoundError("Medical history entry not found")
    return entry
