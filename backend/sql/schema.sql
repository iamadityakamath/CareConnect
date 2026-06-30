-- CareConnect Supabase schema
-- Run in Supabase SQL editor or via migration

-- Enums
CREATE TYPE user_role AS ENUM ('elder', 'caregiver');
CREATE TYPE relationship_status AS ENUM ('pending', 'active');
CREATE TYPE medication_log_status AS ENUM ('pending', 'taken', 'missed');
CREATE TYPE medical_history_category AS ENUM ('condition', 'allergy', 'surgery', 'note');
CREATE TYPE contact_type AS ENUM ('doctor', 'hospital', 'pharmacy', 'emergency');

-- Users (extends auth.users)
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    auth_email TEXT NOT NULL UNIQUE,
    full_name TEXT,
    last_name TEXT NOT NULL,
    role user_role NOT NULL,
    phone TEXT,
    timezone TEXT DEFAULT 'America/Chicago',
    account_status TEXT NOT NULL DEFAULT 'active'
        CHECK (account_status IN ('managed', 'active')),
    login_code TEXT,
    login_code_set_at TIMESTAMPTZ,
    date_of_birth DATE,
    address TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_users_email_unique ON users(email) WHERE email IS NOT NULL;
CREATE INDEX idx_users_last_name ON users(last_name);
CREATE INDEX idx_users_last_name_lower ON users (lower(last_name)) WHERE role = 'elder';
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_patient_login ON users(role, last_name) WHERE role = 'elder';

-- Caregiver-elder relationships
CREATE TABLE relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caregiver_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    elder_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status relationship_status NOT NULL DEFAULT 'pending',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (caregiver_id, elder_id),
    CHECK (caregiver_id != elder_id)
);

CREATE INDEX idx_relationships_caregiver ON relationships(caregiver_id);
CREATE INDEX idx_relationships_elder ON relationships(elder_id);

-- Medications
CREATE TABLE medications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    elder_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    dosage TEXT NOT NULL,
    instructions TEXT,
    frequency TEXT NOT NULL,
    scheduled_times JSONB NOT NULL DEFAULT '[]',
    dose_instructions JSONB NOT NULL DEFAULT '[]',
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_medications_elder ON medications(elder_id);
CREATE INDEX idx_medications_active ON medications(elder_id, active);

-- Medication logs
CREATE TABLE medication_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    elder_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scheduled_for TIMESTAMPTZ NOT NULL,
    taken_at TIMESTAMPTZ,
    status medication_log_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_dose UNIQUE (medication_id, scheduled_for)
);

CREATE INDEX idx_medication_logs_elder ON medication_logs(elder_id);
CREATE INDEX idx_medication_logs_scheduled ON medication_logs(elder_id, scheduled_for);

-- Wellness check-ins
CREATE TABLE checkins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    elder_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mood_score INT NOT NULL CHECK (mood_score BETWEEN 1 AND 5),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_checkins_elder ON checkins(elder_id, created_at DESC);

-- Medical history
CREATE TABLE medical_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    elder_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category medical_history_category NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    date_occurred DATE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_medical_history_elder ON medical_history(elder_id);
CREATE INDEX idx_medical_history_category ON medical_history(elder_id, category);

-- Healthcare contacts
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    elder_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    contact_type contact_type NOT NULL,
    specialty TEXT,
    phone TEXT NOT NULL,
    address TEXT,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_contacts_elder ON contacts(elder_id);
CREATE INDEX idx_contacts_type ON contacts(elder_id, contact_type);

-- Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE medications ENABLE ROW LEVEL SECURITY;
ALTER TABLE medication_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkins ENABLE ROW LEVEL SECURITY;
ALTER TABLE medical_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

-- Users: read/update own profile
CREATE POLICY users_select_own ON users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY users_select_linked ON users
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM relationships r
            WHERE r.status = 'active'
            AND (
                (r.caregiver_id = auth.uid() AND r.elder_id = users.id)
                OR (r.elder_id = auth.uid() AND r.caregiver_id = users.id)
            )
        )
    );

CREATE POLICY users_insert_own ON users
    FOR INSERT WITH CHECK (auth.uid() = id);

CREATE POLICY users_update_own ON users
    FOR UPDATE USING (auth.uid() = id);

-- Relationships
CREATE POLICY relationships_select_participant ON relationships
    FOR SELECT USING (auth.uid() IN (caregiver_id, elder_id));

CREATE POLICY relationships_insert_caregiver ON relationships
    FOR INSERT WITH CHECK (auth.uid() = caregiver_id);

CREATE POLICY relationships_update_elder ON relationships
    FOR UPDATE USING (auth.uid() = elder_id);

CREATE POLICY relationships_delete_participant ON relationships
    FOR DELETE USING (auth.uid() IN (caregiver_id, elder_id));

-- Medications
CREATE POLICY medications_select ON medications
    FOR SELECT USING (
        auth.uid() = elder_id
        OR EXISTS (
            SELECT 1 FROM relationships r
            WHERE r.caregiver_id = auth.uid()
            AND r.elder_id = medications.elder_id
            AND r.status = 'active'
        )
    );

CREATE POLICY medications_insert_caregiver ON medications
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM relationships r
            WHERE r.caregiver_id = auth.uid()
            AND r.elder_id = medications.elder_id
            AND r.status = 'active'
        )
    );

CREATE POLICY medications_update_caregiver ON medications
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM relationships r
            WHERE r.caregiver_id = auth.uid()
            AND r.elder_id = medications.elder_id
            AND r.status = 'active'
        )
    );

-- Medication logs
CREATE POLICY medication_logs_select ON medication_logs
    FOR SELECT USING (
        auth.uid() = elder_id
        OR EXISTS (
            SELECT 1 FROM relationships r
            WHERE r.caregiver_id = auth.uid()
            AND r.elder_id = medication_logs.elder_id
            AND r.status = 'active'
        )
    );

CREATE POLICY medication_logs_insert_elder ON medication_logs
    FOR INSERT WITH CHECK (auth.uid() = elder_id);

CREATE POLICY medication_logs_update_elder ON medication_logs
    FOR UPDATE USING (auth.uid() = elder_id);

-- Check-ins
CREATE POLICY checkins_select ON checkins
    FOR SELECT USING (
        auth.uid() = elder_id
        OR EXISTS (
            SELECT 1 FROM relationships r
            WHERE r.caregiver_id = auth.uid()
            AND r.elder_id = checkins.elder_id
            AND r.status = 'active'
        )
    );

CREATE POLICY checkins_insert_elder ON checkins
    FOR INSERT WITH CHECK (auth.uid() = elder_id);

-- Medical history
CREATE POLICY medical_history_select ON medical_history
    FOR SELECT USING (
        auth.uid() = elder_id
        OR EXISTS (
            SELECT 1 FROM relationships r
            WHERE r.caregiver_id = auth.uid()
            AND r.elder_id = medical_history.elder_id
            AND r.status = 'active'
        )
    );

CREATE POLICY medical_history_write_caregiver ON medical_history
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM relationships r
            WHERE r.caregiver_id = auth.uid()
            AND r.elder_id = medical_history.elder_id
            AND r.status = 'active'
        )
    );

-- Contacts
CREATE POLICY contacts_select ON contacts
    FOR SELECT USING (
        auth.uid() = elder_id
        OR EXISTS (
            SELECT 1 FROM relationships r
            WHERE r.caregiver_id = auth.uid()
            AND r.elder_id = contacts.elder_id
            AND r.status = 'active'
        )
    );

CREATE POLICY contacts_write_caregiver ON contacts
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM relationships r
            WHERE r.caregiver_id = auth.uid()
            AND r.elder_id = contacts.elder_id
            AND r.status = 'active'
        )
    );
