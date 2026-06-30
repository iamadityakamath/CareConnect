"""Tests for caregiver and patient authentication."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db
from app.main import app


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def caregiver_client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "caregiver-1",
        "email": "caregiver@example.com",
        "role": "caregiver",
        "full_name": "Jane Caregiver",
        "last_name": "Caregiver",
        "phone": None,
        "account_status": "active",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_patient_login_endpoint_success(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    with patch("app.services.auth_service.patient_login") as mock_login:
        mock_login.return_value = {
            "access_token": "token",
            "refresh_token": "refresh",
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {
                "id": "patient-1",
                "full_name": "John Smith",
                "last_name": "Smith",
                "role": "elder",
                "account_status": "active",
            },
        }
        client = TestClient(app)
        response = client.post(
            "/auth/patient-login",
            json={"last_name": "Smith", "login_code": "1234"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["access_token"] == "token"


def test_caregiver_login_endpoint(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    with patch("app.services.auth_service.caregiver_login") as mock_login:
        mock_login.return_value = {
            "access_token": "cg-token",
            "refresh_token": "cg-refresh",
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {
                "id": "caregiver-1",
                "email": "jane@example.com",
                "role": "caregiver",
                "full_name": "Jane Doe",
                "last_name": "Doe",
                "account_status": "active",
            },
        }
        client = TestClient(app)
        response = client.post(
            "/auth/caregiver/login",
            json={"email": "jane@example.com", "password": "securepass123"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "caregiver"


def test_provision_patient_requires_caregiver(caregiver_client):
    with patch("app.services.auth_service.provision_patient") as mock_provision:
        mock_provision.return_value = {
            "patient": {
                "id": "patient-1",
                "full_name": "John Smith",
                "last_name": "Smith",
                "role": "elder",
                "account_status": "managed",
            },
            "relationship_id": "rel-1",
        }
        response = caregiver_client.post(
            "/patients/provision",
            json={
                "full_name": "John Smith",
                "last_name": "Smith",
                "login_code": "5678",
            },
        )

    assert response.status_code == 201


def test_patient_cannot_access_caregiver_adherence(mock_db):
    """Patients must not reach caregiver-only adherence endpoint."""
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "patient-1",
        "role": "elder",
        "full_name": "John Smith",
        "last_name": "Smith",
        "account_status": "active",
    }
    client = TestClient(app)
    response = client.get("/medications/patient-1/adherence")
    app.dependency_overrides.clear()

    assert response.status_code == 403


def test_locations_requires_auth(mock_db):
    client = TestClient(app)
    response = client.get("/locations/nearby-hospitals?lat=40.0&lng=-88.0")
    assert response.status_code == 401


def test_patient_login_rejects_invalid_code_format(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)
    response = client.post(
        "/auth/patient-login",
        json={"last_name": "Smith", "login_code": "abc"},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 422
