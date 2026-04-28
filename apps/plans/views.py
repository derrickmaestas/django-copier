from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.tasks.models import Task

from .forms import BucketForm, PlanForm
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


class PlanUpdateView(LoginRequiredMixin, UpdateView):
    model = Plan
    form_class = PlanForm
    template_name = "plans/plan_form.html"

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}

    def get_success_url(self):
        return reverse_lazy("plans:plan-detail", kwargs={"pk": self.object.pk})


class PlanDeleteView(LoginRequiredMixin, DeleteView):
    model = Plan
    template_name = "plans/plan_confirm_delete.html"
    success_url = reverse_lazy("plans:plan-list")

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user)


class BucketScopedQuerysetMixin(LoginRequiredMixin):
    """Restrict buckets to those reachable through the user's team memberships."""

    def get_queryset(self):
        return Bucket.objects.for_user(self.request.user)


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
