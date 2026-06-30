from datetime import date

from pydantic import BaseModel, Field

from app.models.common import MedicalHistoryCategory


class MedicalHistoryCreate(BaseModel):
    elder_id: str
    category: MedicalHistoryCategory
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    date_occurred: date | None = None
    is_active: bool = True


class MedicalHistoryUpdate(BaseModel):
    category: MedicalHistoryCategory | None = None
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    date_occurred: date | None = None
    is_active: bool | None = None


class MedicalHistoryResponse(BaseModel):
    id: str
    elder_id: str
    category: MedicalHistoryCategory
    title: str
    description: str | None = None
    date_occurred: str | None = None
    is_active: bool = True
    created_at: str | None = None


class EmergencyContactSummary(BaseModel):
    id: str
    name: str
    phone: str
    contact_type: str
    is_primary: bool


class EmergencySummaryResponse(BaseModel):
    allergies: list[MedicalHistoryResponse]
    active_conditions: list[MedicalHistoryResponse]
    emergency_contacts: list[EmergencyContactSummary]
