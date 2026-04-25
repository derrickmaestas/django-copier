from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from apps.plans.models import Bucket

from .models import Task


class TaskScopedQuerysetMixin(LoginRequiredMixin):
    """Restrict tasks to those reachable through the user's team memberships."""

    def get_queryset(self):
        return Task.objects.filter(
            bucket__plan__team__memberships__user=self.request.user,
        ).distinct()


class TaskDetailView(TaskScopedQuerysetMixin, DetailView):
    model = Task
    template_name = "tasks/task_detail.html"
    context_object_name = "task"


class TaskCreateView(LoginRequiredMixin, CreateView):
    model = Task
    fields = ["title", "description", "priority", "due_date", "start_date"]
    template_name = "tasks/task_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.bucket = get_object_or_404(
            Bucket.objects.filter(plan__team__memberships__user=request.user),
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
    fields = ["title", "description", "priority", "progress", "due_date", "start_date"]
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
    task = get_object_or_404(
        Task.objects.filter(bucket__plan__team__memberships__user=request.user),
        pk=pk,
    )
    task.mark_complete()
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task.pk}))
