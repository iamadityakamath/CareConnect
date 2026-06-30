from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.dependencies import get_current_user, get_db, require_caregiver, require_patient
from app.models.dashboard import CaregiverDashboardResponse
from app.models.relationship import (
    CaregiverSummary,
    ElderSummary,
    RelationshipInviteCreate,
    RelationshipResponse,
)
from app.services import medication_service, user_service

router = APIRouter()


@router.post("/invite", response_model=RelationshipResponse, status_code=201)
def invite_elder(
    body: RelationshipInviteCreate,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    return user_service.invite_elder(
        db,
        caregiver_id=current_user["id"],
        elder_email=body.elder_email,
        invite_code=body.invite_code,
    )


@router.post("/accept/{relationship_id}", response_model=RelationshipResponse)
def accept_relationship(
    relationship_id: str,
    current_user: dict = Depends(require_patient),
    db: Client = Depends(get_db),
):
    return user_service.accept_relationship(db, relationship_id, current_user["id"])


@router.get("/my-elders", response_model=list[ElderSummary])
def my_elders(
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    return user_service.get_my_elders(db, current_user["id"])


@router.get("/adherence-dashboard", response_model=CaregiverDashboardResponse)
def adherence_dashboard(
    days: int = Query(7, ge=1, le=30),
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    return medication_service.get_caregiver_adherence_dashboard(
        db, current_user["id"], days
    )


@router.get("/my-caregivers", response_model=list[CaregiverSummary])
def my_caregivers(
    current_user: dict = Depends(require_patient),
    db: Client = Depends(get_db),
):
    return user_service.get_my_caregivers(db, current_user["id"])


@router.delete("/{relationship_id}", status_code=204)
def delete_relationship(
    relationship_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    user_service.delete_relationship(db, relationship_id, current_user["id"])
