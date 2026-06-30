#!/usr/bin/env python3
"""
Seed demo caregiver + patient accounts and sample health data.

Requires in .env:
  SUPABASE_URL
  SUPABASE_SERVICE_KEY  (service_role — NOT anon)
  SUPABASE_ANON_KEY

Usage:
    python scripts/seed_demo.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

# Demo credentials — safe for hackathon demos only
CAREGIVER = {
    "email": "jane.doe@careconnect.demo",
    "password": "DemoCare123!",
    "full_name": "Jane Doe",
    "last_name": "Doe",
    "phone": "555-0100",
}
PATIENT = {
    "full_name": "Margaret Smith",
    "last_name": "Smith",
    "login_code": "2847",
    "phone": "555-0200",
}


def _check_service_key() -> None:
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not key or "your-service" in key:
        raise SystemExit(
            "❌ Set SUPABASE_SERVICE_KEY to your service_role key (Supabase → Settings → API)."
        )
    try:
        import base64
        import json

        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        role = json.loads(base64.urlsafe_b64decode(payload)).get("role")
        if role != "service_role":
            raise SystemExit(
                f"❌ SUPABASE_SERVICE_KEY has role '{role}' — you need the service_role key, not anon."
            )
    except SystemExit:
        raise
    except Exception:
        pass


def main() -> None:
    _check_service_key()
    if not os.environ.get("SUPABASE_ANON_KEY"):
        raise SystemExit("❌ SUPABASE_ANON_KEY missing from .env")

    from app.database import get_supabase_client
    from app.services import auth_service, medication_service, medical_history_service, contact_service

    db = get_supabase_client()

    # Caregiver
    existing = db.table("users").select("id").eq("email", CAREGIVER["email"]).limit(1).execute()
    if existing.data:
        print(f"ℹ️  Caregiver already exists: {CAREGIVER['email']}")
        caregiver_id = existing.data[0]["id"]
    else:
        result = auth_service.caregiver_signup(
            db,
            email=CAREGIVER["email"],
            password=CAREGIVER["password"],
            full_name=CAREGIVER["full_name"],
            last_name=CAREGIVER["last_name"],
            phone=CAREGIVER["phone"],
        )
        caregiver_id = result["user"]["id"]
        print(f"✅ Caregiver created: {CAREGIVER['email']}")

    # Patient
    patient_row = (
        db.table("users")
        .select("id")
        .eq("role", "elder")
        .eq("last_name", PATIENT["last_name"])
        .eq("full_name", PATIENT["full_name"])
        .limit(1)
        .execute()
    )
    if patient_row.data:
        patient_id = patient_row.data[0]["id"]
        print(f"ℹ️  Patient already exists: {PATIENT['full_name']}")
    else:
        result = auth_service.provision_patient(
            db,
            caregiver_id=caregiver_id,
            full_name=PATIENT["full_name"],
            last_name=PATIENT["last_name"],
            login_code=PATIENT["login_code"],
            phone=PATIENT["phone"],
        )
        patient_id = result["patient"]["id"]
        print(f"✅ Patient created: {PATIENT['full_name']}")

    # Sample medication
    meds = (
        db.table("medications")
        .select("id")
        .eq("elder_id", patient_id)
        .limit(1)
        .execute()
    )
    if not meds.data:
        medication_service.create_medication(
            db,
            caregiver_id,
            {
                "elder_id": patient_id,
                "name": "Lisinopril",
                "dosage": "10mg",
                "instructions": "Take with water",
                "frequency": "daily",
                "scheduled_times": ["08:00", "20:00"],
            },
        )
        print("✅ Sample medication added")

    # Sample medical history
    history = (
        db.table("medical_history")
        .select("id")
        .eq("elder_id", patient_id)
        .limit(1)
        .execute()
    )
    if not history.data:
        medical_history_service.create_entry(
            db,
            caregiver_id,
            "caregiver",
            {
                "elder_id": patient_id,
                "category": "allergy",
                "title": "Penicillin",
                "description": "Rash and swelling",
                "is_active": True,
            },
        )
        medical_history_service.create_entry(
            db,
            caregiver_id,
            "caregiver",
            {
                "elder_id": patient_id,
                "category": "condition",
                "title": "Type 2 Diabetes",
                "description": "Managed with diet and medication",
                "is_active": True,
            },
        )
        print("✅ Sample medical history added")

    # Emergency contact
    contacts = (
        db.table("contacts")
        .select("id")
        .eq("elder_id", patient_id)
        .limit(1)
        .execute()
    )
    if not contacts.data:
        contact_service.create_contact(
            db,
            caregiver_id,
            "caregiver",
            {
                "elder_id": patient_id,
                "name": "Dr. Emily Chen",
                "contact_type": "doctor",
                "specialty": "Geriatrics",
                "phone": "555-0300",
                "is_primary": True,
            },
        )
        print("✅ Sample contact added")

    print("\n" + "=" * 50)
    print("DEMO LOGINS")
    print("=" * 50)
    print("\nCaregiver (email + password):")
    print(f"  Email:    {CAREGIVER['email']}")
    print(f"  Password: {CAREGIVER['password']}")
    print(f"  Login:    POST /auth/caregiver/login")
    print("\nPatient (last name + numeric code):")
    print(f"  Last name: {PATIENT['last_name']}")
    print(f"  Code:      {PATIENT['login_code']}")
    print(f"  Login:     POST /auth/patient-login")
    print("=" * 50)


if __name__ == "__main__":
    main()
