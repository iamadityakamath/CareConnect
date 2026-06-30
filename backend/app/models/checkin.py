from pydantic import BaseModel, Field


class CheckinCreate(BaseModel):
    mood_score: int = Field(..., ge=1, le=5)
    note: str | None = Field(None, max_length=2000)


class CheckinResponse(BaseModel):
    id: str
    elder_id: str
    mood_score: int
    note: str | None = None
    created_at: str | None = None


class CheckinStatusResponse(BaseModel):
    last_checkin_at: str | None = None
    hours_since: float | None = None
    needs_attention: bool
