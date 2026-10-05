from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.main import create_app


def login_client(settings):
    config = settings.model_copy(
        update={
            "admin_email": "admin@example.com",
            "admin_password": SecretStr("test-password"),
            "admin_api_token": SecretStr("test-server-token"),
            "demo_user_growth_enabled": False,
        }
    )
    return TestClient(create_app(settings=config))


def test_login_accepts_configured_credentials(settings):
    with login_client(settings) as client:
        response = client.post(
            "/api/v1/admin/auth/login",
            headers={"X-Admin-Token": "test-server-token"},
            json={"email": " ADMIN@example.com ", "password": "test-password"},
        )
    assert response.status_code == 200
    assert response.json() == {"email": "admin@example.com"}
    assert "test-password" not in response.text


def test_login_rejects_incorrect_password(settings):
    with login_client(settings) as client:
        response = client.post(
            "/api/v1/admin/auth/login",
            headers={"X-Admin-Token": "test-server-token"},
            json={"email": "admin@example.com", "password": "incorrect"},
        )
    assert response.status_code == 401


def test_login_requires_trusted_frontend_token(settings):
    with login_client(settings) as client:
        response = client.post(
            "/api/v1/admin/auth/login",
            json={"email": "admin@example.com", "password": "test-password"},
        )
    assert response.status_code == 401
