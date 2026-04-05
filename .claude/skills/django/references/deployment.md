# Deployment

## Docker — Multi-Stage Build

```dockerfile
# ─── Stage 1: Build ──────────────────────────
FROM python:3.13-slim AS builder
WORKDIR /build
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*
COPY requirements/production.txt requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: Runtime ────────────────────────
FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/* && \
    addgroup --system planly && \
    adduser --system --ingroup planly planly
COPY --from=builder /install /usr/local
COPY . .
RUN python manage.py collectstatic --noinput
USER planly
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]
```

Multi-stage keeps the image small (no gcc/build headers in final). Static files collected at build time. Non-root user.

## Docker Compose — Local Development

```yaml
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_DB: planly
      POSTGRES_USER: planly
      POSTGRES_PASSWORD: planly
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U planly"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      DJANGO_ENV: development
      DB_HOST: db
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    build: .
    command: python manage.py db_worker
    volumes:
      - .:/app
    env_file: .env
    environment:
      DJANGO_ENV: development
      DB_HOST: db
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

## Gunicorn Configuration

```python
# gunicorn.conf.py
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 4
timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = "info"

graceful_timeout = 30
max_requests = 1000          # recycle workers to prevent memory leaks
max_requests_jitter = 50     # stagger restarts
```

For async views, use `uvicorn.workers.UvicornWorker`:

```python
worker_class = "uvicorn.workers.UvicornWorker"
```

## Static Files with WhiteNoise

Run `collectstatic` in CI/Dockerfile, not on deploy:

```bash
python manage.py collectstatic --noinput
```

Configuration in `production.py`:

```python
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.contrib.sessions.middleware.SessionMiddleware"),
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

## Health Check

```python
# config/urls.py
from django.http import JsonResponse
from django.db import connection


def health_check(request):
    try:
        connection.ensure_connection()
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "error"}, status=503)


urlpatterns = [
    path("health/", health_check, name="health-check"),
    # ...
]
```

## Background Workers

In production, `django-tasks` `DatabaseBackend` needs a separate worker process:

```bash
python manage.py db_worker
```

Run as a separate container/service alongside the web server (the `worker` service in docker-compose).

## Production Security Settings

```python
# config/settings/production.py
DEBUG = False
ALLOWED_HOSTS = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

## Structured Logging

```python
# config/settings/production.py
import structlog

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
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
        "planly": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}
```

Usage:

```python
import structlog

logger = structlog.get_logger("planly.tasks")

def send_assignment_notification(task_id, assignee_id):
    logger.info("sending_assignment_notification", task_id=task_id, assignee_id=assignee_id)
```

## Rate Limiting

```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def login_view(request):
    ...
```

## .dockerignore

```
.git
.env
*.pyc
__pycache__
media/
staticfiles/
.venv/
node_modules/
docs/
*.md
.pre-commit-config.yaml
docker-compose*.yml
```

## .env.example

Document every env var. Commit `.env.example`, gitignore `.env`:

```bash
DJANGO_ENV=development
DJANGO_SECRET_KEY=change-me
DJANGO_ALLOWED_HOSTS=planly.example.com
DB_NAME=planly
DB_USER=planly
DB_PASSWORD=changeme
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://localhost:6379/0
PLANLY_MAX_ATTACHMENT_SIZE_MB=25
```
