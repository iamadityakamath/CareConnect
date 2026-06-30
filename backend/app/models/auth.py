from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserResponse


class CaregiverSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=200)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=30)
    timezone: str | None = Field(None, min_length=1, max_length=64)


class CaregiverLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: int | None = None
    persistent_until: int | None = None
    user: UserResponse
