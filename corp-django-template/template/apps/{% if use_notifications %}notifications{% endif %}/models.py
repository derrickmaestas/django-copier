from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .querysets import NotificationQuerySet


class Notification(TimeStampedModel):
    """An in-app notification.

    Uses a GenericForeignKey to link to any target object without a
    separate FK per type. The `verb` describes what happened.
    """

    class Verb(models.TextChoices):
        CREATED = "created", "Created"
        ASSIGNED = "assigned", "Assigned"
        COMMENTED = "commented", "Commented"
        COMPLETED = "completed", "Completed"
        MENTIONED = "mentioned", "Mentioned"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="actor_notifications",
    )
    verb = models.CharField(max_length=20, choices=Verb.choices)
    description = models.CharField(max_length=255, blank=True)

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    target_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    read_at = models.DateTimeField(null=True, blank=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recipient", "-created_at"],
                name="idx_notif_recipient_created",
            ),
            models.Index(
                fields=["recipient", "read_at"],
                name="idx_notif_unread",
                condition=models.Q(read_at__isnull=True),
            ),
        ]

    def __str__(self):
        return f"{self.actor} {self.verb} → {self.recipient}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_read(self) -> None:
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])
