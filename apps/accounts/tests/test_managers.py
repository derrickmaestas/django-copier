from django.test import TestCase

from apps.accounts.models import User


class TestUserManager(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            employee_id=1001,
            email="jane@example.com",
            password="testpass123",  # noqa: S106
        )
        assert user.pk == 1001
        assert user.employee_id == 1001
        assert user.check_password("testpass123")
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            employee_id=9999,
            email="admin@example.com",
            password="adminpass123",  # noqa: S106
        )
        assert admin.is_staff
        assert admin.is_superuser
