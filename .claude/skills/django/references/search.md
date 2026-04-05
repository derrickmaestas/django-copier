# Full-Text Search

PostgreSQL full-text search — no external service needed. Supports stemming, weighted ranking, and GIN indexes.

## Two-Tier Approach

| Tier | Method | Use when |
|------|--------|----------|
| **Tier 1** | `GeneratedField` | Same-table search, no weights needed |
| **Tier 2** | `django-pgtrigger` | Weighted ranking (title > description) OR cross-table search |

Start with Tier 1. Upgrade to Tier 2 when you need weights or related-model fields.

## Tier 1: GeneratedField (Zero Dependencies)

The database computes and stores the tsvector on every INSERT/UPDATE — no triggers, no signals:

```python
# apps/plans/models.py
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models


class Plan(TimeStampedModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    search_vector = models.GeneratedField(
        expression=SearchVector("title", "description", config="english"),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        indexes = [
            GinIndex(fields=["search_vector"], name="idx_plan_search"),
        ]
```

Run `makemigrations` and `migrate`. Existing rows are computed automatically — no backfill needed.

### Querying Tier 1

```python
# apps/plans/managers.py
from django.contrib.postgres.search import SearchQuery, SearchRank


class PlanQuerySet(models.QuerySet):
    def search(self, query_text):
        if not query_text:
            return self.none()
        query = SearchQuery(query_text, config="english", search_type="websearch")
        return (
            self.filter(search_vector=query)
            .annotate(search_rank=SearchRank("search_vector", query))
            .order_by("-search_rank")
        )
```

`search_type="websearch"` lets users type natural queries like `sprint planning Q3` or `"exact phrase" -excluded`.

### Tier 1 Limitations

- No `setweight()` — Postgres considers it mutable in generated columns
- No cross-table references — only columns on the same table
- No custom trigger logic

## Tier 2: Postgres Triggers with django-pgtrigger

```bash
pip install django-pgtrigger
```

### Step 1: Add SearchVectorField

```python
# apps/tasks/models.py
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField

class Task(TimeStampedModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    search_vector = SearchVectorField(null=True)

    class Meta:
        indexes = [
            GinIndex(fields=["search_vector"], name="idx_task_search"),
        ]
```

### Step 2: Same-Table Trigger with Weights

```python
import pgtrigger

class Task(TimeStampedModel):
    class Meta:
        triggers = [
            pgtrigger.Trigger(
                name="task_search_vector_update",
                when=pgtrigger.Before,
                operation=pgtrigger.Insert | pgtrigger.UpdateOf("title", "description"),
                func=pgtrigger.Func(
                    """
                    NEW.search_vector :=
                        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B');
                    RETURN NEW;
                    """
                ),
            ),
        ]
```

Weight A (title) ranks higher than weight B (description).

### Step 3: Cross-Table Trigger (Comments → Task)

Use raw SQL in a migration for cross-table triggers:

```python
# apps/tasks/migrations/0006_comment_search_trigger.py
migrations.RunSQL(
    sql="""
        CREATE OR REPLACE FUNCTION recompute_task_search_vector()
        RETURNS trigger AS $$
        BEGIN
            UPDATE tasks_task SET search_vector =
                setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
                setweight(
                    to_tsvector('english',
                        coalesce(
                            (SELECT string_agg(body, ' ')
                             FROM tasks_comment WHERE task_id = tasks_task.id),
                            ''
                        )
                    ), 'C'
                )
            WHERE id = COALESCE(NEW.task_id, OLD.task_id);
            RETURN NEW;
        END $$ LANGUAGE plpgsql;

        CREATE TRIGGER comment_updates_task_search
            AFTER INSERT OR UPDATE OF body OR DELETE
            ON tasks_comment
            FOR EACH ROW EXECUTE FUNCTION recompute_task_search_vector();
    """,
    reverse_sql="""
        DROP TRIGGER IF EXISTS comment_updates_task_search ON tasks_comment;
        DROP FUNCTION IF EXISTS recompute_task_search_vector();
    """,
)
```

### Step 4: Backfill Existing Data

Triggers only fire on future writes:

```python
migrations.RunSQL(
    sql="""
        UPDATE tasks_task SET search_vector =
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'B');
    """,
    reverse_sql=migrations.RunSQL.noop,
)
```

### Step 5: Query with Ranking

```python
class TaskQuerySet(models.QuerySet):
    def search(self, query_text):
        if not query_text:
            return self.none()
        query = SearchQuery(query_text, config="english", search_type="websearch")
        return (
            self.filter(search_vector=query)
            .annotate(search_rank=SearchRank("search_vector", query))
            .order_by("-search_rank")
        )
```

## SearchHeadline — Highlighting Matches

```python
from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank

results = (
    Task.objects.for_user(request.user)
    .filter(search_vector=query)
    .annotate(
        search_rank=SearchRank("search_vector", query),
        headline=SearchHeadline(
            "description", query,
            config="english",
            start_sel="<mark>", stop_sel="</mark>",
            max_words=35, min_words=15,
        ),
    )
    .order_by("-search_rank")[:25]
)
```

Render with `{{ task.headline|safe }}`.

## Cross-Model Search

Combine results from different models in a view:

```python
def global_search(request):
    query = request.GET.get("q", "").strip()
    tasks = Task.objects.for_user(request.user).search(query)[:20]
    plans = Plan.objects.for_user(request.user).search(query)[:10]
    # Merge and sort by rank
```

## Managing Triggers

```bash
python manage.py pgtrigger ls        # list all triggers
python manage.py pgtrigger install   # reinstall after manual DB changes
python manage.py pgtrigger disable tasks.Task:task_search_vector_update
python manage.py pgtrigger enable tasks.Task:task_search_vector_update
```

For bulk imports, skip triggers and backfill once:

```python
with pgtrigger.ignore("tasks.Task:task_search_vector_update"):
    Task.objects.bulk_create(large_list_of_tasks)
# Then backfill with raw SQL
```

## When to Use Elasticsearch Instead

Stay with Postgres unless you need: fuzzy matching / typo tolerance, faceted search with counts, cross-database search, or billion-document scale.
