-- Per-dose instructions aligned with scheduled_times (same index).
ALTER TABLE medications
  ADD COLUMN IF NOT EXISTS dose_instructions JSONB NOT NULL DEFAULT '[]';
