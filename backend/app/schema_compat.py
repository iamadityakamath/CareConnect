"""Schema introspection and safe Supabase reads/writes across CareConnect and PillBox."""

from supabase import Client

from app.db_utils import first_row

_TABLE_COLUMNS_CACHE: dict[str, frozenset[str]] = {}

# CareConnect tables and columns (matches sql/schema.sql / live Supabase).
CARECONNECT_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "users": (
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
        "date_of_birth",
        "address",
        "notes",
        "created_at",
    ),
    "relationships": (
        "id",
        "caregiver_id",
        "elder_id",
        "status",
        "created_by",
        "created_at",
    ),
    "medications": (
        "id",
        "elder_id",
        "name",
        "dosage",
        "instructions",
        "dose_instructions",
        "frequency",
        "scheduled_times",
        "active",
        "created_at",
    ),
    "medication_logs": (
        "id",
        "medication_id",
        "elder_id",
        "scheduled_for",
        "taken_at",
        "status",
        "created_at",
    ),
    "checkins": (
        "id",
        "elder_id",
        "mood_score",
        "note",
        "created_at",
    ),
    "medical_history": (
        "id",
        "elder_id",
        "category",
        "title",
        "description",
        "date_occurred",
        "is_active",
        "created_at",
    ),
    "contacts": (
        "id",
        "elder_id",
        "name",
        "contact_type",
        "specialty",
        "phone",
        "address",
        "is_primary",
        "created_at",
    ),
}

# Optional PillBox-only columns probed when present on shared databases.
PILLBOX_OPTIONAL_COLUMNS: dict[str, tuple[str, ...]] = {
    "medications": ("patient_id", "dosage_text", "form", "created_by"),
    "users": (),
    "medication_logs": ("scheduled_at",),
    "medical_history": ("occurred_on",),
    "contacts": ("email", "notes"),
}


def _postgres_error_code(exc: Exception) -> str | None:
    args = getattr(exc, "args", ())
    if args and isinstance(args[0], dict):
        return args[0].get("code")
    return getattr(exc, "code", None)


def is_missing_column_error(exc: Exception) -> bool:
    code = _postgres_error_code(exc)
    if code == "42703":
        return True
    message = str(exc).lower()
    return "does not exist" in message and "column" in message


def reset_schema_cache() -> None:
    """Clear cached column probes (for tests)."""
    _TABLE_COLUMNS_CACHE.clear()


def get_table_columns(db: Client, table: str) -> frozenset[str]:
    """Return columns that exist for ``table`` in the connected database."""
    if table in _TABLE_COLUMNS_CACHE:
        return _TABLE_COLUMNS_CACHE[table]

    candidates = CARECONNECT_TABLE_COLUMNS.get(table, ())
    extras = PILLBOX_OPTIONAL_COLUMNS.get(table, ())
    available: set[str] = set()

    for column in (*candidates, *extras):
        try:
            db.table(table).select(column).limit(1).execute()
            available.add(column)
        except Exception as exc:
            if not is_missing_column_error(exc):
                raise

    _TABLE_COLUMNS_CACHE[table] = frozenset(available)
    return _TABLE_COLUMNS_CACHE[table]


def table_select_expr(db: Client, table: str, *columns: str) -> str:
    """Build a select list using only columns that exist on ``table``."""
    allowed = get_table_columns(db, table)
    if columns:
        selected = [column for column in columns if column in allowed]
    else:
        selected = sorted(allowed)
    if not selected:
        selected = ["id"]
    return ", ".join(dict.fromkeys(selected))


def filter_table_payload(db: Client, table: str, payload: dict) -> dict:
    """Drop fields from ``payload`` that are not columns on ``table``."""
    allowed = get_table_columns(db, table)
    return {key: value for key, value in payload.items() if key in allowed}


def fetch_table_row(
    db: Client,
    table: str,
    match_column: str,
    match_value: str,
    *columns: str,
) -> dict | None:
    """Fetch one row using a schema-safe column list."""
    select_expr = table_select_expr(db, table, *columns) if columns else table_select_expr(db, table)
    return first_row(
        db.table(table)
        .select(select_expr)
        .eq(match_column, match_value)
        .limit(1)
        .execute()
    )


def map_medical_history_payload(db: Client, payload: dict) -> dict:
    """Normalize medical history writes for CareConnect vs legacy column names."""
    mapped = dict(payload)
    columns = get_table_columns(db, "medical_history")

    if "date_occurred" in mapped and "date_occurred" not in columns:
        if "occurred_on" in columns:
            mapped["occurred_on"] = mapped.pop("date_occurred")
    elif "occurred_on" in mapped and "occurred_on" not in columns:
        if "date_occurred" in columns:
            mapped["date_occurred"] = mapped.pop("occurred_on")

    if mapped.get("date_occurred") is not None:
        mapped["date_occurred"] = str(mapped["date_occurred"])[:10]
    if mapped.get("occurred_on") is not None:
        mapped["occurred_on"] = str(mapped["occurred_on"])[:10]

    return filter_table_payload(db, "medical_history", mapped)


def map_medication_log_payload(db: Client, payload: dict) -> dict:
    """Normalize medication log writes for ``scheduled_for`` vs legacy ``scheduled_at``."""
    mapped = dict(payload)
    columns = get_table_columns(db, "medication_logs")

    if "scheduled_for" in mapped and "scheduled_for" not in columns:
        if "scheduled_at" in columns:
            mapped["scheduled_at"] = mapped.pop("scheduled_for")
    elif "scheduled_at" in mapped and "scheduled_at" not in columns:
        if "scheduled_for" in columns:
            mapped["scheduled_for"] = mapped.pop("scheduled_at")

    return filter_table_payload(db, "medication_logs", mapped)


def medication_log_schedule_column(db: Client) -> str:
    """Return the scheduled timestamp column name on ``medication_logs``."""
    columns = get_table_columns(db, "medication_logs")
    if "scheduled_for" in columns:
        return "scheduled_for"
    if "scheduled_at" in columns:
        return "scheduled_at"
    return "scheduled_for"


def normalize_medication_log_row(row: dict) -> dict:
    """Expose ``scheduled_for`` in API responses regardless of storage column."""
    normalized = dict(row)
    if "scheduled_for" not in normalized and normalized.get("scheduled_at"):
        normalized["scheduled_for"] = normalized["scheduled_at"]
    return normalized
