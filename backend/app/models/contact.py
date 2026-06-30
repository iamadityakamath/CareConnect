from pydantic import BaseModel, Field

from app.models.common import ContactType


class ContactCreate(BaseModel):
    elder_id: str
    name: str = Field(..., min_length=1, max_length=200)
    contact_type: ContactType
    specialty: str | None = Field(None, max_length=100)
    phone: str = Field(..., min_length=1, max_length=30)
    address: str | None = None
    is_primary: bool = False


class ContactUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    contact_type: ContactType | None = None
    specialty: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, min_length=1, max_length=30)
    address: str | None = None
    is_primary: bool | None = None


class ContactResponse(BaseModel):
    id: str
    elder_id: str
    name: str
    contact_type: ContactType
    specialty: str | None = None
    phone: str
    address: str | None = None
    is_primary: bool
    created_at: str | None = None
