# CareConnect — Demo Login Credentials

Use these after running `python scripts/setup_supabase.py` and `python scripts/seed_demo.py`.

## Caregiver

| Field | Value |
|-------|-------|
| Email | `jane.doe@careconnect.demo` |
| Password | `DemoCare123!` |

```bash
curl -X POST http://localhost:8000/auth/caregiver/login \
  -H "Content-Type: application/json" \
  -d '{"email":"jane.doe@careconnect.demo","password":"DemoCare123!"}'
```

Run that as **one command** (press Enter only after the last line). Or use this single line:

```bash
curl -X POST http://localhost:8000/auth/caregiver/login -H "Content-Type: application/json" -d '{"email":"jane.doe@careconnect.demo","password":"DemoCare123!"}'
```

## Patient

| Field | Value |
|-------|-------|
| Last name | `Smith` |
| Login code | `2847` |

```bash
curl -X POST http://localhost:8000/auth/patient-login \
  -H "Content-Type: application/json" \
  -d '{"last_name":"Smith","login_code":"2847"}'
```

Single line:

```bash
curl -X POST http://localhost:8000/auth/patient-login -H "Content-Type: application/json" -d '{"last_name":"Smith","login_code":"2847"}'
```

Both responses return `access_token` — use as `Authorization: Bearer <token>`.

## Setup checklist

1. In Supabase Dashboard → **Settings → API**:
   - Copy **anon** key → `SUPABASE_ANON_KEY`
   - Copy **service_role** key → `SUPABASE_SERVICE_KEY` (keep secret)
2. Copy **JWT Secret** → `SUPABASE_JWT_SECRET`
3. In **Settings → Database** → copy **URI** → `DATABASE_URL`
4. Run:
   ```bash
   pip install -r requirements.txt
   python scripts/setup_supabase.py
   python scripts/seed_demo.py
   python run.py
   ```
