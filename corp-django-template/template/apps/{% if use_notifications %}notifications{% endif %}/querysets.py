from django.db import models
from django.utils import timezone


class NotificationQuerySet(models.QuerySet):
    """Custom queryset for Notification with common scoping helpers."""

    def for_user(self, user):
        return self.filter(recipient=user)

    def unread(self):
        return self.filter(read_at__isnull=True)

    def mark_all_read(self):
        return self.filter(read_at__isnull=True).update(read_at=timezone.now())
