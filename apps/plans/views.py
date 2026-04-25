from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.tasks.models import Task

from .models import Bucket, Plan


class PlanListView(LoginRequiredMixin, ListView):
    model = Plan
    template_name = "plans/plan_list.html"
    context_object_name = "plans"

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user).with_task_counts()


class PlanDetailView(LoginRequiredMixin, DetailView):
    """Plan board — shows every bucket for the plan with its tasks."""

    model = Plan
    template_name = "plans/plan_detail.html"
    context_object_name = "plan"

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user).prefetch_related(
            Prefetch(
                "buckets",
                queryset=Bucket.objects.prefetch_related(
                    Prefetch("tasks", queryset=Task.objects.select_related("bucket")),
                ),
            ),
        )


class PlanCreateView(LoginRequiredMixin, CreateView):
    model = Plan
    fields = ["title", "description", "team", "visibility"]
    template_name = "plans/plan_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("plans:plan-detail", kwargs={"pk": self.object.pk})


class PlanUpdateView(LoginRequiredMixin, UpdateView):
    model = Plan
    fields = ["title", "description", "visibility"]
    template_name = "plans/plan_form.html"

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user)

    def get_success_url(self):
        return reverse_lazy("plans:plan-detail", kwargs={"pk": self.object.pk})


class PlanDeleteView(LoginRequiredMixin, DeleteView):
    model = Plan
    template_name = "plans/plan_confirm_delete.html"
    success_url = reverse_lazy("plans:plan-list")

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user)
