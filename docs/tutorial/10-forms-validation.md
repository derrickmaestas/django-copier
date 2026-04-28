# Chapter 10 — Forms & Validation

## Goal

By the end of this chapter you'll have:

- An explicit `forms.py` module in each app that needs user input — no more `fields = [...]` shortcut on the views
- Custom validators where they earn their keep: a `team`-scoping security check on `PlanForm`, a hex-color regex on `LabelForm`, a cross-field `start_date <= due_date` rule on `TaskForm`
- The CRUD surface that Chapter 9 left open: bucket create/edit/delete, label create/edit/delete, single-action endpoints for adding comments and toggling checklist items
- A clear philosophy of *where* validation should live — form vs. serializer vs. model — with a progressive teaching path that mirrors how validation evolves in real codebases

This is the chapter where the tutorial app starts feeling like an actual app. By the end, you can plan, organize, comment, and check items off — all from the browser.

---

## Why a Forms Layer

Chapter 9's views used the `fields = ["title", "description", ...]` shortcut on `CreateView` and `UpdateView`. Django builds a `ModelForm` on the fly from that list. It's a great shortcut for prototypes, but it has three growing-pain limitations that bite quickly:

1. **No place to put custom validation.** You can't override `clean()` or `clean_<field>()` without writing a real form class.
2. **No place to constrain field choices.** A `team` field rendered straight from the model exposes *every team* in the dropdown — including teams the requesting user has no relationship with. A user can pick (or just submit a `team_id`) for any team in the database. We need to scope the queryset to the current user's memberships, and there's no clean way to do that with the inline shortcut.
3. **Forms are a stable abstraction; views aren't.** A form is reusable across HTML, the API (Chapter 13), and any management commands. Views are HTML-specific. Putting validation on the form means the API gets it for free later.

So the rule we'll follow throughout the rest of the project: **any view that takes user input uses a form class declared in `apps/<app>/forms.py`.** No more inline `fields`.

---

## Step 1: The Pattern — `BucketForm`

We'll start with the simplest form because it sets the template for the rest. A `Bucket` belongs to a `Plan`. The user only edits the title; the plan is determined by the URL, and the position is auto-assigned.

```python
# apps/plans/forms.py
from django import forms

from apps.accounts.models import Team

from .models import Bucket, Plan


class BucketForm(forms.ModelForm):
    """Form for creating or editing a Bucket within a known Plan.

    The plan is supplied by the view (resolved from the URL), so only
    the title is exposed to the user. Position is auto-set on create.
    """

    class Meta:
        model = Bucket
        fields = ["title"]
```

That's the minimum. No `clean()` methods — you do *not* need to write `clean_title` to strip whitespace or reject empty titles. Django's `forms.CharField` already has `strip=True` (since 1.9) and `required=True` (always) by default. Writing `def clean_title(self): ...` to do those two things is dead code that duplicates the framework. We'll add custom `clean_*` methods only where they have something the framework doesn't.

The view that drives it:

```python
# apps/plans/views.py — BucketCreateView
class BucketCreateView(LoginRequiredMixin, CreateView):
    model = Bucket
    form_class = BucketForm
    template_name = "plans/bucket_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.plan = get_object_or_404(
            Plan.objects.for_user(request.user),
            pk=kwargs["plan_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.plan = self.plan
        form.instance.position = Bucket.objects.next_position(plan=self.plan)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("plans:plan-detail", kwargs={"pk": self.plan.pk})
```

Three patterns to internalize from this view — they recur across the rest of the chapter:

1. **Resolve the parent in `dispatch()`, not in `form_valid()`.** The bucket can't exist without a plan, and we want to 404 *before* rendering the form (not after the user fills it in and submits). `dispatch` runs on every method, so it covers both `GET` and `POST`.
2. **`Plan.objects.for_user(request.user)` is the gate.** Anyone logged in can hit this URL with any `plan_pk`. The `for_user` queryset filters to plans the user can see; `get_object_or_404` turns the empty queryset into a 404. No object-level permission check needed in the view.
3. **`Bucket.objects.next_position(plan=...)` lives on the queryset.** We'll get to that helper in [Step 6](#step-6-extracting-the-shared-utilities).

The update and delete views are simpler — they reuse a tiny mixin that scopes by membership:

```python
class BucketScopedQuerysetMixin(LoginRequiredMixin):
    """Restrict buckets to those reachable through the user's team memberships."""

    def get_queryset(self):
        return Bucket.objects.for_user(self.request.user)


class BucketUpdateView(BucketScopedQuerysetMixin, UpdateView):
    model = Bucket
    form_class = BucketForm
    template_name = "plans/bucket_form.html"

    def get_success_url(self):
        return reverse("plans:plan-detail", kwargs={"pk": self.object.plan_id})


class BucketDeleteView(BucketScopedQuerysetMixin, DeleteView):
    model = Bucket
    template_name = "plans/bucket_confirm_delete.html"

    def get_success_url(self):
        return reverse("plans:plan-detail", kwargs={"pk": self.object.plan_id})
```

The `Bucket.objects.for_user(user)` method is new; we added it as part of the queryset cleanup in Step 6 of this chapter.

URL patterns are nested under the plan for create, flat for the rest:

```python
# apps/plans/urls.py
path("<int:plan_pk>/buckets/create/", views.BucketCreateView.as_view(), name="bucket-create"),
path("buckets/<int:pk>/edit/", views.BucketUpdateView.as_view(), name="bucket-update"),
path("buckets/<int:pk>/delete/", views.BucketDeleteView.as_view(), name="bucket-delete"),
```

Why nested for create but not for edit/delete? Because create needs the parent in the URL — there's nothing to look up. Edit/delete operate on an existing bucket whose plan can be fetched from the bucket itself.

---

## Step 2: `PlanForm` — The Security Fix

`PlanForm` is the most security-significant form in the chapter. The Chapter 9 plan view used:

```python
fields = ["title", "description", "team", "visibility"]
```

That's a problem. The `team` field is rendered as a dropdown of every Team in the database. A user could submit a request with `team=42` for a team they have no relationship with, and Django would happily save the plan attached to that team. There's nothing in the model layer to prevent it — the FK only checks that team 42 *exists*, not that the user can use it.

The fix is to constrain the form's queryset to teams the user is a member of:

```python
# apps/plans/forms.py
class PlanForm(forms.ModelForm):
    """Form for creating or editing a Plan.

    The `team` queryset is restricted to teams the user is a member of —
    without this, anyone could submit an arbitrary `team_id` and have a
    plan attached to a team they don't belong to.
    """

    class Meta:
        model = Plan
        fields = ["title", "description", "team", "visibility"]

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = Team.objects.filter(memberships__user=user).distinct()
```

Two things worth dwelling on here.

### `user` as a required keyword-only argument

`def __init__(self, *args, user, **kwargs):` — `user` is keyword-only (no default). If the view forgets to pass it, Python raises `TypeError`. That's deliberate: a missing user means the security check silently disappears, and we'd rather fail loudly than render an unscoped form. The view is responsible for supplying it:

```python
class PlanCreateView(LoginRequiredMixin, CreateView):
    model = Plan
    form_class = PlanForm
    template_name = "plans/plan_form.html"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("plans:plan-detail", kwargs={"pk": self.object.pk})
```

`get_form_kwargs()` is the standard CBV hook for passing extra keyword arguments to the form's constructor. Spread the parent kwargs first, then add `user`.

### Why does setting `queryset` on the field alone enforce security?

Because `ModelForm`'s built-in field validation uses the queryset's `.get()` to resolve the submitted ID. If the user submits `team=42` and team 42 isn't in `self.fields["team"].queryset`, the form raises `ValidationError("Select a valid choice...")`. The submitted ID is *never* trusted — Django re-fetches it from the (already-scoped) queryset.

This is the standard Django security pattern for FK fields, and it's why we don't need a separate `clean_team()` check. The queryset constraint *is* the validation.

---

## Step 3: The Small Forms — Label, Checklist, Comment

The remaining domain models that take user input are `Label`, `ChecklistItem`, and `Comment`. None of them needs much:

```python
# apps/tasks/forms.py
import re

from django import forms

from .models import ChecklistItem, Comment, Label, Task

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class LabelForm(forms.ModelForm):
    """Form for creating or editing a Label within a known Plan."""

    class Meta:
        model = Label
        fields = ["name", "color"]

    def clean_color(self):
        color = self.cleaned_data["color"].strip()
        if not HEX_COLOR_RE.match(color):
            raise forms.ValidationError("Color must be a 6-digit hex code (e.g. #6B7280).")
        return color


class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ["title"]


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
```

`LabelForm.clean_color` is the only custom validator — it adds the regex check that the model's `CharField` doesn't enforce. Note we use `clean_color`, the per-field hook, *not* the all-fields `clean()`. The convention:

- **`clean_<field>(self)`** — validate one field. Has access to that field's value via `self.cleaned_data[<field>]`. Runs before `clean()`. Use this whenever the rule depends on only one field.
- **`clean(self)`** — validate across multiple fields. Has access to all of them via `self.cleaned_data`. Use this for cross-field rules like `start_date <= due_date`.

### Views: a CBV trio for Label, three FBVs for Checklist, one FBV for Comment

`Label` follows the same Bucket pattern (CreateView with `dispatch` resolving the plan, plus a scoped Update/Delete pair). It lives in `apps/tasks/views.py` because labels conceptually belong to the tasks domain — they're applied to tasks.

`ChecklistItem` and `Comment` are different. They're sub-resources on a Task with extremely small surfaces — add, toggle, delete for checklist items; add for comments. CBVs would be overkill. Each is a one-action FBV:

```python
# apps/tasks/views.py
@login_required
@require_POST
def checklist_item_add(request, task_pk):
    task = get_object_or_404(Task.objects.for_user(request.user), pk=task_pk)
    form = ChecklistItemForm(request.POST)
    if form.is_valid():
        form.instance.task = task
        form.instance.position = ChecklistItem.objects.next_position(task=task)
        form.save()
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task.pk}))


@login_required
@require_POST
def checklist_item_toggle(request, pk):
    item = get_object_or_404(ChecklistItem.objects.for_user(request.user), pk=pk)
    item.is_completed = not item.is_completed
    item.save(update_fields=["is_completed"])
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": item.task_id}))


@login_required
@require_POST
def checklist_item_delete(request, pk):
    item = get_object_or_404(ChecklistItem.objects.for_user(request.user), pk=pk)
    task_pk = item.task_id
    item.delete()
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task_pk}))


@login_required
@require_POST
def comment_add(request, task_pk):
    task = get_object_or_404(Task.objects.for_user(request.user), pk=task_pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        form.instance.task = task
        form.instance.created_by = request.user
        form.save()
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task.pk}))
```

Three things to notice:

1. **`@require_POST` is on every one.** These are state-changing endpoints. A `GET` to `/checklist/<pk>/toggle/` would be a CSRF nightmare — search-engine crawlers and link previews would happily check off your tasks. The decorator returns 405 for any non-POST.
2. **`form.is_valid()` silently no-ops on failure.** If the title is empty, we just redirect back to the detail page. That's fine for a one-line form — no confirmation roundtrip needed. (When the form gets richer in Chapter 11, we'll surface validation errors in the UI.)
3. **No edit/delete for comments.** This is a deliberate simplification — Microsoft Planner's behavior is "comments are append-only." If you want to retract one, you delete it administratively. We can add edit later if it's actually needed.

---

## Step 4: `TaskForm` — Cross-Field Validation

The task form is where we finally have a *real* multi-field rule. `start_date` and `due_date` are both optional, but if both are set, `start_date` must be on or before `due_date`:

```python
# apps/tasks/forms.py
class TaskForm(forms.ModelForm):
    """Form for creating or editing a Task.

    Past due dates are allowed — Microsoft Planner labels them "Late"
    rather than block creation, which matches how people actually log
    catch-up work.
    """

    class Meta:
        model = Task
        fields = ["title", "description", "priority", "progress", "due_date", "start_date"]

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        due = cleaned.get("due_date")
        if start and due and start > due:
            raise forms.ValidationError(
                {"start_date": "Start date must be on or before the due date."},
            )
        return cleaned


class TaskCreateForm(TaskForm):
    """Task form variant used by TaskCreateView — no `progress` field.

    Newly-created tasks always start at NOT_STARTED; exposing progress on
    the create form is a footgun.
    """

    class Meta(TaskForm.Meta):
        fields = ["title", "description", "priority", "due_date", "start_date"]
```

Three design decisions:

### Past due dates are *allowed*

A common over-zealous validation is "due_date must be in the future." It feels safe but it's wrong: people legitimately log catch-up work, backfill historical records, or set due dates for already-completed tasks. Microsoft Planner's behavior is to *allow* the past date and label the task "Late." We do the same.

The general principle: **structural validation only.** Enforce relationships between fields (start ≤ due) and structural shape (hex color is six chars). Don't enforce business rules like "due dates must be soon" — those almost always have legitimate exceptions.

### Use a dict for `ValidationError` to attach the error to a specific field

`raise forms.ValidationError({"start_date": "..."})` attaches the error to the `start_date` field, so it appears next to the field in the rendered form. Compare to `raise forms.ValidationError("...")`, which would attach the error to `__all__` (the form's non-field errors), and the user would have to hunt for it.

### `TaskCreateForm` removes `progress`

A user creating a brand-new task shouldn't be able to set progress to "Completed" out of the gate — it's a footgun. The create-only variant inherits everything from `TaskForm` (including the `clean()` rule) but overrides `Meta.fields` to drop the column. The update form keeps it because legitimate workflows need to change it.

---

## Step 5: Where Does Validation Belong?

This is the deepest question in the chapter, and Django's answer changes as your project grows. The short version:

> User input from an HTML form? Validate on the form.
> User input from an API request? Validate on the serializer.
> Invariants that should hold no matter who's writing? Validate on the model.

That sounds tidy. In practice it gets messier — you often have the *same rule* (`start_date <= due_date`) that should apply to *both* the form and the serializer. So where does the rule live?

### The progressive answer

Right now, in Chapter 10, there's only one input layer: the HTML form. The rule lives in `TaskForm.clean()`. Done. No abstraction needed.

In Chapter 13 we'll add a REST API. `TaskSerializer.validate()` will need the same rule. At that point, you'll have *two* copies — one on the form, one on the serializer. That's the moment where the duplication becomes *visible*, not hypothetical, and you can make a real choice:

- **Option A: Leave the duplication.** Two copies, kept in sync manually. Cheap to maintain when the rules are simple, has the virtue that errors come from the input layer that produced them (the form's error format vs. the serializer's are slightly different).
- **Option B: Move the rule to `Task.clean()` and call `instance.full_clean()` from both.** DRY, single source of truth, but you pay a coupling cost: the form (or serializer) now has to handle errors raised from the model layer.

We'll walk through both options when Chapter 13 ships, with the duplication staring everyone in the face. **Pre-introducing `full_clean()` here would be teaching the abstraction before showing the problem it solves.** That's not how seasoned engineers learn — you reach for `full_clean()` the *second* time you write the same `clean()` body, not the first.

This is also why we don't put `start_date <= due_date` on the model right now. There's no second writer (no serializer, no admin custom form, no management command) to justify lifting it. When there is, we'll lift it deliberately and explain the trade-offs.

### A quick rule of thumb

Use this when the question comes up:

| Situation | Where it goes |
|---|---|
| Field-shape rule (e.g., regex on a color string) | Form `clean_<field>()` for now, model field `validators=[...]` once it's needed in 2+ places |
| Cross-field rule (e.g., `start ≤ due`) | Form `clean()` for now, model `clean()` once 2+ writers exist |
| Permission scoping (e.g., team must be one user belongs to) | Form (constrain queryset) — almost never on the model, since the user identity isn't a model concern |
| Database invariant (uniqueness, NOT NULL, FK existence) | Model `Meta.constraints` — these are *not* form-level concerns |

---

## Step 6: Extracting the Shared Utilities

Two patterns showed up in this chapter that called for refactoring as soon as we noticed them.

### `for_user(user)` queryset methods

We needed to scope buckets, labels, checklist items, and comments to the requesting user's team memberships. Without a queryset method, every view (and every FBV) had to write the same join chain inline. So we added a `for_user()` to each model's queryset:

```python
# apps/plans/querysets.py
class BucketQuerySet(OrderedQuerySet):
    def for_user(self, user):
        """Return buckets in plans visible to this user through team membership."""
        return self.filter(plan__team__memberships__user=user).distinct()


# apps/tasks/querysets.py
class TaskQuerySet(models.QuerySet):
    def for_user(self, user):
        """Return tasks in plans visible to this user through team membership."""
        return self.filter(bucket__plan__team__memberships__user=user).distinct()

    def assigned_to(self, user):
        """Return tasks the user is explicitly assigned to."""
        return self.filter(assignments__user=user).distinct()
```

`Plan.objects.for_user(user)` was already there from Chapter 6. We followed the same naming for buckets, labels, checklist items, and comments.

### Wait — what was `TaskQuerySet.for_user` before?

Chapter 6 introduced `TaskQuerySet.for_user(user)` with the *narrower* meaning: "tasks the user is assigned to via the Assignment through-model." That's a different concept from membership scoping. With Chapter 10's needs, we now have two distinct queries on Tasks:

- **Membership-scoped** — every task in every plan the user can see
- **Assignment-scoped** — only tasks where the user has an explicit Assignment record

We **renamed** the old method to `assigned_to(user)`, freeing up `for_user(user)` to mean the same membership-scoped concept that `Plan.objects.for_user(user)` already meant. Naming consistency across the project matters: when you read `<Model>.objects.for_user(user)`, the answer should always be "the rows visible to this user through team membership."

If you've already published the Chapter 6 tutorial somewhere, this is a one-line breaking change — update the queryset method name and the test. We've patched the Chapter 6 tutorial in this repo to match.

### `OrderedQuerySet.next_position()`

Both `Bucket` and `ChecklistItem` inherit from `OrderedModel` — they have a `position` field for drag-and-drop ordering. When creating a new instance, the natural position is "after the last existing one." That's the same query for both:

```python
# apps/core/querysets.py
from django.db import models
from django.db.models import Max


class OrderedQuerySet(models.QuerySet):
    """QuerySet base for OrderedModel subclasses.

    Adds a `next_position(**filters)` helper that returns the next
    available position within a scope (e.g. all buckets in a plan, all
    checklist items on a task).
    """

    def next_position(self, **filters) -> int:
        last = self.filter(**filters).aggregate(Max("position"))["position__max"]
        return (last or 0) + 1
```

`BucketQuerySet(OrderedQuerySet)` and `ChecklistItemQuerySet(OrderedQuerySet)` both get the helper for free. The view uses it as:

```python
form.instance.position = Bucket.objects.next_position(plan=self.plan)
# or
form.instance.position = ChecklistItem.objects.next_position(task=task)
```

There is a real race condition lurking here — two simultaneous creates can both compute the same `next_position` and one will fail the unique constraint. The solution is a `SELECT FOR UPDATE` block or a database trigger; we'll address it in Chapter 17 (Performance). For the tutorial app's scale, it's not yet a problem.

### Why we waited

We could have built these abstractions up front, before writing any of the views. We didn't, deliberately:

1. **YAGNI on day one.** We'd have written `next_position()` for `Bucket` and never reused it if we hadn't gotten to checklist items.
2. **The right shape was unclear.** `next_position(plan=...)` vs `next_position()` (using `self` somehow) — only the second instance of the pattern made the right signature obvious.
3. **Reading the duplication is the lesson.** A reader who watches the duplication appear and *then* the refactor learns more than a reader handed the abstraction with no context.

This is the rhythm of real engineering: write naïve code, notice the duplication after the second instance, factor it out. Resist the urge to abstract preemptively.

---

## Step 7: Tests

Form tests go in a new file per app: `apps/<app>/tests/test_forms.py`. Same conventions as model and view tests — `Test*` classes, `test_*` methods, factory_boy for setup.

What to test:

- **Custom `clean()` and `clean_<field>()` logic.** That's where we wrote real code; that's where bugs hide.
- **Permission scoping that's only enforced at the form layer.** `PlanForm`'s team-queryset constraint, for example.

What to skip:

- **Whitespace stripping.** `forms.CharField.strip=True` is a Django default; testing it is testing Django.
- **Required-field rejection.** Same — `required=True` is a default.
- **Field types.** Same.

A representative slice from `apps/plans/tests/test_forms.py`:

```python
import pytest

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.plans.forms import PlanForm
from apps.plans.models import Plan


@pytest.mark.django_db
class TestPlanForm:
    def test_team_choices_limited_to_user_memberships(self):
        user = UserFactory()
        my_team = TeamFactory()
        MembershipFactory(team=my_team, user=user)
        TeamFactory()  # team the user does NOT belong to

        form = PlanForm(user=user)

        assert list(form.fields["team"].queryset) == [my_team]

    def test_cannot_submit_team_user_is_not_in(self):
        user = UserFactory()
        outside_team = TeamFactory()  # user is not a member

        form = PlanForm(
            data={
                "title": "Sneaky plan",
                "description": "",
                "team": outside_team.pk,
                "visibility": Plan.Visibility.PRIVATE,
            },
            user=user,
        )

        assert not form.is_valid()
        assert "team" in form.errors
```

The first test verifies the queryset is constrained at form-construction time. The second verifies that a hostile POST with an out-of-scope team is *rejected by validation*, not silently saved. Both tests exercise real custom code we wrote.

For `TaskForm`, the tests focus on the cross-field date rule:

```python
@pytest.mark.django_db
class TestTaskFormDateValidation:
    def _base_data(self, **overrides):
        data = {
            "title": "A task",
            "description": "",
            "priority": Task.Priority.MEDIUM,
            "progress": Task.Progress.NOT_STARTED,
            "due_date": "",
            "start_date": "",
        }
        data.update(overrides)
        return data

    def test_start_date_after_due_date_invalid(self):
        form = TaskForm(
            data=self._base_data(
                start_date=datetime.date(2026, 5, 10),
                due_date=datetime.date(2026, 5, 1),
            ),
        )
        assert not form.is_valid()
        assert "start_date" in form.errors

    def test_past_due_date_is_allowed(self):
        # Planner-style: backdating completed work is legitimate.
        form = TaskForm(data=self._base_data(due_date=datetime.date(2020, 1, 1)))
        assert form.is_valid(), form.errors
```

The second test is a *positive* test for an explicit policy decision — past due dates are allowed. If someone later adds an over-zealous "no past dates" rule, this test catches it.

---

## A Note on django-crispy-forms

The eagle-eyed reader will notice we're still using `{{ form.as_p }}` in the templates. That's deliberate. `django-crispy-forms` is a *rendering* library — it doesn't change form classes, validators, or the data flow we built in this chapter. It's purely about how the HTML comes out.

We'll bring it in during Chapter 11 (Templates & HTMX), which is where the rendering layer actually gets attention. Adding it now would mean explaining a rendering tool while we're still in the data-input chapter — splitting our focus for no reason.

---

## Verify

```bash
docker compose exec web uv run python manage.py check
docker compose exec web uv run pytest
```

Then poke around in the browser:

```
http://localhost:8000/plans/                                 → list, create a plan
http://localhost:8000/plans/<id>/                             → add buckets, tasks, labels
http://localhost:8000/tasks/<id>/                             → add checklist items, mark complete, comment
```

Try the security check yourself: log in as one user, note a plan ID, log out and log in as a *different* user with no shared teams, and visit `/plans/<that-id>/edit/`. You should get a clean 404, not a 500 or a successful render. Same for direct POSTs.

---

## What We Don't Test (Yet)

- **Form rendering.** `{{ form.as_p }}` produces HTML; that's Django's job. We'll have visual confirmation in the browser, and Chapter 11 will introduce hand-rolled templates that *can* be tested.
- **Race conditions on `next_position`.** Chapter 17 (Performance) addresses concurrent inserts on ordered models.
- **Comment edit/delete flows.** Out of scope — Planner-style append-only.
- **Assignment of users to tasks.** Deferred to Chapter 11, where the HTMX user-picker fits the UX better than a server-rendered dropdown of every team member.

---

## Recap

You added:

- An explicit `forms.py` in each app that takes input — `PlanForm`, `BucketForm`, `TaskForm`/`TaskCreateForm`, `LabelForm`, `ChecklistItemForm`, `CommentForm`
- A security fix: `PlanForm` constrains the team queryset to the user's memberships
- A cross-field validator: `TaskForm.clean()` enforces `start_date ≤ due_date`
- The CRUD that Chapter 9 left out: bucket and label CBVs, checklist and comment FBVs
- A `for_user(user)` queryset method on every model where membership scoping was needed (and a `assigned_to(user)` rename on `TaskQuerySet` to avoid semantic collision)
- A reusable `OrderedQuerySet.next_position(**filters)` helper for `OrderedModel` subclasses
- A focused set of form tests that exercise custom logic and skip framework defaults

The app is now functional in a meaningful way — you can plan, organize, and collaborate. The styling is still rough (Chapter 11's job).

---

## Suggested commit

```
add Chapter 10 — forms & validation

- Add explicit forms.py modules: PlanForm (team-queryset scoping
  fixes a real security hole), BucketForm, LabelForm, ChecklistItemForm,
  CommentForm, TaskForm/TaskCreateForm with start_date<=due_date.
- Build the missing CRUD: bucket and label CBVs (nested under plan),
  checklist add/toggle/delete FBVs, comment add FBV.
- Add for_user(user) queryset methods to Bucket/Label/ChecklistItem/
  Comment for membership-scoped access. Rename TaskQuerySet.for_user
  -> assigned_to (the old method was assignment-scoped, which conflicts
  with the membership-scoped meaning used elsewhere). Update Ch 6 tests
  and tutorial accordingly.
- Add OrderedQuerySet.next_position(**filters) in apps/core/querysets
  for OrderedModel subclasses; replace per-model next_*_position helpers.
- Form tests cover the team-queryset scope, the start/due date rule,
  hex-color regex; view tests cover the new CRUD permission scoping.
```
