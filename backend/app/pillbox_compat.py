"""Helpers for shared Supabase databases that also use the PillBox schema."""

import json

from supabase import Client

from app.db_utils import first_row

_MEDICATIONS_ID_COLUMN: str | None = None
_MEDICATIONS_COLUMNS: frozenset[str] | None = None
_USERS_COLUMNS: frozenset[str] | None = None
_PATIENTS_TABLE_AVAILABLE: bool | None = None
_DOSE_INSTRUCTIONS_PREFIX = "__dose_json:"

_USERS_BASE_COLUMNS = (
    "id",
    "email",
    "auth_email",
    "full_name",
    "last_name",
    "role",
    "phone",
    "timezone",
    "account_status",
    "login_code",
    "login_code_set_at",
    "created_at",
)
_USERS_OPTIONAL_DETAIL_COLUMNS = ("date_of_birth", "address", "notes")
_USERS_PROBE_COLUMNS = _USERS_BASE_COLUMNS + _USERS_OPTIONAL_DETAIL_COLUMNS

_MEDICATIONS_PROBE_COLUMNS = (
    "elder_id",
    "patient_id",
    "name",
    "dosage",
    "dosage_text",
    "form",
    "instructions",
    "dose_instructions",
    "frequency",
    "scheduled_times",
    "active",
    "created_at",
    "created_by",
)


def _postgres_error_code(exc: Exception) -> str | None:
    """Extract a Postgres error code from a Supabase/PostgREST exception."""
    args = getattr(exc, "args", ())
    if args and isinstance(args[0], dict):
        return args[0].get("code")
    return getattr(exc, "code", None)


def _is_missing_column_error(exc: Exception) -> bool:
    code = _postgres_error_code(exc)
    if code == "42703":
        return True
    message = str(exc).lower()
    return "does not exist" in message and "column" in message


def get_medications_id_column(db: Client) -> str:
    """Return ``patient_id`` or ``elder_id`` — whichever the medications table uses."""
    global _MEDICATIONS_ID_COLUMN
    if _MEDICATIONS_ID_COLUMN:
        return _MEDICATIONS_ID_COLUMN

    for column in ("patient_id", "elder_id"):
        try:
            db.table("medications").select(column).limit(1).execute()
            _MEDICATIONS_ID_COLUMN = column
            return column
        except Exception as exc:
            if _is_missing_column_error(exc):
                continue
            raise

    _MEDICATIONS_ID_COLUMN = "elder_id"
    return _MEDICATIONS_ID_COLUMN


def medications_use_patient_id(db: Client) -> bool:
    """Return True when medications rows are keyed by PillBox ``patient_id``."""
    return get_medications_id_column(db) == "patient_id"


def get_medications_columns(db: Client) -> frozenset[str]:
    """Return ``medications`` columns that exist in the connected database."""
    global _MEDICATIONS_COLUMNS
    if _MEDICATIONS_COLUMNS is not None:
        return _MEDICATIONS_COLUMNS

    available: set[str] = set()
    for column in _MEDICATIONS_PROBE_COLUMNS:
        try:
            db.table("medications").select(column).limit(1).execute()
            available.add(column)
        except Exception as exc:
            if not _is_missing_column_error(exc):
                raise

    _MEDICATIONS_COLUMNS = frozenset(available)
    return _MEDICATIONS_COLUMNS


def prepare_medication_write_payload(db: Client, data: dict) -> dict:
    """Build an insert/update payload that only uses columns present in the schema."""
    columns = get_medications_columns(db)
    payload: dict = {}

    elder_id = data.get("elder_id")
    if elder_id:
        if "elder_id" in columns:
            payload["elder_id"] = elder_id
        elif "patient_id" in columns:
            payload["patient_id"] = elder_id

    dosage = data.get("dosage")
    if dosage is not None:
        if "dosage" in columns:
            payload["dosage"] = dosage
        elif "dosage_text" in columns:
            payload["dosage_text"] = dosage

    for key in ("name", "frequency", "scheduled_times", "active", "form", "created_by"):
        if key in data and data[key] is not None and key in columns:
            payload[key] = data[key]

    dose_instructions = data.get("dose_instructions")
    instructions = data.get("instructions")

    if dose_instructions is not None and "dose_instructions" in columns:
        payload["dose_instructions"] = dose_instructions

    if "instructions" in columns:
        if dose_instructions is not None and "dose_instructions" not in columns:
            payload["instructions"] = (
                encode_stored_dose_instructions(dose_instructions) or instructions
            )
        elif instructions is not None:
            payload["instructions"] = instructions
        elif dose_instructions:
            first = next((item for item in dose_instructions if item), None)
            if first:
                payload["instructions"] = first

    return payload


def get_users_columns(db: Client) -> frozenset[str]:
    """Return ``users`` columns that exist in the connected database."""
    global _USERS_COLUMNS
    if _USERS_COLUMNS is not None:
        return _USERS_COLUMNS

    available: set[str] = set()
    for column in _USERS_PROBE_COLUMNS:
        try:
            db.table("users").select(column).limit(1).execute()
            available.add(column)
        except Exception as exc:
            if not _is_missing_column_error(exc):
                raise

    _USERS_COLUMNS = frozenset(available)
    return _USERS_COLUMNS


def users_select_expr(db: Client, *columns: str) -> str:
    """Build a safe ``users`` select list, skipping columns absent from the schema."""
    allowed = get_users_columns(db)
    selected = [column for column in columns if column in allowed]
    if not selected:
        selected = ["id"]
    return ", ".join(dict.fromkeys(selected))


def has_patients_table(db: Client) -> bool:
    """Return True when the shared PillBox ``patients`` table is available."""
    global _PATIENTS_TABLE_AVAILABLE
    if _PATIENTS_TABLE_AVAILABLE is not None:
        return _PATIENTS_TABLE_AVAILABLE

    try:
        db.table("patients").select("id").limit(1).execute()
        _PATIENTS_TABLE_AVAILABLE = True
    except Exception:
        _PATIENTS_TABLE_AVAILABLE = False
    return _PATIENTS_TABLE_AVAILABLE


def filter_users_payload(db: Client, payload: dict) -> dict:
    """Drop ``users`` fields that are not present in the connected schema."""
    allowed = get_users_columns(db)
    return {key: value for key, value in payload.items() if key in allowed}


def fetch_user_row(db: Client, user_id: str) -> dict | None:
    """Fetch a ``users`` row using only columns that exist in the schema."""
    columns = ", ".join(sorted(get_users_columns(db)))
    return first_row(
        db.table("users").select(columns).eq("id", user_id).limit(1).execute()
    )


def fetch_pillbox_patient_row(db: Client, patient_id: str) -> dict | None:
    """Fetch PillBox patient metadata when the ``patients`` table is present."""
    if not has_patients_table(db):
        return None
    try:
        return first_row(
            db.table("patients")
            .select("display_name, date_of_birth, notes")
            .eq("id", patient_id)
            .limit(1)
            .execute()
        )
    except Exception:
        return None


def merge_patient_details(user_row: dict, patient_row: dict | None) -> dict:
    """Merge CareConnect ``users`` fields with PillBox ``patients`` metadata."""
    merged = dict(user_row)
    if not patient_row:
        return merged

    if patient_row.get("display_name") and not merged.get("full_name"):
        merged["full_name"] = patient_row["display_name"]
    if patient_row.get("date_of_birth") and not merged.get("date_of_birth"):
        merged["date_of_birth"] = str(patient_row["date_of_birth"])[:10]
    if patient_row.get("notes") is not None and merged.get("notes") is None:
        merged["notes"] = patient_row["notes"]
    return merged


def enrich_elder_profile(db: Client, user_row: dict) -> dict:
    """Attach PillBox patient details to a CareConnect elder profile."""
    if user_row.get("role") != "elder":
        return user_row
    patient_row = fetch_pillbox_patient_row(db, user_row["id"])
    return merge_patient_details(user_row, patient_row)


def split_profile_updates(db: Client, updates: dict) -> tuple[dict, dict]:
    """Split profile updates between ``users`` and PillBox ``patients`` tables."""
    users_columns = get_users_columns(db)
    users_updates: dict = {}
    patients_updates: dict = {}

    for key, value in updates.items():
        if key == "full_name":
            users_updates["full_name"] = value
            if has_patients_table(db):
                patients_updates["display_name"] = value
        elif key == "date_of_birth":
            if "date_of_birth" in users_columns:
                users_updates["date_of_birth"] = value
            if has_patients_table(db):
                patients_updates["date_of_birth"] = value
        elif key == "notes":
            if "notes" in users_columns:
                users_updates["notes"] = value
            if has_patients_table(db):
                patients_updates["notes"] = value
        elif key == "address":
            if "address" in users_columns:
                users_updates["address"] = value
        elif key in users_columns:
            users_updates[key] = value

    return users_updates, patients_updates


def update_pillbox_patient_details(
    db: Client,
    patient_id: str,
    caregiver_id: str,
    updates: dict,
) -> None:
    """Write patient-specific fields to PillBox ``patients`` when present."""
    if not updates or not has_patients_table(db):
        return

    try:
        existing = first_row(
            db.table("patients").select("id").eq("id", patient_id).limit(1).execute()
        )
        if existing:
            db.table("patients").update(updates).eq("id", patient_id).execute()
            return

        payload = {"id": patient_id, "created_by": caregiver_id, **updates}
        payload.setdefault("display_name", updates.get("display_name") or "Patient")
        db.table("patients").insert(payload).execute()
    except Exception:
        return


def ensure_pillbox_patient(
    db: Client,
    caregiver_id: str,
    patient_id: str,
    display_name: str,
    date_of_birth: str | None = None,
    notes: str | None = None,
) -> None:
    """Ensure a PillBox ``patients`` row exists for a CareConnect elder profile."""
    payload: dict = {"display_name": display_name or "Patient"}
    if date_of_birth:
        payload["date_of_birth"] = date_of_birth
    if notes is not None and notes.strip():
        payload["notes"] = notes.strip()

    try:
        existing = first_row(
            db.table("patients").select("id").eq("id", patient_id).limit(1).execute()
        )
        if existing:
            db.table("patients").update(payload).eq("id", patient_id).execute()
            return

        payload["id"] = patient_id
        payload["created_by"] = caregiver_id
        db.table("patients").insert(payload).execute()
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
    if not normalized.get("scheduled_times") and fallback.get("scheduled_times"):
        normalized["scheduled_times"] = fallback["scheduled_times"]

    times = normalized.get("scheduled_times") or []
    raw_dose = _coerce_dose_instructions(normalized.get("dose_instructions"))
    if raw_dose is None:
        raw_dose = _coerce_dose_instructions(fallback.get("dose_instructions"))

    if raw_dose:
        normalized["dose_instructions"] = align_dose_instructions(times, raw_dose, None)
    else:
        normalized["dose_instructions"] = decode_stored_dose_instructions(
            normalized.get("instructions"), len(times)
        )

    normalized["instructions"] = _display_instruction(
        normalized.get("instructions"), normalized["dose_instructions"]
    )

    return normalized


def _coerce_dose_instructions(value) -> list[str | None] | None:
    """Parse dose_instructions from JSONB list or JSON string."""
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        return [str(v).strip() if v else None for v in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(v).strip() if v else None for v in parsed]
        except json.JSONDecodeError:
            pass
    return None


def _display_instruction(
    stored: str | None, dose_instructions: list[str | None]
) -> str | None:
    """Return a human-readable instruction, never the encoded multi-dose blob."""
    first = next((item for item in dose_instructions if item), None)
    if first:
        return first
    if stored and stored.startswith(_DOSE_INSTRUCTIONS_PREFIX):
        return None
    return stored


def align_dose_instructions(
    scheduled_times: list[str],
    dose_instructions: list[str | None] | None,
    fallback: str | None = None,
) -> list[str | None]:
    """Pad or trim per-dose instructions to match scheduled time slots."""
    count = len(scheduled_times)
    if count == 0:
        return []

    aligned = list(dose_instructions or [])
    while len(aligned) < count:
        aligned.append(fallback if len(aligned) == 0 else None)
    return aligned[:count]


def encode_stored_dose_instructions(dose_instructions: list[str | None]) -> str | None:
    """Serialize per-dose instructions for PillBox ``instructions`` text column."""
    cleaned = [(item or "").strip() for item in dose_instructions]
    if not any(cleaned):
        return None
    if len(cleaned) == 1:
        return cleaned[0] or None
    return _DOSE_INSTRUCTIONS_PREFIX + json.dumps(cleaned)


def decode_stored_dose_instructions(
    stored: str | None, slot_count: int
) -> list[str | None]:
    """Restore per-dose instructions from column JSON or encoded text."""
    if slot_count <= 0:
        return []

    if stored and stored.startswith(_DOSE_INSTRUCTIONS_PREFIX):
        try:
            parsed = json.loads(stored[len(_DOSE_INSTRUCTIONS_PREFIX) :])
            if isinstance(parsed, list):
                return align_dose_instructions(
                    [""] * slot_count,
                    [str(v) if v else None for v in parsed],
                )
        except json.JSONDecodeError:
            pass

    if stored:
        return [stored] + [None] * (slot_count - 1)
    return [None] * slot_count


def instruction_for_dose_index(med: dict, index: int) -> str | None:
    """Return the instruction for a scheduled dose slot."""
    dose_instructions = med.get("dose_instructions")
    if isinstance(dose_instructions, list) and index < len(dose_instructions):
        value = dose_instructions[index]
        if value:
            return value

    stored = med.get("instructions")
    if stored and isinstance(stored, str) and stored.startswith(_DOSE_INSTRUCTIONS_PREFIX):
        decoded = decode_stored_dose_instructions(stored, index + 1)
        if index < len(decoded) and decoded[index]:
            return decoded[index]
        return None

    return stored if index == 0 else None


def attach_pillbox_schedules(db: Client, medications: list[dict]) -> list[dict]:
    """Attach schedule times from PillBox ``schedules`` rows when present."""
    enriched: list[dict] = []
    for med in medications:
        row = dict(med)
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

        enriched.append(normalize_medication_row(row))
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
