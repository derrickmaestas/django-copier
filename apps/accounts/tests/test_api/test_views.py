import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestMeEndpoint:
    """GET /api/v1/me/ returns the authenticated user's profile."""

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get("/api/v1/me/")
        assert response.status_code == 401

    def test_session_auth_returns_current_user(self):
        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/v1/me/")

        assert response.status_code == 200
        assert response.data["employee_id"] == user.employee_id
        assert response.data["email"] == user.email
        assert "password" not in response.data

    def test_jwt_auth_returns_current_user(self):
        user = UserFactory()
        user.set_password("secret-123!")
        user.save()

        client = APIClient()
        token_response = client.post(
            "/api/v1/auth/token/",
            {"employee_id": user.employee_id, "password": "secret-123!"},
            format="json",
        )
        assert token_response.status_code == 200, token_response.data
        access = token_response.data["access"]

        response = client.get(
            "/api/v1/me/",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )

        assert response.status_code == 200
        assert response.data["employee_id"] == user.employee_id
