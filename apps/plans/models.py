from django.conf import settings
from django.db import models

from apps.core.models import OrderedModel, TimeStampedModel

from .querysets import PlanQuerySet


class Plan(TimeStampedModel):
    """A plan (board) that organizes tasks into buckets for a team."""

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        PUBLIC = "public", "Public"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    team = models.ForeignKey(
        "accounts.Team",
        on_delete=models.CASCADE,
        related_name="plans",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_plans",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_plans",
    )
    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )

    objects = PlanQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team", "-created_at"], name="idx_plan_team_created"),
        ]

    def __str__(self):
        return self.title


class Bucket(TimeStampedModel, OrderedModel):
    """A column within a plan that groups tasks (e.g. 'To Do', 'In Progress')."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="buckets")
    title = models.CharField(max_length=255)

    class Meta(OrderedModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "position"],
                name="unique_bucket_position",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]
        indexes = [
            models.Index(fields=["plan", "position"], name="idx_bucket_plan_pos"),
        ]

    def __str__(self):
        return self.title
