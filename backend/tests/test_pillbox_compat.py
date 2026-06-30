"""Tests for per-dose instruction normalization and patient profile bridging."""

from app.pillbox_compat import (
    attach_pillbox_schedules,
    decode_stored_dose_instructions,
    filter_users_payload,
    instruction_for_dose_index,
    merge_patient_details,
    normalize_medication_row,
    split_profile_updates,
)


def test_normalize_decodes_encoded_instructions_after_times_attached():
    row = {
        "id": "med-1",
        "patient_id": "p-1",
        "name": "Test Med",
        "dosage_text": "10mg",
        "instructions": '__dose_json:["After Breakfast", "Before Lunch", "After Dinner"]',
        "dose_instructions": [],
        "scheduled_times": ["08:00", "14:00", "20:00"],
    }

    normalized = normalize_medication_row(row)

    assert normalized["dose_instructions"] == [
        "After Breakfast",
        "Before Lunch",
        "After Dinner",
    ]
    assert normalized["instructions"] == "After Breakfast"


def test_normalize_uses_jsonb_dose_instructions():
    row = {
        "id": "med-2",
        "patient_id": "p-1",
        "name": "Test Med",
        "dosage_text": "10mg",
        "instructions": "legacy",
        "dose_instructions": ["Morning dose", "Evening dose"],
        "scheduled_times": ["08:00", "20:00"],
    }

    normalized = normalize_medication_row(row)

    assert normalized["dose_instructions"] == ["Morning dose", "Evening dose"]
    assert normalized["instructions"] == "Morning dose"


def test_attach_pillbox_schedules_normalizes_after_schedule_times():
    class FakeQuery:
        def __init__(self, schedule):
            self.schedule = schedule

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            class Result:
                data = [self.schedule] if self.schedule else []

            return Result()

    class FakeDb:
        def __init__(self, schedule):
            self.schedule = schedule

        def table(self, name):
            assert name == "schedules"
            return FakeQuery(self.schedule)

    med = {
        "id": "med-3",
        "patient_id": "p-1",
        "name": "Test Med",
        "dosage_text": "10mg",
        "instructions": '__dose_json:["After Breakfast", "Before Lunch", "After Dinner"]',
        "dose_instructions": ["After Breakfast", "Before Lunch", "After Dinner"],
    }
    schedule = {
        "times": ["08:00", "14:00", "20:00"],
        "frequency": "Three times daily",
        "timezone": "America/Chicago",
    }

    result = attach_pillbox_schedules(FakeDb(schedule), [med])

    assert result[0]["scheduled_times"] == ["08:00", "14:00", "20:00"]
    assert result[0]["dose_instructions"] == [
        "After Breakfast",
        "Before Lunch",
        "After Dinner",
    ]
    assert instruction_for_dose_index(result[0], 1) == "Before Lunch"


def test_decode_stored_dose_instructions_round_trip():
    encoded = '__dose_json:["A", "B", "C"]'
    decoded = decode_stored_dose_instructions(encoded, 3)
    assert decoded == ["A", "B", "C"]


class FakeUsersDb:
    """Minimal fake DB for users column probing."""

    def __init__(self, optional_columns: set[str], has_patients: bool = True):
        self.optional_columns = optional_columns
        self.has_patients = has_patients
        import app.pillbox_compat as compat

        compat._USERS_COLUMNS = None
        compat._PATIENTS_TABLE_AVAILABLE = None

    def table(self, name):
        if name == "users":
            return FakeUsersQuery(self.optional_columns)
        if name == "patients":
            return FakePatientsQuery(self.has_patients)
        raise AssertionError(f"unexpected table {name}")


class FakeUsersQuery:
    PROBED_COLUMNS = {
        "date_of_birth",
        "address",
        "notes",
        "login_code",
        "login_code_set_at",
    }

    def __init__(self, optional_columns: set[str]):
        self.optional_columns = optional_columns
        self._column = None

    def select(self, column, **_kwargs):
        self._column = column.split(",")[0].strip() if "," not in column else column
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def execute(self):
        col = self._column
        if col in self.PROBED_COLUMNS and col not in self.optional_columns:
            raise Exception("42703 column does not exist")
        return type("Result", (), {"data": []})()


class FakePatientsQuery:
    def __init__(self, available: bool):
        self.available = available

    def select(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if not self.available:
            raise Exception("relation patients does not exist")
        return type("Result", (), {"data": []})()


def test_merge_patient_details_fills_missing_users_fields():
    user = {"id": "p-1", "full_name": "Jane", "role": "elder"}
    patient = {
        "display_name": "Jane Doe",
        "date_of_birth": "1945-03-12",
        "notes": "Uses walker",
    }

    merged = merge_patient_details(user, patient)

    assert merged["full_name"] == "Jane"
    assert merged["date_of_birth"] == "1945-03-12"
    assert merged["notes"] == "Uses walker"


def test_split_profile_updates_routes_to_patients_when_users_columns_missing():
    db = FakeUsersDb(optional_columns=set())

    users_updates, patients_updates = split_profile_updates(
        db,
        {
            "full_name": "Jane Doe",
            "date_of_birth": "1945-03-12",
            "notes": "Allergic to penicillin",
            "address": "123 Main St",
        },
    )

    assert users_updates == {"full_name": "Jane Doe"}
    assert patients_updates == {
        "display_name": "Jane Doe",
        "date_of_birth": "1945-03-12",
        "notes": "Allergic to penicillin",
    }


def test_filter_users_payload_drops_missing_detail_columns():
    db = FakeUsersDb(optional_columns={"notes"})

    payload = filter_users_payload(
        db,
        {
            "id": "p-1",
            "full_name": "Jane",
            "date_of_birth": "1945-03-12",
            "address": "123 Main St",
            "notes": "Care notes",
        },
    )

    assert "date_of_birth" not in payload
    assert "address" not in payload
    assert payload["notes"] == "Care notes"
    assert payload["full_name"] == "Jane"
