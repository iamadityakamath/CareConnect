# PillBox — Architecture Decisions

## D1 · Patient auth mechanism
**Choice:** Admin sign-in via stored password returning real Supabase tokens.

FastAPI creates a Supabase auth user per patient with a random password stored in `patient_secrets` (service-role-only table). On code redemption FastAPI calls the Supabase token endpoint directly via HTTP, gets a real `{access_token, refresh_token}` pair, and returns it to Flutter. Flutter stores both tokens in `SharedPreferences` and calls `supabase.auth.recoverSession(sessionJson)` to restore a full Supabase session. Because the tokens are native Supabase JWTs, RLS policies apply automatically to all direct Supabase queries from the Flutter client.

Why not custom JWTs: real tokens have refresh support and don't require keeping the JWT secret on every service.

## D2 · `_auth_password` protection
Stored in a separate `patient_secrets` table with RLS enabled and **no SELECT policy**. Supabase denies any authenticated client access. The FastAPI service role bypasses RLS and reads it exclusively.

## D3 · Flutter folder name
The Flutter app stays in `pillbox/` (the name created by `flutter create`). The spec's `/app` name was aspirational; renaming would break IntelliJ/Android Studio project files.

## D4 · Dose generation strategy
APScheduler runs every minute in FastAPI, generating doses for a rolling 48-hour window. Dose rows are upserted with `ON CONFLICT (schedule_id, scheduled_at) DO NOTHING` for idempotency. Doses past their window still `pending` are marked `missed` every 30 minutes.

## D5 · Patient code reusability
Login codes are **reusable** until explicitly revoked by the caregiver (to survive demo-day page reloads and cache clears). The `login_codes.used_at` column records the first redemption; subsequent uses just re-issue the session.

## D6 · State management
Plain `flutter_riverpod` (no code generation). `StreamProvider` for live Supabase realtime, `FutureProvider` for one-shot fetches, `StateNotifierProvider` for mutable local state. Avoids `build_runner` complexity during the hackathon.

## D7 · Flutter web storage
`SharedPreferences` on Flutter web maps to `window.localStorage`. Combined with Supabase Flutter's own localStorage persistence, patient sessions survive page refreshes without any server round-trip.

## D8 · API base URL
Passed at build time via `--dart-define=API_BASE_URL=https://...`. Default falls back to `http://localhost:8000` for local dev. Never hardcoded.
