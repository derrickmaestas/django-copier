from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel

from .querysets import AttachmentQuerySet


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
    size_bytes = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)

    objects = AttachmentQuerySet.as_manager()

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

    def save(self, *args, **kwargs):
        """Derive size_bytes from the uploaded file.

        Reading `file.size` may trigger a backend stat (network call on S3),
        so we do it once at save time and cache the result on the row.
        """
        if self.file:
            self.size_bytes = self.file.size
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        max_bytes = settings.PLANLY_MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
        size = self.file.size if self.file else self.size_bytes
        if size > max_bytes:
            mb = round(size / (1024 * 1024), 2)
            raise ValidationError(
                {
                    "file": (
                        f"File is {mb} MB — "
                        f"exceeds the {settings.PLANLY_MAX_ATTACHMENT_SIZE_MB} MB limit."
                    )
                }
            )
