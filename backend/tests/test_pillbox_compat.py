"""Tests for per-dose instruction normalization."""

from app.pillbox_compat import (
    attach_pillbox_schedules,
    decode_stored_dose_instructions,
    instruction_for_dose_index,
    normalize_medication_row,
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
