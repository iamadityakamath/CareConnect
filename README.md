# PillBox — Elderly Medication Reminder

> Live demo: **https://YOUR_DEPLOYMENT_URL**

A web-first Flutter app that helps elderly patients take medications on time, managed behind the scenes by a caregiver.

## Architecture

```
Flutter Web  ──►  FastAPI (REST)  ──►  Supabase Postgres
                         │
                         └── Supabase Auth (caregivers + patient sessions)
```

## Quick Start

### Prerequisites
- Flutter SDK ≥ 3.12
- Supabase project (free tier works)
- FastAPI backend running (see `/backend` — hosted separately)

### 1. Run Supabase migrations
Open your Supabase project → SQL Editor → run in order:
```
supabase/migrations/001_schema.sql
supabase/migrations/002_rls.sql
```

### 2. Configure environment
```bash
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_ANON_KEY, API_BASE_URL
```

### 3. Run Flutter web locally
```bash
cd pillbox
flutter pub get
flutter run -d chrome \
  --dart-define=SUPABASE_URL=https://YOUR.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=your-anon-key \
  --dart-define=API_BASE_URL=http://localhost:8000
```

### 4. Build for production
```bash
flutter build web \
  --dart-define=SUPABASE_URL=https://YOUR.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=your-anon-key \
  --dart-define=API_BASE_URL=https://your-backend.onrender.com
# Deploy the build/web/ folder to Firebase Hosting / Netlify / Vercel
```

## Demo Script (2-3 min)

1. **Caregiver signs up** at `/auth/signup` — enters name, email, password.
2. **Caregiver creates a patient** — taps "Add Patient", fills in name, gets a 7-character login code.
3. **Open incognito window**, navigate to the app, tap "Patient? Enter your code" → paste the code → locked patient UI appears.
4. **Caregiver adds a medication** (Lisinopril 10mg, daily at 8 AM & 8 PM).
5. **Patient taps "I Took It"** on the next dose card → green confirmation animation.
6. **Caregiver dashboard** refreshes (live via Supabase Realtime) → adherence ticks up.
7. *Optional:* Demo the in-app foreground reminder by waiting for a scheduled dose time or using the debug "Send Test Reminder" button on the patient detail screen.

## Folder Structure

```
pillbox/             Flutter web app
  lib/
    core/            env, theme, constants, api client
    routing/         go_router config
    models/          Dart data classes
    features/
      auth/          login, signup, patient code entry
      caregiver/     dashboard, patient detail, medication CRUD
      patient/       next dose, today schedule, history
supabase/
  migrations/        Postgres schema + RLS policies
DECISIONS.md         Key architecture decisions
.env.example         Environment variable template
```

## Notes
- HTTPS is required for Service Worker / web push. Local dev uses localhost (exempt).
- iOS Safari web push only works when the app is added to the home screen as a PWA.
