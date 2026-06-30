from fastapi import APIRouter, Depends
from supabase import Client

from app.dependencies import get_current_user, get_db, require_caregiver
from datetime import date

from app.models.patient import PatientDetailResponse, PatientProvisionCreate, PatientProvisionResponse
from app.models.user import PatientLoginCodeUpdate, UserResponse
from app.services import auth_service, user_service

router = APIRouter()


@router.post("/provision", response_model=PatientProvisionResponse, status_code=201)
def provision_patient(
    body: PatientProvisionCreate,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    """Create a patient account with a numeric login code and link to the caregiver."""
    result = auth_service.provision_patient(
        db,
        caregiver_id=current_user["id"],
        full_name=body.full_name,
        last_name=body.last_name,
        login_code=body.login_code,
        phone=body.phone,
        timezone=body.timezone,
        date_of_birth=body.date_of_birth.isoformat() if body.date_of_birth else None,
        address=body.address,
        notes=body.notes,
    )
    return {
        "patient": result["patient"],
        "relationship_id": result["relationship_id"],
    }


@router.get("/{patient_id}", response_model=PatientDetailResponse)
def get_patient(
    patient_id: str,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    """Get a linked patient's full profile for the caregiver dashboard."""
    return user_service.get_patient_detail(db, current_user["id"], patient_id)


@router.patch("/{patient_id}/login-code", response_model=UserResponse)
def reset_login_code(
    patient_id: str,
    body: PatientLoginCodeUpdate,
    current_user: dict = Depends(require_caregiver),
    db: Client = Depends(get_db),
):
    """Reset a linked patient's numeric login code."""
    return auth_service.update_patient_login_code(
        db, current_user["id"], patient_id, body.login_code
    )
