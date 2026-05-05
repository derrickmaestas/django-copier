import os

from django.core.exceptions import ImproperlyConfigured

from config.settings.base import *  # noqa: F401, F403

DEBUG = False

# ──────────────────────────────────────────────
# Fail-fast environment validation
# ──────────────────────────────────────────────
# Raise on import — never let a misconfigured prod boot up far enough to
# accept traffic. Each check covers a setting whose insecure default
# would compromise the deploy in a different way.

# 1. SECRET_KEY: signs sessions, password resets, and JWTs.
if not SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY environment variable must be set in production."
    )

# 2. ADMIN_URL: shipping `/admin/` in prod hands bots a free login page to
# brute-force. The base settings default to `admin/`; production must
# override with a hard-to-guess path via DJANGO_ADMIN_URL.
if ADMIN_URL == "admin/":  # noqa: F405
    raise ImproperlyConfigured(
        "DJANGO_ADMIN_URL must be overridden in production "
        "(do not ship the default `admin/` path)."
    )

# 3. ALLOWED_HOSTS: an empty list combined with DEBUG=False causes Django
# to reject every request with DisallowedHost, but a missing env var is
# more usefully diagnosed up-front with a clear message than via a 400
# response on the first hit.
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must list at least one hostname in production."
    )

# 4. DB_PASSWORD: the only field on the connection that's secret. The
# others have safe defaults; this one must come from the environment.
if not os.environ.get("DB_PASSWORD"):
    raise ImproperlyConfigured(
        "DB_PASSWORD environment variable must be set in production."
    )

# ──────────────────────────────────────────────
# Security headers
# ──────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Block clickjacking — we never embed our pages in another origin's frame.
X_FRAME_OPTIONS = "DENY"
# Don't leak referrers to third parties when users follow off-site links.
SECURE_REFERRER_POLICY = "same-origin"
# Force browsers to honor declared content-type rather than sniffing.
SECURE_CONTENT_TYPE_NOSNIFF = True

# ──────────────────────────────────────────────
# Content Security Policy (Django 6 built-in)
# ──────────────────────────────────────────────
# Strict by default: same-origin everything, no inline scripts or styles,
# no remote loads. We're set up for this — HTMX is vendored under
# /static/vendor/, Tailwind compiles to a static file, and there are no
# inline <script> tags in the templates. Adding a CDN later means
# explicitly extending the relevant directive here, not loosening the
# global default.
SECURE_CSP = {
    "default-src": ("'self'",),
    "script-src": ("'self'",),
    "style-src": ("'self'",),
    "img-src": ("'self'", "data:"),
    "font-src": ("'self'",),
    "connect-src": ("'self'",),
    "frame-ancestors": ("'none'",),
    "base-uri": ("'self'",),
    "form-action": ("'self'",),
}

MIDDLEWARE = [  # noqa: F405
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    *MIDDLEWARE,  # noqa: F405
]

# ──────────────────────────────────────────────
# Static files — whitenoise
# ──────────────────────────────────────────────
MIDDLEWARE.insert(  # noqa: F405
    MIDDLEWARE.index("django.contrib.sessions.middleware.SessionMiddleware"),  # noqa: F405
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": os.environ.get("AWS_STORAGE_BUCKET_NAME", ""),
            "region_name": os.environ.get("AWS_S3_REGION_NAME", "us-east-1"),
            "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL", ""),
            "custom_domain": os.environ.get("AWS_S3_CUSTOM_DOMAIN", ""),
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ──────────────────────────────────────────────
# Email — real SMTP
# ──────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.mailgun.org")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@planly.example.com")

# ──────────────────────────────────────────────
# Caching — Redis
# ──────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    }
}

# ──────────────────────────────────────────────
# Logging — structured for production
# ──────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "django.utils.log.ServerFormatter",
            "format": "%(levelname)s %(asctime)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "level": "WARNING",
        "handlers": ["console"],
    },
    "loggers": {
        "django": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        "planly": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}
