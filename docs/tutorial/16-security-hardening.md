# Chapter 16 — Security Hardening

## Goal

By the end of this chapter you'll have:

- **Production settings that fail to import** when any of `DJANGO_SECRET_KEY`, `DJANGO_ADMIN_URL`, `DJANGO_ALLOWED_HOSTS`, or `DB_PASSWORD` are missing or default
- **Strict CSP** (`default-src 'self'`) wired through Django 6's built-in `ContentSecurityPolicyMiddleware`
- The full **production security-headers checklist**: HSTS with preload, secure cookies, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_PROXY_SSL_HEADER`
- **Attachment upload validation**: filename safety, size cap, extension allowlist, libmagic content-type sniffing
- A **`IsTeamOwnerOrAdmin`** permission class layered on top of the queryset-level team scoping, so plain members can read and update Plans but only owners/admins can delete or change visibility
- Tests that prove every check fires when it should

The big themes: **fail loudly at import time**, **defense in depth** (queryset + permission + form/serializer + database constraint), and **content-type sniffing**, not extension trust.

---

## Why fail-fast at import time

A misconfigured production deploy is more dangerous than a crashed one. A crash gets noticed; a deploy that boots with `DEBUG=True` or `ALLOWED_HOSTS=['*']` quietly serves traffic for a week before someone catches the stack trace in a 500 page.

The standard Django pattern — `os.environ.get("X", "fallback")` — is exactly the wrong shape for production secrets. The fallback is what bites you. Replace it with: read the variable, validate it, and `raise ImproperlyConfigured` on import if anything's wrong. Django catches `ImproperlyConfigured` early and refuses to boot.

```python
# config/settings/production.py
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY environment variable must be set in production."
    )

if ADMIN_URL == "admin/":
    raise ImproperlyConfigured(
        "DJANGO_ADMIN_URL must be overridden in production "
        "(do not ship the default `admin/` path)."
    )

ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must list at least one hostname in production."
    )

if not os.environ.get("DB_PASSWORD"):
    raise ImproperlyConfigured(
        "DB_PASSWORD environment variable must be set in production."
    )
```

Four checks, four reasons:

| Variable | What goes wrong if it's missing/default |
|---|---|
| `DJANGO_SECRET_KEY` | Sessions, password resets, JWTs all become forgeable |
| `DJANGO_ADMIN_URL` | `/admin/` is a free login form for credential-stuffing bots |
| `DJANGO_ALLOWED_HOSTS` | Empty list blocks every request — diagnose up-front, not via opaque 400s |
| `DB_PASSWORD` | The only secret in `DATABASES["default"]`; the rest have safe defaults |

### Testing import-time failures

Settings that fail at *import* aren't testable with `@override_settings` — that fixture overrides attribute access on an already-loaded module. We need to actually re-import. `monkeypatch` lets us mutate `os.environ`; `importlib.reload` does the rest:

```python
def _reload_production(monkeypatch, env_overrides):
    for key, value in {**SANE_ENV, **env_overrides}.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    sys.modules.pop("config.settings.production", None)
    sys.modules.pop("config.settings.base", None)
    return importlib.import_module("config.settings.production")


class TestProductionFailFast:
    def test_default_admin_url_raises(self, monkeypatch):
        with pytest.raises(ImproperlyConfigured, match="DJANGO_ADMIN_URL"):
            _reload_production(monkeypatch, {"DJANGO_ADMIN_URL": "admin/"})
```

The `sys.modules.pop` line is the part that makes this work. Without it, the second import is a cache hit and our checks never run again.

---

## Production security headers

Django ships these as opt-in settings; production turns them all on:

```python
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000          # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
```

A few of these need a sentence:

- **`SECURE_PROXY_SSL_HEADER`** — production runs behind a TLS-terminating proxy (Cloudflare, an ALB, nginx). Django has no idea the original request was HTTPS unless the proxy tells it via `X-Forwarded-Proto`. If you skip this setting, `SECURE_SSL_REDIRECT` redirects on a loop.
- **`SECURE_HSTS_PRELOAD`** — opts your domain into the browser's HSTS preload list, which means your site gets HTTPS-only treatment *before* the first request reaches it. Don't set this on a domain you might want to serve over HTTP later.
- **`SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE`** — both refuse to attach to a non-HTTPS request. Combined with `SECURE_SSL_REDIRECT`, you can't accidentally leak a session over plain HTTP.

`manage.py check --deploy` runs against the production settings module and fails CI on any oversight here.

---

## Strict Content Security Policy

CSP is the rule that browsers enforce *for* you about what content can load on your pages. Get it strict, and an XSS bug downgrades from "attacker runs JavaScript in your origin" to "attacker writes HTML that the browser refuses to execute."

Django 6 ships `django.middleware.csp.ContentSecurityPolicyMiddleware`. We wire it first in the middleware chain (so the header is on every response, including 404s and 500s):

```python
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

MIDDLEWARE = [
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    *MIDDLEWARE,
]
```

`'self'` everywhere — and importantly, **no `'unsafe-inline'`** in either `script-src` or `style-src`. The site loads zero inline scripts and zero inline styles.

This is only achievable because of decisions we made earlier:

- **HTMX is vendored** under `/static/vendor/htmx.min.js` (Ch 11). No CDN, no inline `<script>` block.
- **Tailwind compiles to a single static file** (`/static/css/tailwind.css`). No inline `<style>`.
- **HTMX attributes are not inline scripts.** `hx-get`, `hx-post`, `hx-headers='{"X-CSRFToken": "..."}'` are HTML attributes; CSP's `script-src` rule doesn't apply to attribute values.
- **Crispy-form-rendered templates produce no inline `style="..."`** — Tailwind classes only.

If you ever need to add an inline `<script>` (say, for a third-party widget), the right path is *nonce-based*: extend `script-src` with `"'nonce-{nonce}'"`, emit `nonce="{% csp_nonce %}"` on the script tag. Don't loosen the global default.

`frame-ancestors 'none'` and `X-Frame-Options: DENY` are belt-and-suspenders; both block clickjacking, and they degrade gracefully on browsers that only honor one.

---

## Attachment upload validation

A `FileField` accepts whatever the browser sends. The browser-supplied `Content-Type` is a string the user controls. The filename is a string the user controls. Treat both as untrusted, and validate the bytes with libmagic.

The validators live in `apps/attachments/validators.py` and run as `clean_file()` on `AttachmentForm`:

```python
def run_all(uploaded_file) -> None:
    validate_filename(uploaded_file.name)
    validate_size(uploaded_file)
    validate_extension(uploaded_file.name)
    validate_content_type(uploaded_file)
```

Order matters — the cheapest checks (filename string ops, size attribute) run before we read any of the file body. By the time libmagic is invoked, we've already weeded out nine kinds of garbage.

### What each check rejects

**`validate_filename`** — path separators (`/`, `\`), null bytes, leading dots, and any name with more than one extension. The `invoice.pdf.exe` trick relies on Windows defaulting to "hide known extensions"; rejecting any name with two dots in the basename closes that vector. (Real `archive.tar.gz`-style names go in our `.zip` allowlist instead, served as a single archive extension.)

**`validate_size`** — `PLANLY_MAX_ATTACHMENT_SIZE_MB`, defaulting to 25. Stops a single user from filling the bucket; tunable per-deploy via env var.

**`validate_extension`** — an explicit allowlist. PDFs, Office docs, common image formats, plain text, JSON, ZIP. Anything else is rejected by name; we don't try to enumerate banned extensions because the list is unbounded.

**`validate_content_type`** — the interesting one. We read the first 8 KB into memory and run libmagic on it:

```python
head = uploaded_file.read(SNIFF_BYTES)
uploaded_file.seek(0)  # rewind so the rest of the upload pipeline still works
sniffed = magic.from_buffer(head, mime=True)
if sniffed not in ALLOWED_MIME_TYPES:
    raise ValidationError({"file": f"Detected content type {sniffed!r} is not allowed."})
```

A `.pdf` file with PE/Mach-O bytes inside is sniffed as `application/x-dosexec` or `application/x-mach-binary` — and rejected. The `seek(0)` is non-negotiable: without it, the rest of the upload pipeline gets only the unread tail of the file.

`libmagic` is a system library — `apt install libmagic1` in the Dockerfile, plus `python-magic` in `pyproject.toml`. The runtime image picks it up automatically.

### Why filename safety also sanitizes

Even with `attachment_upload_path` rooted at `/attachments/task_<id>/`, a filename of `../../etc/passwd` could in theory trip a misconfigured S3 backend or a future migration to local-disk storage in some test environment. Treat untrusted filenames as untrusted everywhere.

### Form vs serializer

We expose the validation as a `clean_file` on the form so the (eventual) HTML upload page benefits without thinking about it. The same validators are imported and called from the API serializer the day we add an API endpoint for uploads. Same code, same error messages, same allowlists.

---

## Permission tightening: members vs owners

Chapter 13 set up the API with the simple rule "any team member, full CRUD on team-scoped resources." That works for a tutorial, but it's not the realistic Planner-style split. Owners, admins, and members are different.

The decision we made for this chapter:

| Action | Required role |
|---|---|
| Read a Plan, Bucket, Task, Comment | Any team member |
| Create / update Tasks, Buckets, Comments, ChecklistItems | Any team member |
| Update Plan title or description | Any team member |
| **Update Plan visibility** | Owner or admin |
| **Delete Plan** | Owner or admin |
| Manage Memberships | (Out of scope for this chapter) |

Members do everything they could do before *except* the two privileged operations. That's a small enough list to express in one permission class.

```python
# apps/plans/api/permissions.py
class IsTeamOwnerOrAdmin(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return self._user_has_privileged_role(request.user, obj.team_id)
        if request.method in {"PATCH", "PUT"}:
            if "visibility" in (request.data or {}):
                return self._user_has_privileged_role(request.user, obj.team_id)
        return True

    @staticmethod
    def _user_has_privileged_role(user, team_id) -> bool:
        return Membership.objects.filter(
            user=user, team_id=team_id, role__in=PRIVILEGED_ROLES,
        ).exists()
```

A few things worth pulling out:

- **Reads always pass.** The queryset already filters to the user's plans; if they got far enough to invoke `has_object_permission`, they're allowed to see this row.
- **DELETE always requires a privileged role.** No exceptions.
- **PATCH/PUT with `visibility`** in the payload escalates. Other fields don't. This is the pattern: gate on the *combination* of method and the specific field being changed, not on the verb alone.
- **Inherits from `IsAuthenticated`.** No need to re-check authentication; the parent class does it.

The view then uses just this class:

```python
class PlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTeamOwnerOrAdmin]
    ...
```

### Why the queryset is *still* the primary defense

If you read the test for non-members:

```python
def test_non_member_delete_is_404_not_403(self, member_client):
    """The queryset hides the plan first; the permission class never sees it."""
    client, _, _ = member_client
    other_plan = PlanFactory(team=TeamFactory())
    response = client.delete(f"/api/v1/plans/{other_plan.pk}/")
    assert response.status_code == 404
```

Non-members get **404**, not 403. The queryset filter `for_user(request.user)` runs before the permission check, so the lookup fails before `has_object_permission` is invoked. We don't leak object existence to people who shouldn't even know the row exists.

The permission class only runs for users who *have* a Membership row on the plan's team — it's the within-team gate, not the across-team gate.

---

## What we didn't build (yet)

- **Membership management endpoints.** Adding/removing members and changing roles needs its own permission tier (typically owner-only). Out of scope for this chapter; it's a single-day add-on once the data model is right.
- **Per-action rate limiting.** `django-ratelimit` on login attempts and the JWT obtain endpoint. We'll wire it in Chapter 18 (deployment) — rate limiting is operational policy, often handled at the proxy layer (Cloudflare, ALB) rather than in the app.
- **EXIF stripping for image uploads.** A photographer's camera embeds GPS in JPEGs. If your users post images, you probably want to strip EXIF before storing. One Pillow call away; deferred until image-heavy use cases drive it.
- **Anti-virus scanning.** Industrial uploads send the bytes through ClamAV or a cloud-side scanner. We're sniffing for *type* but not for malicious payloads of allowed types. For Planner-scale internal use this is acceptable; for a public file-sharing service it isn't.
- **Audit logging.** `django-easy-audit` or `django-auditlog` for "who changed what when." Worth adding when you have a compliance story to tell.

---

## Suggested commit message

```
add Chapter 16 — security hardening

* config/settings/production.py: fail-fast import-time checks for
  DJANGO_SECRET_KEY, DJANGO_ADMIN_URL (refuses default `admin/`),
  DJANGO_ALLOWED_HOSTS, and DB_PASSWORD; adds X_FRAME_OPTIONS=DENY,
  SECURE_REFERRER_POLICY=same-origin, SECURE_CONTENT_TYPE_NOSNIFF;
  wires django.middleware.csp.ContentSecurityPolicyMiddleware first
  with default-src 'self' (no inline scripts/styles, no remote loads,
  frame-ancestors 'none')
* Dockerfile: install libmagic1 in the runtime image so python-magic
  imports cleanly
* pyproject.toml: + python-magic
* apps/attachments/validators.py: filename safety (no path separators,
  no leading dots, exactly one extension), size cap from
  PLANLY_MAX_ATTACHMENT_SIZE_MB, extension allowlist, content-type
  sniff via libmagic against an explicit MIME allowlist; centralizes
  validation so the form, the future API serializer, and any bulk
  importer share one code path
* apps/attachments/forms.py: AttachmentForm.clean_file() runs the
  validator stack
* apps/plans/api/permissions.py: IsTeamOwnerOrAdmin extends
  IsAuthenticated; DELETE and visibility changes require the user's
  Membership.role to be OWNER or ADMIN; reads and other writes flow
  through unchanged. The queryset filter remains the primary defense
  (non-members still get 404, not 403)
* apps/plans/api/views.py: PlanViewSet uses IsTeamOwnerOrAdmin
* apps/core/tests/test_production_settings.py: importlib.reload-based
  tests covering each fail-fast branch + every security-header setting
* apps/attachments/tests/test_validators.py: rejection tests for path
  separators, null bytes, double extensions, oversize, banned
  extensions, and renamed executables disguised as PDFs
* apps/plans/tests/test_api/test_permissions.py: member-vs-owner-vs-
  admin matrix for delete and visibility; non-member still gets 404
* docs/tutorial/16-security-hardening.md
```

---

## Where this lands us

We've named the security baseline (Ch 15 §8), implemented it (this chapter), and proven it with tests. The next chapter — **Chapter 17 — Performance & Query Optimization** — does the equivalent for query discipline: turning the principles in §3 of the best-practices chapter into hard `assertNumQueries` tests across the kanban board, the `/api/v1/tasks/` list, and the search endpoints.
