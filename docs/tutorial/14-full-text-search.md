# Chapter 14 — Full-Text Search

## Goal

By the end of this chapter you'll have:

- A **Tier 1** FTS column on `Plan` — a `search_vector` `GeneratedField` Postgres maintains automatically from the row's own `title` + `description`
- A **Tier 2** FTS column on `Task` — a denormalized `tsvector` updated by `django-pgtrigger` triggers that fold in text from related `Comment` rows
- A custom **`english_unaccent`** text-search configuration so `résumé` finds `resume`
- A unified **`/search/?q=…&type=…`** view with HTMX-swap tabs (All / Plans / Tasks)
- An equivalent **`/api/v1/search/?q=…&type=…`** endpoint returning ranked hits with `<b>match</b>` snippets
- The existing API list endpoints (`?search=` on `/api/v1/plans/` and `/api/v1/tasks/`) quietly upgraded from `icontains` to FTS
- Tests covering ranking, weights, comment fan-out, HTMX partials, type filtering, and team scoping

The big themes: **let Postgres do the work** (no application-level indexing), **two tiers for two shapes of data** (own-row vs cross-row), and **one search expression** between the HTML side and the API.

---

## Why Postgres FTS

You have three real options for full-text search at this scale:

| Option | Why it could work | Why it doesn't here |
|---|---|---|
| `icontains` | Already in our queryset | No ranking, no stemming, no diacritics, can't search across related rows |
| Postgres FTS | Built into the database we already run; ranks; stems; supports unaccent | Quirks (we'll cover them) |
| Elasticsearch / Meilisearch | Industrial-grade ranking, fuzzy matching, faceting | A whole second datastore to operate, replicate, and back up |

We pick Postgres because we're not at a scale where Elasticsearch pays for itself, and because keeping search on the database we already have means search results are *exactly* as fresh as the rows themselves — no replication lag, no sync queues. When Planly hits the scale where Postgres FTS is too slow, we'll know it from query logs and can add a search service then.

---

## Two tiers, one model layer

The shape of the data dictates which FTS approach to use.

**Tier 1 is "the searchable text lives entirely on this row."** That's `Plan` — a plan's searchable text is its own `title` and `description`. We model that with a `GeneratedField` whose expression is a tsvector:

```python
# apps/plans/models.py
class Plan(TimeStampedModel):
    ...
    search_vector = models.GeneratedField(
        expression=(
            SearchVector("title", config="english_unaccent", weight="A")
            + SearchVector("description", config="english_unaccent", weight="B")
        ),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        indexes = [
            ...,
            GinIndex(fields=["search_vector"], name="idx_plan_search_vector"),
        ]
```

Postgres maintains the column automatically on every insert and update. There is *no* application code path that can forget to refresh it — the constraint lives in the schema. `db_persist=True` is the postgres-flavored way of saying `STORED` (required for GIN-indexable tsvectors).

**Tier 2 is "the searchable text spans this row and its related rows."** That's `Task` — when someone types `kanban`, they expect to find a task whose own title says nothing about kanban but whose comments do. A `GeneratedField` can only see its own row, so we step up to a real `tsvector` column maintained by Postgres triggers via `django-pgtrigger`:

```python
# apps/tasks/models.py
search_vector = SearchVectorField(null=True, blank=True)

class Meta:
    indexes = [..., GinIndex(fields=["search_vector"], name="idx_task_search_vector")]
    triggers = [
        pgtrigger.Trigger(
            name="task_search_vector_self",
            level=pgtrigger.Row,
            when=pgtrigger.Before,
            operation=pgtrigger.Insert | pgtrigger.UpdateOf("title", "description"),
            func="NEW.search_vector := <tsvector expression>; RETURN NEW;",
        ),
    ]
```

That's the *first* trigger — it fires when the task itself changes. The *second* trigger lives on `Comment` and rebuilds the parent task's vector when a comment is inserted, edited, or deleted:

```python
class Comment(TimeStampedModel):
    ...
    class Meta:
        triggers = [
            pgtrigger.Trigger(
                name="comment_fanout_to_task_search_vector",
                level=pgtrigger.Row,
                when=pgtrigger.After,
                operation=(
                    pgtrigger.Insert
                    | pgtrigger.UpdateOf("body", "task_id")
                    | pgtrigger.Delete
                ),
                func="UPDATE tasks_task t SET search_vector = <expr> "
                     "WHERE t.id = COALESCE(NEW.task_id, OLD.task_id); RETURN NULL;",
            ),
        ]
```

A few things worth pulling out:

- `pgtrigger.UpdateOf("body", "task_id")` only fires the trigger when `body` or the parent FK changes — editing other comment fields doesn't pay the rebuild cost.
- `COALESCE(NEW.task_id, OLD.task_id)` handles all three operations with one statement: `INSERT` populates `NEW`, `DELETE` populates `OLD`, `UPDATE` populates both.
- The trigger writes `tasks_task` directly. When the parent task itself was just cascade-deleted, `WHERE t.id = …` matches zero rows — Postgres returns silently rather than erroring, which is exactly what we want.
- We share one SQL expression between both triggers via a module-level constant (`_TASK_SEARCH_VECTOR_SQL.format(...)`) so they can't drift apart. If we ever change the weighting, both triggers update in one place.

### The tsvector expression itself

```sql
setweight(to_tsvector('english_unaccent', coalesce({title}, '')), 'A') ||
setweight(to_tsvector('english_unaccent', coalesce({description}, '')), 'B') ||
setweight(to_tsvector('english_unaccent',
    coalesce((
        SELECT string_agg(c.body, ' ')
        FROM tasks_comment c
        WHERE c.task_id = {task_id}
    ), '')
), 'C')
```

Three parts, three weights:

- **A — title** (highest weight; if the user types a word in your title, that's the strongest signal)
- **B — description**
- **C — comment bodies, concatenated** (lower than the task's own text but still searchable)

`coalesce(..., '')` everywhere so a NULL field doesn't poison the whole expression. The subquery on `tasks_comment` runs in the trigger context — for a typical task with a handful of comments it's effectively free.

---

## The `english_unaccent` text-search configuration

`unaccent` strips diacritics. To use it transparently — without rewriting every query — we layer it into a *text search configuration* and reference that config everywhere:

```sql
CREATE TEXT SEARCH CONFIGURATION english_unaccent ( COPY = pg_catalog.english );
ALTER TEXT SEARCH CONFIGURATION english_unaccent
    ALTER MAPPING FOR hword, hword_part, word
    WITH unaccent, english_stem;
```

That goes in `apps/core/migrations/0001_extensions.py` alongside `UnaccentExtension()` and `TrigramExtension()`. Now `to_tsvector('english_unaccent', 'résumé')` produces `'resume':1`, identical to `to_tsvector('english_unaccent', 'resume')` — so a search for either string finds either document. `pg_trgm` is staged for future "did you mean…" fallback (out of scope for this chapter).

The migration declares its forward and reverse SQL together so a `migrate core zero` cleanly drops the configuration:

```python
operations = [
    UnaccentExtension(),
    TrigramExtension(),
    migrations.RunSQL(CREATE_UNACCENT_CONFIG, reverse_sql=DROP_UNACCENT_CONFIG),
]
```

Both Plan and Task FTS migrations declare a dependency on `('core', '0001_extensions')` so a fresh-DB rebuild can never run the column-creating SQL before the config exists.

---

## The queryset method — and a Django gotcha

Both `PlanQuerySet` and `TaskQuerySet` expose the same `.search(query, with_headline=False)` shape:

```python
def search(self, query: str, *, with_headline: bool = False):
    cleaned = (query or "").strip()
    if not cleaned:
        return self.none()
    ts_query = SearchQuery(cleaned, search_type="websearch", config="english_unaccent")
    qs = self.filter(search_vector=ts_query).annotate(
        rank=SearchRank(F("search_vector"), ts_query),
    )
    if with_headline:
        qs = qs.annotate(
            headline=SearchHeadline(
                "description", ts_query, config="english_unaccent",
                start_sel="<b>", stop_sel="</b>",
            )
        )
    return qs.order_by("-rank", "-created_at")
```

Three details earn their lines:

1. **`search_type="websearch"`** — this passes the user's input through Postgres's `websearch_to_tsquery`, which understands quoted phrases (`"login flow"`), `OR`, and `-excluded`. It's the same syntax users already know from web search engines and never raises on bad input.
2. **`SearchRank(F("search_vector"), ts_query)`** — and this one is a real Django gotcha. If you write `SearchRank("search_vector", ts_query)`, Django wraps the field as `to_tsvector(coalesce(search_vector::text, ''))` — it casts your stored tsvector to text and re-tokenizes it, **silently dropping the A/B/C weights** you worked to build. Wrapping in `F()` tells Django "this is already a tsvector, use it directly." Verified by reading the generated SQL: `F()` produces `ts_rank(search_vector, …)`; the string form produces `ts_rank(to_tsvector(coalesce(search_vector::text, '')), …)`. The first is what you want.
3. **`SearchHeadline("description", …)`** — the snippet is built from the *text* (description), not the tsvector. We pass the same `config="english_unaccent"` so the headline's tokenization matches what was indexed. The `<b>` markers are inert HTML — the API serializes them as-is, the HTML side could either render them or strip them depending on context.

`order_by("-rank", "-created_at")` makes ranking primary and falls back to recency for ties.

---

## The HTML view — unified search with HTMX tabs

```python
# apps/core/views.py
@login_required
def search(request):
    query = (request.GET.get("q") or "").strip()
    type_filter = request.GET.get("type")
    if type_filter not in ALLOWED_TYPES:
        type_filter = None

    plans = Plan.objects.none()
    tasks = Task.objects.none()
    if query:
        if type_filter is None or type_filter == "plan":
            plans = Plan.objects.for_user(request.user).search(query)[:25]
        if type_filter is None or type_filter == "task":
            tasks = (
                Task.objects.for_user(request.user)
                .search(query)
                .select_related("bucket", "bucket__plan")[:25]
            )

    template = (
        "core/search.html#results"
        if request.headers.get("HX-Request") == "true"
        else "core/search.html"
    )
    return render(request, template, {"query": query, "type_filter": type_filter,
                                       "plans": plans, "tasks": tasks})
```

A few things worth pulling out:

- **Both branches still pipe through `for_user(...)`** — the FTS search vector doesn't know about teams, so we couple FTS filtering to the team-scoped queryset before slicing. A non-member can never see search hits for content they couldn't otherwise see.
- **Whitelist the `type` parameter.** Anything other than `plan` or `task` falls through to "no filter" (mixed results). This is cheaper than 400-erroring on a typo.
- **HTMX returns just the partial.** When the click came from a tab (`HX-Request: true`), we render `core/search.html#results` — a `{% partialdef results inline %}` block defined inside the same page template. The full URL bar still updates because the tab uses `hx-push-url="true"`, so reloading the page rebuilds the same view (as the full template) with the same filter applied.

The Django 6 `partialdef` syntax is `{% partialdef name inline %}` — *not* `inline=True`. Earlier versions of `django-template-partials` accepted `inline=True`, but the built-in tag in Django 6 is stricter. Trip on this once and you remember it forever.

> **Gotcha: `{# … #}` is single-line only.** A first draft of the tabs included a multi-line annotation written as `{# Tabs use HTMX… hx-push-url updates the address bar… #}`. Django parses `{# … #}` as a *single-line* comment — anything after the first newline is treated as literal template content. The annotation rendered onto the page in plain text. The fix: any comment that wraps to a second line must use `{% comment %}…{% endcomment %}`. Reserve `{# … #}` for inline single-line annotations (`<div>{# hidden by feature flag #}</div>`).

The tabs themselves carry both `href` (for non-HTMX fallback) and `hx-get` (for the HTMX swap) — progressive enhancement built in. JavaScript-disabled visitors get a normal full-page request; everyone else gets the smooth tab swap.

---

## Search bar in the global nav

`templates/base.html` grows a search input on the navbar that submits to `/search/`:

```html
{% if user.is_authenticated %}
  <form action="{% url 'core:search' %}" method="get"
        class="flex flex-1 max-w-md mx-4">
    <input type="search" name="q" value="{{ request.GET.q|default:'' }}"
           placeholder="Search plans &amp; tasks…"
           class="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm
                  focus:outline-none focus:ring-2 focus:ring-indigo-500"
           aria-label="Search plans and tasks">
  </form>
{% endif %}
```

Three notes:

- **`type="search"`** gets the OS-native clear-button-on-the-right and dedicated keyboard.
- **`value="{{ request.GET.q|default:'' }}"`** keeps the query visible in the navbar after a search — clicking elsewhere doesn't clear what you typed.
- **No `hidden sm:flex` qualifier.** A first draft hid the bar on viewports under 640px (the Tailwind `sm` breakpoint), reasoning that mobile users would tap a separate icon to expand it. We pulled that — for a productivity tool, the search bar earns its real estate at every width, and adding a hide/expand toggle was extra surface for no benefit.

We don't add HTMX live-search (typing-as-you-go) because the FTS query is heavy enough that we want explicit submission. Type, Enter, see results.

---

## API: upgrade `?search=` and add `/api/v1/search/`

### Upgrading the existing `?search=` parameter

The Plan and Task ViewSets already accepted `?search=` from `SearchFilter`, which does case-insensitive `icontains` across `search_fields = ["title", "description"]`. We replace that with FTS by overriding `get_queryset()`:

```python
# apps/plans/api/views.py
def get_queryset(self):
    qs = Plan.objects.for_user(self.request.user).select_related("team", "owner", "created_by")
    search = (self.request.query_params.get("search") or "").strip()
    if search:
        return Plan.objects.for_user(self.request.user).search(search)
    return qs
```

We *don't* declare `search_fields` anymore — `SearchFilter`'s icontains pass would fight ranking. The FTS branch returns results already ordered by `-rank`, and DRF's default ordering kicks in only when no explicit ordering is set.

Existing API clients calling `?search=login` see no breaking change — they get *better* results: ranked, stemmed, with diacritics handled, and (for tasks) including matches in comment bodies. A client that only used the plain icontains semantics doesn't notice.

### The unified `/api/v1/search/` endpoint

For "I want to search across both plans and tasks at once" — exactly the shape of the HTML page — we add a small `APIView` under `apps/core/api/views.py`:

```python
class SearchView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SearchHitSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(name="q", type=str, required=True, location="query"),
            OpenApiParameter(name="type", type=str, required=False, location="query",
                             enum=sorted(ALLOWED_TYPES)),
        ],
        responses=SearchHitSerializer(many=True),
    )
    def get(self, request):
        ...
```

Each hit is a flat dict — `type`, `id`, `title`, `url`, `rank`, `headline` — so the response is a homogeneous list regardless of which kinds matched. Clients can branch on `type` to render plan rows differently from task rows; the schema stays a single shape.

The endpoint is *not* paginated. Search caps at 25 hits per resource and that's the whole list. Pagination is a *browse* feature; search is "I know what I want, find it now." If you need more than 25 hits, the query was wrong, not the page size.

```python
hits.sort(key=lambda hit: hit["rank"], reverse=True)
return Response(SearchHitSerializer(hits, many=True).data)
```

Mixing the two resources by rank means the strongest match floats to the top regardless of kind — a task whose comment exactly matches the query can outrank a plan with a tangential title hit. That's usually the right call for a unified bar.

---

## Tests

### Test layout — what goes where

Mirroring our existing convention:

```
apps/plans/tests/test_querysets.py      # PlanQuerySet.search() ranking, weights, unaccent
apps/tasks/tests/test_querysets.py      # TaskQuerySet.search() including comment fan-out
apps/core/tests/test_views.py           # /search/ HTML view, HTMX partial, type filter, scoping
apps/core/tests/test_api/test_views.py  # /api/v1/search/ + ?search= upgrades on plans/tasks
apps/core/tests/test_api/test_serializers.py  # SearchHitSerializer shape
```

Trigger behavior is covered as part of `TaskQuerySet.search()` — we assert *outcomes* (a search after a comment edit returns the right tasks), not the trigger SQL itself, because the trigger is the implementation detail that gets us there.

### Assertions that earned their slot

A few tests in this batch are doing more than they look:

```python
def test_comment_edit_updates_search_vector(self):
    """Editing a comment body re-fires the fan-out trigger."""
    task = TaskFactory(title="Latency", description="")
    comment = CommentFactory(task=task, body="kanban query")

    comment.body = "graphql resolver"
    comment.save()

    assert task not in Task.objects.search("kanban")
    assert task in Task.objects.search("graphql")
```

This test asserts something that no application code did. The body changed, the trigger fired, the task's search vector was rewritten. If the trigger were missing (or wired to the wrong `UpdateOf` columns), the old lexemes would linger and `search("kanban")` would still return the task. This is the test that protects the entire Tier 2 contract.

```python
def test_does_not_leak_other_team_results(self, member_team):
    PlanFactory(team=TeamFactory(), title="Secret Project Phoenix")
    response = client.get(reverse("core:search"), {"q": "phoenix"})
    assert b"Secret Project Phoenix" not in response.content
```

The FTS column doesn't know about teams; if you forget to compose `for_user()` with `.search()`, search becomes an information-disclosure vector. This test asserts you didn't forget. If a future refactor moves FTS to its own ad-hoc view or strips the for_user call, this goes red.

### Migrations are now run

Earlier chapters configured pytest with `--no-migrations` for speed — Django's syncdb-style table creation skipped migration ordering and saved a few seconds per fresh DB. Chapter 14 doesn't have that option: extensions, the `english_unaccent` config, GIN indexes, and pgtriggers all live in migration operations and would never reach the test DB under syncdb. We dropped `--no-migrations` from `pyproject.toml`:

```toml
addopts = "--ds=config.settings.test --reuse-db -q --import-mode=importlib"
```

`--reuse-db` keeps the cost low — once the test DB is built, every subsequent run reuses it. When you change a migration, pass `--create-db` once to rebuild from scratch.

### Test-only concrete models that previously got tables for free

`apps/core/tests/test_models.py` declares `ConcreteTimeStamped`, `ConcreteOrdered`, and `ConcreteTimeStampedOrdered` purely to exercise the abstract bases. Under `--no-migrations` syncdb saw them as installed models and created tables. Under proper migrations there's no migration operation that would. We restore the missing tables in `apps/conftest.py` with a session-scoped, autouse fixture that uses `connection.schema_editor()` to create them once and drop them at session end:

```python
@pytest.fixture(scope="session", autouse=True)
def _create_abstract_base_test_tables(django_db_setup, django_db_blocker):
    from apps.core.tests.test_models import (
        ConcreteOrdered, ConcreteTimeStamped, ConcreteTimeStampedOrdered,
    )
    test_only_models = [ConcreteTimeStamped, ConcreteOrdered, ConcreteTimeStampedOrdered]
    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        for model in test_only_models:
            editor.create_model(model)
    yield
    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        for model in reversed(test_only_models):
            editor.delete_model(model)
```

That keeps the abstract-base unit tests usable without polluting production migrations with test-only models.

---

## What we didn't build

- **Comment-direct search.** A search hit on a Task brings the task with it; we didn't add a separate "find me the comment that matches" view. If you want it, mirror the Plan pattern with a Tier 1 GeneratedField on Comment.
- **Trigram fallback.** We installed `pg_trgm` so `Plan.objects.annotate(similarity=TrigramSimilarity("title", "<typo>"))` is available, but the unified search doesn't fall back to it when the FTS query has no hits. That's a "did you mean…" feature for a later chapter.
- **Faceting** ("show me a count of plans vs tasks for this query"). The unified endpoint could grow that — useful if you start showing facet pills in the HTML tabs. For now the count comes from the rendered list.
- **Synonyms.** Postgres supports synonym dictionaries in text-search configs (`mySynonyms`). If product wants `dashboard ↔ board ↔ overview` to interchange, that's an ALTER on `english_unaccent`.

---

## Suggested commit message

```
add Chapter 14 — full-text search

* apps/core/migrations/0001_extensions.py: install unaccent + pg_trgm
  and create the english_unaccent text-search configuration that layers
  unaccent in front of the English stemmer
* apps/plans/models.py: Tier 1 — Plan.search_vector as a GeneratedField
  combining title (weight A) and description (weight B); GIN index
* apps/tasks/models.py: Tier 2 — Task.search_vector tsvector populated
  by two pgtriggers: BEFORE-INSERT/UPDATE on Task itself, and
  AFTER-INSERT/UPDATE/DELETE on Comment that rebuilds the parent task's
  vector. One shared SQL expression keeps both triggers in sync.
* apps/{plans,tasks}/querysets.py: .search(query, with_headline=False)
  runs websearch_to_tsquery, ranks via SearchRank(F("search_vector")),
  optionally annotates a <b>match</b> headline, orders by rank then
  created_at. F() avoids Django's silent re-tokenization that drops
  the stored A/B/C weights.
* apps/core/views.py + templates/core/search.html: unified /search/
  view with HTMX tab swap (All / Plans / Tasks), partialdef results
  block for the swap target
* templates/base.html: search bar in the global nav
* apps/core/api/{views,serializers,urls}.py: /api/v1/search/?q=&type=
  returning ranked SearchHitSerializer rows; @extend_schema annotates
  parameters and response for spectacular
* apps/{plans,tasks}/api/views.py: ?search= on the list endpoints now
  branches into the FTS .search() queryset method instead of icontains
* config/api_router.py + config/urls.py: wire /search/ and /api/v1/search/
* pyproject.toml: drop --no-migrations from pytest addopts so test
  DBs receive the extension migration, FTS config, GIN indexes, and
  triggers
* apps/conftest.py: session-scoped autouse fixture creating tables
  for the test-only concrete models in apps/core/tests/test_models.py
  (these previously got tables via syncdb under --no-migrations)
* Tests cover Plan and Task search ranking, weight ordering, unaccent
  matching, comment-fan-out via trigger (insert/update/delete), HTMX
  partial responses, type filtering, team scoping for both HTML and
  API, and SearchHitSerializer shape
* docs/tutorial/14-full-text-search.md
```

---

## Where this lands us

Phase 4 of the tutorial is now done. We have:

- **Server-rendered HTML** with HTMX (Chapters 9–11)
- **Background pipeline** for fan-out work (Chapter 12)
- **REST API** for clients that don't share the browser session (Chapter 13)
- **Full-text search** across both layers, sharing one queryset method (this chapter)

Next up: **Phase 5 — Best Practices & Production**, beginning with **Chapter 15 — Django Best Practices**, a standalone reference chapter that consolidates the patterns and trade-offs we've made in code into one place.
