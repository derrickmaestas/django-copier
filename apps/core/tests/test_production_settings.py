"""Verify config/settings/production.py imports only when the env is sane.

Each test sets up an environment that's correct *except* for one variable,
re-imports the module, and asserts the right `ImproperlyConfigured` fires.
We use `importlib.reload` (rather than the `settings` fixture) because the
checks live at module top level — they only run on import, not on attribute
access, so a regular settings override doesn't exercise them.
"""

import importlib
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

# A valid baseline; each test overrides one slot to a bad value.
SANE_ENV = {
    "DJANGO_SECRET_KEY": "x" * 50,
    "DJANGO_ADMIN_URL": "secret-prefix/",
    "DJANGO_ALLOWED_HOSTS": "planly.example.com",
    "DB_PASSWORD": "real-password",
}


def _reload_production(monkeypatch, env_overrides):
    """Reload config.settings.production with a controlled environment."""
    for key, value in {**SANE_ENV, **env_overrides}.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    # Force a fresh import — the failing checks are at module top level,
    # so the second time around their state is cached as the success path.
    sys.modules.pop("config.settings.production", None)
    sys.modules.pop("config.settings.base", None)
    return importlib.import_module("config.settings.production")


class TestProductionFailFast:
    """Production settings refuse to import with any insecure default in place."""

    def test_loads_when_environment_is_sane(self, monkeypatch):
        module = _reload_production(monkeypatch, {})
        assert module.DEBUG is False
        assert module.ALLOWED_HOSTS == ["planly.example.com"]

    def test_missing_secret_key_raises(self, monkeypatch):
        with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
            _reload_production(monkeypatch, {"DJANGO_SECRET_KEY": ""})

    def test_default_admin_url_raises(self, monkeypatch):
        with pytest.raises(ImproperlyConfigured, match="DJANGO_ADMIN_URL"):
            _reload_production(monkeypatch, {"DJANGO_ADMIN_URL": "admin/"})

    def test_missing_admin_url_falls_back_to_default_and_raises(self, monkeypatch):
        """Unset DJANGO_ADMIN_URL means base.py uses `admin/` — must still fail."""
        with pytest.raises(ImproperlyConfigured, match="DJANGO_ADMIN_URL"):
            _reload_production(monkeypatch, {"DJANGO_ADMIN_URL": None})

    def test_empty_allowed_hosts_raises(self, monkeypatch):
        with pytest.raises(ImproperlyConfigured, match="DJANGO_ALLOWED_HOSTS"):
            _reload_production(monkeypatch, {"DJANGO_ALLOWED_HOSTS": ""})

    def test_missing_allowed_hosts_raises(self, monkeypatch):
        with pytest.raises(ImproperlyConfigured, match="DJANGO_ALLOWED_HOSTS"):
            _reload_production(monkeypatch, {"DJANGO_ALLOWED_HOSTS": None})

    def test_missing_db_password_raises(self, monkeypatch):
        with pytest.raises(ImproperlyConfigured, match="DB_PASSWORD"):
            _reload_production(monkeypatch, {"DB_PASSWORD": ""})


class TestProductionSecurityHeaders:
    """Production settings enable the headers a public deploy expects."""

    def test_https_redirect_and_hsts_configured(self, monkeypatch):
        module = _reload_production(monkeypatch, {})
        assert module.SECURE_SSL_REDIRECT is True
        assert module.SECURE_HSTS_SECONDS >= 31_536_000
        assert module.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
        assert module.SECURE_HSTS_PRELOAD is True

    def test_secure_cookies(self, monkeypatch):
        module = _reload_production(monkeypatch, {})
        assert module.SESSION_COOKIE_SECURE is True
        assert module.CSRF_COOKIE_SECURE is True

    def test_clickjacking_and_sniffing_protections(self, monkeypatch):
        module = _reload_production(monkeypatch, {})
        assert module.X_FRAME_OPTIONS == "DENY"
        assert module.SECURE_CONTENT_TYPE_NOSNIFF is True
        assert module.SECURE_REFERRER_POLICY == "same-origin"

    def test_csp_middleware_installed_first(self, monkeypatch):
        module = _reload_production(monkeypatch, {})
        assert (
            module.MIDDLEWARE[0]
            == "django.middleware.csp.ContentSecurityPolicyMiddleware"
        )

    def test_csp_default_is_self_only(self, monkeypatch):
        module = _reload_production(monkeypatch, {})
        assert module.SECURE_CSP["default-src"] == ("'self'",)
        # Frame embedding completely blocked on top of X-Frame-Options.
        assert module.SECURE_CSP["frame-ancestors"] == ("'none'",)
