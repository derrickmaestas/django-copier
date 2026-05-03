import pytest

from apps.accounts.api.serializers import UserSerializer
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestUserSerializer:
    """UserSerializer is read-only and intentionally narrow."""

    def test_serializes_safe_fields(self):
        user = UserFactory(display_name="Drake", email="drake@example.com")

        data = UserSerializer(user).data

        assert data["employee_id"] == user.employee_id
        assert data["display_name"] == "Drake"
        assert data["email"] == "drake@example.com"
        assert data["is_manager"] is False

    def test_does_not_expose_password(self):
        user = UserFactory()
        user.set_password("secret")
        user.save()

        data = UserSerializer(user).data

        assert "password" not in data

    def test_all_fields_read_only(self):
        """No field on this serializer accepts writes — it's a projection."""
        for name, field in UserSerializer().fields.items():
            assert field.read_only, f"{name} should be read-only"
