"""Gunicorn configuration for the production WSGI server.

Loaded automatically by `gunicorn config.wsgi:application -c gunicorn.conf.py`
(the Dockerfile CMD points here). Each setting below is documented with
the trade-off it makes; lift this file as-is for a vanilla deploy and
tune the worker count once you know your CPU/RAM budget.
"""

import multiprocessing
import os

# ── Bind & connection ──────────────────────────────────────────────
bind = "0.0.0.0:8000"

# When Django reads request.is_secure() and the X-Forwarded-Proto
# header, it trusts these proxy IPs to set it. "*" accepts any peer —
# fine when the only thing in front is a known reverse proxy on the
# same private network. Tighten via the FORWARDED_ALLOW_IPS env var
# when the proxy is on a known set of addresses.
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "*")

# ── Worker model ───────────────────────────────────────────────────
# 2 * cores + 1 is the gunicorn-recommended starting point for sync
# workers. Bump up if requests are I/O-heavy.
workers = int(
    os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1)
)
worker_class = "sync"

# Recycle each worker after this many requests so any slow leak gets
# a chance to clear. Jitter avoids stampede.
max_requests = 1000
max_requests_jitter = 100

# Pre-fork the application before spawning workers — copy-on-write
# means each worker shares the parent's read-only memory pages.
preload_app = True

# ── Timeouts ───────────────────────────────────────────────────────
timeout = 30
graceful_timeout = 30

# ── Logging — stdout/stderr; log aggregator handles the rest ───────
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# One JSON object per access-log line so the corporate log aggregator
# parses them with the same pipeline as the application's structlog.
access_log_format = (
    '{"time":"%(t)s","method":"%(m)s","path":"%(U)s","status":%(s)s,'
    '"latency_ms":%(L)s,"bytes":%(b)s,"remote":"%(h)s"}'
)
