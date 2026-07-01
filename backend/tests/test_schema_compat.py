"""Tests for schema-aware Supabase table helpers."""

import app.pillbox_compat as pillbox_compat
from app.schema_compat import (
    filter_table_payload,
    get_table_columns,
    map_medical_history_payload,
    map_medication_log_payload,
    medication_log_schedule_column,
    reset_schema_cache,
)


class FakeTableDb:
    def __init__(self, table_columns: dict[str, set[str]]):
        self.table_columns = table_columns
        reset_schema_cache()
        pillbox_compat._MEDICATIONS_ID_COLUMN = None
        pillbox_compat._PATIENTS_TABLE_AVAILABLE = None

    def table(self, name):
        return FakeTableQuery(self.table_columns.get(name, set()))


class FakeTableQuery:
    def __init__(self, columns: set[str]):
        self.columns = columns
        self._column = None

    def select(self, column, **_kwargs):
        self._column = column.split(",")[0].strip()
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self._column not in self.columns:
            raise Exception("42703 column does not exist")
        return type("Result", (), {"data": []})()


def test_get_table_columns_matches_careconnect_medications():
    db = FakeTableDb(
        {
            "medications": {
                "id", "elder_id", "name", "dosage", "instructions",
                "dose_instructions", "frequency", "scheduled_times", "active", "created_at",
            }
        }
    )

    columns = get_table_columns(db, "medications")

    assert "dose_instructions" in columns
    assert "patient_id" not in columns


def test_filter_table_payload_drops_unknown_fields():
    db = FakeTableDb({"contacts": {"id", "elder_id", "name", "contact_type", "phone", "is_primary"}})

    payload = filter_table_payload(
        db,
        "contacts",
        {
            "elder_id": "e1",
            "name": "Dr Smith",
            "contact_type": "doctor",
            "phone": "555-0100",
            "email": "legacy@example.com",
            "notes": "legacy notes",
        },
    )

    assert payload == {
        "elder_id": "e1",
        "name": "Dr Smith",
        "contact_type": "doctor",
        "phone": "555-0100",
    }


def test_map_medical_history_payload_maps_date_occurred():
    db = FakeTableDb({"medical_history": {"id", "elder_id", "category", "title", "date_occurred"}})

    payload = map_medical_history_payload(
        db,
        {"elder_id": "e1", "category": "condition", "title": "Asthma", "date_occurred": "2020-05-01"},
    )

    assert payload["date_occurred"] == "2020-05-01"


def test_map_medication_log_payload_uses_scheduled_for():
    db = FakeTableDb(
        {"medication_logs": {"id", "medication_id", "elder_id", "scheduled_for", "status"}}
    )

    payload = map_medication_log_payload(
        db,
        {"medication_id": "m1", "elder_id": "e1", "scheduled_for": "2026-06-30T08:00:00+00:00", "status": "taken"},
    )

    assert payload["scheduled_for"] == "2026-06-30T08:00:00+00:00"
    assert medication_log_schedule_column(db) == "scheduled_for"
