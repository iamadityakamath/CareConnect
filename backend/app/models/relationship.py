from pydantic import BaseModel, EmailStr, Field

from app.models.common import RelationshipStatus


class RelationshipInviteCreate(BaseModel):
    elder_email: EmailStr | None = None
    invite_code: str | None = Field(None, min_length=6, max_length=64)


class RelationshipResponse(BaseModel):
    id: str
    caregiver_id: str
    elder_id: str
    status: RelationshipStatus
    created_by: str | None = None
    created_at: str | None = None


class ElderSummary(BaseModel):
    elder_id: str
    full_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    login_code: str | None = None
    relationship_id: str
    status: RelationshipStatus
    last_checkin_at: str | None = None
    active_medication_count: int = 0


class CaregiverSummary(BaseModel):
    caregiver_id: str
    full_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    relationship_id: str
    status: RelationshipStatus
