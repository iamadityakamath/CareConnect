from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models.common import UserRole


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole
    phone: str | None = Field(None, max_length=30)
    timezone: str | None = Field(None, min_length=1, max_length=64)


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=200)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=30)
    timezone: str | None = Field(None, min_length=1, max_length=64)
    date_of_birth: date | None = None
    address: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=2000)


class PatientLoginCodeUpdate(BaseModel):
    login_code: str = Field(..., description="New 4–6 digit numeric code")

    @field_validator("login_code")
    @classmethod
    def validate_login_code(cls, value: str) -> str:
        import re
        if not re.match(r"^\d{4,6}$", value):
            raise ValueError("Login code must be 4–6 digits")
        return value


class UserResponse(BaseModel):
    id: str
    email: str | None = None
    full_name: str | None = None
    last_name: str | None = None
    role: UserRole | None = None
    phone: str | None = None
    timezone: str | None = None
    account_status: str | None = None
    login_code_set_at: str | None = None
    date_of_birth: str | None = None
    address: str | None = None
    notes: str | None = None
    created_at: str | None = None
