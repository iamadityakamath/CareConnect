-- Add login_code for caregiver-visible patient sign-in codes.
-- Run in Supabase SQL editor if users table already exists.

ALTER TABLE users ADD COLUMN IF NOT EXISTS login_code TEXT;

COMMENT ON COLUMN users.login_code IS
  'Numeric sign-in code set by caregiver. Stored for caregiver dashboard display; also used as Supabase Auth password.';
