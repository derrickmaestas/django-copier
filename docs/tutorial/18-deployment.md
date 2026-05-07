# Chapter 18 — Production Deployment

## Goal

By the end of this chapter you'll have:

- A **`compose.prod.yaml`** that brings up `db`, `web`, and `worker` with health checks and restart policies, no exposed DB port, and a private compose network
- **`gunicorn.conf.py`** tuned for a vanilla deploy: workers from `2*cores+1`, `preload_app=True`, `max_requests` recycling, JSON-format access logs, and `forwarded_allow_ips` configurable from env
- **structlog** wired through Django's `LOGGING` dict — pretty key-value rendering for local dev, JSON for production, both reading the same processor pipeline so application-level `structlog.get_logger()` calls and stdlib `logging` calls produce identical output
- A bare **`/health/` endpoint** at the project root: 200 with `{"status": "ok"}` when the DB is reachable, 503 with `{"status": "db_unreachable"}` otherwise. No auth required; safe for LB and orchestrator probes.
- **Postgres-backed cache** instead of Redis (one less service to operate; fast enough until you actually need it)
- **`pytest --cov` coverage gate at 85%** — the project currently sits at **94.98%**, so the threshold sticks
- A **first-deploy guide** at the bottom of this chapter

The big themes: **lean on what you already have** (Postgres for cache, stdout for logs); **stay deploy-target agnostic** (the compose file works on any Docker host; layer Fly/Railway specifics on top); and **make observability decisions explicit** — including what we *didn't* add and when you should.

---

## The compose stack

Three services. No reverse proxy in this file — the deploy host (or the platform you're targeting) terminates TLS in front of `web:8000`.

```yaml
services:
  db:
    ports: !reset []           # never expose Postgres to the host
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    restart: unless-stopped

  web:
    build: .
    ports:
      - "8000:8000"
    env_file: .env.production
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
      DB_HOST: db
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider",
             "http://localhost:8000/health/"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 30s
    restart: unless-stopped

  worker:
    build: .
    command: python manage.py db_worker --queue-name default
    env_file: .env.production
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
      DB_HOST: db
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
```

A few details earn a sentence:

- **`!reset []` on db.ports.** The base `compose.yaml` exposes Postgres on the host for local development. In production, the DB sits on the private compose network only — there's no host binding, no firewall rule, no surface area to scan. The `!reset` syntax tells compose to drop the inherited port mapping.
- **`env_file: .env.production`.** Production env vars are out-of-band; the `.env.production` file is placed on the deploy host (typically by your CI or a config management tool) and gitignored. Secrets live there: `DJANGO_SECRET_KEY`, `DJANGO_ADMIN_URL`, `DB_PASSWORD`, `AWS_*`, `EMAIL_HOST_PASSWORD`.
- **`healthcheck` calls `/health/`** — the application's own readiness probe, not just `pg_isready` from a sidecar. We're proving that the gunicorn worker is alive *and* that it can talk to the DB from inside its own process.
- **`restart: unless-stopped`** keeps the service up across host reboots without flapping during a manual `docker compose down`.
- **`worker --queue-name default`** drains all enqueued `django.tasks` from the Postgres queue. When `notifications` traffic outgrows the default queue, split it into a second worker service with `--queue-name notifications` and route via `.using(queue_name="notifications").enqueue(...)` from the call site.

---

## Gunicorn tuning

```python
# gunicorn.conf.py
import multiprocessing
import os

bind = "0.0.0.0:8000"
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "*")

workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"

max_requests = 1000
max_requests_jitter = 100
preload_app = True

timeout = 30
graceful_timeout = 30

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = (
    '{"time":"%(t)s","method":"%(m)s","path":"%(U)s","status":%(s)s,'
    '"latency_ms":%(L)s,"bytes":%(b)s,"remote":"%(h)s"}'
)
```

The two settings most worth understanding:

**`preload_app = True`.** Gunicorn imports your application *before* forking workers. The forked workers share the parent's read-only memory pages via copy-on-write, which saves roughly `(workers - 1) × code_size` of RAM. In return you give up two things: the master process holds an active DB connection during fork (close it in `post_fork` if your driver complains), and reloading code requires restarting the master. For Django, the win is large.

**`max_requests = 1000` with `max_requests_jitter = 100`.** Each worker recycles after handling 1000–1100 requests. This gives any slow leak — DB connection pool growing, file handles not closing, monkey-patched garbage accumulating — a regular chance to clear. Jitter means the workers don't all hit the limit at the same second and trigger a stampede.

**`forwarded_allow_ips`** controls which proxy IPs gunicorn trusts to set `X-Forwarded-Proto`. `"*"` is fine when the only thing in front is a known proxy on the private network; tighten it to specific addresses when the proxy lives elsewhere.

**`access_log_format` is JSON.** One line per request, key-value structured, parseable by the same log aggregator that handles application logs. Field names match the structlog conventions so the aggregator doesn't have to guess.

---

## Structured logging with structlog

Same processor pipeline for both stdlib `logging.getLogger(__name__)` calls and direct `structlog.get_logger()` calls. The only difference between dev and prod is the *renderer* at the end of the chain.

`config/settings/base.py` configures structlog at import time and registers a `ProcessorFormatter` with the `ConsoleRenderer`:

```python
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

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structlog_console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(),
        },
    },
    ...
}
```

`config/settings/production.py` swaps in the JSON renderer:

```python
LOGGING = {
    "version": 1,
    ...
    "formatters": {
        "structlog_json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
        },
    },
    ...
}
```

In dev:

```
2026-05-06T16:42:11.302Z [info     ] task created [planly.tasks] task_id=42 actor_id=1003
```

In production, the same `logger.info("task created", task_id=42, actor_id=1003)` call writes:

```json
{"event":"task created","task_id":42,"actor_id":1003,"level":"info",
 "logger":"planly.tasks","timestamp":"2026-05-06T16:42:11.302Z"}
```

A corporate log aggregator can ingest the JSON line as-is, index by any field, and graph by any combination.

---

## The `/health/` endpoint

```python
# apps/core/views.py
@require_GET
def health(request):
    try:
        connection.ensure_connection()
    except DatabaseError:
        return JsonResponse({"status": "db_unreachable"}, status=503)
    return JsonResponse({"status": "ok"})
```

Three deliberate properties:

1. **No auth.** Probes from load balancers and orchestrators don't carry credentials. The endpoint reveals nothing — no version string, no environment label, no user info — so leaving it public is safe.
2. **Database check.** `connection.ensure_connection()` opens a real connection (or reuses the pooled one) and raises `DatabaseError` on failure. We don't want "process is alive but every request 500s because Postgres is down" to count as healthy.
3. **GET only.** `@require_GET` makes POST/PUT/DELETE return 405 — orchestrator probes always GET, anything else is a misuse worth rejecting.

The compose `healthcheck` calls this endpoint with `wget --spider`. If the process is alive but the DB has been down for `interval × retries` (15s × 3 = 45s by default), Docker marks the container unhealthy and your orchestrator restarts it.

---

## Coverage gate

`pytest --cov` runs the test suite under coverage instrumentation. The baseline before this chapter:

```
TOTAL                                    1215     61    95%
Required test coverage of 85.0% reached. Total coverage: 94.98%
267 passed, 2 warnings in 14.85s
```

94.98% coverage on the 1215 source lines — well past the 85% gate the plan called for. The gate is set in `pyproject.toml`:

```toml
[tool.coverage.report]
fail_under = 85
show_missing = true
```

The gate runs only when you pass `--cov`; a plain `uv run pytest` skips the instrumentation cost (15s without coverage, 17s with). CI runs `uv run pytest --cov` once per build; developers run `uv run pytest` for the inner loop.

> **Update `.gitlab-ci.yml`** — flip the existing `pytest` job to the coverage variant, and add the manual `deploy` stage:
>
> ```yaml
> stages:
>   - lint
>   - test
>   - validate
>   - deploy        # new
>
> pytest:
>   stage: test
>   services:
>     - name: postgres:17
>       alias: db
>   variables:
>     # …existing DB_* + DJANGO_SECRET_KEY values…
>   script:
>     - uv run pytest --cov   # was `uv run pytest`
>
> deploy:
>   stage: deploy
>   script:
>     - echo "Tag $CI_COMMIT_TAG built; replace with your deploy command."
>   rules:
>     - if: '$CI_COMMIT_TAG =~ /^v[0-9]+\./'
>       when: manual
> ```
>
> The `deploy` job's `rules` block restricts it to tag pushes matching `v*`, and `when: manual` keeps a human in the loop — no autopilot deploy on tag. Replace the placeholder echo with the real deploy command (kubectl apply, ssh deploy script, Fly machine deploy, etc.) when the target is settled.

The 5% that *isn't* covered is mostly:
- Error branches we can't easily exercise (the `except DatabaseError` branch of `/health/` when migrations are running — exercised by mocking)
- Some HTMX view branches that only fire for invalid form input on the API (covered indirectly)
- Production-only settings code that would need a separate harness

Don't chase 100%. The interesting tests are about *behavior*; coverage is a hint that you've covered the main paths.

---

## When to add Redis

We're shipping with `DatabaseCache` (Postgres-backed). It's slower than Redis on a per-call basis but adds zero operational surface. **Add Redis when one of these becomes true:**

- **You're caching the kanban board response.** Per-user, per-plan response caching cuts the kanban view from ~50ms to ~2ms — but the cache hit rate matters, and PG-backed cache won't keep up with a high churn pattern. Redis becomes worth the extra service when the saving exceeds ~30s of CPU per worker per minute.
- **Sessions are migrated to the cache backend.** `SESSION_ENGINE = "django.contrib.sessions.backends.cache"` is faster than DB sessions for high-traffic auth, but only if the cache is fast. PG-backed cache for sessions means you're hitting Postgres twice per request — a wash. Redis is the right answer.
- **You add rate limiting (`django-ratelimit`).** Counter increments and TTLs are exactly the workload Redis is built for. PG-backed counters work but add measurable contention at any real volume.
- **You need pub/sub for live updates** (Django Channels, server-sent events). Redis is the standard backplane.

The swap is two settings changes:

```python
# config/settings/production.py
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/0"),
    }
}
```

…and adding a `redis` service to `compose.prod.yaml`:

```yaml
redis:
  image: redis:7-alpine
  command: ["redis-server", "--save", "", "--appendonly", "no"]
  restart: unless-stopped
```

(No persistence — the cache is, well, a cache.) The application code doesn't change.

---

## When to add Sentry (or another error tracker)

We didn't wire Sentry into this build because Planly is deployed inside a corporate environment that may not have the Sentry SaaS — or any third-party observability service — available. The `LOGGING` setup we have (structlog → JSON → stdout → corporate log aggregator) covers the *recording* side: every uncaught exception becomes a log line with the full stack trace, ready for the aggregator to alert on.

What you give up by not having an error tracker:

- **Deduplication.** A new exception flooding the logs reads as "thousands of identical lines" instead of "one issue, count: 1247." A log aggregator can do this with effort; Sentry does it out of the box.
- **Release tagging.** Sentry tags every error with the commit/release it happened on, so "this regressed in last week's deploy" is a single click. Without Sentry, you correlate manually using the deploy timestamp.
- **Performance traces.** `traces_sample_rate=0.1` gives you per-request timing breakdown for 10% of traffic — invaluable when chasing a slow endpoint.

**Add an error tracker when one of these is true:**

- **Sentry SaaS becomes available** in the corporate environment, *and* legal/security signs off on sending stack traces and request metadata to a third party.
- **You can self-host a Sentry-compatible server.** GlitchTip is the open-source option that speaks Sentry's API; you can deploy it inside the corporate network on the same compose stack pattern. The application-side wiring is identical to Sentry SaaS — the DSN just points at your own server.
- **Aggregator-based alerting becomes too noisy** to triage. If you're filtering 30 different log signatures by hand to find the one that matters, deduplication earns its keep.

The wiring would look like this — kept here for reference:

```python
# config/settings/production.py — only when SENTRY_DSN is set
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

if (sentry_dsn := os.environ.get("SENTRY_DSN")):
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,  # never send user emails or session data
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        release=os.environ.get("SENTRY_RELEASE"),
    )
```

`uv add --group prod sentry-sdk` to install. The `if SENTRY_DSN:` gate means the SDK only runs when the env var is set — local production smoke tests stay free of Sentry overhead.

---

## First-deploy guide

A reproducible deploy from a clean Docker host. Adapt the secret-management step to your environment.

### 1. Stage the secrets

Place `.env.production` on the deploy host with at minimum:

```bash
DJANGO_SECRET_KEY=<50+ random chars; openssl rand -base64 50>
DJANGO_ADMIN_URL=<random-prefix>/         # e.g. 7K3xM9q2/
DJANGO_ALLOWED_HOSTS=planly.example.com
DB_NAME=planly
DB_USER=planly
DB_PASSWORD=<strong; from a password manager, NOT typed>
DB_HOST=db
PLANLY_MAX_ATTACHMENT_SIZE_MB=25
AWS_STORAGE_BUCKET_NAME=planly-attachments
AWS_S3_REGION_NAME=us-east-1
AWS_ACCESS_KEY_ID=<from IAM>
AWS_SECRET_ACCESS_KEY=<from IAM>
EMAIL_HOST=<smtp host>
EMAIL_HOST_USER=<smtp user>
EMAIL_HOST_PASSWORD=<smtp password>
DEFAULT_FROM_EMAIL=noreply@planly.example.com
```

`chmod 600 .env.production` and confirm the file is owned by the deploy user, not the world.

### 2. Build and start

```bash
docker compose -f compose.yaml -f compose.prod.yaml build
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

The `web` service has a healthcheck on `/health/`; `docker compose ps` shows `(healthy)` once the DB is reachable from gunicorn.

### 3. First-time database setup

```bash
docker compose -f compose.yaml -f compose.prod.yaml exec web \
    python manage.py migrate

docker compose -f compose.yaml -f compose.prod.yaml exec web \
    python manage.py createcachetable

docker compose -f compose.yaml -f compose.prod.yaml exec web \
    python manage.py createsuperuser
```

`createcachetable` creates the `planly_cache_table` Postgres table that `DatabaseCache` reads and writes to. Skip it if you've moved to Redis (above).

### 4. Verify

```bash
curl -i https://planly.example.com/health/
# HTTP/1.1 200 OK
# {"status":"ok"}

curl -i https://planly.example.com/${DJANGO_ADMIN_URL}
# HTTP/1.1 200 OK   (admin login page)

curl -i https://planly.example.com/api/v1/docs/
# HTTP/1.1 200 OK   (Swagger UI)
```

Sign in, create a Team, confirm membership and notification flow end-to-end.

### 5. Subsequent deploys

```bash
git pull origin main
docker compose -f compose.yaml -f compose.prod.yaml build
docker compose -f compose.yaml -f compose.prod.yaml up -d
docker compose -f compose.yaml -f compose.prod.yaml exec web \
    python manage.py migrate
```

`docker compose up -d` restarts only the changed services. Healthchecks gate the rollout; an unhealthy `web` won't get traffic.

### 6. Rollback

```bash
git checkout <previous-good-tag>
docker compose -f compose.yaml -f compose.prod.yaml build
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

If the migration is forward-incompatible: `python manage.py migrate <app> <previous-migration>` *first*, then redeploy.

---

## What we didn't build

- **CI/CD pipeline.** GitHub Actions, GitLab CI, Jenkins — opinionated, deploy-target dependent, easy to add when you know the platform. The build steps are: `pytest`, `pytest --cov`, `manage.py check --deploy`, `manage.py spectacular --validate --fail-on-warn`, `docker compose build`. CI script is the cron of those.
- **Backups.** `pg_dump` to S3 daily on a sidecar; a restore-from-backup procedure documented alongside it. Operational; varies wildly by environment.
- **Blue-green or zero-downtime deploys.** Single-host compose deploys are fine for the project's scale. When you need zero downtime, the answer is two web services behind the proxy with a connection drain — outside compose's natural sweet spot.
- **CDN in front of the web service.** Static files are served by whitenoise from gunicorn directly. For low-to-medium traffic that's fine; for higher traffic, fronting with a CDN that respects whitenoise's `Cache-Control: max-age=31536000, immutable` headers is a one-config change at the CDN side.

---

## Suggested commit message

```
add Chapter 18 — production deployment

* config/settings/production.py: switch CACHES to Postgres-backed
  DatabaseCache (createcachetable on first deploy); structlog JSON
  renderer in LOGGING for machine-parseable stdout
* config/settings/base.py: structlog.configure() at import time;
  ConsoleRenderer in LOGGING for human-readable local dev. Same
  processor pipeline shared with production — only the final
  renderer changes.
* apps/core/views.py: bare /health/ endpoint, 200 + {status:"ok"}
  on success, 503 + {status:"db_unreachable"} when
  connection.ensure_connection() raises. Public, GET-only, no app
  info disclosed.
* apps/core/urls.py: wire /health/
* apps/core/tests/test_views.py: TestHealthEndpoint covers the
  happy path, the unauth path, the DB-down path (mocked
  ensure_connection), and 405 on POST
* gunicorn.conf.py: preload_app, max_requests + jitter for worker
  recycling, JSON-format access_log_format, FORWARDED_ALLOW_IPS
  configurable from env, GUNICORN_WORKERS env override
* compose.prod.yaml: !reset on db.ports (private network only),
  healthcheck on web that hits /health/, restart: unless-stopped on
  every service, env_file: .env.production, worker --queue-name
  default, removed redis service
* pyproject.toml: + pytest-cov in test deps; coverage data_file
  /tmp (the runtime user can't write to /app); fail_under = 85
  (current coverage 94.98%); removed sentry-sdk from prod deps
  (corporate env may not have Sentry — when-to-add section in tutorial)
* docs/tutorial/18-deployment.md: full chapter including a
  first-deploy guide, "When to add Redis" and "When to add Sentry
  (if available)" sections explaining the trade-offs and the swap path
```

---

## Where this lands us

Phase 5 — and the Planly tutorial — is now done. Eighteen chapters covering:

| Phase | Chapters | What it built |
|---|---|---|
| 1. Foundation | 1–3 | Project structure, Docker dev environment, testing setup |
| 2. Data layer | 4–8 | Models, accounts, plans, tasks, attachments, notifications, admin |
| 3. Server-rendered app | 9–12 | URL routing, views, forms, templates + HTMX, signals + background tasks |
| 4. API & search | 13–14 | DRF (JWT + session), full-text search (Tier 1 + Tier 2) |
| 5. Best practices & production | 15–18 | Best practices reference, security hardening, performance, deployment |

What's left as exercises for the reader:

- Membership management endpoints (owner-only)
- EXIF stripping for image uploads
- CI/CD wiring for your platform of choice
- Live updates (Django Channels with Redis pub/sub) when the kanban needs them
- Multi-tenancy if Planly grows to serve multiple isolated customers from one deploy

Each of these slots into the patterns we've already built; none of them require revisiting the architecture. That's the goal of every architectural decision in the project — **the next change is additive, never a rewrite.**
