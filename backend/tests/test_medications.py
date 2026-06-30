"""Unit tests demonstrating mocked db dependency for medication endpoints."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db
from app.main import app
from app.services import medication_service


@pytest.fixture
def mock_db():
    """Build a chained mock that mimics supabase-py fluent API."""
    db = MagicMock()
    table_mock = MagicMock()
    db.table.return_value = table_mock

    select_chain = MagicMock()
    table_mock.select.return_value = select_chain
    select_chain.eq.return_value = select_chain
    select_chain.order.return_value = select_chain

    execute_result = MagicMock()
    execute_result.data = [
        {
            "id": "med-1",
            "elder_id": "elder-1",
            "name": "Aspirin",
            "dosage": "81mg",
            "instructions": "With food",
            "frequency": "daily",
            "scheduled_times": ["08:00"],
            "active": True,
            "created_at": "2026-01-01T08:00:00Z",
        }
    ]
    select_chain.execute.return_value = execute_result
    return db


@pytest.fixture
def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "caregiver-1",
        "email": "caregiver@example.com",
        "role": "caregiver",
        "full_name": "Jane Caregiver",
        "phone": None,
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_medications_service(mock_db, monkeypatch):
    """Service-layer test: list_medications returns active medications."""
    monkeypatch.setattr(
        medication_service,
        "verify_elder_access",
        lambda db, requester_id, elder_id, requester_role: None,
    )
    monkeypatch.setattr(
        medication_service,
        "get_medications_id_column",
        lambda db: "elder_id",
    )

    result = medication_service.list_medications(
        mock_db, "elder-1", "caregiver-1", "caregiver"
    )

    assert len(result) == 1
    assert result[0]["name"] == "Aspirin"
    mock_db.table.assert_called_with("medications")


def test_list_medications_endpoint(client, monkeypatch):
    """Router test with overridden get_db dependency."""
    monkeypatch.setattr(
        medication_service,
        "list_medications",
        lambda db, elder_id, requester_id, requester_role: [
            {
                "id": "med-1",
                "elder_id": elder_id,
                "name": "Aspirin",
                "dosage": "81mg",
                "instructions": None,
                "frequency": "daily",
                "scheduled_times": ["08:00"],
                "active": True,
                "created_at": "2026-01-01T08:00:00Z",
            }
        ],
    )

    response = client.get("/medications/elder-1")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["name"] == "Aspirin"
