from datetime import date, datetime, timedelta, timezone

from supabase import Client

from app.db_utils import first_row
from app.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.pillbox_compat import (
    align_dose_instructions,
    attach_pillbox_schedules,
    create_pillbox_schedule,
    encode_stored_dose_instructions,
    ensure_pillbox_patient,
    get_medications_id_column,
    instruction_for_dose_index,
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
    dose_instructions = align_dose_instructions(
        scheduled_times,
        data.get("dose_instructions"),
        data.get("instructions"),
    )
    data["dose_instructions"] = dose_instructions
    data["instructions"] = dose_instructions[0] if dose_instructions else data.get("instructions")

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

        pillbox_payload = {
            "patient_id": elder_id,
            "name": data["name"],
            "dosage_text": data["dosage"],
            "form": "pill",
            "instructions": data["instructions"],
            "active": True,
            "created_by": caregiver_id,
            "dose_instructions": dose_instructions,
        }
        try:
            result = db.table("medications").insert(pillbox_payload).execute()
        except Exception:
            pillbox_payload["instructions"] = encode_stored_dose_instructions(dose_instructions)
            pillbox_payload.pop("dose_instructions", None)
            result = db.table("medications").insert(pillbox_payload).execute()
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
    return _list_active_medications(db, elder_id)


def _list_active_medications(db: Client, elder_id: str) -> list[dict]:
    """Return active medications with schedules attached when using PillBox schema."""
    column = get_medications_id_column(db)
    result = (
        db.table("medications")
        .select("*")
        .eq(column, elder_id)
        .eq("active", True)
        .order("created_at", desc=True)
        .execute()
    )
    rows = result.data or []
    if column == "patient_id":
        return attach_pillbox_schedules(db, rows)
    return [normalize_medication_row(row) for row in rows]


def _dose_log_for_slot(
    db: Client, medication_id: str, scheduled_iso: str
) -> dict | None:
    """Find a medication log row for a scheduled dose time."""
    return first_row(
        db.table("medication_logs")
        .select("*")
        .eq("medication_id", medication_id)
        .eq("scheduled_for", scheduled_iso)
        .limit(1)
        .execute()
    )


def _build_today_dose_slots(db: Client, elder_id: str, pending_only: bool = False) -> list[dict]:
    """Build today's dose slots from medications and optional log status."""
    today = date.today()
    start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    now = datetime.now(timezone.utc)

    meds = _list_active_medications(db, elder_id)
    doses: list[dict] = []

    for med in meds:
        dosage = med.get("dosage") or med.get("dosage_text") or ""
        for index, time_str in enumerate(med.get("scheduled_times", [])):
            hour, minute = _parse_time(time_str)
            scheduled_dt = start.replace(hour=hour, minute=minute)
            if scheduled_dt >= end:
                continue

            scheduled_iso = scheduled_dt.isoformat()
            log = _dose_log_for_slot(db, med["id"], scheduled_iso)

            status = "pending"
            log_id = None
            taken_at = None
            if log:
                status = log["status"]
                log_id = log["id"]
                taken_at = log.get("taken_at")

            minutes_overdue = 0
            if status == "pending" and scheduled_dt < now:
                minutes_overdue = max(0, int((now - scheduled_dt).total_seconds() / 60))

            if pending_only and status != "pending":
                continue

            doses.append({
                "log_id": log_id,
                "medication_id": med["id"],
                "medication_name": med["name"],
                "dosage": dosage,
                "instructions": instruction_for_dose_index(med, index),
                "scheduled_for": scheduled_iso,
                "status": status,
                "taken_at": taken_at,
                "minutes_overdue": minutes_overdue,
            })

    doses.sort(key=lambda d: d["scheduled_for"])
    return doses


def get_today_doses(
    db: Client, elder_id: str, requester_id: str, requester_role: str
) -> list[dict]:
    """Return all of today's scheduled doses with taken/pending status."""
    verify_elder_access(db, requester_id, elder_id, requester_role)
    return _build_today_dose_slots(db, elder_id, pending_only=False)


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
    return _build_today_dose_slots(db, elder_id, pending_only=True)


def get_adherence_stats(
    db: Client, elder_id: str, requester_id: str, requester_role: str, days: int = 7
) -> dict:
    """Return adherence statistics by merging schedules with dose logs."""
    verify_elder_access(db, requester_id, elder_id, requester_role)

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    since_date = since.date()

    meds = _list_active_medications(db, elder_id)

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

        for med in meds:
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

    total = taken + missed
    return {
        "period": f"last_{days}_days",
        "total_scheduled": total,
        "taken": taken,
        "missed": missed,
        "adherence_pct": round((taken / total) * 100) if total else 100,
        "daily_breakdown": breakdown,
    }


ON_TIME_GRACE_MINUTES = 30
_STATUS_PRIORITY = {"overdue": 0, "in_progress": 1, "upcoming": 2, "complete": 3, "no_meds": 4}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _summarize_patient_today(doses: list[dict], elder: dict) -> dict:
    """Build per-patient today adherence summary for the caregiver dashboard."""
    scheduled = len(doses)
    if scheduled == 0:
        return {
            "elder_id": elder["elder_id"],
            "full_name": elder.get("full_name"),
            "last_name": elder.get("last_name"),
            "today_scheduled": 0,
            "today_taken": 0,
            "today_on_time": 0,
            "today_late": 0,
            "today_pending": 0,
            "today_overdue": 0,
            "today_missed": 0,
            "adherence_today_pct": 100,
            "week_taken": 0,
            "week_missed": 0,
            "week_adherence_pct": 100,
            "status": "no_meds",
            "next_dose_at": None,
            "last_taken_at": None,
            "overdue_doses": [],
        }

    taken = on_time = late = pending = overdue = missed = 0
    overdue_doses: list[dict] = []
    upcoming: list[dict] = []
    taken_times: list[str] = []

    for dose in doses:
        if dose["status"] == "taken":
            taken += 1
            scheduled_dt = _parse_iso(dose["scheduled_for"])
            taken_dt = _parse_iso(dose.get("taken_at"))
            if (
                scheduled_dt
                and taken_dt
                and taken_dt <= scheduled_dt + timedelta(minutes=ON_TIME_GRACE_MINUTES)
            ):
                on_time += 1
            else:
                late += 1
            if dose.get("taken_at"):
                taken_times.append(dose["taken_at"])
        elif dose["status"] == "pending":
            pending += 1
            minutes_overdue = dose.get("minutes_overdue", 0)
            if minutes_overdue > ON_TIME_GRACE_MINUTES:
                missed += 1
                overdue_doses.append({
                    "medication_name": dose["medication_name"],
                    "dosage": dose["dosage"],
                    "scheduled_for": dose["scheduled_for"],
                    "minutes_overdue": minutes_overdue,
                })
            elif minutes_overdue > 0:
                overdue += 1
                overdue_doses.append({
                    "medication_name": dose["medication_name"],
                    "dosage": dose["dosage"],
                    "scheduled_for": dose["scheduled_for"],
                    "minutes_overdue": minutes_overdue,
                })
            else:
                upcoming.append(dose)

    if overdue > 0 or missed > 0:
        status = "overdue"
    elif pending > 0 and taken > 0:
        status = "in_progress"
    elif pending == 0:
        status = "complete"
    else:
        status = "upcoming"

    next_dose = min(upcoming, key=lambda d: d["scheduled_for"]) if upcoming else None
    last_taken = max(taken_times) if taken_times else None

    return {
        "elder_id": elder["elder_id"],
        "full_name": elder.get("full_name"),
        "last_name": elder.get("last_name"),
        "today_scheduled": scheduled,
        "today_taken": taken,
        "today_on_time": on_time,
        "today_late": late,
        "today_pending": pending,
        "today_overdue": overdue,
        "today_missed": missed,
        "adherence_today_pct": round((taken / scheduled) * 100) if scheduled else 100,
        "week_taken": 0,
        "week_missed": 0,
        "week_adherence_pct": 100,
        "status": status,
        "next_dose_at": next_dose["scheduled_for"] if next_dose else None,
        "last_taken_at": last_taken,
        "overdue_doses": overdue_doses,
    }


def get_caregiver_adherence_dashboard(
    db: Client, caregiver_id: str, days: int = 7
) -> dict:
    """Aggregate medication adherence across all linked patients for the caregiver home."""
    from app.services.user_service import get_my_elders

    elders = get_my_elders(db, caregiver_id)
    patients: list[dict] = []
    aggregated_daily: dict[str, dict[str, int]] = {}
    week_taken_total = 0
    week_missed_total = 0

    for elder in elders:
        doses = _build_today_dose_slots(db, elder["elder_id"])
        summary = _summarize_patient_today(doses, elder)
        week_stats = get_adherence_stats(
            db, elder["elder_id"], caregiver_id, "caregiver", days
        )
        summary["week_taken"] = week_stats["taken"]
        summary["week_missed"] = week_stats["missed"]
        summary["week_adherence_pct"] = week_stats.get("adherence_pct", 100)
        week_taken_total += week_stats["taken"]
        week_missed_total += week_stats["missed"]

        for day in week_stats["daily_breakdown"]:
            bucket = aggregated_daily.setdefault(day["date"], {"taken": 0, "missed": 0})
            bucket["taken"] += day["taken"]
            bucket["missed"] += day["missed"]

        patients.append(summary)

    patients.sort(key=lambda p: (_STATUS_PRIORITY.get(p["status"], 99), p.get("full_name") or ""))

    doses_scheduled = sum(p["today_scheduled"] for p in patients)
    doses_taken = sum(p["today_taken"] for p in patients)
    doses_on_time = sum(p["today_on_time"] for p in patients)
    doses_late = sum(p["today_late"] for p in patients)
    doses_pending = sum(p["today_pending"] for p in patients)
    doses_overdue = sum(p["today_overdue"] for p in patients)
    doses_missed = sum(p["today_missed"] for p in patients)
    on_track = sum(1 for p in patients if p["status"] in ("complete", "upcoming", "in_progress"))
    need_attention = sum(1 for p in patients if p["status"] == "overdue")

    week_total = week_taken_total + week_missed_total
    return {
        "date": date.today().isoformat(),
        "totals": {
            "patients": len(patients),
            "doses_scheduled_today": doses_scheduled,
            "doses_taken_today": doses_taken,
            "doses_on_time_today": doses_on_time,
            "doses_late_today": doses_late,
            "doses_pending_today": doses_pending,
            "doses_overdue_today": doses_overdue,
            "doses_missed_today": doses_missed,
            "patients_on_track": on_track,
            "patients_need_attention": need_attention,
        },
        "overall_today_pct": round((doses_taken / doses_scheduled) * 100) if doses_scheduled else 100,
        "overall_week_pct": round((week_taken_total / week_total) * 100) if week_total else 100,
        "daily_breakdown": [
            {"date": d, "taken": v["taken"], "missed": v["missed"]}
            for d, v in sorted(aggregated_daily.items())
        ],
        "patients": patients,
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
