"""Gateway auth + DRF only — no HTMX, no FTS, no attachments, no notifications."""

from __future__ import annotations

from .conftest import needs_uv, run


class TestGatewayApiOnly:
    def test_generates_expected_layout(self, generate):
        proj = generate("gateway-api-only")
        # Auth path is gateway, not OIDC:
        assert (proj / "apps" / "accounts" / "gateway_auth.py").exists()
        assert not (proj / "apps" / "accounts" / "auth.py").exists()
        # DRF is on:
        assert (proj / "config" / "api_router.py").exists()
        assert (proj / "apps" / "accounts" / "api" / "authentication.py").exists()
        # Other features off:
        assert not (proj / "apps" / "attachments").exists()
        assert not (proj / "apps" / "notifications").exists()
        assert not (proj / "static").exists()

    def test_authentication_uses_gateway_class(self, generate):
        proj = generate("gateway-api-only")
        base = (proj / "config" / "settings" / "base.py").read_text()
        assert "GatewayAPIAuthentication" in base
        assert "OIDCJWTAuthentication" not in base
        api_auth = (proj / "apps" / "accounts" / "api" / "authentication.py").read_text()
        assert "GatewayAPIAuthentication" in api_auth
        assert "X-Forwarded-User" in api_auth or "HEADER_EMPLOYEE_ID" in api_auth

    def test_login_template_exists_for_non_oidc(self, generate):
        proj = generate("gateway-api-only")
        # Gateway auth doesn't use OIDC URLs, so the standard
        # registration/login.html should be present.
        assert (proj / "templates" / "registration" / "login.html").exists()

    @needs_uv
    def test_uv_sync_succeeds(self, generate):
        proj = generate("gateway-api-only")
        run(["uv", "sync", "--all-groups"], cwd=proj)

    @needs_uv
    def test_django_check_passes(self, generate):
        proj = generate("gateway-api-only")
        run(["uv", "sync", "--all-groups"], cwd=proj)
        run(
            ["uv", "run", "python", "manage.py", "check"],
            cwd=proj,
            env={"DJANGO_SETTINGS_MODULE": "config.settings.test"},
        )
