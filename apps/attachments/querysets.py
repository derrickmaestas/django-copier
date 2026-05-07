from django.db import models


class AttachmentQuerySet(models.QuerySet):
    """Custom queryset for Attachment with team-scoped access."""

    def for_user(self, user):
        """Return attachments on tasks visible to this user via team membership."""
        return self.filter(
            task__bucket__plan__team__memberships__user=user
        ).distinct()
