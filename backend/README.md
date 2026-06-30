# CareConnect API

FastAPI backend for the CareConnect elder-care monitoring platform. Connects to Supabase (Postgres + Auth) with a singleton database client pattern.

## Setup

1. **Clone and enter the project**

   ```bash
   cd careconnect-api
   ```

2. **Create a virtual environment and install dependencies**

   Use **Python 3.11–3.13** (recommended). Python 3.14 is not fully supported by all dependencies yet.

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   For `scripts/setup_supabase.py` only, also run:

   ```bash
   pip install -r requirements-setup.txt
   ```

3. **Configure environment variables**

   ```bash
   cp .env.example .env
   ```

   Fill in:

   | Variable | Description |
   |----------|-------------|
   | `SUPABASE_URL` | Your Supabase project URL |
   | `SUPABASE_SERVICE_KEY` | Service role key (server-side only) |
   | `SUPABASE_ANON_KEY` | Anon/public key (patient login) |
   | `SUPABASE_JWT_SECRET` | JWT secret from Supabase project settings |
   | `GOOGLE_PLACES_API_KEY` | Google Places API key (for nearby hospitals) |
   | `ENVIRONMENT` | `development` or `production` |

4. **Apply the database schema**

   Run `sql/schema.sql` in the Supabase SQL editor, or:

   ```bash
   pip install -r requirements-setup.txt   # once, if not already installed
   python scripts/setup_supabase.py
   ```

## Authentication (Supabase)

Both **caregivers** and **patients** authenticate through Supabase Auth. All routes except login/signup require `Authorization: Bearer <access_token>`.

### Caregiver flow
1. `POST /auth/caregiver/signup` — email, password, name → creates Supabase Auth user + caregiver profile, returns tokens
2. `POST /auth/caregiver/login` — email + password → returns tokens
3. `POST /patients/provision` — create patients with a numeric login code

### Patient flow
1. Caregiver provisions patient via `POST /patients/provision`
2. `POST /auth/patient-login` — last name + numeric code → returns tokens

### Access control

| Persona | Can access |
|---------|------------|
| **Caregiver** | Full records for all linked patients: meds, history, contacts, check-in history, adherence charts |
| **Patient** | Own check-ins, med reminders, dose confirmation, emergency summary only |

Only these auth endpoints are public: `/auth/caregiver/signup`, `/auth/caregiver/login`, `/auth/patient-login`, and `/health`.

## Patient login (last name + numeric code)

Caregivers create patient accounts with a simple numeric code. Patients sign in without email:

1. **Caregiver** signs up → `POST /auth/caregiver/signup`
2. **Caregiver** adds patient → `POST /patients/provision` with `login_code` (4–6 digits)
3. **Patient** opens app → `POST /auth/patient-login` with `last_name` + `login_code`
4. Use `access_token` as `Authorization: Bearer <token>` on all other routes

5. **Start the server**

   ```bash
   python run.py
   ```

   API docs: http://localhost:8000/docs

   **Auth test UI:** http://localhost:8000/test-ui/

   **Sample webpage:** http://localhost:8000/sample-webpage/

   Flow: caregiver sign up → add patient → dashboard. Caregiver log in and patient log in go straight to the dashboard.

## Run tests

```bash
pytest tests/ -v
```

## Architecture

- **`app/config.py`** — Settings loaded once via `@lru_cache`
- **`app/database.py`** — Singleton Supabase client via `@lru_cache`
- **`app/dependencies.py`** — `get_current_user`, `require_caregiver`, `require_patient`
- **`app/routers/`** — Thin HTTP layer
- **`app/services/`** — Business logic (framework-agnostic)
- **`app/models/`** — Pydantic request/response schemas
- **`app/exceptions.py`** — Domain exceptions + handlers

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (public) |
| GET | `/auth/me` | Current user profile (auth + users table) |
| POST | `/auth/caregiver/signup` | Register caregiver (Supabase Auth + profile) |
| POST | `/auth/caregiver/login` | Caregiver email/password login |
| POST | `/auth/patient-login` | Patient sign-in with last name + numeric code |
| POST | `/users` | Create user profile after Supabase signup |
| POST | `/patients/provision` | Caregiver creates patient with login code |
| PATCH | `/patients/{patient_id}/login-code` | Caregiver resets patient login code |
| GET | `/users/{user_id}` | Get user profile (self or linked) |
| PATCH | `/users/{user_id}` | Update own profile |
| POST | `/relationships/invite` | Caregiver invites elder by email or invite code |
| POST | `/relationships/accept/{relationship_id}` | Elder accepts pending link |
| GET | `/relationships/my-elders` | Caregiver dashboard: linked elders with summaries |
| GET | `/relationships/my-caregivers` | Elder’s linked caregivers |
| DELETE | `/relationships/{relationship_id}` | Unlink caregiver and elder |
| POST | `/medications` | Caregiver adds medication for elder |
| GET | `/medications/{elder_id}` | List active medications |
| PATCH | `/medications/{medication_id}` | Update medication |
| DELETE | `/medications/{medication_id}` | Soft-delete medication |
| POST | `/medications/{medication_id}/confirm` | Elder confirms dose taken |
| GET | `/medications/{elder_id}/pending` | Today’s pending/overdue doses |
| GET | `/medications/{elder_id}/adherence` | Adherence stats for charting |
| POST | `/checkins` | Elder submits wellness check-in |
| GET | `/checkins/{elder_id}` | Paginated check-in history |
| GET | `/checkins/{elder_id}/status` | Last check-in + needs-attention flag |
| POST | `/medical-history` | Add medical history entry |
| GET | `/medical-history/{elder_id}` | List history (optional `?category=`) |
| PATCH | `/medical-history/{entry_id}` | Update entry |
| DELETE | `/medical-history/{entry_id}` | Delete entry |
| GET | `/medical-history/{elder_id}/emergency-summary` | ER-ready allergies, conditions, contacts |
| POST | `/contacts` | Add healthcare contact |
| GET | `/contacts/{elder_id}` | List contacts (optional `?contact_type=`) |
| PATCH | `/contacts/{contact_id}` | Update contact |
| DELETE | `/contacts/{contact_id}` | Delete contact |
| GET | `/locations/nearby-hospitals` | Nearby hospitals via Google Places |

## Auth

JWTs are issued by Supabase Auth and validated with `SUPABASE_JWT_SECRET`. The API loads the user's role from the `users` table and enforces caregiver vs patient access on every route.
