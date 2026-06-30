from pydantic import BaseModel, Field

from app.models.common import MedicationLogStatus


class MedicationCreate(BaseModel):
    elder_id: str
    name: str = Field(..., min_length=1, max_length=200)
    dosage: str = Field(..., min_length=1, max_length=100)
    instructions: str | None = None
    frequency: str = Field(..., min_length=1, max_length=100)
    scheduled_times: list[str] = Field(..., min_length=1)


class MedicationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    dosage: str | None = Field(None, min_length=1, max_length=100)
    instructions: str | None = None
    frequency: str | None = Field(None, min_length=1, max_length=100)
    scheduled_times: list[str] | None = None
    active: bool | None = None


class MedicationResponse(BaseModel):
    id: str
    elder_id: str
    name: str
    dosage: str
    instructions: str | None = None
    frequency: str
    scheduled_times: list[str]
    active: bool
    created_at: str | None = None


class MedicationConfirmRequest(BaseModel):
    scheduled_for: str | None = None


class MedicationLogResponse(BaseModel):
    id: str
    medication_id: str
    elder_id: str
    scheduled_for: str
    taken_at: str | None = None
    status: MedicationLogStatus
    created_at: str | None = None


class PendingDoseResponse(BaseModel):
    log_id: str | None = None
    medication_id: str
    medication_name: str
    dosage: str
    scheduled_for: str
    status: MedicationLogStatus
    minutes_overdue: int


class DailyAdherenceBreakdown(BaseModel):
    date: str
    taken: int
    missed: int


class AdherenceStatsResponse(BaseModel):
    period: str
    total_scheduled: int
    taken: int
    missed: int
    daily_breakdown: list[DailyAdherenceBreakdown]
