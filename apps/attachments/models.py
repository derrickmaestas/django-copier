from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel


def attachment_upload_path(instance: Attachment, filename: str) -> str:
    """Group uploaded files under a per-task directory."""
    return f"attachments/task_{instance.task_id}/{filename}"


class Attachment(TimeStampedModel):
    """A file attached to a task. Stored on S3 in production, local disk in dev."""

    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_attachments",
    )
    file = models.FileField(upload_to=attachment_upload_path)
    filename = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task", "-created_at"], name="idx_attach_task_created"),
        ]

    def __str__(self):
        return self.filename

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 2)

    def clean(self):
        super().clean()
        max_bytes = settings.PLANLY_MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
        if self.size_bytes > max_bytes:
            raise ValidationError(
                {
                    "file": (
                        f"File is {self.size_mb} MB — "
                        f"exceeds the {settings.PLANLY_MAX_ATTACHMENT_SIZE_MB} MB limit."
                    )
                }
            )
