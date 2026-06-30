"""CORS preflight and response header tests."""

from fastapi.testclient import TestClient

from app.main import app


def test_cors_preflight_allows_any_origin():
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "https://my-frontend.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://my-frontend.example.com"
    assert "POST" in (response.headers.get("access-control-allow-methods") or "")


def test_cors_response_includes_origin_for_api_call():
    client = TestClient(app)
    response = client.get(
        "/health",
        headers={"Origin": "https://careconnect-app.vercel.app"},
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://careconnect-app.vercel.app"
