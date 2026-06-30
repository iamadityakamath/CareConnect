from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.dependencies import get_current_user, get_db, require_caregiver, require_patient
from app.models.checkin import CheckinCreate, CheckinResponse, CheckinStatusResponse
from app.services import checkin_service

router = APIRouter()


@router.post("", response_model=CheckinResponse, status_code=201)
def create_checkin(
    body: CheckinCreate,
    current_user: dict = Depends(require_patient),
    db: Client = Depends(get_db),
):
    """Patient submits their own wellness check-in."""
    return checkin_service.create_checkin(
        db, current_user["id"], body.mood_score, body.note
    )


@router.get("/{elder_id}/status", response_model=CheckinStatusResponse)
def checkin_status(
    elder_id: str,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    """Caregiver checks whether a patient needs attention."""
    return checkin_service.get_checkin_status(
        db, elder_id, current_user["id"], current_user.get("role", "")
    )


@router.get("/{elder_id}", response_model=list[CheckinResponse])
def list_checkins(
    elder_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    """Caregiver views a patient's check-in history."""
    return checkin_service.list_checkins(
        db, elder_id, current_user["id"], current_user.get("role", ""), page, page_size
    )
