from supabase import Client

from app.db_utils import first_row
from app.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.services.user_service import verify_caregiver_for_elder, verify_elder_access


def create_contact(db: Client, requester_id: str, requester_role: str, data: dict) -> dict:
    """Add a healthcare contact for an elder (caregiver only)."""
    if requester_role != "caregiver":
        raise ForbiddenError("Only caregivers can manage contacts")

    elder_id = data["elder_id"]
    verify_caregiver_for_elder(db, requester_id, elder_id)

    result = db.table("contacts").insert(data).execute()
    if not result.data:
        raise ValidationError("Failed to create contact")
    return result.data[0]


def list_contacts(
    db: Client,
    elder_id: str,
    requester_id: str,
    requester_role: str,
    contact_type: str | None = None,
) -> list[dict]:
    """List contacts for an elder, optionally filtered by type."""
    verify_elder_access(db, requester_id, elder_id, requester_role)
    query = db.table("contacts").select("*").eq("elder_id", elder_id)
    if contact_type:
        query = query.eq("contact_type", contact_type)
    result = query.order("is_primary", desc=True).order("created_at", desc=True).execute()
    return result.data or []


def update_contact(
    db: Client, contact_id: str, requester_id: str, requester_role: str, updates: dict
) -> dict:
    """Update a healthcare contact (caregiver only)."""
    if requester_role != "caregiver":
        raise ForbiddenError("Only caregivers can manage contacts")

    contact = _get_contact(db, contact_id)
    verify_caregiver_for_elder(db, requester_id, contact["elder_id"])

    filtered = {k: v for k, v in updates.items() if v is not None}
    if not filtered:
        return contact

    result = (
        db.table("contacts")
        .update(filtered)
        .eq("id", contact_id)
        .execute()
    )
    if not result.data:
        raise NotFoundError("Contact not found")
    return result.data[0]


def delete_contact(
    db: Client, contact_id: str, requester_id: str, requester_role: str
) -> None:
    """Delete a healthcare contact (caregiver only)."""
    if requester_role != "caregiver":
        raise ForbiddenError("Only caregivers can manage contacts")

    contact = _get_contact(db, contact_id)
    verify_caregiver_for_elder(db, requester_id, contact["elder_id"])
    db.table("contacts").delete().eq("id", contact_id).execute()


def _get_contact(db: Client, contact_id: str) -> dict:
    contact = first_row(
        db.table("contacts")
        .select("*")
        .eq("id", contact_id)
        .limit(1)
        .execute()
    )
    if not contact:
        raise NotFoundError("Contact not found")
    return contact
