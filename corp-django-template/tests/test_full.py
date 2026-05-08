"""Full combination: every toggle on."""

from __future__ import annotations

from .conftest import needs_uv, run


class TestFull:
    def test_generates_expected_layout(self, generate):
        proj = generate("full")
        for path in [
            "pyproject.toml",
            "config/settings/base.py",
            "config/api_router.py",
            "apps/core/migrations/0001_extensions.py",
            "apps/accounts/auth.py",
            "apps/accounts/api/authentication.py",
            "apps/attachments/models.py",
            "apps/attachments/validators.py",
            "apps/notifications/models.py",
            "apps/notifications/tasks.py",
            "apps/example/signals.py",
            "templates/partials/_form_card.html",
            "static/vendor/htmx.min.js",
            "static/css/source.css",
        ]:
            assert (proj / path).exists(), f"missing: {path}"

    def test_base_settings_include_all_features(self, generate):
        proj = generate("full")
        base = (proj / "config" / "settings" / "base.py").read_text()
        assert "REST_FRAMEWORK" in base
        assert "SPECTACULAR_SETTINGS" in base
        assert "django_tailwind_cli" in base
        assert "OIDC_OP_DISCOVERY_ENDPOINT" in base
        assert "apps.attachments" in base
        assert "apps.notifications" in base

    def test_compose_includes_worker_and_tailwind(self, generate):
        proj = generate("full")
        local = (proj / "compose.local.yml").read_text()
        assert "worker:" in local
        assert "tailwind:" in local

    @needs_uv
    def test_uv_sync_succeeds(self, generate):
        proj = generate("full")
        run(["uv", "sync", "--all-groups"], cwd=proj)

    @needs_uv
    def test_django_check_passes(self, generate):
        proj = generate("full")
        run(["uv", "sync", "--all-groups"], cwd=proj)
        run(
            ["uv", "run", "python", "manage.py", "check"],
            cwd=proj,
            env={"DJANGO_SETTINGS_MODULE": "config.settings.test"},
        )

    @needs_uv
    def test_spectacular_validates(self, generate):
        proj = generate("full")
        run(["uv", "sync", "--all-groups"], cwd=proj)
        run(
            ["uv", "run", "python", "manage.py", "spectacular", "--validate", "--fail-on-warn"],
            cwd=proj,
            env={"DJANGO_SETTINGS_MODULE": "config.settings.test"},
        )
