# Chapter 15 — Django Best Practices

A standalone reference. Where earlier chapters built things one at a time, this one steps back and names the patterns we kept reaching for — and the ones we deliberately avoided. Read it after you've seen the project come together; the rules earn themselves more clearly when you can point at the code where they paid off.

Each section ends with a **Reach for / Avoid** pair you can skim later. The final section walks through the half-dozen mistakes I'd flag first in code review, with wrong-then-right examples for each.

---

## 1. Project structure

The shape of the codebase is a contract. Get it right early, and every later decision (testing, deploys, refactors) is cheaper. Get it wrong, and you spend years working around a hardcoded import path.

**`apps/` is a Python package, not a folder convention.** It has an `__init__.py`. Every app is registered as `apps.<name>` and its `AppConfig.name` matches that string exactly. This isn't aesthetic — it's what lets `from apps.tasks.models import Task` work the same way in dev, in tests, and in the running app, with no `sys.path` shuffling at the call site.

**`config/` is the project package — never the project's name.** A directory named `config/` is grep-able, refactor-safe, and doesn't mislead a reader into thinking they need to learn what "planly" is before reading the settings module. The chosen project name lives in one place: `pyproject.toml`.

**Settings split into per-environment modules** (`base`, `local`, `test`, `production`) and each entry point sets `DJANGO_SETTINGS_MODULE` directly. No `__init__.py` router that branches on `DJANGO_ENV` — `DJANGO_SETTINGS_MODULE` is already the routing primitive Django gives you. Don't build a second one.

**Each `AppConfig` sets a short `label`** (`"tasks"`, not `"apps.tasks"`). The label is what Django uses for table prefixes (`tasks_task` vs `apps_tasks_task`) and the admin URL — the short form keeps both clean.

> **Reach for:** `apps/<name>/`, `config/`, split settings, short `app_label`, `sys.path.append(BASE_DIR / "apps")` in entry points.
> **Avoid:** project package named after the product, single monolithic `settings.py`, `DJANGO_ENV` routers in `__init__.py`, importing app code via the dotted `apps.tasks.models` path *inside* `apps/tasks/` (use `from .models` there).

---

## 2. Model design

A model is more than a table — it's the place where domain rules live. The view layer should *call* the model; it should not *recompute* what the model already knows.

**Fat models.** When a behavior depends on a model's own state, write it as a method or property on that model. `Task.is_overdue` lives on `Task`; `Task.mark_complete()` lives on `Task`. Views become orchestration code: receive request, call domain method, return response. If a view exceeds 20 lines, business logic is leaking in.

**Abstract bases for shared timestamping and ordering.** `TimeStampedModel` (with `created_at` / `modified_at`) and `OrderedModel` (with `position`) absorb the boilerplate. Multiple inheritance composes them: `class Bucket(TimeStampedModel, OrderedModel)`. The base classes carry no `objects` manager so subclasses can override freely.

**Custom QuerySets in `querysets.py`, custom Managers in `managers.py`.**

| File | Holds | When |
|---|---|---|
| `querysets.py` | `models.QuerySet` subclass, wired via `as_manager()` | Chainable query helpers — `for_user()`, `with_task_counts()`, `search()` |
| `managers.py` | `models.Manager` or `BaseUserManager` subclass | Custom *creation* logic — `create_user()`, `create_superuser()` |

`for_user(user)` is the team-scoping primitive. Every model that's reachable through team membership exposes it — `Plan.objects.for_user(u)`, `Task.objects.for_user(u)`, `Comment.objects.for_user(u)`. The signature is identical everywhere; views, the API, the search code, and the admin all use the same call.

**`IntegerChoices` with gaps for ordered values.** `URGENT = 1, IMPORTANT = 3, MEDIUM = 5, LOW = 9`. The gaps mean you can insert a new tier later (`HIGH = 4`) without renumbering. `TextChoices` for purely categorical labels (`Visibility`, `Role`).

**Constraints in the database, not in `clean()`.** `UniqueConstraint(fields=["plan", "name"], name="unique_label_per_plan")` survives raw SQL inserts, bulk operations, and concurrent writes. `clean()` runs only when the form runs it — that's a coin flip in production.

> **Reach for:** fat models, `TimeStampedModel` everywhere, custom `QuerySet` per app, `for_user()` as the team-scoping primitive, `IntegerChoices` with gaps, `UniqueConstraint`/`CheckConstraint` for invariants.
> **Avoid:** computing `is_overdue` in the view, forms-only validation for hard invariants, signals when a method would do (see §5), `objects = models.Manager()` to override Django's default (override `Meta.base_manager_name` if you really need it).

---

## 3. Query discipline

Django makes it trivially easy to write N+1 queries. Treat that as a warning, not a feature.

**Default to `select_related` for FK and OneToOne.** Forces a JOIN in a single query. Use it on every list view that displays a foreign-key field.

**`prefetch_related` for M2M and reverse FK.** Issues a second query and stitches results together in Python. Used liberally in our `TaskViewSet` to keep the assignees per-task at one extra query, not N.

**`Prefetch()` for filtered prefetches.** When you want "all tasks for this plan, but only the user's incomplete ones," `Prefetch("buckets__tasks", queryset=Task.objects.filter(...).select_related(...))` is the tool. Don't iterate and filter in Python after the fetch.

**`update_fields` on `save()` for narrow updates.** A `task.save(update_fields=["progress", "completed_at"])` writes one `UPDATE … SET progress=…, completed_at=…` instead of touching every column. Cheaper, and crucially, it stops `auto_now` fields from being updated when you didn't intend it.

**Indexes follow access patterns, not data shape.** Plans get an index on `(team, -created_at)` because the list view filters by team and orders by recency. Tasks get a *partial* index on `progress` only where `progress < 100` because the "active tasks" query is the hot path. Index what you actually query.

**Query-count tests for hot paths.** `assertNumQueries(N)` in any view that lists more than a handful of objects. Without it, the gap between "this works on my dev DB with three rows" and "this brought prod to its knees" is a single careless `prefetch_related` removal.

**FTS with GIN, not LIKE.** `icontains` is fine for ten rows; full-text search is the answer above that. Tier 1 is a `GeneratedField` (the row's own text); Tier 2 is a `SearchVectorField` maintained by `pgtrigger` triggers (when related-row text counts).

> **Reach for:** `select_related` on every FK in a list, `prefetch_related` on every M2M, `Prefetch()` when filtering matters, `update_fields`, GIN+FTS for text search.
> **Avoid:** raw `.filter(field__icontains=...)` for anything user-facing past dev data, indexes "just in case," lookup loops in Python that should be a single `prefetch_related`.

---

## 4. Permissions

The standard DRF cookbook says "write a `BasePermission`." That's not wrong, but it's not the *primary* defense.

**The queryset is the primary defense.** When `get_queryset()` returns `Plan.objects.for_user(request.user)`, three things happen for free:

- **List endpoints** show only the user's plans.
- **Detail / update / delete** falls through `get_object_or_404`-style; a non-member gets a **404, not 403**.
- **Refactors** can't accidentally regress the rule. The team-scoping is in the data layer, where the data layer enforces it.

**404, not 403, for unauthorized object access.** A 403 confirms "this resource exists, you can't have it." A 404 says "this resource may or may not exist; you wouldn't know." The latter doesn't leak object existence to attackers probing for valid IDs.

**Permission classes are bouncers, not bookkeepers.** `[IsAuthenticated]` handles "you have to be logged in." Anything past that — "is this resource yours?", "are you in this team?", "is this plan public?" — should be expressed in the queryset filter, not duplicated in a `has_object_permission()` method that a future change might forget to call.

**Server-stamps `created_by` and friends.** The serializer marks them read-only; the view calls `serializer.save(created_by=self.request.user)` in `perform_create`. A client sending `{"created_by": 999}` gets the field overwritten silently — there's no "do you trust the client" decision to make at runtime.

> **Reach for:** queryset-level scoping with `for_user()`, server-stamped audit fields, 404 over 403, `IsAuthenticated` plus business-logic-in-the-queryset.
> **Avoid:** parallel permission classes that re-implement what the queryset already filters, exposing object existence via 403 vs 404 difference, trusting any client-supplied "who did this" field.

---

## 5. Signals vs methods

Signals are pub-sub, and they're powerful. They're also *over-used*. Before reaching for one, ask:

> Could I do this with a method on the model, called from the place that triggered the event?

If yes, do that. Methods are easier to reason about, easier to grep for, easier to test. Signals are spooky-action-at-a-distance — code in `apps/foo` runs because of an event in `apps/bar` with no direct call site.

**A signal earns its keep when:**

1. **Trigger and response live in different apps**, and you don't want them coupled at the call site. (`apps.notifications` reacts to `apps.tasks`; tomorrow an analytics app, a search-index app, or a webhook app subscribes too — without `apps.tasks` knowing they exist.)
2. **The trigger has many call sites you don't control**, and the response is an invariant. (The admin, the API, raw `task.save()` from a management command — all bypass your fat-model methods. A `pre_save` signal that stamps `completed_at` when `progress` hits 100% catches all of them.)
3. **The reaction needs only the model instance** — not `request.user`, not the active locale, not any request-scoped context. If you need request context, the *view* should call the function directly.

**`apps.tasks` ships both kinds.** `Task.mark_complete()` is a fat-model method; views call it directly. `pre_save` on `Task` stamps `completed_at` as a fan-out invariant — the safety net that catches every save path. The signal exists *because* the method isn't the only entry point; it isn't a replacement for the method.

**`AppConfig.ready()` is the only place to register signals.** Local imports inside `ready()` (with a `# noqa: F401` to silence "unused") avoid circular-import problems. Never put `@receiver` decorators in `models.py` — when the app loads twice (test setup, migration plan, management command introspection), receivers fire twice.

**View-level enqueue when the actor is `request.user`.** Assignment notifications need the actor for self-suppression — "don't notify me if I assigned myself." `Assignment` doesn't carry an `assigned_by` field (and shouldn't), so the *view* enqueues `send_assignment_notification(task_id, assignee_id, request.user.pk)`. A signal couldn't do this without polluting the model.

> **Reach for:** fat-model methods first; `pre_save` for invariants; `post_save` for cross-app fan-out via `django.tasks`.
> **Avoid:** `@receiver` decorators in `models.py`, signals when you needed a method, signals that depend on request-scoped context, multiple receivers competing to set the same field.

---

## 6. API design

DRF gives you a lot of knobs. Pick the smallest set that solves the problem.

**Two authentication classes, JWT first.** Browser-bound clients carry the same session cookie that powers the HTML side; external clients use JWT bearer tokens. Putting JWT first in `DEFAULT_AUTHENTICATION_CLASSES` makes the `WWW-Authenticate` challenge correct, and unauthenticated requests return **401**, not 403.

**Versioning is in the URL.** `URLPathVersioning` with `/api/v1/` is the most legible scheme — a log line tells you which version a client hit, and a CDN can route by path. Header- or query-param versioning is harder to debug for no real benefit.

**One aggregator, per-app `api/urls.py`.** `config/api_router.py` includes each app's API URLs flat under `/api/v1/`. Each app owns its own `DefaultRouter` and registers its own ViewSets. Resources sit at `/api/v1/plans/`, `/api/v1/tasks/`, not `/api/v1/plans/plans/`.

**Read-only fields enforce server-stamped invariants.** Anything the server controls — `created_by`, `completed_at`, `position`, `assignees` (managed via Assignment endpoints) — is `read_only=True` on the serializer. A client posting that field gets the value silently overwritten.

**Filtering uses `django-filter`; a `FilterSet` for cross-model filters.** `?priority=1` is fine via `filterset_fields = ["priority"]`. `?plan=42` on tasks (which have no direct FK to Plan) needs an explicit `FilterSet` with `plan = NumberFilter(field_name="bucket__plan_id")`.

**OpenAPI is a CI gate.** `python manage.py spectacular --validate --fail-on-warn` exits non-zero on any schema warning. Type-hinted `SerializerMethodField` resolvers, `queryset = Model.objects.none()` on every ViewSet (so spectacular can introspect without a request user), and `@extend_schema` annotations on plain `APIView`s are the three things that keep this exit code at 0.

**Read-only ViewSets stay narrow on purpose.** Notifications are server-emitted; clients don't `POST` them. `ReadOnlyModelViewSet` makes `POST` and `DELETE` return 405 by default; a custom `@action(detail=True, methods=["post"])` on `mark_read/` is the explicit, named mutation the API exposes.

> **Reach for:** session + JWT, URL-path versioning, per-app `api/urls.py`, `read_only_fields`, `FilterSet` for cross-model filters, `@action` for explicit named mutations, schema-validation in CI.
> **Avoid:** writing your own auth backend, header versioning, exposing every Django field as writable, "kitchen-sink" `ModelViewSet` where `ReadOnlyModelViewSet` would do, trusting client-supplied `created_by`.

---

## 7. Testing philosophy

Tests are not a chore you do *after* code — they're the cadence by which you write code.

**TDD from chapter 4 onward.** Models, querysets, views, API endpoints, signals, FTS, all have tests written either alongside or before the implementation. The exception is the literal first chapter or two of project setup; the moment you have a model or a view, you have a test.

**Test what you wrote, skip what Django wrote.** Test custom methods (`Task.mark_complete()`), properties (`is_overdue`), and queryset helpers. *Don't* test field existence, `auto_now`, `Meta.ordering`, or "this `CharField` saves and retrieves." Those are Django's tests; you don't need to re-run them per-project.

**Test layout mirrors the implementation.** When the implementation is a single file (`models.py`), the test is a single file (`test_models.py`). When the implementation grows into a *subpackage* (`apps/tasks/api/` with `views.py`, `serializers.py`, `filters.py`), the tests grow to a parallel subpackage (`apps/tasks/tests/test_api/test_views.py`, `test_serializers.py`, `test_filters.py`). Each test file maps to one implementation file. Don't lump the API tests into a flat `test_api.py` — that's a future thousand-line catch-all.

**Factories in `factories.py`, not in fixtures.** factory-boy beats Django fixtures for one reason: factories are code, so refactors of the model carry through automatically; a `dumpdata`/`loaddata` JSON fixture goes stale silently the day someone renames a field.

**`@pytest.mark.django_db` is the contract.** Every test that hits the DB declares it. The `--no-migrations` shortcut works *until* a migration carries something tests need (extensions, FTS configs, GIN indexes, triggers). Then you take it off and let the migrations run.

**No header comments or decorative separators in test files.** Class names and docstrings are sufficient; ASCII-art separators rot the moment you reorder methods. The class docstring already names what the class is for.

**Query-count tests for list endpoints.** `assertNumQueries(N)` is the only thing standing between "ships fine" and "production goes down at scale." Treat them as load-bearing tests, not optional decoration.

> **Reach for:** TDD, factory-boy, `@pytest.mark.django_db`, test-layout-mirrors-implementation, `assertNumQueries` on hot list views, custom-method tests.
> **Avoid:** testing Django itself, JSON fixtures, header comments in tests, lumping subpackage tests into a flat file, mocking the database in tests that should hit it.

---

## 8. Security defaults

Most security wins are *defaults*, not heroic measures.

**`DJANGO_ADMIN_URL` env var, validated in production.** The admin doesn't sit at `/admin/` in prod — it sits at whatever path you set on the env. Production settings fail to import if the variable is unset, so you can't accidentally deploy with the default.

**Body-level CSRF for HTMX.** A single `<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>` sets the header for every HTMX request from that page. Per-form `{% csrf_token %}` hidden inputs are the alternative, and they're tedious *and* prone to be omitted on a new fragment.

**JWT first in the auth class order.** Forces unauthenticated API requests to return `401 + WWW-Authenticate: Bearer` instead of `403 + no challenge`. Tiny detail, real difference for clients that need to know whether they should retry with credentials.

**`PASSWORD_HASHERS = ["MD5PasswordHasher"]` in `test.py` only.** Production uses Argon2 or PBKDF2 (Django's default). The test hasher is *only* loaded by the test settings module — anything else and a misconfigured deploy ships with the toy hasher.

**Server-stamped audit fields are never client-writable.** Said earlier in §4 and §6. It's repeated here because it's the single most common authorization bug in DRF projects.

**Storage is S3-compatible, not local disk in production.** `django-storages[s3]` everywhere; `MEDIA_ROOT` exists only in dev. A user-uploaded file should never share a filesystem with the application code that serves it.

**CSP is on by default in `production.py`.** Vendored HTMX, vendored fonts, no `'unsafe-inline'` in style or script directives. The decisions you make in dev — vendoring HTMX rather than CDN-loading it — are what make a strict CSP achievable in prod.

> **Reach for:** env-driven `ADMIN_URL`, body-level CSRF, JWT-first auth ordering, server-stamped fields, S3 storage, strict CSP from day one.
> **Avoid:** hardcoded `/admin/`, per-form CSRF inputs alongside HTMX, `'unsafe-inline'` in CSP, local-disk storage in production, debug toolbar in non-DEBUG.

---

## 9. Common anti-patterns

Six wrong-then-right pairs from the project, plus a bullet list of the rest. These are the mistakes I'd flag in a code review on day one.

### 9.1 The `SearchRank("field", q)` re-tokenization trap

```python
# ❌ Wrong — silently drops weight info
qs = self.filter(search_vector=ts_query).annotate(
    rank=SearchRank("search_vector", ts_query),
)
```

```python
# ✅ Right — uses the stored tsvector directly
qs = self.filter(search_vector=ts_query).annotate(
    rank=SearchRank(F("search_vector"), ts_query),
)
```

The string form makes Django wrap `search_vector` in `to_tsvector(coalesce(search_vector::text, ''))` — it casts your stored tsvector to text and re-tokenizes it, losing the A/B/C weights you painstakingly set with `setweight()`. `F()` tells Django "this is already a tsvector." Diff the generated SQL to convince yourself.

### 9.2 Multi-line `{# … #}` template comments

```django
{# ❌ Wrong — comment text renders into the page
   This explanation spans multiple lines because
   the engineer thought {# was a block-comment.
#}
```

```django
{% comment %}
  ✅ Right — this never reaches the rendered page.
  Use {% comment %}…{% endcomment %} for anything
  that wraps to a second line.
{% endcomment %}
```

`{# … #}` is a single-line comment in Django. Anything past the first newline is treated as literal template content and rendered into the response. Reserve `{# … #}` for inline single-line annotations (`<div>{# hidden by feature flag #}</div>`).

### 9.3 Local imports

```python
# ❌ Wrong — hides the import chain inside a function
def export_plan(plan_id):
    from apps.plans.models import Plan
    from apps.tasks.models import Task
    ...
```

```python
# ✅ Right — top-level imports
from apps.plans.models import Plan
from apps.tasks.models import Task

def export_plan(plan_id):
    ...
```

Local imports were a 2010-era workaround for circular-dependency problems. In a healthy project, you have circulars *only* in two places: `AppConfig.ready()` registering signals, and the rare type-checking-only import inside `if TYPE_CHECKING:`. Outside those, top-level imports — always. Local imports hide call graphs from grep, defer ImportErrors to runtime, and slow down repeated function calls.

### 9.4 Trusting client-supplied `created_by`

```python
# ❌ Wrong — accepts whatever the client posts
class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["title", "description", "team", "created_by"]
```

```python
# ✅ Right — server stamps it
class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["title", "description", "team", "created_by"]
        read_only_fields = ["created_by"]

class PlanViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
```

The client is never the source of truth for "who did this." Read-only on the wire, server-stamped in `perform_create`. The single-most-common authorization bug in DRF apps is leaving an audit field writable.

### 9.5 Signals where a method would do

```python
# ❌ Wrong — a signal that runs in-process to do work the caller could do directly
@receiver(post_save, sender=Task)
def update_completed_timestamp(sender, instance, **kwargs):
    if instance.progress == 100 and instance.completed_at is None:
        instance.completed_at = timezone.now()
        instance.save(update_fields=["completed_at"])  # recursive!
```

```python
# ✅ Right — a fat-model method, called from the view
class Task(TimeStampedModel):
    def mark_complete(self):
        self.progress = self.Progress.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["progress", "completed_at"])

# View
task.mark_complete()
```

The wrong version is also a near-infinite loop (the signal fires its own `save()` which fires the signal again). The right version is direct, testable, and grep-able. *If* you also need the invariant for code paths that bypass `mark_complete()` (admin, raw scripts), reach for a `pre_save` signal that *only* sets `instance.completed_at` (no `instance.save()` — the invoking save will do that).

### 9.6 `SearchFilter` next to FTS

```python
# ❌ Wrong — icontains fights the FTS ranker
class TaskViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "description"]

    def get_queryset(self):
        qs = Task.objects.for_user(self.request.user)
        if search := self.request.query_params.get("search"):
            qs = qs.search(search)
        return qs
```

```python
# ✅ Right — drop SearchFilter; FTS .search() owns ?search=
class TaskViewSet(viewsets.ModelViewSet):
    # SearchFilter is intentionally not listed; .search() handles it.
    filter_backends = [DjangoFilterBackend, OrderingFilter]

    def get_queryset(self):
        qs = Task.objects.for_user(self.request.user)
        if search := self.request.query_params.get("search"):
            return Task.objects.for_user(self.request.user).search(search)
        return qs
```

`SearchFilter` does post-hoc icontains across `search_fields` *after* your FTS branch already ranked and ordered the results. It re-orders by nothing useful and silently undoes your ranking. Pick one or the other — for FTS-backed search, that means dropping `SearchFilter`.

### Other traps worth one bullet each

- **`assertNumQueries(N)` missing on list views.** A single `select_related` regression turns a one-query page into a hundred-query page; without the test, you find out from prod.
- **Blocking calls inside `django.tasks` task functions.** Tasks should be idempotent and accept primitive ids only — never model instances. A model instance pickled into the queue is a data-leak waiting to happen.
- **`@override_settings` on `pytest` test classes.** Doesn't work — those aren't `SimpleTestCase` subclasses. Use the `settings` fixture and `pytest.mark.usefixtures` instead.
- **`enqueue()` is the only way to call a `@django_task()` function.** Calling it directly raises `TypeError: 'Task' object is not callable`. In tests, set the backend to `ImmediateBackend` and `.enqueue()` the same way production does.
- **Header comments and ASCII-art separators in test files.** Class names and docstrings already do the labelling; the separators rot the moment someone reorders methods.
- **`DJANGO_SETTINGS_MODULE` indirection via a `DJANGO_ENV` router in `config/settings/__init__.py`.** Add nothing. Each entry point sets `DJANGO_SETTINGS_MODULE` directly; the env var is the only routing primitive you need.
- **`{% partialdef name inline=True %}` in Django 6.** The new built-in tag accepts the bare word `inline`, not `inline=True`. The previous `django-template-partials` package allowed both; Django 6's tag is stricter.
- **`MEDIA_ROOT` in production.** Local disk = single point of failure that's also gone after the next container redeploy. S3-compatible storage from day one; `MEDIA_ROOT` exists only in `local.py` and `test.py`.

---

## Where this lands us

Phase 5 is "best practices and production." This chapter named the patterns; the next two chapters apply them.

- **Chapter 16 — Security Hardening**: CSP, upload validation, fail-fast on unset `DJANGO_ADMIN_URL`, deeper per-object permission checks. Section 8 above is the framing; Ch 16 is the discipline.
- **Chapter 17 — Performance & Query Optimization**: turning §3's principles into hard `assertNumQueries` tests across the app. The kanban board, the `/api/v1/tasks/` list, and the search endpoints are the three hot paths to harden.

The shape of the rest of Phase 5 is operational, not architectural. The architectural decisions are this chapter — make them well, and Chs 16–18 are mostly knobs to turn.
