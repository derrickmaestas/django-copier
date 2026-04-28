from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from apps.plans.models import Bucket, Plan

from .forms import ChecklistItemForm, CommentForm, LabelForm, TaskCreateForm, TaskForm
from .models import ChecklistItem, Comment, Label, Task


class TaskScopedQuerysetMixin(LoginRequiredMixin):
    """Restrict tasks to those reachable through the user's team memberships."""

    def get_queryset(self):
        return Task.objects.for_user(self.request.user).select_related("bucket")


class TaskDetailView(TaskScopedQuerysetMixin, DetailView):
    model = Task
    template_name = "tasks/task_detail.html"
    context_object_name = "task"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related(
                "checklist_items",
                Prefetch(
                    "comments",
                    queryset=Comment.objects.select_related("created_by"),
                ),
            )
        )


class TaskCreateView(LoginRequiredMixin, CreateView):
    model = Task
    form_class = TaskCreateForm
    template_name = "tasks/task_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.bucket = get_object_or_404(
            Bucket.objects.for_user(request.user),
            pk=kwargs["bucket_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.bucket = self.bucket
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("plans:plan-detail", kwargs={"pk": self.bucket.plan_id})


class TaskUpdateView(TaskScopedQuerysetMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = "tasks/task_form.html"

    def get_success_url(self):
        return reverse("tasks:task-detail", kwargs={"pk": self.object.pk})


class TaskDeleteView(TaskScopedQuerysetMixin, DeleteView):
    model = Task
    template_name = "tasks/task_confirm_delete.html"

    def get_success_url(self):
        return reverse("plans:plan-detail", kwargs={"pk": self.object.bucket.plan_id})


@login_required
@require_POST
def task_mark_complete(request, pk):
    task = get_object_or_404(Task.objects.for_user(request.user), pk=pk)
    task.mark_complete()
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task.pk}))


class LabelScopedQuerysetMixin(LoginRequiredMixin):
    """Restrict labels to those reachable through the user's team memberships."""

    def get_queryset(self):
        return Label.objects.for_user(self.request.user)


class LabelCreateView(LoginRequiredMixin, CreateView):
    model = Label
    form_class = LabelForm
    template_name = "tasks/label_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.plan = get_object_or_404(
            Plan.objects.for_user(request.user),
            pk=kwargs["plan_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.plan = self.plan
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("plans:plan-detail", kwargs={"pk": self.plan.pk})


class LabelUpdateView(LabelScopedQuerysetMixin, UpdateView):
    model = Label
    form_class = LabelForm
    template_name = "tasks/label_form.html"

    def get_success_url(self):
        return reverse("plans:plan-detail", kwargs={"pk": self.object.plan_id})


class LabelDeleteView(LabelScopedQuerysetMixin, DeleteView):
    model = Label
    template_name = "tasks/label_confirm_delete.html"

    def get_success_url(self):
        return reverse("plans:plan-detail", kwargs={"pk": self.object.plan_id})


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
