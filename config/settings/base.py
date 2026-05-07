import os
from datetime import timedelta
from pathlib import Path

import structlog
from dotenv import load_dotenv

# Wire structlog so any structlog.get_logger() call shares the same
# processor pipeline as stdlib logging via ProcessorFormatter (see
# LOGGING below). This block runs at import time — once, before
# Django's own logging config is applied.
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root

# Load .env file from the project root. Existing env vars take precedence
# (so production values set via the OS/container are never overwritten).
load_dotenv(BASE_DIR / ".env", override=False)

# ──────────────────────────────────────────────
# Environment variables
# ──────────────────────────────────────────────
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")

# URL prefix for the Django admin. Defaults to "admin/" for local dev; in
# production set DJANGO_ADMIN_URL to a hard-to-guess path so the admin login
# page isn't sitting at a well-known URL for bots to hammer.
ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "admin/")

# ──────────────────────────────────────────────
# Application definition
# ──────────────────────────────────────────────
INSTALLED_APPS = [
    # Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "django_extensions",
    "storages",
    "django_tailwind_cli",
    "template_partials",
    "crispy_forms",
    "crispy_tailwind",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "pgtrigger",
    "django.contrib.postgres",
    # Planly apps
    "apps.core",
    "apps.accounts",
    "apps.plans",
    "apps.tasks",
    "apps.attachments",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ──────────────────────────────────────────────
# Database — PostgreSQL only
# ──────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "planly"),
        "USER": os.environ.get("DB_USER", "planly"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "600")),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/plans/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ──────────────────────────────────────────────
# Templates
# ──────────────────────────────────────────────
TEMPLATES = [
    {
        # Plain Django backend — django-template-partials wraps the loaders
        # via its AppConfig.ready(), so just having "template_partials" in
        # INSTALLED_APPS makes the {% partialdef %} / {% partial %} tags
        # available in every template without an explicit {% load partials %}.
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ──────────────────────────────────────────────
# Internationalization
# ──────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ──────────────────────────────────────────────
# Static & Media files
# ──────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ──────────────────────────────────────────────
# Background Tasks (Django 6)
# ──────────────────────────────────────────────
TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.immediate.ImmediateBackend",
    }
}

# ──────────────────────────────────────────────
# Tailwind (django-tailwind-cli)
# ──────────────────────────────────────────────
# Use the standalone tailwindcss binary we install at /usr/local/bin/
# in the Dockerfile, rather than letting the package auto-download it
# at runtime (the planly user has no writable home directory for the
# default download path).
TAILWIND_CLI_USE_SYSTEM_BINARY = True
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
TAILWIND_CLI_SRC_CSS = "static/css/source.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"

# ──────────────────────────────────────────────
# Crispy Forms
# ──────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# ──────────────────────────────────────────────
# REST Framework
# ──────────────────────────────────────────────
# Two authentication classes coexist: SessionAuthentication is what the
# browser carries via the same cookie that powers the server-rendered
# views, so /api/docs/ and any in-app fetch() works out of the box.
# JWTAuthentication is for clients that don't share a session (mobile,
# external scripts, the eventual SPA).
REST_FRAMEWORK = {
    # Order matters: DRF uses the first auth class's `authenticate_header()`
    # to build the WWW-Authenticate challenge on a 401. JWT first gives API
    # clients a proper 401 with a Bearer challenge; session auth still works
    # for the browsable API and any in-app fetch() that carries the cookie.
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ("v1",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    # Our custom User model uses employee_id as the primary key, not the
    # default `id`. Tell simplejwt to encode that into the token claims and
    # to look it up the same way on decode.
    "USER_ID_FIELD": "employee_id",
    "USER_ID_CLAIM": "employee_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Planly API",
    "DESCRIPTION": "Task management — Plans, Buckets, Tasks, Comments, Notifications.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Tell spectacular about our URL versioning so /api/v1/ shows up in the
    # generated schema and Swagger UI's Try-It-Out hits the right path.
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+/",
}

# ──────────────────────────────────────────────
# Logging — structlog with a console renderer for local dev
# ──────────────────────────────────────────────
# Both the stdlib `logging` calls and any direct `structlog.get_logger()`
# call funnel through the same processor chain, so one configuration
# covers both styles. Production overrides this with a JSON renderer
# (see config/settings/production.py).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        # The `()` key takes a callable that returns the formatter
        # instance; the `processor` argument is the structlog renderer
        # invoked at the end of the chain. ConsoleRenderer indents and
        # colorizes for humans; production swaps in JSONRenderer.
        "structlog_console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structlog_console",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "django": {"level": "INFO", "propagate": True},
        "planly": {"level": "DEBUG", "propagate": True},
    },
}

# ──────────────────────────────────────────────
# Planly-specific settings
# ──────────────────────────────────────────────
PLANLY_MAX_ATTACHMENT_SIZE_MB = int(os.environ.get("PLANLY_MAX_ATTACHMENT_SIZE_MB", "25"))
PLANLY_MAX_BUCKETS_PER_PLAN = int(os.environ.get("PLANLY_MAX_BUCKETS_PER_PLAN", "200"))
PLANLY_MAX_TASKS_PER_PLAN = int(os.environ.get("PLANLY_MAX_TASKS_PER_PLAN", "9000"))
