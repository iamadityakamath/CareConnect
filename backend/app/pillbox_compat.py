"""Helpers for shared Supabase databases that also use the PillBox schema."""

from supabase import Client

from app.db_utils import first_row


def medications_use_patient_id(db: Client) -> bool:
    """Return True when medications rows are keyed by PillBox ``patient_id``."""
    try:
        db.table("medications").select("patient_id").limit(1).execute()
        return True
    except Exception:
        return False


def ensure_pillbox_patient(
    db: Client,
    caregiver_id: str,
    patient_id: str,
    display_name: str,
) -> None:
    """Ensure a PillBox ``patients`` row exists for a CareConnect elder profile."""
    try:
        existing = first_row(
            db.table("patients").select("id").eq("id", patient_id).limit(1).execute()
        )
        if existing:
            return

        db.table("patients").insert(
            {
                "id": patient_id,
                "display_name": display_name or "Patient",
                "created_by": caregiver_id,
            }
        ).execute()
    except Exception:
        # PillBox patients table not present — CareConnect-only database.
        return


def normalize_medication_row(row: dict, fallback: dict | None = None) -> dict:
    """Map PillBox medication columns to the CareConnect API shape."""
    normalized = dict(row)
    fallback = fallback or {}

    if normalized.get("patient_id") and not normalized.get("elder_id"):
        normalized["elder_id"] = normalized["patient_id"]
    if normalized.get("dosage_text") and not normalized.get("dosage"):
        normalized["dosage"] = normalized["dosage_text"]

    normalized.setdefault("frequency", fallback.get("frequency", "Daily"))
    normalized.setdefault("scheduled_times", fallback.get("scheduled_times", []))
    normalized.setdefault("instructions", fallback.get("instructions"))
    return normalized


def attach_pillbox_schedules(db: Client, medications: list[dict]) -> list[dict]:
    """Attach schedule times from PillBox ``schedules`` rows when present."""
    enriched: list[dict] = []
    for med in medications:
        row = normalize_medication_row(med)
        try:
            schedule = first_row(
                db.table("schedules")
                .select("times, frequency, timezone")
                .eq("medication_id", med["id"])
                .eq("active", True)
                .limit(1)
                .execute()
            )
        except Exception:
            schedule = None

        if schedule:
            row["scheduled_times"] = schedule.get("times") or []
            row["frequency"] = schedule.get("frequency") or row.get("frequency")
        enriched.append(row)
    return enriched


def create_pillbox_schedule(
    db: Client,
    medication_id: str,
    scheduled_times: list[str],
    frequency: str,
    timezone: str = "America/Chicago",
) -> None:
    """Create a PillBox schedule row for a medication."""
    try:
        db.table("schedules").insert(
            {
                "medication_id": medication_id,
                "frequency": "daily",
                "times": scheduled_times,
                "timezone": timezone,
            }
        ).execute()
    except Exception:
        # schedules table missing on CareConnect-only databases.
        return
