from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models

from apps.core.models import OrderedModel, TimeStampedModel

from .querysets import BucketQuerySet, PlanQuerySet


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
    # Tier 1 FTS: a tsvector computed by Postgres from this row's own
    # fields (title weighted A, description weighted B). The DB
    # maintains it on every insert/update — no triggers, no signal
    # handlers, no application code path can forget to refresh it.
    search_vector = models.GeneratedField(
        expression=(
            SearchVector("title", config="english_unaccent", weight="A")
            + SearchVector("description", config="english_unaccent", weight="B")
        ),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    objects = PlanQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team", "-created_at"], name="idx_plan_team_created"),
            GinIndex(fields=["search_vector"], name="idx_plan_search_vector"),
        ]

    def __str__(self):
        return self.title


class Bucket(TimeStampedModel, OrderedModel):
    """A column within a plan that groups tasks (e.g. 'To Do', 'In Progress')."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="buckets")
    title = models.CharField(max_length=255)

    objects = BucketQuerySet.as_manager()

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
