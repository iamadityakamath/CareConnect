from fastapi import APIRouter, Depends
from supabase import Client

from app.dependencies import get_authenticated_user, get_current_user, get_db
from app.exceptions import ForbiddenError, ValidationError
from app.models.common import UserRole
from app.models.user import UserCreate, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter()


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    body: UserCreate,
    auth_user: dict = Depends(get_authenticated_user),
    db: Client = Depends(get_db),
):
    """
    Create a caregiver profile after Supabase signup on the frontend.
    Patient profiles are created by caregivers via POST /patients/provision.
    """
    if body.role != UserRole.CAREGIVER:
        raise ForbiddenError("Patient accounts are created by a caregiver, not self-registration")

    if not auth_user.get("email"):
        raise ValidationError("Authenticated email is required for caregiver registration")

    return user_service.create_user_profile(
        db,
        user_id=auth_user["id"],
        email=auth_user.get("email"),
        auth_email=auth_user["email"],
        full_name=body.full_name,
        last_name=body.last_name,
        role=body.role.value,
        phone=body.phone,
        timezone=body.timezone,
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    return user_service.get_user_profile(db, user_id, current_user["id"])


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    body: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    return user_service.update_user_profile(
        db, user_id, current_user["id"], body.model_dump()
    )
