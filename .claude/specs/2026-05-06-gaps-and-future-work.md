# Planly — Gaps and Future Work

**Status:** Living document. **Last reviewed:** 2026-05-06.

A catalog of features, integrations, and improvements that are intentionally absent from the 18-chapter tutorial as it stands today. Each item lists *why it would land*, *what shape filling it would take*, and *how big the change is*. Use this as the queue when stakeholder priorities surface a need.

---

## How to read this document

Items are grouped by category, ordered roughly by urgency within each group. Effort labels are estimates only:

- **S** — half a day or less
- **M** — one to three days
- **L** — a week or more, possibly its own appendix chapter

Status icons:

- ✅ — completed
- 🟡 — partially landed; still has gaps
- ⬜ — open

---

## 1. Half-built features

Code/models exist but the feature isn't reachable through the UI or wasn't implemented end-to-end.

### ✅ Top-level README and refreshed `.env.example`

Landed 2026-05-06 (`README.md`, `.env.example`). First-impression entry point for a fresh clone.

### ✅ Attachment upload UI

Landed 2026-05-06 (`apps/attachments/views.py`, `urls.py`, `querysets.py`; `apps/tasks/templates/tasks/task_detail.html` Attachments section; tutorial Ch 11 §10.6 + Ch 16 cross-references). HTMX-based multipart upload with libmagic-validated content types, per-task team-scoping, and delete-and-remove.

### ⬜ Notification preferences UI — **M**

The `NotificationPreference` model (Ch 7) has fields for `email_on_assignment`, `email_on_comment`, `email_on_due_soon`, `daily_digest` — but no view to edit them, and the existing notification fan-out (`apps/notifications/tasks.py::send_comment_notification`) doesn't read the preferences.

**Shape**: a `/me/notifications/preferences/` view rendered by a ModelForm; HTMX-toggled checkboxes; the existing `send_*_notification` tasks gain a `if not _wants(recipient_id, channel): return` guard at the top.

**Trigger**: first user complains about email noise, or compliance asks for explicit opt-in.

### ⬜ Team / membership management UI — **M**

`Team` and `Membership` exist with role choices (OWNER, ADMIN, MEMBER); admin can edit them via `/admin/`, but a plain user can't add a teammate without superuser access.

**Shape**: `/teams/<id>/members/` listing current memberships with HTMX add (search team members → add → render new row) and remove (with the same `IsTeamOwnerOrAdmin` permission from Ch 16). Mirror the Plan visibility/destructive split — only owners + admins can change membership rolls.

**Trigger**: SSO appendix is implemented (group-claim → membership sync makes this less urgent, but corporate environments without group-claim wiring still need a UI).

### ⬜ Recurring tasks — **M**

`apps/tasks/models.py` doesn't carry recurrence fields; the design spec mentions a `recur_tasks` management command that would expand "daily standup" into a fresh Task each day.

**Shape**: add a `Task.recurrence` field (TextChoices: NONE, DAILY, WEEKLY, MONTHLY) plus `recurrence_end_date`; write a `manage.py recur_tasks` command that finds completed recurring tasks and clones them with the next due date; schedule it via the deploy environment's cron equivalent.

**Trigger**: real users start tracking standups, retros, weekly reports — anything that repeats.

---

## 2. Common production needs we never showed

Patterns every Django deploy eventually faces. Currently absent or only stubbed.

### ⬜ Sending email — **S**

`config/settings/production.py` configures the SMTP backend (`EMAIL_HOST`, etc.) but nothing in the codebase actually sends a message. Notification emails, invite emails, password-reset (when not on SSO) — all unwired.

**Shape**: a small section in Ch 12 that adds `send_assignment_email` alongside `send_assignment_notification`; uses Django's `send_mail` with a plain-text + HTML alternative; `templates/emails/...` for the HTML body. Test backend (`config/settings/test.py`) already uses `locmem.EmailBackend`, so test assertions are `assert len(mail.outbox) == 1`.

**Trigger**: notification preferences UI lands and "I want emails too" becomes real.

### ⬜ Scheduled jobs — **S–M**

`django.tasks` enqueues *on demand*; the tutorial never schedules a recurring job. Daily-digest emails, the recurring-tasks expansion above, weekly cleanup — all need a scheduler.

**Shape**: minimal — a small section of Ch 18 explaining the three options (cron-in-Docker for self-hosted; k8s `CronJob` for Kubernetes; APScheduler for an in-process scheduler when neither is available) and showing the cron-in-Docker version. `manage.py recur_tasks` is the example.

**Trigger**: any feature that has a "...every day at 8 AM" requirement.

### ⬜ Database backups + restore — **S**

Mentioned as deferred in Ch 18. A deploy without a documented backup procedure is missing the most important operational document.

**Shape**: a small `compose.prod.yaml` sidecar service that runs `pg_dump` to S3 daily; a `restore-from-backup` step-by-step in the deploy guide showing how to drop the db, recreate, and `pg_restore`. Self-hosted Postgres only — managed Postgres providers handle this themselves.

**Trigger**: pre-launch operational checklist.

### ⬜ Throttling / rate limiting — **S**

Ch 16 deferred to Ch 18; Ch 18 deferred to "operational policy at the proxy layer." Neither chapter shows what `django-ratelimit` looks like wired in. Login endpoint and any future password-reset flow are exposed.

**Shape**: install `django-ratelimit`; decorate the OIDC callback (or whichever entry point survives) with `@ratelimit(key="ip", rate="10/m", block=True)`. Pair with rate limiting on the `/api/v1/auth/token/` endpoint when it still exists. Cache backend is Postgres (Ch 18) — fine for low/medium traffic, switch to Redis if rate limiting becomes the contention bottleneck.

**Trigger**: any external-facing deploy.

### ⬜ Reversible / online migrations — **M**

The tutorial has one `RunSQL` migration (FTS extensions) and a few schema migrations. None of them demonstrate adding a column to a large table without locking writes.

**Shape**: a small Ch 17.5 or appendix walking through three real patterns: (1) splitting "add NOT NULL column with default" into add-nullable → backfill → add-NOT-NULL; (2) `RunPython` with `reverse_code=migrations.RunPython.noop` for one-way data migrations; (3) `pgtrigger` migrations behind a feature flag for rollback.

**Trigger**: first migration that touches a >10M-row table in production.

### ⬜ Request-ID middleware for log correlation — **S**

structlog renders nicely but log lines from one request can't be grouped across workers. Five-line middleware that adds an `X-Request-ID` (from upstream, or generated) and binds it as a structlog `contextvar` rounds out the logging story.

**Shape**: `apps/core/middleware.py::RequestIDMiddleware`; reads `X-Request-ID` from the incoming request (some proxies set it) or generates a UUID; binds via `structlog.contextvars.bind_contextvars(request_id=...)`; clears on response. Add to `MIDDLEWARE` in `base.py` near the top.

**Trigger**: first time you trace an incident across multiple log lines and lose your place.

---

## 3. Junior-dev quality-of-life

Repo hygiene that every "I just cloned this" experience hits.

### ✅ Top-level README

Done (above).

### ✅ `.env.example`

Done (above).

### ⬜ Pre-commit hooks — **S**

`ruff format`, `ruff check`, `ty check` are described as "run before commit" by convention but never wired into `.pre-commit-config.yaml`. Common practice; one-file add. Catches lint/type/format slips before the GitLab CI does.

**Shape**: `.pre-commit-config.yaml` running `ruff check`, `ruff format`, `ty check` (and optionally a YAML/TOML linter). One-paragraph addition to Ch 3 alongside the GitLab CI section.

**Trigger**: any time someone pushes a commit that fails CI on a lint issue that pre-commit would have caught locally.

### ⬜ CONTRIBUTING.md — **S**

Absent. For a tutorial reader who wants to extend Planly, no guide on style, branching, PR shape, what reviewers will check.

**Shape**: a short doc covering — branch naming, conventional-commit-ish message format we've been using, expected pre-commit + test passing, where to find what (link to the tutorial), how to add a memory of a project rule via CLAUDE.md.

### ⬜ `.editorconfig` — **S**

No file; we hit CRLF/LF warnings repeatedly during the build. An `.editorconfig` standardizes line endings, indent style, trailing-whitespace handling across editors.

**Shape**: one file, ~15 lines, no chapter section needed.

---

## 4. Topics mentioned-but-deferred-and-never-revisited

A chapter says "we'll cover this later" or "deferred to Ch X" and the later chapter doesn't deliver. Listed in approximate priority.

### ⬜ Pagination on the kanban board — **M**

Ch 17 acknowledged the tipping point but never showed how. Boards over ~500 tasks per column will hit it.

**Shape**: per-bucket task slicing in `PlanDetailView` (`Task.objects.filter(bucket=bucket)[:50]`), with HTMX-driven "show 50 more" append. Reuse the §10.2 pattern from Ch 11.

**Trigger**: first board breaks the visual layout or response time crosses 500 ms.

### ⬜ View-level caching of the kanban response — **M**

Ch 17 deferred; Ch 18's "When to add Redis" section names it but doesn't wire it.

**Shape**: per-user, per-plan cache key; invalidate on any write to the plan, its buckets, or any task in any of its buckets. Best done with a small `apps/plans/cache.py` that owns the keys + invalidation signals.

**Trigger**: a real plan with substantial data measurably hurts P95 response time.

### ⬜ CDN in front of static files — **S**

WhiteNoise serves manifest-named static files with `Cache-Control: max-age=31536000, immutable`; that's CDN-friendly. Ch 18 noted this is a one-config-change at the CDN side; we never wrote that note as code.

**Shape**: a paragraph in Ch 18 explaining what to set on the CDN (Cloudflare / Akamai / corporate equivalent) so it respects the immutability headers.

### ⬜ Audit logging — **L**

Listed as next-step in Ch 16; deferred in Ch 18. Compliance-heavy environments require it.

**Shape**: either `django-easy-audit` (drop-in, less control) or hand-rolled audit `Event` model + a `post_save` signal on the watched models. The latter is more code but stays compatible with existing event bus / SIEM integrations.

**Trigger**: legal/compliance asks "who changed this row last and when."

### ⬜ Soft deletes — **L**

The data model deletes things outright. No "trash bin" pattern, no recovery from accidental delete.

**Shape**: an abstract `SoftDeleteModel(TimeStampedModel)` with a nullable `deleted_at`; an `objects` manager filtered to `deleted_at__isnull=True`; an `all_objects` manager that doesn't filter. Apply selectively (Plan, Task — yes; Comment — probably not).

**Trigger**: first time someone deletes a plan and asks if it can be recovered.

---

## 5. Strategic gaps (each is an appendix-sized chapter)

Big topics that aren't bugs in what's there but are visibly absent from the tutorial.

### ⬜ Internationalization (i18n / l10n) — **L**

`USE_I18N = True` in settings, but no `gettext_lazy`, no `LocaleMiddleware`, no translatable strings. A bilingual deploy (English/French, English/Spanish) needs all three.

**Shape**: appendix walking through wrapping user-facing strings, the `makemessages` / `compilemessages` workflow, locale-routing middleware, language-switch UI, time-zone-per-user (`timezone.activate()` from a profile field). ~3000 words.

### ⬜ Real-time updates via Django Channels — **L**

Notifications today require a page reload to surface. Live updates on the kanban (someone moves a task → everyone sees it) needs WebSockets.

**Shape**: appendix introducing Channels, the ASGI swap, Redis as the channel layer, the `consumers.py` pattern, broadcast-on-signal. ~4000 words. Has hard dependencies (Redis, ASGI server config).

### ⬜ Two-factor auth (when not using SSO) — **M**

Moot under the SSO appendix; missing for non-SSO deploys.

**Shape**: `django-otp` with TOTP via authenticator apps; recovery codes; admin enforcement for staff users.

### ⬜ Property-based testing with Hypothesis — **M**

Tutorial uses pytest + factory-boy. Property-based testing would catch invariants that example-based tests miss — "for any valid plan, with_task_counts() never produces a negative number."

**Shape**: a section in Ch 17 (or its own short appendix) showing Hypothesis applied to query-set methods and form validators.

### ⬜ Audit trail (paired with soft deletes) — **L**

"Who did what when" — extension of audit logging above; combined with soft deletes gives full undo + history.

### ⬜ Multi-tenancy — **L**

Planly today serves one logical org per deploy. Multiple isolated customer orgs from one deploy is a different shape: tenant-scoped queryset middleware, tenant-aware migrations, tenant-routed URLs.

**Shape**: probably won't fit in an appendix — refactor of the data layer. Defer until product asks.

---

## 6. Decided to NOT do

For completeness — things that came up but were intentionally rejected, with the rationale captured here so the question doesn't keep coming back.

### Sentry integration — REJECTED

The corporate environment may not have Sentry SaaS available; legal/security wouldn't sign off on sending stack traces externally. structlog JSON to stdout + corporate log aggregator is the substitute. If the corporate env later approves an internal Sentry-compatible server (GlitchTip), revisit — Ch 18 has the wiring kept as reference code.

### Redis for the cache backend — REJECTED (for now)

`DatabaseCache` (Postgres-backed) is the tutorial default because nothing in Planly currently leans on the cache hard enough to justify operating Redis as a separate service. When kanban-response caching, rate-limit counters, sessions, or pub/sub land, Redis becomes worth the operational cost. See Ch 18 "When to add Redis" for the trigger and the swap path.

### Per-step CI (one job per phase) — REJECTED

Considered breaking `pytest` into per-app jobs for parallelism. Rejected because the test suite runs in ~12 seconds; parallelism overhead would dwarf the saving.

### Front-end SPA — REJECTED

Considered for completeness; Planly is intentionally an HTMX-driven server-rendered app. The DRF API supports a future SPA but the tutorial doesn't build one.

---

## How to use this document

When stakeholder priorities surface a need, look here first — most "we should add X" requests have a sketch already written. Update the entry's status when work lands; move completed items to a "Recently shipped" section if this list grows past about a dozen ⬜ entries.

The document lives at `.claude/specs/2026-05-06-gaps-and-future-work.md`. Date-prefixed because it's a planning artifact, alongside the original tutorial design spec. Keep edits human-curated rather than auto-generated — the value is in the *why* sections, not the title list.
