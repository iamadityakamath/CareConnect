from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.dependencies import get_current_user, get_db, require_caregiver, require_patient
from app.models.medication import (
    AdherenceStatsResponse,
    MedicationConfirmRequest,
    MedicationCreate,
    MedicationLogResponse,
    MedicationResponse,
    MedicationUpdate,
    PendingDoseResponse,
)
from app.services import medication_service

router = APIRouter()


@router.post("", response_model=MedicationResponse, status_code=201)
def create_medication(
    body: MedicationCreate,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    return medication_service.create_medication(
        db, current_user["id"], body.model_dump()
    )


@router.get("/{elder_id}/pending", response_model=list[PendingDoseResponse])
def pending_doses(
    elder_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    return medication_service.get_pending_doses(
        db, elder_id, current_user["id"], current_user.get("role", "")
    )


@router.get("/{elder_id}/adherence", response_model=AdherenceStatsResponse)
def adherence_stats(
    elder_id: str,
    days: int = Query(7, ge=1, le=90),
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    return medication_service.get_adherence_stats(
        db, elder_id, current_user["id"], current_user.get("role", ""), days
    )


@router.get("/{elder_id}", response_model=list[MedicationResponse])
def list_medications(
    elder_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    return medication_service.list_medications(
        db, elder_id, current_user["id"], current_user.get("role", "")
    )


@router.patch("/{medication_id}", response_model=MedicationResponse)
def update_medication(
    medication_id: str,
    body: MedicationUpdate,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    return medication_service.update_medication(
        db, medication_id, current_user["id"], body.model_dump()
    )


@router.delete("/{medication_id}", response_model=MedicationResponse)
def delete_medication(
    medication_id: str,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    return medication_service.soft_delete_medication(
        db, medication_id, current_user["id"]
    )


@router.post("/{medication_id}/confirm", response_model=MedicationLogResponse)
def confirm_dose(
    medication_id: str,
    body: MedicationConfirmRequest = MedicationConfirmRequest(),
    current_user: dict = Depends(require_patient),
    db: Client = Depends(get_db),
):
    return medication_service.confirm_dose(
        db, medication_id, current_user["id"], body.scheduled_for
    )
