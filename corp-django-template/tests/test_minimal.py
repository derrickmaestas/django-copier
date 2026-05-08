"""Minimal combination: OIDC auth, no optional features."""

from __future__ import annotations

from .conftest import needs_uv, run


class TestMinimal:
    def test_generates_expected_layout(self, generate):
        proj = generate("minimal")
        assert (proj / "pyproject.toml").exists()
        assert (proj / "config" / "settings" / "base.py").exists()
        assert (proj / "apps" / "core" / "models.py").exists()
        assert (proj / "apps" / "accounts" / "auth.py").exists()
        # Toggled-off dirs should NOT exist:
        assert not (proj / "apps" / "attachments").exists()
        assert not (proj / "apps" / "notifications").exists()
        assert not (proj / "static").exists()
        assert not (proj / "config" / "api_router.py").exists()
        # Conditional partials dir should be absent:
        assert not (proj / "templates" / "partials").exists()

    def test_base_settings_have_no_drf_block(self, generate):
        proj = generate("minimal")
        base = (proj / "config" / "settings" / "base.py").read_text()
        assert "REST_FRAMEWORK" not in base
        assert "SPECTACULAR_SETTINGS" not in base
        assert "django_tailwind_cli" not in base

    @needs_uv
    def test_uv_sync_succeeds(self, generate):
        proj = generate("minimal")
        run(["uv", "sync", "--all-groups"], cwd=proj)

    @needs_uv
    def test_django_check_passes(self, generate):
        proj = generate("minimal")
        run(["uv", "sync", "--all-groups"], cwd=proj)
        run(
            ["uv", "run", "python", "manage.py", "check"],
            cwd=proj,
            env={"DJANGO_SETTINGS_MODULE": "config.settings.test"},
        )
