from fastapi import APIRouter, Depends
from supabase import Client

from app.dependencies import get_current_user, get_db
from app.models.auth import (
    AuthSessionResponse,
    CaregiverLoginRequest,
    CaregiverSignupRequest,
)
from app.models.patient import PatientLoginRequest
from app.models.user import UserResponse
from app.services import auth_service, user_service

router = APIRouter()


@router.post("/caregiver/signup", response_model=AuthSessionResponse, status_code=201)
def caregiver_signup(
    body: CaregiverSignupRequest,
    db: Client = Depends(get_db),
):
    """Register a caregiver account via Supabase Auth (email + password)."""
    return auth_service.caregiver_signup(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        last_name=body.last_name,
        phone=body.phone,
        timezone=body.timezone,
    )


@router.post("/caregiver/login", response_model=AuthSessionResponse)
def caregiver_login(
    body: CaregiverLoginRequest,
    db: Client = Depends(get_db),
):
    """Sign in a caregiver with email + password."""
    return auth_service.caregiver_login(db, body.email, body.password)


@router.post("/patient-login", response_model=AuthSessionResponse)
def patient_login(
    body: PatientLoginRequest,
    db: Client = Depends(get_db),
):
    """Sign in a patient with last name + numeric code."""
    return auth_service.patient_login(db, body.last_name, body.login_code)


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Return the authenticated user's profile (caregiver or patient)."""
    return user_service.get_me_profile(db, current_user["id"], current_user)
