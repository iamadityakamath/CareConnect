from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.dependencies import get_current_user, get_db, require_caregiver
from app.models.contact import ContactCreate, ContactResponse, ContactUpdate
from app.services import contact_service

router = APIRouter()


@router.post("", response_model=ContactResponse, status_code=201)
def create_contact(
    body: ContactCreate,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    return contact_service.create_contact(
        db, current_user["id"], current_user.get("role", ""), body.model_dump(mode="json")
    )


@router.get("/{elder_id}", response_model=list[ContactResponse])
def list_contacts(
    elder_id: str,
    contact_type: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Caregiver or patient views contacts for a linked patient."""
    return contact_service.list_contacts(
        db, elder_id, current_user["id"], current_user.get("role", ""), contact_type
    )


@router.patch("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: str,
    body: ContactUpdate,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    return contact_service.update_contact(
        db, contact_id, current_user["id"], current_user.get("role", ""), body.model_dump(mode="json")
    )


@router.delete("/{contact_id}", status_code=204)
def delete_contact(
    contact_id: str,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    contact_service.delete_contact(
        db, contact_id, current_user["id"], current_user.get("role", "")
    )
