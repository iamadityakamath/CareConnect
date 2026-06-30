from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class UserRole(str, Enum):
    ELDER = "elder"
    CAREGIVER = "caregiver"


class RelationshipStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"


class MedicationLogStatus(str, Enum):
    PENDING = "pending"
    TAKEN = "taken"
    MISSED = "missed"


class MedicalHistoryCategory(str, Enum):
    CONDITION = "condition"
    ALLERGY = "allergy"
    SURGERY = "surgery"
    NOTE = "note"


class ContactType(str, Enum):
    DOCTOR = "doctor"
    HOSPITAL = "hospital"
    PHARMACY = "pharmacy"
    EMERGENCY = "emergency"


class TimestampMixin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime | None = None
