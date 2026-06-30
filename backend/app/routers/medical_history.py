from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.dependencies import get_current_user, get_db, require_caregiver
from app.models.medical_history import (
    EmergencySummaryResponse,
    MedicalHistoryCreate,
    MedicalHistoryResponse,
    MedicalHistoryUpdate,
)
from app.services import medical_history_service

router = APIRouter()


@router.post("", response_model=MedicalHistoryResponse, status_code=201)
def create_entry(
    body: MedicalHistoryCreate,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    """Caregiver adds a medical history entry for a linked patient."""
    data = body.model_dump(mode="json")
    if data.get("date_occurred"):
        data["date_occurred"] = str(data["date_occurred"])
    return medical_history_service.create_entry(
        db, current_user["id"], current_user.get("role", ""), data
    )


@router.get("/{elder_id}/emergency-summary", response_model=EmergencySummaryResponse)
def emergency_summary(
    elder_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Emergency snapshot — caregiver or the patient themselves."""
    return medical_history_service.get_emergency_summary(
        db, elder_id, current_user["id"], current_user.get("role", "")
    )


@router.get("/{elder_id}", response_model=list[MedicalHistoryResponse])
def list_entries(
    elder_id: str,
    category: str | None = Query(None),
    active_only: bool | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Caregiver or patient views medical history for a linked patient."""
    return medical_history_service.list_entries(
        db,
        elder_id,
        current_user["id"],
        current_user.get("role", ""),
        category,
        active_only,
    )


@router.patch("/{entry_id}", response_model=MedicalHistoryResponse)
def update_entry(
    entry_id: str,
    body: MedicalHistoryUpdate,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    return medical_history_service.update_entry(
        db, entry_id, current_user["id"], current_user.get("role", ""), body.model_dump(mode="json")
    )


@router.delete("/{entry_id}", status_code=204)
def delete_entry(
    entry_id: str,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    medical_history_service.delete_entry(
        db, entry_id, current_user["id"], current_user.get("role", "")
    )
