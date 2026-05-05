import pgtrigger
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils import timezone

from apps.core.models import OrderedModel, TimeStampedModel

from .querysets import (
    ChecklistItemQuerySet,
    CommentQuerySet,
    LabelQuerySet,
    TaskQuerySet,
)

# Postgres expression that recomputes Task.search_vector from a row's
# own title (weight A) + description (weight B) plus the concatenation
# of all related comment bodies (weight C). Defined once and substituted
# into both triggers — keeps the two SQL bodies in sync by construction.
_TASK_SEARCH_VECTOR_SQL = """
    setweight(to_tsvector('english_unaccent', coalesce({title}, '')), 'A') ||
    setweight(to_tsvector('english_unaccent', coalesce({description}, '')), 'B') ||
    setweight(to_tsvector('english_unaccent',
        coalesce((
            SELECT string_agg(c.body, ' ')
            FROM tasks_comment c
            WHERE c.task_id = {task_id}
        ), '')
    ), 'C')
"""


class Task(TimeStampedModel):
    """A task within a bucket. The central model of the application."""

    class Priority(models.IntegerChoices):
        URGENT = 1, "Urgent"
        IMPORTANT = 3, "Important"
        MEDIUM = 5, "Medium"
        LOW = 9, "Low"

    class Progress(models.IntegerChoices):
        NOT_STARTED = 0, "Not started"
        IN_PROGRESS = 50, "In progress"
        COMPLETED = 100, "Completed"

    bucket = models.ForeignKey(
        "plans.Bucket",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.PositiveSmallIntegerField(
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    progress = models.PositiveSmallIntegerField(
        choices=Progress.choices,
        default=Progress.NOT_STARTED,
    )
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tasks",
    )
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Assignment",
        related_name="assigned_tasks",
        blank=True,
    )
    labels = models.ManyToManyField(
        "Label",
        related_name="tasks",
        blank=True,
    )

    # Tier 2 FTS: a denormalized tsvector maintained by Postgres
    # triggers, not a GeneratedField. Why not generated? Because the
    # vector folds in text from related Comment rows; a generated
    # column can only see the row it lives on. The triggers below
    # rebuild this column whenever a Task or any of its Comments
    # changes — both write paths write the column the same way.
    search_vector = SearchVectorField(null=True, blank=True)

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["bucket", "-created_at"], name="idx_task_bucket_created"),
            models.Index(fields=["due_date"], name="idx_task_due_date"),
            models.Index(
                fields=["progress"],
                name="idx_task_incomplete",
                condition=models.Q(progress__lt=100),
            ),
            GinIndex(fields=["search_vector"], name="idx_task_search_vector"),
        ]
        triggers = [
            # Recompute search_vector whenever a row's own title or
            # description changes (and on every insert).
            pgtrigger.Trigger(
                name="task_search_vector_self",
                level=pgtrigger.Row,
                when=pgtrigger.Before,
                operation=pgtrigger.Insert | pgtrigger.UpdateOf("title", "description"),
                func=(
                    "NEW.search_vector := "
                    + _TASK_SEARCH_VECTOR_SQL.format(
                        title="NEW.title",
                        description="NEW.description",
                        task_id="NEW.id",
                    )
                    + "; RETURN NEW;"
                ),
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self) -> bool:
        """True if the task is past its due date and not yet completed."""
        return (
            self.due_date is not None
            and self.due_date < timezone.now().date()
            and self.progress < self.Progress.COMPLETED
        )

    def mark_complete(self) -> None:
        """Set this task to completed with a timestamp."""
        self.progress = self.Progress.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["progress", "completed_at"])


class Assignment(TimeStampedModel):
    """Explicit M2M through model linking tasks to assigned users."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["task", "user"],
                name="unique_task_assignment",
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.task}"


class ChecklistItem(TimeStampedModel, OrderedModel):
    """A checklist item within a task."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="checklist_items")
    title = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)

    objects = ChecklistItemQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["task", "position"],
                name="unique_checklist_position",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]
        indexes = [
            models.Index(fields=["task", "position"], name="idx_checklist_task_pos"),
        ]

    def __str__(self):
        return self.title


class Label(TimeStampedModel):
    """A colored label scoped to a plan, shared across that plan's tasks."""

    plan = models.ForeignKey(
        "plans.Plan",
        on_delete=models.CASCADE,
        related_name="labels",
    )
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=7, default="#6B7280")  # hex color

    objects = LabelQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "name"],
                name="unique_label_per_plan",
            ),
        ]

    def __str__(self):
        return self.name


class Comment(TimeStampedModel):
    """A comment on a task."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="comments",
    )
    body = models.TextField()

    objects = CommentQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["task", "created_at"], name="idx_comment_task_created"),
        ]
        triggers = [
            # When a comment is added, edited, or deleted, rebuild the
            # parent task's search_vector from scratch. UPDATE-zero-rows
            # is the right behavior when the task itself was just
            # cascade-deleted — we don't error, we just no-op.
            pgtrigger.Trigger(
                name="comment_fanout_to_task_search_vector",
                level=pgtrigger.Row,
                when=pgtrigger.After,
                operation=(
                    pgtrigger.Insert
                    | pgtrigger.UpdateOf("body", "task_id")
                    | pgtrigger.Delete
                ),
                # The format() call substitutes only hardcoded SQL
                # identifiers (`t.title`, `t.description`, `t.id`) into a
                # constant template — there's no user input on this path.
                func=(
                    "UPDATE tasks_task t SET search_vector = "  # noqa: S608
                    + _TASK_SEARCH_VECTOR_SQL.format(
                        title="t.title",
                        description="t.description",
                        task_id="t.id",
                    )
                    + " WHERE t.id = COALESCE(NEW.task_id, OLD.task_id); RETURN NULL;"
                ),
            ),
        ]

    def __str__(self):
        return f"Comment by {self.created_by} on {self.task}"
