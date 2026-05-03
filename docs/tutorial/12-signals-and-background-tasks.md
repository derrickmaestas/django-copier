# Chapter 12 — Signals & Background Tasks

## Goal

By the end of this chapter you'll have:

- Two **`django.tasks` background functions** in `apps/notifications/tasks.py` that create in-app notifications: one for assignments, one for comments
- A **`post_save` signal** on `Comment` that fans every new comment out to the task's watchers (assignees + creator), suppressing self-notifications
- A **`pre_save` invariant signal** on `Task` that stamps `completed_at` whenever progress hits 100%, regardless of how the task was saved
- A **view-level enqueue** for assignment notifications, where the actor is `request.user` — demonstrating when *not* to use a signal
- Tests that override the task backend to `ImmediateBackend` per-test, so we exercise the signal → enqueue → execute → DB row pipeline end-to-end

The big themes of this chapter are *when to reach for a signal* (and when not to), and *how Django 6's built-in `django.tasks` framework replaces the older third-party stack* (Celery, RQ, dramatiq, django-q).

---

## Why Signals — and Why Not

Signals are Django's pub-sub primitive. Models (and other parts of the framework) emit named events; receivers listen for them and react. They're powerful, and they're *over-used*. Before reaching for a signal, ask:

> Could I do this with a method on the model, called from the place that triggered the event?

If yes, do that. A method is easier to reason about, easier to test, easier to grep for. Signals are spooky-action-at-a-distance — code in `apps/foo` runs because of an event in `apps/bar`, with no direct call site. That's exactly when bugs become hard to track.

The cases where a signal genuinely earns its keep:

1. **The trigger and the response live in different apps**, and you don't want them coupled at the call site. (Today: `apps.notifications` reacts to `apps.tasks`. Tomorrow: an analytics app, a webhook app, a search-index app — each can subscribe without `apps.tasks` knowing they exist.)
2. **The trigger has many call sites you don't control**, and you need invariant enforcement no matter who saves the model. (The admin, the API, raw `task.save()` from a management command — all of those bypass your fat-model methods.)
3. **You can derive everything you need from the model instance itself.** Signals don't have access to `request.user`, the current locale, the active database transaction, or any other request-scoped context. If your reaction needs that context, the *view* should call the function directly.

We use rule #1 for the `Comment.post_save` signal (cross-app reaction with the actor on the model). We use rule #2 for the `Task.pre_save` invariant. We use rule #3 to *avoid* a signal for assignment notifications — the view fires those because the actor (`request.user`) isn't on `Assignment`.

---

## Step 1: Why `django.tasks` Replaces Celery

For ten years, every Django job-queue tutorial started with "first install Celery, RabbitMQ or Redis, configure a worker, set up `celery.py`…" That stack is real engineering, but it's heavy for a small app and brings two competing dependency trees into your project.

Django 6 ships **`django.tasks`** in core. The mental model is the same as Celery — decorate a function so it can be enqueued, run a worker process to consume the queue — but the implementation is dramatically simpler:

| Concept | Celery | `django.tasks` |
|---|---|---|
| Decorator | `@shared_task` | `@task()` |
| Enqueue | `my_task.delay(args)` or `my_task.apply_async(...)` | `my_task.enqueue(args)` |
| Backend | RabbitMQ, Redis, SQS, … | In-memory (immediate), in-memory (dummy), Postgres (database) |
| Worker | `celery -A proj worker` | `manage.py db_worker` |
| Result store | Separate config | The same database row |

There's no broker. There's no JSON serializer choice. There's no second tool. The Postgres database you already have *is* the queue. Tasks are rows in a table; the worker is a Django management command that pulls and runs them.

This isn't right for *every* workload — Celery is still better when you need cross-language workers, exotic schedulers, or 100k jobs/sec. But for the 95% of Django apps that need "send the email after the request finishes," `django.tasks` is enough, and it's already in your tree.

### Three Backends, One Knob

| Environment | Backend | Behavior |
|---|---|---|
| Development | `ImmediateBackend` | Tasks run inline in the request, blocking it |
| Tests | `DummyBackend` | Tasks are captured but never executed — you assert that `.enqueue()` was called |
| Production | `DatabaseBackend` | Tasks become rows in a Postgres table; `manage.py db_worker` is a separate process that runs them |

Switching is one setting change per environment:

```python
# config/settings/base.py — dev default
TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.immediate.ImmediateBackend",
    }
}

# config/settings/test.py
TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.dummy.DummyBackend",
    }
}

# config/settings/production.py
TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.database.DatabaseBackend",
        "QUEUES": ["default", "notifications"],
    }
}
```

We already wired the dev/test settings in earlier chapters. The production block goes in alongside the gunicorn config in Chapter 18.

### The `django_task` Import Alias

Our `apps.tasks` Django app has a name collision with `django.tasks`. Importing `from django.tasks import task` and then writing `@task()` in a file inside `apps/tasks/` becomes confusing fast — the reader can't tell at a glance whether `task` refers to the framework decorator or the model.

The convention from the project's `CLAUDE.md`:

```python
from django.tasks import task as django_task
```

Now `@django_task()` is unambiguous, and `from .models import Task` reads naturally next to it. Tiny rule, big payoff in readability over hundreds of files.

---

## Step 2: Two Background Tasks

Both tasks live in `apps/notifications/tasks.py`. Each one accepts **primitive ids only** — `int` arguments, never model instances. That's a hard rule for queued jobs:

- A task may run minutes or hours after enqueueing — by then, the model state could have changed.
- A task body needs to be serializable. Most backends pickle or JSON-encode arguments, and large model instances drag related objects with them.
- Tests stay simple: pass an integer, not a fixture.

```python
# apps/notifications/tasks.py
from django.contrib.contenttypes.models import ContentType
from django.tasks import task as django_task

from apps.tasks.models import Comment, Task

from .models import Notification


@django_task()
def send_assignment_notification(
    task_id: int,
    assignee_id: int,
    actor_id: int | None = None,
) -> None:
    """Create an in-app notification for a newly assigned user.

    No-op when the actor and the assignee are the same user — assigning
    yourself shouldn't notify yourself.
    """
    if actor_id is not None and actor_id == assignee_id:
        return
    task = Task.objects.filter(pk=task_id).first()
    if task is None:
        return
    Notification.objects.create(
        recipient_id=assignee_id,
        actor_id=actor_id,
        verb=Notification.Verb.ASSIGNED,
        target_content_type=ContentType.objects.get_for_model(Task),
        target_object_id=task.pk,
        description=f'assigned you to "{task.title}"',
    )
```

Two patterns to internalize:

- **`Model.objects.filter(pk=...).first()`**, *not* `Model.objects.get(pk=...)`. By the time the task runs, the row may have been deleted. We don't want a `DoesNotExist` exception to retry the task forever — we want to silently no-op. (For tasks where missing data *is* an error, raise explicitly. Here the user could plausibly delete the task before the worker picks up the notification.)
- **The actor-equals-recipient short-circuit at the top.** Checking it before any database work means you don't pay the cost of a query when the answer is "do nothing."

The comment task is structurally similar but does fan-out:

```python
@django_task()
def send_comment_notification(comment_id: int) -> None:
    """Notify everyone watching a task when a new comment is posted.

    "Watching" means the task's assignees plus its creator. The commenter
    is removed from the recipient set so people don't get notified about
    their own comments.
    """
    comment = (
        Comment.objects
        .filter(pk=comment_id)
        .select_related("task")
        .first()
    )
    if comment is None:
        return

    task = comment.task
    actor_id = comment.created_by_id

    recipient_ids = set(task.assignees.values_list("pk", flat=True))
    if task.created_by_id is not None:
        recipient_ids.add(task.created_by_id)
    recipient_ids.discard(actor_id)
    if not recipient_ids:
        return

    target_ct = ContentType.objects.get_for_model(Task)
    description = f'commented on "{task.title}"'
    Notification.objects.bulk_create(
        [
            Notification(
                recipient_id=rid,
                actor_id=actor_id,
                verb=Notification.Verb.COMMENTED,
                target_content_type=target_ct,
                target_object_id=task.pk,
                description=description,
            )
            for rid in recipient_ids
        ]
    )
```

A few decisions worth highlighting:

- **`set` for the recipient list**, not a list. Assignees and creator can overlap; using a set deduplicates for free, and `.discard(actor_id)` is `O(1)`.
- **`bulk_create` instead of a loop**. A task with five watchers should not result in five round-trips to the database. `bulk_create` issues one INSERT.
- **`select_related("task")`** on the comment fetch. We need `comment.task.title` and `comment.task.created_by_id` — without `select_related`, that's an extra query for the FK, and another for the assignees through M2M. We follow up with `task.assignees.values_list("pk", flat=True)` which issues exactly one more query. Total: two queries per task execution.

Note we do *not* `select_related("created_by")`. We only need `comment.created_by_id`, which is already on the row — no extra query.

---

## Step 3: The Comment Signal

The signal itself is trivial. All the logic is in the task; the signal just kicks it off:

```python
# apps/tasks/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.notifications.tasks import send_comment_notification

from .models import Comment, Task


@receiver(post_save, sender=Comment)
def comment_post_save(sender, instance, created, **kwargs):
    """Fan a new comment out to everyone watching the task."""
    if not created:
        return
    send_comment_notification.enqueue(instance.pk)
```

Two principles in five lines of body:

- **Guard on `created`.** `post_save` fires for both inserts *and* updates — the `created` flag tells you which. Editing an existing comment shouldn't re-notify everyone.
- **Pass an id, not the instance.** Same rule as the task itself: `instance.pk` is a safe primitive; the model instance is not.

The fan-out logic — *who* gets notified, dedup, self-suppression — lives inside the task, not in the signal. The signal stays a one-liner and the task body is the unit of testable behavior.

---

## Step 4: The `pre_save` Invariant Signal

The Task model already has a `mark_complete()` helper that sets `progress` and stamps `completed_at`. So why do we need a signal?

Because `mark_complete()` is just one path. Three others bypass it entirely:

1. The Django admin lets you edit `progress` directly and click Save.
2. The DRF API (Chapter 13) will accept partial updates: `PATCH /tasks/123 {"progress": 100}`.
3. A management command, fixture loader, or `python manage.py shell` hand-edit can call `task.save()` straight up.

In all three cases, `completed_at` would silently stay `None` for a task that's clearly been completed. That's the kind of subtle data-quality bug that survives for years undetected. A `pre_save` signal closes the gap:

```python
@receiver(pre_save, sender=Task)
def task_pre_save_set_completed_at(sender, instance, **kwargs):
    """Stamp ``completed_at`` whenever a task transitions to 100% progress.

    ``Task.mark_complete()`` already does this, but anything that bypasses
    that helper — direct ``task.save()``, the admin, the API, raw fixtures —
    would leave ``completed_at`` stale. Treat this signal as a safety net
    for the invariant rather than the primary code path.
    """
    if instance.progress != Task.Progress.COMPLETED:
        return

    if instance.pk is None:
        if instance.completed_at is None:
            instance.completed_at = timezone.now()
        return

    previous = (
        Task.objects.filter(pk=instance.pk)
        .only("progress", "completed_at")
        .first()
    )
    if previous is None:
        return
    transitioning = previous.progress != Task.Progress.COMPLETED
    if transitioning and instance.completed_at is None:
        instance.completed_at = timezone.now()
```

Three behaviours encoded in the body, in order of likelihood:

1. **Progress isn't 100% — early-return.** Most saves don't touch progress; we want to do as little work as possible in those cases. This is the hot path.
2. **Brand-new task created at 100%.** `instance.pk is None` means `pre_save` is firing for an INSERT. There's no previous row to compare against; if `completed_at` is unset, stamp it.
3. **Existing task transitioning to 100%.** We need to read the *previous* state from the database to detect the transition. `.only("progress", "completed_at")` keeps that lookup minimal — Django generates a `SELECT progress, completed_at FROM tasks_task WHERE id = %s` instead of pulling every column.

Why don't we just *always* set `completed_at` whenever progress is 100? Because re-saving an already-completed task (e.g., changing the description) would clobber the original timestamp. The "transition" check preserves the first-completion timestamp — which is what users actually want when they look at their history.

`pre_save` versus `post_save` matters here too: `pre_save` runs *before* the row is written, so we mutate `instance.completed_at` directly and the value goes into the same INSERT/UPDATE Django was about to issue. If we used `post_save` we'd need a second `instance.save()`, which would re-fire signals — a recipe for infinite loops.

---

## Step 5: Connecting Signals via `AppConfig.ready()`

Putting `@receiver` decorators in `signals.py` is necessary but not sufficient — Django won't import that module unless something else does. The convention is to import it from the app's `AppConfig.ready()` hook:

```python
# apps/tasks/apps.py
from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasks"
    label = "tasks"
    verbose_name = "Tasks & Assignments"

    def ready(self):
        from . import signals  # noqa: F401
```

Three rules around `ready()`:

1. **The import is local.** Django calls `ready()` after every app is loaded; doing the import inside the method avoids circular imports at module load time. (This is one of the very few legitimate uses of an inline import — and CLAUDE.md calls it out as such.)
2. **The `noqa: F401` is intentional.** ruff would otherwise flag the import as unused. The whole point is the side effect of importing the file (registering the `@receiver` decorators).
3. **Don't put signal receivers in `models.py`.** It's tempting because the signal is tightly coupled to a model, but it muddies the file's responsibility — `models.py` is for shape, `signals.py` is for reactions. Test fixtures and migrations import `models.py` constantly; you don't want them to drag signal side effects along.

---

## Step 6: When *Not* to Use a Signal — the Assignment Path

The third notification — a user being assigned to a task — could *also* be a signal on `Assignment.post_save`. We deliberately don't do that.

Why? Because the assignment notification needs the **actor** (the person who did the assigning), and `Assignment` doesn't have an `assigned_by` field. The actor is `request.user` at the moment the view runs. Signals don't have access to the request.

Solving this with a signal would require one of:

- Adding `assigned_by` to the model (a migration just for notifications — over-coupled).
- A thread-local middleware that stashes the current user (works but spooky; thread-locals leak in async contexts).
- A signal that just says "someone got assigned" with no actor (pretty useless).

The simplest, clearest fix is to skip the signal entirely and fire the notification from the view, where the actor is right there:

```python
# apps/tasks/views.py — task_assign
from apps.notifications.tasks import send_assignment_notification


@login_required
@require_POST
def task_assign(request, pk, user_pk):
    task = get_object_or_404(Task.objects.for_user(request.user), pk=pk)
    member = get_object_or_404(
        User.objects.filter(memberships__team=task.bucket.plan.team),
        pk=user_pk,
    )
    _, created = Assignment.objects.get_or_create(task=task, user=member)
    if created:
        send_assignment_notification.enqueue(
            task.pk, member.pk, request.user.pk
        )
    if _is_htmx(request):
        return render(request, "tasks/task_detail.html#assignees", {"task": task})
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task.pk}))
```

Two refinements over the previous version:

- **`get_or_create` returns a `created` flag.** Re-assigning the same user to the same task is idempotent — but should *not* send a duplicate notification. We only enqueue when the row was actually created.
- **`request.user.pk` is the actor.** We pass it as the third argument; `send_assignment_notification` short-circuits if it equals the assignee.

The teaching point here is more important than the implementation: **let the call site decide whether a signal or a direct call is appropriate.** Signals aren't free — they're a coupling tool with real costs. Use them when the trigger and the response are in different apps and the response can be derived from the model alone. Otherwise, just call the function.

---

## Step 7: Tests

We need two test files: one for the signal-driven path, one for the task itself.

### Testing Signals via the Immediate Backend

The default test backend is `DummyBackend` — it captures `.enqueue()` calls but doesn't execute them. That's fine for asserting that *enqueueing happened* but useless for asserting that the *task body did the right thing*.

For the signal tests, we want end-to-end assurance: signal fires → task enqueued → task body runs → notification rows exist. The simplest way to get that is a per-test fixture that swaps the backend to `ImmediateBackend`:

```python
# apps/tasks/tests/test_signals.py
import pytest

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification
from apps.tasks.models import Task
from apps.tasks.tests.factories import (
    AssignmentFactory,
    CommentFactory,
    TaskFactory,
)


@pytest.fixture
def immediate_tasks(settings):
    """Run enqueued django.tasks inline so we can assert on their effects."""
    settings.TASKS = {
        "default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"},
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("immediate_tasks")
class TestCommentSignal:
    """Posting a comment fans a notification out to the task's watchers."""

    def test_notifies_assignees_and_creator(self):
        creator = UserFactory()
        assignee_a = UserFactory()
        assignee_b = UserFactory()
        task = TaskFactory(created_by=creator)
        AssignmentFactory(task=task, user=assignee_a)
        AssignmentFactory(task=task, user=assignee_b)

        commenter = UserFactory()
        CommentFactory(task=task, created_by=commenter)

        recipients = set(
            Notification.objects.values_list("recipient_id", flat=True)
        )
        assert recipients == {creator.pk, assignee_a.pk, assignee_b.pk}
```

A few things going on here that deserve attention:

- **`pytest.mark.usefixtures("immediate_tasks")`** at the class level applies the fixture to every test inside without binding the fixture name to a parameter. Cleaner than putting `immediate_tasks` in every method signature.
- **`pytest-django` provides the `settings` fixture.** Mutating `settings.TASKS` inside the fixture is reverted after the test ends. We're not subclassing `SimpleTestCase`, so the `@override_settings` *decorator* doesn't work — pytest's `settings` fixture is the idiomatic equivalent.
- **The assertion targets `recipient_ids`**, not the count or the description text. Counts are easy to fake; the *who* is what we care about. By collapsing into a set we also verify deduplication — two assignees and one creator → exactly three notifications, no duplicates.

The other tests in the class cover the edge cases: commenter is also an assignee (themselves should be excluded), commenter is the only watcher (no notifications at all), and saving an existing comment (no signal fan-out). Each one exercises one branch of the task body.

### Testing the Invariant Signal

The `Task.pre_save` signal doesn't enqueue anything — it just mutates the instance about to be saved. No backend swap needed:

```python
@pytest.mark.django_db
class TestTaskCompletedAtInvariant:
    """A pre_save signal stamps completed_at when progress hits 100%."""

    def test_direct_save_to_complete_stamps_completed_at(self):
        task = TaskFactory(progress=Task.Progress.NOT_STARTED)

        task.progress = Task.Progress.COMPLETED
        task.save()
        task.refresh_from_db()

        assert task.completed_at is not None

    def test_repeated_save_at_100_keeps_original_timestamp(self):
        task = TaskFactory(progress=Task.Progress.NOT_STARTED)
        task.progress = Task.Progress.COMPLETED
        task.save()
        task.refresh_from_db()
        first_stamp = task.completed_at

        task.description = "edited"
        task.save()
        task.refresh_from_db()

        assert task.completed_at == first_stamp
```

The "repeated save" test is the one most likely to break in the future if someone refactors the signal carelessly — it pins down the "preserve original timestamp" behavior that distinguishes the right implementation from a naive `if progress == 100: completed_at = now()` one-liner.

### Testing the Task Directly

For the assignment task, we don't have a signal to trigger — we call `.enqueue()` directly. We still want the immediate backend so the body actually runs:

```python
# apps/notifications/tests/test_tasks.py
@pytest.mark.django_db
@pytest.mark.usefixtures("immediate_tasks")
class TestSendAssignmentNotification:
    def test_creates_notification_for_assignee(self):
        actor = UserFactory()
        assignee = UserFactory()
        task = TaskFactory()

        send_assignment_notification.enqueue(task.pk, assignee.pk, actor.pk)

        notif = Notification.objects.get()
        assert notif.recipient_id == assignee.pk
        assert notif.actor_id == actor.pk
        assert notif.verb == Notification.Verb.ASSIGNED
        assert notif.target == task

    def test_skips_when_actor_assigns_themselves(self):
        user = UserFactory()
        task = TaskFactory()

        send_assignment_notification.enqueue(task.pk, user.pk, user.pk)

        assert Notification.objects.count() == 0
```

A subtle point: we always call `.enqueue()`, never the function directly. The `@django_task()` decorator turns the function into a `Task` wrapper object — calling it directly raises `TypeError: 'Task' object is not callable`. `.enqueue()` is the right entry point both in production and in tests. This forces tests to exercise the same path the application uses, which is exactly what you want.

---

## Step 8: Verify

```bash
docker compose exec web uv run python manage.py check
docker compose exec web uv run pytest
```

The full suite should be 130 passing. We added eight signal tests and four task tests on top of the 118 from earlier chapters.

In the browser, confirm the loop end-to-end:

1. Sign in as user `1`, then in another browser (or incognito) as user `2`.
2. As user `1`, open a task and click "+ Assign", then click user `2`.
3. As user `2`, navigate to `/notifications/` — there should be a fresh "1 assigned you to ..." entry.
4. As user `1`, post a comment on a task user `2` is also assigned to.
5. As user `2`, refresh `/notifications/` — another entry, now "1 commented on ...".
6. From the admin, edit any task's `progress` to `100` and save. Look at the row in the DB or the admin detail — `completed_at` is now set, even though we never called `mark_complete()`.

That last check is the proof the invariant signal earns its keep.

---

## What Each Pattern Cost Us

It's worth explicitly tallying the line count of each pattern as a reality check on the "signals are coupling" warning:

| Pattern | Lines added | Where |
|---|---|---|
| `send_assignment_notification` task body | ~17 | `apps/notifications/tasks.py` |
| `send_comment_notification` task body | ~28 | `apps/notifications/tasks.py` |
| `Comment.post_save` signal | 5 | `apps/tasks/signals.py` |
| `Task.pre_save` invariant | ~22 | `apps/tasks/signals.py` |
| Assignment view enqueue | 4 | `apps/tasks/views.py` |
| Apps.py wiring | 2 | `apps/tasks/apps.py` |

The signal bodies are thin because the *work* lives in the task functions. That's the right division of labor: signals are dispatchers, tasks are workers, and a future Chapter 13 (DRF API) and Chapter 14 (search index) will plug into the same task functions without changing a single signal.

---

## What We Didn't Build

- **Email delivery** for notifications. The `NotificationPreference` model already has `email_on_assignment` / `email_on_comment` toggles; once SMTP settings land in Chapter 18 we'll add an `email_on_*` task layer that fans out from the same enqueue points. Deferring it keeps this chapter focused on signals as a primitive.
- **Notification preferences enforcement.** Right now we always create the in-app notification, regardless of the user's preferences. That belongs in the task body: read `NotificationPreference` for the recipient, skip if disabled. Easy to bolt on; left as an exercise.
- **Real-time delivery.** Pushing notifications to a connected browser session via SSE or WebSockets is a Chapter 11.5 we deliberately deferred. The notifications are persisted; the user just has to refresh to see them.
- **Retry policy.** Production tasks may fail (e.g., the database is briefly down). `django.tasks` supports retries via `Task.retry()` and the backend-level `MAX_RETRIES` setting. We'll configure that alongside the production deployment in Chapter 18.

---

## Suggested Commit Message

```
add Chapter 12 — signals and background tasks

* apps/notifications/tasks.py: send_assignment_notification and
  send_comment_notification, decorated with @django_task() and accepting
  primitive ids only
* apps/tasks/signals.py: Comment.post_save fans new comments out to
  watchers; Task.pre_save stamps completed_at on transition to 100%
* apps/tasks/apps.py: ready() imports the signals module so receivers
  register at app load time
* apps/tasks/views.py: task_assign enqueues send_assignment_notification
  with request.user.pk as the actor — illustrates when not to use a signal
* Tests use a per-test ImmediateBackend fixture (settings.TASKS swap)
  to run enqueued tasks inline, asserting end-to-end on Notification rows
* docs/tutorial/12-signals-and-background-tasks.md
```
