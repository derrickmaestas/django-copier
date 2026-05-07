# Chapter 17 — Performance & Query Optimization

## Goal

By the end of this chapter you'll have:

- **Exact `assertNumQueries(N)` regression tests** on every hot path: kanban board, plan list, task list (HTML + API), task detail, search (HTML + API), notification list (HTML + API)
- A non-trivial seed dataset in each test so a hidden N+1 has somewhere to surface
- The one N+1 we found in the audit fixed (`task.assignees` walking unprefetched in `TaskDetailView`)
- An **index audit** confirming every WHERE/JOIN column on the hot paths uses a btree or GIN index — and a written record of the few redundant indexes worth pruning later

The big themes: **constant query budget, regardless of dataset size**; **hard-cap with exact counts so accidental drops are flagged too**; and **index discipline through audit, not through guessing**.

---

## Why exact counts (and not `<= N` ceilings)

The `django_assert_num_queries(N)` fixture, like Django's `assertNumQueries`, checks for an exact match. You'll be tempted to write `<= N` so a future optimization doesn't break the test. Don't.

The test pins what the code does *today*. Two failure modes:

- **Count goes up** — a regression. Most often a `.count()` or `.exists()` on a non-prefetched relation, or a new template loop that walks an unprefetched FK. Read the error, find the cause, fix.
- **Count goes down** — equally interesting. Either a real optimization (great — bake the new number into the test in the same commit, with a message explaining why) or an accidental drop because a feature was silently removed (a prefetch yields zero rows because the wrong relation is being queried; a serializer field was dropped). The test forces you to prove which.

A `<= N` test only catches half of these. Exact counts force a conversation.

---

## The seeded dataset matters

A perf test on a single bucket with a single task and a single assignee runs the same number of queries as one with twenty buckets, hundreds of tasks, and many assignees — *if* the prefetch chain is right. **Iff**. Test against a single row and an N+1 is invisible. The prefetch could be missing entirely; with one row there's nothing for it to do anyway.

Every test in this chapter seeds a dataset with multiplicity:

```python
@pytest.fixture
def member_with_full_plan(client, django_assert_num_queries):
    user = UserFactory()
    user.set_password("pw")
    user.save()
    team = TeamFactory()
    MembershipFactory(team=team, user=user)
    plan = PlanFactory(team=team)

    other_users = [UserFactory() for _ in range(3)]
    for bucket_pos in range(3):
        bucket = BucketFactory(plan=plan, position=bucket_pos)
        for _ in range(5):
            task = TaskFactory(bucket=bucket)
            for assignee in other_users:
                AssignmentFactory(task=task, user=assignee)
            for item_pos in range(2):
                ChecklistItemFactory(task=task, position=item_pos)
    ...
```

Three buckets × five tasks × three assignees × two checklist items. That's enough cross-product that the difference between "one query" and "one per row" is unambiguous.

The "doubling" test makes this explicit:

```python
def test_kanban_query_count_unchanged_when_dataset_grows(
    self, member_with_full_plan
):
    """Doubling the dataset does NOT increase the query count — the canonical
    N+1 detector. If this fails the prefetch chain has a hole somewhere."""
    client, plan, django_assert_num_queries = member_with_full_plan
    for bucket in plan.buckets.all():
        for _ in range(5):
            TaskFactory(bucket=bucket)

    with django_assert_num_queries(5):
        response = client.get(f"/plans/{plan.pk}/")
    assert response.status_code == 200
```

Same data shape, twice the rows, *same* query count. That's the test that protects every assumption the view makes about prefetching.

---

## What the budgets actually are

After fixes, every hot path runs at constant query count over the dataset. The number you compare against in the test is the *exact* count for the path under that fixture's seed:

| Path | Test | Queries | What they are |
|---|---|---|---|
| Kanban board (`/plans/<id>/`) | `apps/plans/.../test_performance.py` | 5 | session, current user, plan SELECT (with for_user JOIN), buckets prefetch, tasks prefetch |
| Plan list (`/plans/`) | same | 3 | session, current user, plans SELECT with `with_task_counts()` annotations folded in |
| Task list API (`/api/v1/tasks/`) | `apps/tasks/.../test_performance.py` | 3 | pagination COUNT, the SELECT (with `select_related("bucket","created_by")`), assignees prefetch |
| Task detail (`/tasks/<id>/`) | same | 7 | session, user, task SELECT, four prefetches (checklist items, assignees, comments-with-author, plus the for_user team JOIN folded into the SELECT) |
| Search HTML (`/search/?q=…`) | `apps/core/.../test_performance.py` | 4 | session, user, Plan FTS, Task FTS |
| Search API (`/api/v1/search/`) | same | 2 | Plan FTS + Task FTS — `force_authenticate` skips session/user lookups |
| Notification list (`/notifications/`) | `apps/notifications/.../test_performance.py` | 4 | session, user, pagination COUNT, SELECT with actor JOIN |
| Notification list API | same | 2 | pagination COUNT + SELECT with actor + target_content_type JOINs |

A few patterns you can read off this table:

1. **`APIClient.force_authenticate` skips two queries** (session + user) compared to `client.force_login`. JSON-side budgets are smaller for that reason; don't compare them apples-to-apples with HTML-side counts.
2. **DRF list endpoints cost two queries minimum** — the pagination COUNT and the SELECT itself. There's no way down from there without disabling pagination.
3. **`select_related` rolls into the same SELECT**; it doesn't add queries. `prefetch_related` always adds one query per relation. That's why the kanban board (two prefetches) costs more queries than the plan list (zero prefetches), even though the kanban renders far less paginated data.

---

## The one N+1 the audit caught

`TaskDetailView` was prefetching `checklist_items` and `comments` but *not* `assignees`. The `task_detail.html` template walks `task.assignees.all` to render the assignee chip list (and decide whether to show the empty-state line). Without a prefetch that's an extra query per page load — small in isolation, but the kind of thing that quietly slows a busy detail page.

Fixed by adding `"assignees"` to the prefetch list:

```python
class TaskDetailView(TaskScopedQuerysetMixin, DetailView):
    def get_queryset(self):
        return (
            super().get_queryset()
            .prefetch_related(
                "checklist_items",
                "assignees",                   # <- added
                Prefetch(
                    "comments",
                    queryset=Comment.objects.select_related("created_by"),
                ),
            )
        )
```

The test that would have failed if this regressed — and that did fail before the fix — is the dataset-doubling test on `/tasks/<id>/`: `with django_assert_num_queries(7)`. Without the prefetch the count crept up by exactly one per page load.

---

## Index audit

Each query goes through `WHERE` and `JOIN` columns; each of those should hit an index. Walking the hot paths and matching against the schema:

| Query | Column(s) | Index |
|---|---|---|
| `Plan.objects.for_user(user)` | `team__memberships__user` | `accounts_membership.user_id` (Django FK auto-index) |
| `Plan.objects.with_task_counts()` | reverse FK to Bucket → Task | `idx_bucket_plan_pos`, `idx_task_bucket_created` |
| `Plan.objects.search(q)` | `search_vector` | `idx_plan_search_vector` (GIN) |
| `Bucket.objects.filter(plan=…).order_by("position")` | `(plan_id, position)` | `idx_bucket_plan_pos` |
| `Task.objects.for_user(user)` | `bucket__plan__team__memberships__user` | every link is indexed |
| `Task.objects.filter(bucket=…)` | `bucket_id` | `idx_task_bucket_created` |
| `Task.objects.overdue()` | `(due_date, progress)` | `idx_task_due_date` + `idx_task_incomplete` partial |
| `Task.objects.search(q)` | `search_vector` | `idx_task_search_vector` (GIN) |
| `Notification.objects.for_user(user)` | `recipient_id` | `idx_notif_recipient_created` |
| `Notification.objects.unread()` | `recipient_id, read_at IS NULL` | `idx_notif_unread` partial |
| `Comment.objects.filter(task=…).order_by("created_at")` | `(task_id, created_at)` | `idx_comment_task_created` |

Every hot-path lookup hits an index. The data-layer chapters (6, 7, 14) added these as we built features; a clean audit at this point validates that work.

### Redundant indexes (cosmetic)

- `tasks_checklistitem.position` — `position`-only btree alongside the more useful `(task_id, position)` composite. Postgres won't pick the single-column one for our queries.
- `tasks_checklistitem.task_id` — Django's auto-FK index, redundant with `idx_checklist_task_pos` whose first column is `task_id`.

These don't slow anything down meaningfully (a few extra inserts per row, a kilobyte each). They're noted here so a future cleanup PR knows where to look; we're not adding the migration in this chapter.

---

## Pagination cap on the kanban

The kanban board renders every task in every bucket — no slicing. For Planner-scale plans (under ~500 tasks) that's fine; the prefetch chain keeps query count constant, and the per-task render is cheap.

The tipping point is the *template* render, not the database: HTML for hundreds of tasks gets large, and the resulting page weight starts hurting time-to-interactive. When you see kanban response times creeping past ~500 ms for boards over ~500 tasks, the right move is paginating buckets — render the first 50 task cards per column with a "show 50 more" affordance that triggers an HTMX append.

We're not adding that yet because no real plan in the dataset hits the limit. The cap is the *number to watch*; the implementation is the same HTMX append pattern from Chapter 11's checklist work.

---

## Working with `django-debug-toolbar` in dev

Inside the running container, the toolbar's SQL panel shows every query a request issues, with the call stack and the time spent. When you're hunting an N+1:

1. Open the toolbar's **SQL** panel.
2. Reload the page; note the query count and the total ms.
3. **Look for repeated similar queries** — a stack of `SELECT … WHERE id = N` is the canonical N+1 footprint.
4. Trace the call stack of one of them to the template or view line that triggered it.
5. Add the missing relation to `prefetch_related` (or use `Prefetch()` if the relation needs a custom queryset).

The perf tests in this chapter codify the *post-fix* state. The toolbar is what you use to find the *pre-fix* state.

---

## What we didn't build

- **View-level caching.** Per-user kanban response cached in Redis for N seconds is the next lever. We deferred it because cache *invalidation* is its own problem (a task move, a comment add, a checklist toggle all need to bust the right key) and that machinery is bigger than the perf win warrants today.
- **Pagination on the kanban.** Documented above as the tipping point.
- **Query-level metrics in production.** A separate exporter to Prometheus or DataDog that tracks `db.queries.count` per view. Operational, not architectural; lives in Chapter 18.

---

## Suggested commit message

```
add Chapter 17 — performance & query optimization

* apps/plans/tests/test_performance.py: hard-cap kanban board (5 q),
  plan list (3 q), and the dataset-doubling N+1 detector
* apps/tasks/tests/test_performance.py: hard-cap /api/v1/tasks/ (3 q)
  and /tasks/<id>/ (7 q); both stay constant when the dataset doubles
* apps/notifications/tests/test_performance.py: hard-cap /notifications/
  (4 q) and /api/v1/notifications/ (2 q)
* apps/core/tests/test_performance.py: hard-cap /search/ (4 q for an
  active query, 2 q when q is empty) and /api/v1/search/ (2 q)
* apps/tasks/views.py: add `assignees` to TaskDetailView's
  prefetch_related — the template walks `task.assignees.all` to render
  the chip list, which without the prefetch was an extra query per
  detail page load
* docs/tutorial/17-performance.md
```

---

## Where this lands us

Phase 5 has two more chapters: **Chapter 18 — Production Deployment** finalizes the `compose.prod.yaml`, gunicorn, whitenoise, Sentry, and structlog wiring, and turns the security and performance work we've done into a reproducible deploy. After that, the tutorial is done.
