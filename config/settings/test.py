from config.settings.base import *  # noqa: F401, F403

DEBUG = False
SECRET_KEY = "insecure-test-key-do-not-use-in-production"  # noqa: S105

# ──────────────────────────────────────────────
# Fast password hashing — tests run 10x faster
# ──────────────────────────────────────────────
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ──────────────────────────────────────────────
# Email — capture, don't send
# ──────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# ──────────────────────────────────────────────
# Caching — per-test isolation
# ──────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ──────────────────────────────────────────────
# Background Tasks — inspect without executing
# ──────────────────────────────────────────────
TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.dummy.DummyBackend",
    }
}

# ──────────────────────────────────────────────
# Media — use temp directory for uploaded files
# ──────────────────────────────────────────────
import tempfile  # noqa: E402

MEDIA_ROOT = tempfile.mkdtemp()
