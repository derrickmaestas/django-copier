from django.conf import settings
from django.test import TestCase


class TestSettings(TestCase):
    """Verify the test pipeline and critical settings."""

    def test_django_settings_loaded(self):
        assert settings.SETTINGS_MODULE == "config.settings.test"

    def test_custom_user_model_configured(self):
        assert settings.AUTH_USER_MODEL == "accounts.User"
