from django.db import models
from django.utils import timezone


class NotificationQuerySet(models.QuerySet):
    """Custom queryset for Notification with common scoping helpers."""

    def for_user(self, user):
        return self.filter(recipient=user)

    def unread(self):
        return self.filter(read_at__isnull=True)

    def mark_all_read(self):
        """Bulk-mark all notifications in this queryset as read.

        Uses a single UPDATE — prefer this to iterating and saving each one.
        """
        return self.filter(read_at__isnull=True).update(read_at=timezone.now())
