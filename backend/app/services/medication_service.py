from datetime import date, datetime, timedelta, timezone

from supabase import Client

from app.db_utils import first_row
from app.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.pillbox_compat import (
    attach_pillbox_schedules,
    create_pillbox_schedule,
    ensure_pillbox_patient,
    medications_use_patient_id,
    normalize_medication_row,
)
from app.services.user_service import verify_caregiver_for_elder, verify_elder_access


def create_medication(db: Client, caregiver_id: str, data: dict) -> dict:
    """Add a medication schedule for an elder (caregiver only)."""
    elder_id = data["elder_id"]
    verify_caregiver_for_elder(db, caregiver_id, elder_id)

    scheduled_times = data.get("scheduled_times") or ["08:00"]
    frequency = data.get("frequency") or "Daily"

    if medications_use_patient_id(db):
        elder = first_row(
            db.table("users").select("full_name, timezone").eq("id", elder_id).limit(1).execute()
        ) or {}
        ensure_pillbox_patient(
            db,
            caregiver_id,
            elder_id,
            elder.get("full_name") or data.get("name") or "Patient",
        )

        result = db.table("medications").insert(
            {
                "patient_id": elder_id,
                "name": data["name"],
                "dosage_text": data["dosage"],
                "form": "pill",
                "instructions": data.get("instructions"),
                "active": True,
                "created_by": caregiver_id,
            }
        ).execute()
        if not result.data:
            raise ValidationError("Failed to create medication")

        med = result.data[0]
        create_pillbox_schedule(
            db,
            med["id"],
            scheduled_times,
            frequency,
            elder.get("timezone") or "America/Chicago",
        )
        return normalize_medication_row(med, data)

    result = db.table("medications").insert(data).execute()
    if not result.data:
        raise ValidationError("Failed to create medication")
    return normalize_medication_row(result.data[0], data)


def list_medications(db: Client, elder_id: str, requester_id: str, requester_role: str) -> list[dict]:
    """List active medications for an elder."""
    verify_elder_access(db, requester_id, elder_id, requester_role)

    if medications_use_patient_id(db):
        result = (
            db.table("medications")
            .select("*")
            .eq("patient_id", elder_id)
            .eq("active", True)
            .order("created_at", desc=True)
            .execute()
        )
        return attach_pillbox_schedules(db, result.data or [])

    result = (
        db.table("medications")
        .select("*")
        .eq("elder_id", elder_id)
        .eq("active", True)
        .order("created_at", desc=True)
        .execute()
    )
    return [normalize_medication_row(row) for row in (result.data or [])]


def update_medication(db: Client, medication_id: str, caregiver_id: str, updates: dict) -> dict:
    """Update medication dosage, schedule, or active flag."""
    med = _get_medication(db, medication_id)
    verify_caregiver_for_elder(db, caregiver_id, med["elder_id"])

    filtered = {k: v for k, v in updates.items() if v is not None}
    if not filtered:
        return med

    result = (
        db.table("medications")
        .update(filtered)
        .eq("id", medication_id)
        .execute()
    )
    if not result.data:
        raise NotFoundError("Medication not found")
    return result.data[0]


def soft_delete_medication(db: Client, medication_id: str, caregiver_id: str) -> dict:
    """Soft-delete a medication by setting active=false."""
    return update_medication(db, medication_id, caregiver_id, {"active": False})


def confirm_dose(
    db: Client, medication_id: str, elder_id: str, scheduled_for: str | None
) -> dict:
    """Confirm a medication dose was taken by the elder."""
    med = _get_medication(db, medication_id)
    if med["elder_id"] != elder_id:
        raise ForbiddenError("Can only confirm your own medications")

    now = datetime.now(timezone.utc).isoformat()
    scheduled = scheduled_for or now

    existing = first_row(
        db.table("medication_logs")
        .select("*")
        .eq("medication_id", medication_id)
        .eq("scheduled_for", scheduled)
        .limit(1)
        .execute()
    )

    if existing:
        result = (
            db.table("medication_logs")
            .update({"status": "taken", "taken_at": now})
            .eq("id", existing["id"])
            .execute()
        )
    else:
        result = (
            db.table("medication_logs")
            .insert({
                "medication_id": medication_id,
                "elder_id": elder_id,
                "scheduled_for": scheduled,
                "taken_at": now,
                "status": "taken",
            })
            .execute()
        )

    if not result.data:
        raise ValidationError("Failed to confirm dose")
    return result.data[0]


def get_pending_doses(db: Client, elder_id: str, requester_id: str, requester_role: str) -> list[dict]:
    """Return today's pending doses with overdue minutes for an elder."""
    verify_elder_access(db, requester_id, elder_id, requester_role)

    today = date.today()
    start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    meds = (
        db.table("medications")
        .select("*")
        .eq("elder_id", elder_id)
        .eq("active", True)
        .execute()
    )

    pending: list[dict] = []
    now = datetime.now(timezone.utc)

    for med in meds.data or []:
        for time_str in med.get("scheduled_times", []):
            hour, minute = _parse_time(time_str)
            scheduled_dt = start.replace(hour=hour, minute=minute)
            if scheduled_dt >= end:
                continue

            scheduled_iso = scheduled_dt.isoformat()
            log = first_row(
                db.table("medication_logs")
                .select("*")
                .eq("medication_id", med["id"])
                .eq("scheduled_for", scheduled_iso)
                .limit(1)
                .execute()
            )

            status = "pending"
            log_id = None
            if log:
                status = log["status"]
                log_id = log["id"]

            if status == "pending" and scheduled_dt < now:
                minutes_overdue = int((now - scheduled_dt).total_seconds() / 60)
                pending.append({
                    "log_id": log_id,
                    "medication_id": med["id"],
                    "medication_name": med["name"],
                    "dosage": med["dosage"],
                    "scheduled_for": scheduled_iso,
                    "status": status,
                    "minutes_overdue": max(0, minutes_overdue),
                })
            elif status == "pending":
                pending.append({
                    "log_id": log_id,
                    "medication_id": med["id"],
                    "medication_name": med["name"],
                    "dosage": med["dosage"],
                    "scheduled_for": scheduled_iso,
                    "status": status,
                    "minutes_overdue": 0,
                })

    return pending


def get_adherence_stats(
    db: Client, elder_id: str, requester_id: str, requester_role: str, days: int = 7
) -> dict:
    """Return adherence statistics by merging schedules with dose logs."""
    verify_elder_access(db, requester_id, elder_id, requester_role)

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    since_date = since.date()

    meds = (
        db.table("medications")
        .select("*")
        .eq("elder_id", elder_id)
        .eq("active", True)
        .execute()
    )

    logs_result = (
        db.table("medication_logs")
        .select("*")
        .eq("elder_id", elder_id)
        .gte("scheduled_for", since.isoformat())
        .execute()
    )
    logs_by_key = {
        (log["medication_id"], log["scheduled_for"][:19]): log
        for log in (logs_result.data or [])
    }

    taken = 0
    missed = 0
    daily: dict[str, dict[str, int]] = {}

    for day_offset in range(days):
        day = since_date + timedelta(days=day_offset)
        if day > now.date():
            break
        day_start = datetime.combine(day, datetime.min.time()).replace(tzinfo=timezone.utc)

        for med in meds.data or []:
            for time_str in med.get("scheduled_times", []):
                hour, minute = _parse_time(time_str)
                scheduled_dt = day_start.replace(hour=hour, minute=minute)
                if scheduled_dt < since or scheduled_dt > now:
                    continue

                day_key = day.isoformat()
                if day_key not in daily:
                    daily[day_key] = {"taken": 0, "missed": 0}

                log_key = (med["id"], scheduled_dt.isoformat()[:19])
                log = logs_by_key.get(log_key)

                if log and log["status"] == "taken":
                    taken += 1
                    daily[day_key]["taken"] += 1
                elif log and log["status"] == "missed":
                    missed += 1
                    daily[day_key]["missed"] += 1
                elif scheduled_dt < now - timedelta(minutes=30):
                    missed += 1
                    daily[day_key]["missed"] += 1

    breakdown = [
        {"date": d, "taken": v["taken"], "missed": v["missed"]}
        for d, v in sorted(daily.items())
    ]

    return {
        "period": f"last_{days}_days",
        "total_scheduled": taken + missed,
        "taken": taken,
        "missed": missed,
        "daily_breakdown": breakdown,
    }


def _get_medication(db: Client, medication_id: str) -> dict:
    med = first_row(
        db.table("medications")
        .select("*")
        .eq("id", medication_id)
        .limit(1)
        .execute()
    )
    if not med:
        raise NotFoundError("Medication not found")
    return normalize_medication_row(med)


def _parse_time(time_str: str) -> tuple[int, int]:
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValidationError(f"Invalid time format: {time_str}")
    return int(parts[0]), int(parts[1])
