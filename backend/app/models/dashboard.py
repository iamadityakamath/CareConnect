from pydantic import BaseModel

from app.models.medication import DailyAdherenceBreakdown


class OverdueDoseSummary(BaseModel):
    medication_name: str
    dosage: str
    scheduled_for: str
    minutes_overdue: int


class PatientAdherenceSummary(BaseModel):
    elder_id: str
    full_name: str | None = None
    last_name: str | None = None
    today_scheduled: int
    today_taken: int
    today_on_time: int
    today_late: int
    today_pending: int
    today_overdue: int
    today_missed: int
    adherence_today_pct: int
    week_taken: int
    week_missed: int
    week_adherence_pct: int
    status: str
    next_dose_at: str | None = None
    last_taken_at: str | None = None
    overdue_doses: list[OverdueDoseSummary]


class DashboardTotals(BaseModel):
    patients: int
    doses_scheduled_today: int
    doses_taken_today: int
    doses_on_time_today: int
    doses_late_today: int
    doses_pending_today: int
    doses_overdue_today: int
    doses_missed_today: int
    patients_on_track: int
    patients_need_attention: int


class CaregiverDashboardResponse(BaseModel):
    date: str
    totals: DashboardTotals
    overall_today_pct: int
    overall_week_pct: int
    daily_breakdown: list[DailyAdherenceBreakdown]
    patients: list[PatientAdherenceSummary]
