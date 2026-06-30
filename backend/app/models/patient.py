import re

from pydantic import BaseModel, Field, field_validator

from app.models.user import UserResponse

LOGIN_CODE_PATTERN = re.compile(r"^\d{4,6}$")


class PatientProvisionCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    last_name: str = Field(..., min_length=1, max_length=100)
    login_code: str = Field(..., description="4–6 digit numeric code the patient will use to sign in")
    phone: str | None = Field(None, max_length=30)
    timezone: str | None = Field(None, min_length=1, max_length=64)

    @field_validator("login_code")
    @classmethod
    def validate_login_code(cls, value: str) -> str:
        if not LOGIN_CODE_PATTERN.match(value):
            raise ValueError("Login code must be 4–6 digits")
        return value

    @field_validator("last_name")
    @classmethod
    def normalize_last_name(cls, value: str) -> str:
        return value.strip()


class PatientProvisionResponse(BaseModel):
    patient: UserResponse
    relationship_id: str


class PatientLoginRequest(BaseModel):
    last_name: str = Field(..., min_length=1, max_length=100)
    login_code: str = Field(..., description="Numeric code set by the caregiver")

    @field_validator("login_code")
    @classmethod
    def validate_login_code(cls, value: str) -> str:
        if not LOGIN_CODE_PATTERN.match(value):
            raise ValueError("Login code must be 4–6 digits")
        return value

    @field_validator("last_name")
    @classmethod
    def normalize_last_name(cls, value: str) -> str:
        return value.strip()
