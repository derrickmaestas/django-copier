from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import OrderedModel, TimeStampedModel

from .querysets import TaskQuerySet


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

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["task", "created_at"], name="idx_comment_task_created"),
        ]

    def __str__(self):
        return f"Comment by {self.created_by} on {self.task}"
